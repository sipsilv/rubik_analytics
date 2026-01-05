"""
Database Writer Service for Corporate Announcements
Single-threaded writer that reads from queue and writes to DuckDB
"""
import logging
import duckdb
import os
from typing import Dict, Any, Optional
from queue import Queue, Empty
from threading import Thread, Event
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)


class AnnouncementsDBWriter:
    """
    Database writer for Corporate Announcements
    
    Responsibilities:
    - Read from FIFO queue
    - Write to DuckDB in transactions
    - Enforce uniqueness on announcement_id
    - Ignore duplicates silently
    - Single writer thread (no concurrent writes)
    """
    
    def __init__(self, message_queue: Queue):
        """
        Initialize database writer
        
        Args:
            message_queue: FIFO queue with parsed announcement messages
        """
        self.message_queue = message_queue
        self.running = False
        self.stop_event = Event()
        self.writer_thread: Optional[Thread] = None
        self.db_path = self._get_db_path()
        self._init_database()
    
    def _get_db_path(self) -> str:
        """Get path to announcements DuckDB database"""
        data_dir = os.path.abspath(settings.DATA_DIR)
        db_dir = os.path.join(data_dir, "Company Fundamentals")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
        return db_path
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            conn = duckdb.connect(self.db_path)
            
            # Create table with required schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_announcements (
                    announcement_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    exchange VARCHAR,
                    headline VARCHAR,
                    description TEXT,
                    category VARCHAR,
                    announcement_datetime TIMESTAMP,
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    attachment_id VARCHAR,
                    symbol_nse VARCHAR,
                    symbol_bse VARCHAR,
                    raw_payload TEXT,
                    UNIQUE(announcement_id)
                )
            """)
            
            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_datetime 
                ON corporate_announcements(announcement_datetime DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_received_at 
                ON corporate_announcements(received_at DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_symbol 
                ON corporate_announcements(symbol)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Initialized announcements database at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing announcements database: {e}", exc_info=True)
            raise
    
    def start(self):
        """Start the database writer in background thread"""
        if self.running:
            logger.warning("Database writer already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.writer_thread = Thread(target=self._run_writer, daemon=True)
        self.writer_thread.start()
        logger.info("Started announcements database writer")
    
    def stop(self):
        """Stop the database writer"""
        if not self.running:
            return
        
        logger.info("Stopping announcements database writer")
        self.running = False
        self.stop_event.set()
        
        if self.writer_thread:
            self.writer_thread.join(timeout=5)
        
        logger.info("Announcements database writer stopped")
    
    def _run_writer(self):
        """Main writer loop"""
        batch = []
        batch_size = 10
        batch_timeout = 1.0  # seconds
        
        while self.running and not self.stop_event.is_set():
            try:
                # Try to get message from queue (with timeout)
                try:
                    message = self.message_queue.get(timeout=batch_timeout)
                    batch.append(message)
                except Empty:
                    # Timeout - process batch if any messages
                    if batch:
                        self._write_batch(batch)
                        batch = []
                    continue
                
                # If batch is full, write immediately
                if len(batch) >= batch_size:
                    self._write_batch(batch)
                    batch = []
                
            except Exception as e:
                logger.error(f"Error in writer loop: {e}", exc_info=True)
                # Clear batch on error to avoid retrying bad data
                batch = []
        
        # Write remaining batch on shutdown
        if batch:
            self._write_batch(batch)
    
    def _match_symbol_from_db(self, conn, headline: str, description: str, search_text: str = None) -> tuple:
        """
        Try to match announcement with symbols from symbols database
        
        Matching strategy:
        1. Search for company names in headline/description/search_text
        2. Match against symbols.name field (company name)
        3. Return trading_symbol and exchange
        
        Args:
            conn: DuckDB connection
            headline: Announcement headline
            description: Announcement description
            search_text: Additional search text (e.g., from raw_payload)
        
        Returns: (symbol_nse, symbol_bse, company_name) or (None, None, None)
        """
        try:
            from app.api.v1.symbols import get_symbols_db_path
            import os
            
            symbols_db_path = get_symbols_db_path()
            if not os.path.exists(symbols_db_path):
                return (None, None, None)
            
            # Attach symbols database
            try:
                normalized_path = symbols_db_path.replace('\\', '/')
                conn.execute(f"ATTACH '{normalized_path}' AS symbols_db")
            except:
                # Already attached or error - test if accessible
                try:
                    conn.execute("SELECT 1 FROM symbols_db.symbols LIMIT 1")
                except:
                    return (None, None, None)
            
            # Combine headline, description, and search_text for searching
            if search_text is None:
                search_text = f"{headline or ''} {description or ''}".strip()
            else:
                search_text = f"{headline or ''} {description or ''} {search_text}".strip()
            
            if not search_text:
                return (None, None, None)
            
            search_text_upper = search_text.upper()
            
            # Match by company name - look for symbols where name appears in announcement text
            # Only match equity instruments (EQ) to avoid matching options/futures
            # Use more precise matching with word boundaries and scoring
            
            # First, try exact or near-exact matches (full company name appears in text)
            # This prioritizes complete company names over partial matches
            # We need to pass search_text_upper multiple times for the CASE and WHERE clauses
            matches = conn.execute("""
                SELECT 
                    trading_symbol, 
                    exchange, 
                    name,
                    CASE 
                        -- Exact match (highest priority)
                        WHEN UPPER(?) = UPPER(name) THEN 1
                        -- Full name appears as whole word in text (high priority)
                        WHEN ? LIKE '% ' || UPPER(name) || ' %' THEN 2
                        WHEN ? LIKE '% ' || UPPER(name) || '.' THEN 2
                        WHEN ? LIKE '% ' || UPPER(name) || ',' THEN 2
                        WHEN ? LIKE UPPER(name) || ' %' THEN 2
                        WHEN ? LIKE '% ' || UPPER(name) THEN 2
                        -- Full name appears anywhere (medium priority)
                        WHEN ? LIKE '%' || UPPER(name) || '%' THEN 3
                        -- Partial match (lower priority)
                        WHEN UPPER(name) LIKE '%' || SUBSTRING(?, 1, 50) || '%' THEN 4
                        ELSE 5
                    END as match_score,
                    LENGTH(name) as name_length
                FROM symbols_db.symbols
                WHERE name IS NOT NULL
                  AND name != ''
                  AND status = 'ACTIVE'
                  AND instrument_type = 'EQ'
                  AND (
                    -- Exact match
                    UPPER(?) = UPPER(name)
                    -- Full name as word boundary
                    OR ? LIKE '% ' || UPPER(name) || ' %'
                    OR ? LIKE '% ' || UPPER(name) || '.'
                    OR ? LIKE '% ' || UPPER(name) || ','
                    OR ? LIKE UPPER(name) || ' %'
                    OR ? LIKE '% ' || UPPER(name)
                    -- Full name anywhere
                    OR ? LIKE '%' || UPPER(name) || '%'
                    -- Partial match (only if name is at least 5 chars to avoid false positives)
                    OR (LENGTH(name) >= 5 AND UPPER(name) LIKE '%' || SUBSTRING(?, 1, 50) || '%')
                  )
                ORDER BY 
                    match_score ASC,
                    name_length DESC,
                    name ASC
                LIMIT 5
            """, [
                search_text_upper,  # CASE: exact match check
                search_text_upper,  # CASE: word boundary 1
                search_text_upper,  # CASE: word boundary 2
                search_text_upper,  # CASE: word boundary 3
                search_text_upper,  # CASE: word boundary 4
                search_text_upper,  # CASE: word boundary 5
                search_text_upper,  # CASE: full name anywhere
                search_text_upper,  # CASE: partial match
                search_text_upper,  # WHERE: exact match
                search_text_upper,  # WHERE: word boundary 1
                search_text_upper,  # WHERE: word boundary 2
                search_text_upper,  # WHERE: word boundary 3
                search_text_upper,  # WHERE: word boundary 4
                search_text_upper,  # WHERE: word boundary 5
                search_text_upper,  # WHERE: full name anywhere
                search_text_upper   # WHERE: partial match
            ]).fetchall()
            
            if matches:
                # Filter out poor matches - only accept score 1-3 (exact, word boundary, or full name)
                # Score 4 (partial) is only accepted if it's a very long company name (likely unique)
                good_matches = []
                for match in matches:
                    trading_symbol, exchange, company_name, match_score, name_length = match
                    # Accept exact matches, word boundary matches, full name matches
                    # For partial matches, only accept if name is long (>= 15 chars) to reduce false positives
                    if match_score <= 3 or (match_score == 4 and name_length >= 15):
                        good_matches.append(match)
                
                if good_matches:
                    # Use best match (first result, already sorted by relevance)
                    trading_symbol, exchange, company_name, match_score, name_length = good_matches[0]
                    
                    # Extract base symbol (remove -EQ suffix if present)
                    base_symbol = trading_symbol.replace("-EQ", "").replace("-BE", "").replace("-FUT", "").replace("-OPT", "")
                    
                    if exchange.upper() == 'NSE':
                        return (base_symbol, None, company_name)
                    elif exchange.upper() == 'BSE':
                        return (None, base_symbol, company_name)
                    else:
                        # Default to NSE
                        return (base_symbol, None, company_name)
            
            return (None, None, None)
            
        except Exception as e:
            logger.debug(f"Error matching symbol from DB: {e}")
            return (None, None, None)
    
    def _write_batch(self, batch: list):
        """Write batch of announcements to database"""
        if not batch:
            return
        
        conn = None
        try:
            conn = duckdb.connect(self.db_path)
            
            inserted = 0
            duplicates = 0
            errors = 0
            
            for message in batch:
                try:
                    # VALIDATION: Skip messages with no announcement_id
                    announcement_id = message.get("announcement_id")
                    if not announcement_id:
                        errors += 1
                        logger.debug("Skipping message with no announcement_id")
                        continue
                    
                    # VALIDATION: Skip blank announcements (no headline and no description)
                    headline = message.get("headline")
                    description = message.get("description")
                    if not headline and not description:
                        errors += 1
                        logger.debug(f"Skipping blank announcement: {announcement_id}")
                        continue
                    
                    # Skip if headline is just "-" or empty
                    if headline and headline.strip() in ["-", "", "null", "None"]:
                        errors += 1
                        logger.debug(f"Skipping announcement with invalid headline: {announcement_id}")
                        continue
                    
                    # Check for duplicate BEFORE processing (more efficient)
                    # Also check for duplicates based on headline + datetime if announcement_id is not unique enough
                    existing = conn.execute("""
                        SELECT announcement_id FROM corporate_announcements 
                        WHERE announcement_id = ?
                    """, [announcement_id]).fetchone()
                    
                    if existing:
                        duplicates += 1
                        logger.debug(f"Skipping duplicate announcement: {announcement_id}")
                        continue  # Skip duplicate
                    
                    # Additional check: If headline and datetime match, consider it a duplicate
                    # This catches cases where announcement_id might be generated differently
                    if headline:
                        similar = conn.execute("""
                            SELECT announcement_id FROM corporate_announcements 
                            WHERE headline = ? 
                              AND announcement_datetime = ?
                            LIMIT 1
                        """, [headline, announcement_datetime]).fetchone()
                        
                        if similar:
                            duplicates += 1
                            logger.debug(f"Skipping duplicate announcement (same headline+datetime): {announcement_id}")
                            continue
                    
                    # Double-check: Also check if we're about to insert a duplicate
                    # This handles race conditions where another thread might have inserted between check and insert
                    
                    # Try to match symbols from symbols database if not already present
                    if not message.get("symbol_nse") and not message.get("symbol_bse") and not message.get("symbol"):
                        # Get raw_payload for additional matching context
                        raw_payload = message.get("raw_payload")
                        raw_payload_text = ""
                        if raw_payload:
                            try:
                                import json
                                payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                                # Extract text from common fields
                                for key in ['company', 'companyName', 'company_name', 'name', 'symbol', 'tradingSymbol', 'trading_symbol']:
                                    if key in payload_data and payload_data[key]:
                                        raw_payload_text += f" {str(payload_data[key])}"
                                # Also extract from nested structures
                                if isinstance(payload_data, dict):
                                    for value in payload_data.values():
                                        if isinstance(value, str) and len(value) > 3:
                                            raw_payload_text += f" {value[:100]}"  # Limit length
                            except:
                                if isinstance(raw_payload, str):
                                    raw_payload_text = raw_payload[:500]
                        
                        # Combine all text for matching
                        search_text = f"{headline or ''} {description or ''} {raw_payload_text}".strip()
                        
                        matched_nse, matched_bse, matched_company = self._match_symbol_from_db(conn, headline, description, search_text)
                        if matched_nse or matched_bse:
                            # Update message with matched symbols
                            if matched_nse:
                                message["symbol_nse"] = matched_nse
                                message["symbol"] = matched_nse
                            if matched_bse:
                                message["symbol_bse"] = matched_bse
                                if not message.get("symbol"):
                                    message["symbol"] = matched_bse
                            logger.info(f"Matched symbols for {announcement_id}: NSE={matched_nse}, BSE={matched_bse}, Company={matched_company}")
                    
                    # Parse announcement_datetime
                    announcement_datetime = None
                    if message.get("announcement_datetime"):
                        try:
                            # Try to parse various datetime formats
                            dt_str = message["announcement_datetime"]
                            if isinstance(dt_str, str):
                                # Try ISO format first
                                try:
                                    announcement_datetime = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                                except:
                                    # Try other formats
                                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                                        try:
                                            announcement_datetime = datetime.strptime(dt_str, fmt)
                                            break
                                        except:
                                            continue
                            
                            if announcement_datetime and announcement_datetime.tzinfo is None:
                                announcement_datetime = announcement_datetime.replace(tzinfo=timezone.utc)
                        except Exception as e:
                            logger.debug(f"Could not parse announcement_datetime: {e}")
                            announcement_datetime = None
                    
                    # Parse received_at
                    received_at = datetime.now(timezone.utc)
                    if message.get("received_at"):
                        try:
                            received_at = datetime.fromisoformat(message["received_at"].replace('Z', '+00:00'))
                        except:
                            pass
                    
                    # Check for duplicate BEFORE inserting (more efficient)
                    existing = conn.execute("""
                        SELECT announcement_id FROM corporate_announcements 
                        WHERE announcement_id = ?
                    """, [announcement_id]).fetchone()
                    
                    if existing:
                        duplicates += 1
                        logger.debug(f"Skipping duplicate announcement: {announcement_id}")
                        continue  # Skip duplicate
                    
                    # Ensure we have a symbol value (prioritize symbol_nse, then symbol_bse, then symbol)
                    symbol_value = message.get("symbol_nse") or message.get("symbol_bse") or message.get("symbol")
                    
                    # Insert new announcement
                    # Use INSERT OR IGNORE to handle race conditions (if duplicate check passed but another thread inserted)
                    try:
                        # Check count before insert
                        count_before = conn.execute("SELECT COUNT(*) FROM corporate_announcements WHERE announcement_id = ?", [announcement_id]).fetchone()[0]
                        
                        conn.execute("""
                            INSERT OR IGNORE INTO corporate_announcements (
                                announcement_id,
                                symbol,
                                exchange,
                                headline,
                                description,
                                category,
                                announcement_datetime,
                                received_at,
                                attachment_id,
                                symbol_nse,
                                symbol_bse,
                                raw_payload
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            announcement_id,
                            symbol_value,  # Use best available symbol
                            message.get("exchange"),
                            headline,
                            description,
                            message.get("category"),
                            announcement_datetime,
                            received_at,
                            message.get("attachment_id"),
                            message.get("symbol_nse"),
                            message.get("symbol_bse"),
                            message.get("raw_payload")
                        ])
                        
                        # Check count after insert to see if it was actually inserted
                        count_after = conn.execute("SELECT COUNT(*) FROM corporate_announcements WHERE announcement_id = ?", [announcement_id]).fetchone()[0]
                        if count_after > count_before:
                            inserted += 1
                        else:
                            # INSERT OR IGNORE silently ignored duplicate (race condition)
                            duplicates += 1
                            logger.debug(f"Duplicate ignored by INSERT OR IGNORE (race condition): {announcement_id}")
                    except Exception as insert_error:
                        # Handle any other errors
                        error_msg = str(insert_error).lower()
                        if "duplicate" in error_msg or "unique" in error_msg or "primary key" in error_msg:
                            duplicates += 1
                            logger.debug(f"Duplicate detected on insert: {announcement_id}")
                        else:
                            errors += 1
                            logger.error(f"Error inserting announcement {announcement_id}: {insert_error}")
                            raise
                    
                except Exception as e:
                    errors += 1
                    logger.error(f"Error writing announcement {message.get('announcement_id')}: {e}")
                    logger.debug(f"Message: {message}")
            
            conn.commit()
            
            if inserted > 0 or duplicates > 0 or errors > 0:
                logger.debug(f"Wrote batch: {inserted} inserted, {duplicates} duplicates, {errors} errors")
            
        except Exception as e:
            logger.error(f"Error writing batch to database: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            if conn:
                conn.close()

