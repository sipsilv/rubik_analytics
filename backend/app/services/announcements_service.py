"""
Corporate Announcements Service
Clean implementation for TrueData Corporate Announcements ingestion via WebSocket.

Pipeline: Fetch → Normalize → De-duplicate → Persist → Serve UI

UNIQUE KEY: SHA-256 hash of (ISIN + Exchange Symbol + Headline + DateTime)
"""
import asyncio
import hashlib
import json
import logging
import os
import websockets
from datetime import datetime, timezone
from queue import Queue
from threading import Thread, Event, Lock
from typing import Optional, Dict, Any, List

import duckdb

from app.core.config import settings
from app.core.database import get_db
from app.models.connection import Connection
from app.services.truedata_api_service import get_truedata_api_service

logger = logging.getLogger(__name__)


class AnnouncementsService:
    """
    Corporate Announcements ingestion service.
    
    Handles WebSocket connection to TrueData, message processing,
    and immediate database persistence with SHA-256 hash deduplication.
    """
    
    _instance: Optional['AnnouncementsService'] = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.workers: Dict[int, 'WebSocketWorker'] = {}
        self.db_path = self._get_db_path()
        self._init_database()
        self._initialized = True
        logger.info(f"AnnouncementsService initialized. DB: {self.db_path}")
    
    def _get_db_path(self) -> str:
        """Get path to announcements DuckDB database."""
        data_dir = os.path.abspath(settings.DATA_DIR)
        db_dir = os.path.join(data_dir, "Company Fundamentals")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "corporate_announcements.duckdb")
    
    def _init_database(self):
        """Initialize database with new schema."""
        try:
            conn = duckdb.connect(self.db_path)
            
            # Check if old table exists and has old schema
            try:
                result = conn.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'corporate_announcements'
                """).fetchall()
                existing_columns = {row[0] for row in result}
                
                # If old schema exists (has announcement_id as primary key), we need to migrate
                if 'announcement_id' in existing_columns and 'unique_hash' not in existing_columns:
                    logger.info("Detected old schema. Creating new table...")
                    # Drop the old table and create new one
                    conn.execute("DROP TABLE IF EXISTS corporate_announcements_old")
                    conn.execute("ALTER TABLE corporate_announcements RENAME TO corporate_announcements_old")
                    logger.info("Old table renamed to corporate_announcements_old")
            except Exception:
                # Table doesn't exist or other error - continue with creation
                pass
            
            # Create new table with proper schema
            # unique_hash is the PRIMARY KEY - enforces deduplication at DB level
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_announcements (
                    unique_hash VARCHAR PRIMARY KEY,
                    announcement_datetime TIMESTAMP,
                    company_info VARCHAR,
                    headline VARCHAR,
                    category VARCHAR,
                    attachments JSON,
                    source_link VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_payload TEXT
                )
            """)
            
            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ann_datetime 
                ON corporate_announcements(announcement_datetime DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ann_created_at 
                ON corporate_announcements(created_at DESC)
            """)
            
            conn.commit()
            conn.close()
            logger.info("Database schema initialized successfully.")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
            raise
    
    def start_worker(self, connection_id: int) -> bool:
        """Start WebSocket worker for a TrueData connection."""
        if connection_id in self.workers:
            logger.info(f"Worker for connection {connection_id} exists, restarting...")
            self.stop_worker(connection_id)
        
        try:
            worker = WebSocketWorker(connection_id, self.db_path)
            worker.start()
            self.workers[connection_id] = worker
            logger.info(f"Started worker for connection {connection_id}")
            print(f"[ANNOUNCEMENTS] ✅ Started worker for TrueData connection {connection_id}")
            return True
        except Exception as e:
            logger.error(f"Error starting worker for connection {connection_id}: {e}")
            return False
    
    def stop_worker(self, connection_id: int) -> bool:
        """Stop WebSocket worker for a connection."""
        if connection_id not in self.workers:
            return True
        
        try:
            worker = self.workers.pop(connection_id)
            worker.stop()
            logger.info(f"Stopped worker for connection {connection_id}")
            print(f"[ANNOUNCEMENTS] ⏹ Stopped worker for TrueData connection {connection_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping worker for connection {connection_id}: {e}")
            return False
    
    def stop_all(self):
        """Stop all workers."""
        for connection_id in list(self.workers.keys()):
            self.stop_worker(connection_id)
        logger.info("All workers stopped.")
    
    def is_worker_running(self, connection_id: int) -> bool:
        """Check if worker is running."""
        worker = self.workers.get(connection_id)
        return worker is not None and worker.running
    
    def get_status(self, connection_id: int) -> Dict:
        """Get worker status."""
        worker = self.workers.get(connection_id)
        if not worker:
            return {"running": False, "connection_id": connection_id}
        
        return {
            "running": worker.running,
            "connection_id": connection_id,
            "stats": worker.get_stats()
        }


class WebSocketWorker:
    """
    WebSocket worker for a single TrueData connection.
    
    Handles connection, message parsing, and immediate database persistence.
    """
    
    def __init__(self, connection_id: int, db_path: str):
        self.connection_id = connection_id
        self.db_path = db_path
        self.running = False
        self.stop_event = Event()
        self.worker_thread: Optional[Thread] = None
        self.websocket = None
        
        # Stats
        self.stats = {
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
            "errors": 0,
            "last_received_at": None
        }
        self.stats_lock = Lock()
        
        # Reconnection settings
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.current_reconnect_delay = self.reconnect_delay
    
    def start(self):
        """Start the worker thread."""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.worker_thread = Thread(target=self._run, daemon=True)
        self.worker_thread.start()
    
    def stop(self):
        """Stop the worker thread."""
        self.running = False
        self.stop_event.set()
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        with self.stats_lock:
            return self.stats.copy()
    
    def _run(self):
        """Run the WebSocket event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._worker_loop())
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
        finally:
            loop.close()
    
    async def _worker_loop(self):
        """Main worker loop with auto-reconnect."""
        while self.running and not self.stop_event.is_set():
            try:
                if not self._is_connection_enabled():
                    await asyncio.sleep(5)
                    continue
                
                await self._connect_and_process()
                
            except Exception as e:
                logger.error(f"Worker error for connection {self.connection_id}: {e}")
                if self.running:
                    await asyncio.sleep(self.current_reconnect_delay)
                    self.current_reconnect_delay = min(
                        self.current_reconnect_delay * 2,
                        self.max_reconnect_delay
                    )
    
    async def _connect_and_process(self):
        """Connect to WebSocket and process messages."""
        try:
            # Get WebSocket URL
            db_gen = get_db()
            db = next(db_gen)
            try:
                api_service = get_truedata_api_service(self.connection_id, db)
                ws_url = api_service.get_websocket_url()
            finally:
                db.close()
            
            logger.info(f"Connecting to WebSocket: {ws_url.split('?')[0]}...")
            
            async with asyncio.timeout(30.0):
                async with websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    self.current_reconnect_delay = self.reconnect_delay
                    
                    logger.info(f"Connected to Corporate Announcements WebSocket")
                    print(f"[ANNOUNCEMENTS] ✅ WebSocket connected for connection {self.connection_id}")
                    
                    async for message in websocket:
                        if self.stop_event.is_set():
                            break
                        
                        try:
                            self._process_message(message)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            with self.stats_lock:
                                self.stats["errors"] += 1
                            
        except websockets.exceptions.ConnectionClosed:
            if self.running:
                logger.warning(f"WebSocket disconnected, will reconnect...")
        except asyncio.TimeoutError:
            logger.error(f"WebSocket connection timeout")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    def _process_message(self, raw_message: str):
        """
        Process a single WebSocket message.
        
        Pipeline: Parse → Normalize → Generate Hash → Persist
        """
        # LOG RAW PAYLOAD FOR AUDIT/DEBUG
        logger.debug(f"Raw payload: {raw_message[:500]}...")
        
        with self.stats_lock:
            self.stats["received"] += 1
            self.stats["last_received_at"] = datetime.now(timezone.utc).isoformat()
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {raw_message[:200]}")
            return
        
        # Parse announcement based on format
        announcement = self._parse_announcement(data, raw_message)
        
        if not announcement:
            logger.debug("Message skipped - not a valid announcement")
            return
        
        # Persist to database
        self._persist_announcement(announcement)
    
    def _parse_announcement(self, data: Any, raw_message: str) -> Optional[Dict]:
        """
        Parse announcement from WebSocket message.
        
        TrueData sends announcements in array format:
        [announcement_id, datetime, num, "", "SYMBOL_BSE", "Company Name", "N", category, category, headline, ...]
        """
        if isinstance(data, list) and len(data) >= 10:
            return self._parse_array_format(data, raw_message)
        elif isinstance(data, dict):
            return self._parse_dict_format(data, raw_message)
        
        return None
    
    def _parse_array_format(self, data: List, raw_message: str) -> Optional[Dict]:
        """Parse array format announcement."""
        try:
            # Array positions based on TrueData format
            # [0] = announcement_id (ignored - we use hash)
            # [1] = datetime
            # [4] = symbol (e.g., "RELIANCE_NSE", "SBIN_BSE")
            # [5] = company name
            # [7] = category
            # [9] = headline
            # [10+] = may contain attachment info
            
            source_datetime = data[1] if len(data) > 1 else None
            symbol_raw = data[4] if len(data) > 4 else None
            company_name = data[5] if len(data) > 5 else None
            category = data[7] if len(data) > 7 else None
            headline = data[9] if len(data) > 9 else None
            
            # Skip if no headline
            if not headline or (isinstance(headline, str) and headline.strip() in ["-", "", "null", "None"]):
                return None
            
            # Parse symbol and exchange
            nse_symbol = None
            bse_symbol = None
            isin = None
            
            if symbol_raw and isinstance(symbol_raw, str):
                symbol_upper = symbol_raw.upper().strip()
                
                if "_BSE" in symbol_upper or symbol_upper.endswith("_B"):
                    bse_symbol = symbol_upper.replace("_BSE", "").replace("_B", "").strip()
                elif "_NSE" in symbol_upper or symbol_upper.endswith("_N"):
                    nse_symbol = symbol_upper.replace("_NSE", "").replace("_N", "").strip()
                else:
                    nse_symbol = symbol_upper  # Default to NSE
            
            # Normalize datetime to UTC
            announcement_datetime = self._normalize_datetime(source_datetime)
            
            # Build company_info string
            company_info = self._build_company_info(
                company_name=company_name,
                nse_symbol=nse_symbol,
                bse_symbol=bse_symbol,
                isin=isin
            )
            
            # Parse attachments (if available in array)
            attachments = self._parse_attachments_from_array(data)
            
            # Source link (if available)
            source_link = None
            if len(data) > 11 and data[11] and isinstance(data[11], str) and data[11].startswith("http"):
                source_link = data[11]
            
            # Generate unique hash
            unique_hash = self._generate_hash(
                isin=isin,
                exchange_symbol=nse_symbol or bse_symbol,
                headline=str(headline).strip() if headline else "",
                datetime_str=announcement_datetime.isoformat() if announcement_datetime else ""
            )
            
            return {
                "unique_hash": unique_hash,
                "announcement_datetime": announcement_datetime,
                "company_info": company_info,
                "headline": str(headline).strip() if headline else None,
                "category": str(category).strip() if category else None,
                "attachments": attachments,
                "source_link": source_link,
                "raw_payload": raw_message
            }
            
        except Exception as e:
            logger.error(f"Error parsing array format: {e}")
            return None
    
    def _parse_dict_format(self, data: Dict, raw_message: str) -> Optional[Dict]:
        """Parse dictionary format announcement."""
        try:
            # Extract fields with multiple possible names
            headline = (
                data.get("headline") or data.get("Headline") or 
                data.get("subject") or data.get("title")
            )
            
            if not headline or (isinstance(headline, str) and headline.strip() in ["-", "", "null", "None"]):
                return None
            
            source_datetime = (
                data.get("announcement_datetime") or data.get("datetime") or
                data.get("date") or data.get("timestamp")
            )
            
            company_name = data.get("company_name") or data.get("company")
            nse_symbol = data.get("symbol_nse") or data.get("NSE")
            bse_symbol = data.get("symbol_bse") or data.get("BSE")
            isin = data.get("isin") or data.get("ISIN")
            category = data.get("category") or data.get("descriptor")
            
            # Single symbol field
            if not nse_symbol and not bse_symbol:
                symbol = data.get("symbol")
                exchange = data.get("exchange", "NSE").upper()
                if symbol:
                    if exchange in ["NSE", "N"]:
                        nse_symbol = symbol
                    elif exchange in ["BSE", "B"]:
                        bse_symbol = symbol
                    else:
                        nse_symbol = symbol
            
            announcement_datetime = self._normalize_datetime(source_datetime)
            
            company_info = self._build_company_info(
                company_name=company_name,
                nse_symbol=nse_symbol,
                bse_symbol=bse_symbol,
                isin=isin
            )
            
            # Parse attachments
            attachments = self._parse_attachments_from_dict(data)
            
            # Source link
            source_link = (
                data.get("link") or data.get("url") or
                data.get("source_url") or data.get("announcement_link")
            )
            
            unique_hash = self._generate_hash(
                isin=isin,
                exchange_symbol=nse_symbol or bse_symbol,
                headline=str(headline).strip() if headline else "",
                datetime_str=announcement_datetime.isoformat() if announcement_datetime else ""
            )
            
            return {
                "unique_hash": unique_hash,
                "announcement_datetime": announcement_datetime,
                "company_info": company_info,
                "headline": str(headline).strip() if headline else None,
                "category": str(category).strip() if category else None,
                "attachments": attachments,
                "source_link": source_link,
                "raw_payload": raw_message
            }
            
        except Exception as e:
            logger.error(f"Error parsing dict format: {e}")
            return None
    
    def _normalize_datetime(self, dt_value: Any) -> Optional[datetime]:
        """Normalize datetime to UTC."""
        if not dt_value:
            return None
        
        try:
            if isinstance(dt_value, datetime):
                dt = dt_value
            elif isinstance(dt_value, str):
                # Try various formats
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d",
                    "%d-%m-%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S"
                ]:
                    try:
                        dt = datetime.strptime(dt_value.replace('Z', ''), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Try ISO format as fallback
                    try:
                        dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
                    except:
                        return None
            else:
                return None
            
            # Ensure UTC timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
            
        except Exception:
            return None
    
    def _build_company_info(
        self,
        company_name: Optional[str],
        nse_symbol: Optional[str],
        bse_symbol: Optional[str],
        isin: Optional[str]
    ) -> str:
        """
        Build company_info string.
        Format: "Company Name | NSE: SYMBOL | BSE: SYMBOL | ISIN: CODE"
        """
        parts = []
        
        if company_name and str(company_name).strip():
            parts.append(str(company_name).strip())
        
        if nse_symbol and str(nse_symbol).strip():
            parts.append(f"NSE: {str(nse_symbol).strip()}")
        
        if bse_symbol and str(bse_symbol).strip():
            parts.append(f"BSE: {str(bse_symbol).strip()}")
        
        if isin and str(isin).strip():
            parts.append(f"ISIN: {str(isin).strip()}")
        
        return " | ".join(parts) if parts else ""
    
    def _parse_attachments_from_array(self, data: List) -> List[Dict]:
        """Parse attachments from array format."""
        attachments = []
        
        # TrueData may include attachment info at specific positions
        # Check positions 10, 11 for attachment IDs/URLs
        try:
            for i in range(10, min(len(data), 15)):
                item = data[i]
                if isinstance(item, str) and (item.startswith("http") or item.endswith(".pdf")):
                    attachments.append({
                        "file_name": item.split("/")[-1] if "/" in item else item,
                        "file_url": item,
                        "mime_type": "application/pdf" if item.endswith(".pdf") else None
                    })
                elif isinstance(item, dict) and "url" in item:
                    attachments.append({
                        "file_name": item.get("filename") or item.get("name") or "attachment",
                        "file_url": item.get("url"),
                        "mime_type": item.get("mime_type") or item.get("content_type")
                    })
        except Exception:
            pass
        
        return attachments
    
    def _parse_attachments_from_dict(self, data: Dict) -> List[Dict]:
        """Parse attachments from dictionary format."""
        attachments = []
        
        # Check various attachment field names
        attachment_data = (
            data.get("attachments") or data.get("attachment") or
            data.get("files") or data.get("documents")
        )
        
        if not attachment_data:
            # Check for single attachment fields
            attachment_id = data.get("attachment_id") or data.get("file_id")
            attachment_url = data.get("attachment_url") or data.get("file_url")
            
            if attachment_id or attachment_url:
                attachments.append({
                    "file_name": str(attachment_id) if attachment_id else "attachment",
                    "file_url": attachment_url,
                    "mime_type": None
                })
            return attachments
        
        # Handle list of attachments
        if isinstance(attachment_data, list):
            for item in attachment_data:
                if isinstance(item, dict):
                    attachments.append({
                        "file_name": item.get("file_name") or item.get("filename") or item.get("name") or "attachment",
                        "file_url": item.get("file_url") or item.get("url") or item.get("link"),
                        "mime_type": item.get("mime_type") or item.get("content_type")
                    })
                elif isinstance(item, str):
                    attachments.append({
                        "file_name": item.split("/")[-1] if "/" in item else item,
                        "file_url": item if item.startswith("http") else None,
                        "mime_type": None
                    })
        elif isinstance(attachment_data, dict):
            attachments.append({
                "file_name": attachment_data.get("file_name") or attachment_data.get("filename") or "attachment",
                "file_url": attachment_data.get("file_url") or attachment_data.get("url"),
                "mime_type": attachment_data.get("mime_type")
            })
        
        return attachments
    
    def _generate_hash(
        self,
        isin: Optional[str],
        exchange_symbol: Optional[str],
        headline: str,
        datetime_str: str
    ) -> str:
        """
        Generate SHA-256 hash from unique key components.
        
        UNIQUE KEY: ISIN + Exchange Symbol + Headline + DateTime
        """
        # Normalize components
        isin_norm = (str(isin).strip().upper() if isin else "").encode('utf-8')
        symbol_norm = (str(exchange_symbol).strip().upper() if exchange_symbol else "").encode('utf-8')
        headline_norm = (str(headline).strip() if headline else "").encode('utf-8')
        datetime_norm = (str(datetime_str).strip() if datetime_str else "").encode('utf-8')
        
        # Combine with separator
        combined = b"|".join([isin_norm, symbol_norm, headline_norm, datetime_norm])
        
        # Generate SHA-256 hash
        return hashlib.sha256(combined).hexdigest()
    
    def _persist_announcement(self, announcement: Dict):
        """
        Persist announcement to database immediately.
        
        Uses unique_hash as PRIMARY KEY for DB-level deduplication.
        """
        conn = None
        try:
            conn = duckdb.connect(self.db_path)
            
            # Try to insert - will fail if duplicate (PRIMARY KEY violation)
            try:
                conn.execute("""
                    INSERT INTO corporate_announcements (
                        unique_hash,
                        announcement_datetime,
                        company_info,
                        headline,
                        category,
                        attachments,
                        source_link,
                        created_at,
                        raw_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    announcement["unique_hash"],
                    announcement["announcement_datetime"],
                    announcement["company_info"],
                    announcement["headline"],
                    announcement["category"],
                    json.dumps(announcement["attachments"]) if announcement["attachments"] else "[]",
                    announcement["source_link"],
                    datetime.now(timezone.utc),
                    announcement["raw_payload"]
                ])
                
                conn.commit()
                
                with self.stats_lock:
                    self.stats["inserted"] += 1
                
                logger.info(f"Inserted announcement: {announcement['headline'][:50]}...")
                
            except Exception as insert_error:
                error_msg = str(insert_error).lower()
                if "duplicate" in error_msg or "unique" in error_msg or "primary key" in error_msg:
                    with self.stats_lock:
                        self.stats["duplicates"] += 1
                    logger.debug(f"Duplicate announcement skipped: {announcement['unique_hash'][:16]}...")
                else:
                    with self.stats_lock:
                        self.stats["errors"] += 1
                    logger.error(f"Insert error: {insert_error}")
            
        except Exception as e:
            with self.stats_lock:
                self.stats["errors"] += 1
            logger.error(f"Database error: {e}")
        finally:
            if conn:
                conn.close()
    
    def _is_connection_enabled(self) -> bool:
        """Check if connection is enabled."""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                conn = db.query(Connection).filter(
                    Connection.id == self.connection_id,
                    Connection.provider == "TrueData"
                ).first()
                return conn and conn.is_enabled
            finally:
                db.close()
        except Exception:
            return False


def get_announcements_service() -> AnnouncementsService:
    """Get the global announcements service instance."""
    return AnnouncementsService()


# Backward compatibility alias
def get_announcements_manager() -> AnnouncementsService:
    """Alias for backward compatibility."""
    return get_announcements_service()

