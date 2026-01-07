"""
WebSocket Worker for TrueData Corporate Announcements
Handles persistent WebSocket connection, message parsing, and queueing
"""
import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from queue import Queue, Empty
from threading import Thread, Event
from app.services.truedata_api_service import get_truedata_api_service
from app.core.database import get_db
from app.models.connection import Connection

logger = logging.getLogger(__name__)


class AnnouncementsWebSocketWorker:
    """
    WebSocket worker for Corporate Announcements ingestion
    
    Responsibilities:
    - Maintain persistent WebSocket connection
    - Parse incoming announcement messages
    - Push parsed data to FIFO queue
    - Auto-reconnect on disconnect
    - MUST NOT write to DB (that's the writer's job)
    """
    
    def __init__(self, connection_id: int, message_queue: Queue):
        """
        Initialize WebSocket worker
        
        Args:
            connection_id: TrueData connection ID
            message_queue: FIFO queue for parsed messages
        """
        self.connection_id = connection_id
        self.message_queue = message_queue
        self.websocket = None
        self.running = False
        self.stop_event = Event()
        self.worker_thread: Optional[Thread] = None
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60  # max seconds between reconnects
        self.current_reconnect_delay = self.reconnect_delay
        
    def start(self):
        """Start the WebSocket worker in background thread"""
        if self.running:
            logger.warning(f"WebSocket worker for connection {self.connection_id} already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.worker_thread = Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()
        logger.info(f"Started WebSocket worker for connection {self.connection_id}")
    
    def stop(self):
        """Stop the WebSocket worker"""
        if not self.running:
            return
        
        logger.info(f"Stopping WebSocket worker for connection {self.connection_id}")
        self.running = False
        self.stop_event.set()
        
        # Close WebSocket connection
        if self.websocket:
            try:
                asyncio.run(self._close_websocket())
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        # Wait for thread to finish (with timeout)
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        logger.info(f"WebSocket worker for connection {self.connection_id} stopped")
    
    def _run_worker(self):
        """Run WebSocket worker in event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._worker_loop())
        except Exception as e:
            logger.error(f"WebSocket worker loop error: {e}", exc_info=True)
        finally:
            loop.close()
    
    async def _worker_loop(self):
        """Main worker loop with auto-reconnect"""
        while self.running and not self.stop_event.is_set():
            try:
                # Check if connection is enabled
                if not self._is_connection_enabled():
                    logger.info(f"Connection {self.connection_id} is disabled, waiting...")
                    await asyncio.sleep(5)
                    continue
                
                # Connect and process messages
                await self._connect_and_process()
                
            except Exception as e:
                logger.error(f"WebSocket worker error: {e}", exc_info=True)
                if self.running and not self.stop_event.is_set():
                    # Wait before reconnecting
                    await asyncio.sleep(self.current_reconnect_delay)
                    # Exponential backoff (capped at max)
                    self.current_reconnect_delay = min(
                        self.current_reconnect_delay * 2,
                        self.max_reconnect_delay
                    )
    
    async def _connect_and_process(self):
        """Connect to WebSocket and process messages"""
        try:
            # Get WebSocket URL from TrueData API service
            db_gen = get_db()
            db = next(db_gen)
            try:
                api_service = get_truedata_api_service(self.connection_id, db)
                ws_url = api_service.get_websocket_url()
            except ValueError as e:
                # Credentials decryption failed or missing
                error_msg = str(e)
                if "decrypt" in error_msg.lower() or "encryption" in error_msg.lower() or "credentials" in error_msg.lower():
                    logger.error(
                        f"Cannot decrypt credentials for connection {self.connection_id}. "
                        f"This usually means the ENCRYPTION_KEY has changed. "
                        f"Please reconfigure the connection with valid credentials."
                    )
                    # Wait longer before retrying (5 minutes) to avoid spam
                    await asyncio.sleep(300)
                    return
                raise
            except Exception as e:
                logger.error(f"Error getting WebSocket URL for connection {self.connection_id}: {e}")
                # Wait before retrying
                await asyncio.sleep(30)
                return
            finally:
                db.close()
            
            logger.info(f"Connecting to Corporate Announcements WebSocket: {ws_url.split('?')[0]}...")
            
            # Connect with longer timeout for initial handshake
            # Corporate Announcements WebSocket may take longer to establish
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(
                        ws_url,
                        ping_interval=30,
                        ping_timeout=10,
                        close_timeout=10
                    ),
                    timeout=30.0  # 30 second timeout for handshake
                )
            except asyncio.TimeoutError:
                logger.error(f"WebSocket connection timeout for connection {self.connection_id} after 30 seconds")
                raise Exception(f"WebSocket connection timeout - check network and TrueData service status")
            except Exception as e:
                logger.error(f"WebSocket connection failed for connection {self.connection_id}: {e}")
                raise
            
            try:
                async with websocket:
                    self.websocket = websocket
                    self.current_reconnect_delay = self.reconnect_delay  # Reset on successful connect
                    logger.info(f"Connected to Corporate Announcements WebSocket for connection {self.connection_id}")
                    print(f"[ANNOUNCEMENTS] ✅ Connected to Corporate Announcements WebSocket for connection {self.connection_id}")
                    
                    # Process messages
                    async for message in websocket:
                        if self.stop_event.is_set():
                            break
                        
                        try:
                            # Parse and queue message
                            parsed = self._parse_message(message)
                            if parsed:
                                self.message_queue.put(parsed)
                                announcement_id = parsed.get('announcement_id', 'unknown')
                                headline = parsed.get('headline', '')[:50] if parsed.get('headline') else 'N/A'
                                logger.info(f"Received announcement: {announcement_id} - {headline}")
                                logger.debug(f"Queued announcement: {announcement_id}")
                            else:
                                # This is expected - messages without headline/description are skipped
                                # Only log at debug level to reduce noise
                                logger.debug(f"Skipped invalid announcement message (no headline/description or invalid data)")
                        except Exception as e:
                            logger.error(f"Error parsing announcement message: {e}")
                            logger.debug(f"Raw message: {message[:500] if isinstance(message, str) else str(message)[:500]}")
            finally:
                # Ensure websocket is closed
                try:
                    if 'websocket' in locals():
                        await websocket.close()
                except:
                    pass
                
        except websockets.exceptions.ConnectionClosed:
            if self.running and not self.stop_event.is_set():
                logger.warning(f"WebSocket connection closed for connection {self.connection_id}, will reconnect")
        except asyncio.TimeoutError:
            if self.running and not self.stop_event.is_set():
                logger.error(f"WebSocket connection timeout for connection {self.connection_id}")
                # Wait before retrying
                await asyncio.sleep(10)
        except ValueError as e:
            # Credentials decryption error - handled above, just return
            if self.running and not self.stop_event.is_set():
                logger.error(f"WebSocket worker error (credentials): {e}")
            return
        except Exception as e:
            if self.running and not self.stop_event.is_set():
                error_msg = str(e)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    logger.error(f"WebSocket connection timeout for connection {self.connection_id}: {e}")
                else:
                    logger.error(f"WebSocket connection error for connection {self.connection_id}: {e}")
                # Wait before retrying
                await asyncio.sleep(10)
                return
    
    async def _close_websocket(self):
        """Close WebSocket connection"""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
    
    def _parse_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Parse WebSocket message into structured announcement data
        
        TrueData WebSocket messages can have various formats:
        1. Array format: ["id", "datetime", num, "", "SYMBOL_BSE", "Company Name", "N", "category", "category", "headline", ...]
        2. Dictionary format: {"announcement_id": "...", "headline": "...", ...}
        
        This parser handles both formats.
        """
        try:
            data = json.loads(message)
            
            # Log the actual message structure for debugging (first few messages only)
            if not hasattr(self, '_logged_message_count'):
                self._logged_message_count = 0
            if self._logged_message_count < 5:
                logger.info(f"Sample WebSocket message structure (full): {json.dumps(data, indent=2)}")
                logger.info(f"Message type: {type(data).__name__}, Length: {len(data) if isinstance(data, (list, dict)) else 'N/A'}")
                # Also print to console for visibility
                print(f"\n[WEBSOCKET MESSAGE] Sample message structure:")
                print(f"Type: {type(data).__name__}")
                if isinstance(data, list):
                    print(f"Array length: {len(data)}")
                    print("Array content (first 10 items):")
                    for i, item in enumerate(data[:10]):
                        print(f"  [{i}]: {item} ({type(item).__name__})")
                elif isinstance(data, dict):
                    print(f"Dict keys: {list(data.keys())}")
                    print(json.dumps(data, indent=2)[:1000])  # First 1000 chars
                print()
                self._logged_message_count += 1
            
            # HANDLE ARRAY FORMAT (TrueData sends announcements as arrays)
            # Format: [announcement_id, datetime, num, "", "SYMBOL_BSE", "Company Name", "N", category, category, headline, ...]
            if isinstance(data, list) and len(data) >= 10:
                try:
                    # Extract fields from array (based on observed TrueData format)
                    # [0] = announcement_id
                    # [1] = datetime
                    # [4] = symbol (e.g., "SSLEL_BSE", "RELIANCE_NSE")
                    # [5] = company name
                    # [7] = category
                    # [9] = headline/description
                    
                    announcement_id = str(data[0]) if data[0] else None
                    announcement_datetime = data[1] if len(data) > 1 else None
                    symbol_raw = data[4] if len(data) > 4 else None
                    company_name = data[5] if len(data) > 5 else None
                    category = data[7] if len(data) > 7 else None
                    headline = data[9] if len(data) > 9 else None
                    
                    # Parse symbol to determine exchange
                    symbol_nse = None
                    symbol_bse = None
                    exchange = None
                    
                    if symbol_raw and isinstance(symbol_raw, str):
                        symbol_upper = symbol_raw.upper()
                        if "_BSE" in symbol_upper or symbol_upper.endswith("_B"):
                            # BSE symbol
                            symbol_bse = symbol_upper.replace("_BSE", "").replace("_B", "").strip()
                            exchange = "BSE"
                        elif "_NSE" in symbol_upper or symbol_upper.endswith("_N"):
                            # NSE symbol
                            symbol_nse = symbol_upper.replace("_NSE", "").replace("_N", "").strip()
                            exchange = "NSE"
                        else:
                            # Default to NSE if no suffix
                            symbol_nse = symbol_upper.strip()
                            exchange = "NSE"
                    
                    # Validate we have minimum required data
                    if not announcement_id:
                        logger.warning("Array format message missing announcement_id")
                        return None
                    
                    if not headline or (isinstance(headline, str) and headline.strip() in ["-", "", "null", "None"]):
                        logger.warning(f"Array format announcement {announcement_id}: no valid headline")
                        return None
                    
                    parsed = {
                        "announcement_id": str(announcement_id),
                        "symbol": symbol_nse or symbol_bse or symbol_raw,  # Best available symbol
                        "symbol_nse": symbol_nse,
                        "symbol_bse": symbol_bse,
                        "exchange": exchange,
                        "headline": headline if isinstance(headline, str) else str(headline) if headline else None,
                        "description": None,  # Array format doesn't have separate description
                        "category": category if isinstance(category, str) else str(category) if category else None,
                        "announcement_datetime": announcement_datetime,
                        "attachment_id": None,  # Not available in array format
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "raw_payload": message,  # Store raw for debugging
                        "_company_name_hint": company_name  # Store for potential matching
                    }
                    
                    logger.info(f"Parsed array format announcement: {announcement_id}, Symbol: {symbol_nse or symbol_bse}, Company: {company_name}")
                    return parsed
                    
                except Exception as e:
                    logger.error(f"Error parsing array format message: {e}")
                    logger.debug(f"Array data: {data[:10] if len(data) > 10 else data}")
                    # Fall through to dictionary parsing
            
            # HANDLE DICTIONARY FORMAT (fallback for other message formats)
            if isinstance(data, dict):
                # Try multiple possible ID fields
                announcement_id = (
                    data.get("announcement_id") or 
                    data.get("id") or 
                    data.get("announcementId") or
                    data.get("AnnouncementID") or
                    data.get("announcementID") or
                    data.get("_id") or
                    str(data.get("timestamp", "")) + "_" + str(data.get("symbol", "")) if data.get("timestamp") or data.get("symbol") else None
                )
                
                # If still no ID, try to generate one from available fields
                if not announcement_id:
                    # Try to create a unique ID from timestamp + symbol
                    timestamp = data.get("timestamp") or data.get("date") or data.get("announcement_datetime") or data.get("tradedate")
                    symbol = data.get("symbol") or data.get("symbol_nse") or data.get("symbol_bse")
                    if timestamp and symbol:
                        announcement_id = f"{symbol}_{timestamp}"
                    elif timestamp:
                        announcement_id = f"ann_{timestamp}"
                    elif symbol:
                        announcement_id = f"{symbol}_{datetime.now(timezone.utc).timestamp()}"
                    else:
                        # Last resort: use hash of message
                        import hashlib
                        announcement_id = hashlib.md5(message.encode()).hexdigest()[:16]
                
                if not announcement_id:
                    logger.warning("Dictionary message missing announcement_id and cannot generate one, skipping")
                    logger.debug(f"Message keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    return None
                
                # Extract symbol(s) - try multiple possible field names and variations
                symbol = (
                    data.get("symbol") or 
                    data.get("Symbol") or
                    data.get("SYMBOL") or
                    data.get("company_symbol") or
                    data.get("trading_symbol") or
                    data.get("TradingSymbol") or
                    data.get("companySymbol") or
                    data.get("CompanySymbol") or
                    data.get("scrip") or
                    data.get("Scrip") or
                    data.get("scripcode") or
                    data.get("ScripCode")
                )
                symbol_nse = (
                    data.get("symbol_nse") or 
                    data.get("SymbolNSE") or 
                    data.get("symbolNSE") or
                    data.get("NSE") or
                    data.get("nse_symbol") or
                    data.get("NSE_SYMBOL")
                )
                symbol_bse = (
                    data.get("symbol_bse") or 
                    data.get("SymbolBSE") or 
                    data.get("symbolBSE") or
                    data.get("BSE") or
                    data.get("bse_symbol") or
                    data.get("BSE_SYMBOL")
                )
                
                # Try to extract from exchange-specific fields
                if not symbol_nse and not symbol_bse:
                    # Check if there's a nested structure
                    if isinstance(data.get("nse"), dict):
                        symbol_nse = data["nse"].get("symbol") or data["nse"].get("trading_symbol")
                    if isinstance(data.get("bse"), dict):
                        symbol_bse = data["bse"].get("symbol") or data["bse"].get("trading_symbol")
                
                # If single symbol provided, try to determine exchange
                if symbol and not symbol_nse and not symbol_bse:
                    # Try to infer exchange from symbol format or use data.get("exchange")
                    exchange = (
                        data.get("exchange") or 
                        data.get("Exchange") or 
                        data.get("EXCHANGE") or
                        data.get("exch") or
                        data.get("Exch") or
                        "NSE"  # Default to NSE
                    )
                    if exchange.upper() in ["NSE", "N", "NSECM", "NSE_EQ"]:
                        symbol_nse = symbol
                    elif exchange.upper() in ["BSE", "B", "BSEEQ", "BSE_EQ"]:
                        symbol_bse = symbol
                    else:
                        # Default to NSE if unknown
                        symbol_nse = symbol
                
                # Build parsed announcement - try multiple field name variations
                headline = (
                    data.get("headline") or 
                    data.get("Headline") or
                    data.get("HEADLINE") or
                    data.get("subject") or 
                    data.get("Subject") or
                    data.get("title") or
                    data.get("Title") or
                    data.get("news_sub") or
                    data.get("NewsSub")
                )
                
                description = (
                    data.get("description") or 
                    data.get("Description") or
                    data.get("DESCRIPTION") or
                    data.get("news_body") or 
                    data.get("NewsBody") or
                    data.get("body") or
                    data.get("Body") or
                    data.get("content") or
                    data.get("Content")
                )
                
                # VALIDATION: Skip blank/invalid announcements
                # Must have at least headline OR description to be valid
                if not headline and not description:
                    # This is expected - some WebSocket messages may not have headline/description
                    # Only log at debug level to reduce noise in production
                    logger.debug(f"Skipping announcement {announcement_id}: no headline or description")
                    return None
                
                # Skip if headline is just "-" or empty string
                if headline and headline.strip() in ["-", "", "null", "None"]:
                    # This is expected - invalid headlines are filtered out
                    logger.debug(f"Skipping announcement {announcement_id}: invalid headline '{headline}'")
                    return None
                
                parsed = {
                    "announcement_id": str(announcement_id),
                    "symbol": symbol,  # Keep for reference
                    "symbol_nse": symbol_nse,
                    "symbol_bse": symbol_bse,
                    "exchange": data.get("exchange") or data.get("Exchange") or data.get("EXCHANGE"),
                    "headline": headline,
                    "description": description,
                    "category": (
                        data.get("category") or 
                        data.get("Category") or
                        data.get("CATEGORY") or
                        data.get("descriptor") or 
                        data.get("Descriptor") or
                        data.get("type") or
                        data.get("Type") or
                        data.get("TYPE")
                    ),
                    "announcement_datetime": (
                        data.get("announcement_datetime") or 
                        data.get("AnnouncementDateTime") or
                        data.get("tradedate") or 
                        data.get("TradeDate") or
                        data.get("date") or
                        data.get("Date") or
                        data.get("DATE") or
                        data.get("timestamp") or
                        data.get("Timestamp")
                    ),
                    "attachment_id": (
                        data.get("attachment_id") or 
                        data.get("AttachmentID") or
                        data.get("attachment") or
                        data.get("Attachment") or
                        data.get("file_id") or
                        data.get("FileID")
                    ),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "raw_payload": message  # Store raw for debugging
                }
                
                return parsed
            
            # If neither array nor dict format matches
            logger.warning(f"Unknown message format: {type(data).__name__}")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
            logger.debug(f"Raw message (first 500 chars): {message[:500] if isinstance(message, str) else str(message)[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing message: {e}", exc_info=True)
            logger.debug(f"Raw message (first 500 chars): {message[:500] if isinstance(message, str) else str(message)[:500]}")
            return None
    
    def _is_connection_enabled(self) -> bool:
        """Check if TrueData connection is enabled"""
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
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            return False

