"""
Corporate Announcements Service
Handles storage, retrieval, and ingestion of corporate announcements from TrueData
"""
import os
import duckdb
import logging
import threading
import csv
import io
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.core.config import settings
from app.services.truedata_api_service import get_truedata_api_service

logger = logging.getLogger(__name__)

# Thread-safe initialization flag
_init_lock = threading.Lock()
_initialized = False


def get_announcements_db_path() -> str:
    """Get the path to the corporate announcements DuckDB database file"""
    data_dir = os.path.abspath(settings.DATA_DIR)
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    return db_path


def get_db_connection():
    """Get DuckDB connection for corporate announcements"""
    db_path = get_announcements_db_path()
    conn = duckdb.connect(db_path)
    # Set consistent configuration to avoid connection conflicts
    conn.execute("PRAGMA enable_progress_bar=false")
    return conn


def init_announcements_database():
    """Initialize DuckDB database and create corporate_announcements table if it doesn't exist"""
    global _initialized
    
    # Thread-safe initialization check
    if _initialized:
        return
    
    with _init_lock:
        # Double-check after acquiring lock
        if _initialized:
            return
        
        db_path = get_announcements_db_path()
        conn = None
        try:
            # Try to connect with a timeout to avoid hanging on locked files
            conn = duckdb.connect(db_path)
            # Set consistent configuration
            conn.execute("PRAGMA enable_progress_bar=false")
            
            # Check if table exists and has correct schema
            table_exists = False
            schema_correct = False
            try:
                result = conn.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'corporate_announcements'
                """).fetchall()
                
                if result:
                    table_exists = True
                    existing_columns = [row[0] for row in result]
                    required_columns = ['id', 'trade_date', 'script_code', 'symbol_nse', 'symbol_bse', 
                                        'company_name', 'file_status', 'news_headline', 'news_subhead',
                                        'news_body', 'descriptor_id', 'announcement_type', 'meeting_type',
                                        'date_of_meeting']
                    
                    # Check if all required columns exist
                    schema_correct = all(col in existing_columns for col in required_columns)
                    
                    if table_exists and not schema_correct:
                        logger.warning(f"Table exists with incorrect schema. Existing columns: {existing_columns}")
                        logger.info("Dropping and recreating table with correct schema...")
                        conn.execute("DROP TABLE IF EXISTS corporate_announcements")
                        table_exists = False
            except Exception as schema_check_error:
                # Table might not exist or info_schema not available
                logger.debug(f"Schema check error (may be expected): {schema_check_error}")
            
            # Create corporate_announcements table with all documented fields
            if not table_exists:
                conn.execute("""
                    CREATE TABLE corporate_announcements (
                        id VARCHAR PRIMARY KEY,
                        trade_date TIMESTAMP WITH TIME ZONE,
                        script_code INTEGER,
                        symbol_nse VARCHAR,
                        symbol_bse VARCHAR,
                        company_name VARCHAR,
                        file_status VARCHAR,
                        news_headline VARCHAR,
                        news_subhead VARCHAR,
                        news_body TEXT,
                        descriptor_id INTEGER,
                        announcement_type VARCHAR,
                        meeting_type VARCHAR,
                        date_of_meeting TIMESTAMP WITH TIME ZONE,
                        attachment_data BLOB,
                        attachment_content_type VARCHAR,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Created corporate_announcements table with correct schema")
            else:
                # Check if attachment columns exist, add them if not
                try:
                    existing_columns = [row[0] for row in conn.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'corporate_announcements'
                    """).fetchall()]
                    
                    if 'attachment_data' not in existing_columns:
                        conn.execute("ALTER TABLE corporate_announcements ADD COLUMN attachment_data BLOB")
                        logger.info("Added attachment_data column to corporate_announcements table")
                    
                    if 'attachment_content_type' not in existing_columns:
                        conn.execute("ALTER TABLE corporate_announcements ADD COLUMN attachment_content_type VARCHAR")
                        logger.info("Added attachment_content_type column to corporate_announcements table")
                except Exception as alter_error:
                    logger.debug(f"Could not add attachment columns (may already exist): {alter_error}")
            
            # Create descriptor_metadata table for caching descriptor information
            conn.execute("""
                CREATE TABLE IF NOT EXISTS descriptor_metadata (
                    descriptor_id INTEGER PRIMARY KEY,
                    descriptor_name VARCHAR NOT NULL,
                    descriptor_category VARCHAR,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance optimization
            # Index on trade_date (most common filter and ORDER BY column)
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_date ON corporate_announcements(trade_date DESC)")
                logger.info("Created index on trade_date")
            except Exception as idx_error:
                logger.debug(f"Index on trade_date may already exist: {idx_error}")
            
            # Index on symbol_nse for faster symbol filtering
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_nse ON corporate_announcements(symbol_nse)")
                logger.info("Created index on symbol_nse")
            except Exception as idx_error:
                logger.debug(f"Index on symbol_nse may already exist: {idx_error}")
            
            # Index on symbol_bse for faster symbol filtering
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_bse ON corporate_announcements(symbol_bse)")
                logger.info("Created index on symbol_bse")
            except Exception as idx_error:
                logger.debug(f"Index on symbol_bse may already exist: {idx_error}")
            
            # Index on company_name for faster filtering
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_company_name ON corporate_announcements(company_name)")
                logger.info("Created index on company_name")
            except Exception as idx_error:
                logger.debug(f"Index on company_name may already exist: {idx_error}")
            
            # Index on descriptor_id for faster metadata joins
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_descriptor_id ON corporate_announcements(descriptor_id)")
                logger.info("Created index on descriptor_id")
            except Exception as idx_error:
                logger.debug(f"Index on descriptor_id may already exist: {idx_error}")
            
            conn.commit()
            
            _initialized = True
            logger.info("Corporate announcements database initialized with indexes")
        except Exception as e:
            logger.error(f"Error initializing announcements database: {e}")
            # Don't raise - allow retry on next call
            # This prevents blocking if another process has the file locked
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass


class AnnouncementsService:
    """Service for managing corporate announcements"""
    
    def __init__(self):
        self.db_path = get_announcements_db_path()
        # Ensure database is initialized (thread-safe)
        init_announcements_database()
    
    def _get_conn(self):
        """Get database connection - always create new connection and close it after use"""
        try:
            conn = duckdb.connect(self.db_path)
            # Set consistent configuration to avoid connection conflicts
            conn.execute("PRAGMA enable_progress_bar=false")
            return conn
        except Exception as e:
            logger.error(f"Error connecting to announcements database: {e}")
            # Re-initialize in case of issues
            global _initialized
            _initialized = False
            init_announcements_database()
            # Retry connection
            conn = duckdb.connect(self.db_path)
            conn.execute("PRAGMA enable_progress_bar=false")
            return conn
    
    def insert_announcement(self, announcement: Dict[str, Any]) -> bool:
        """
        Insert or update an announcement with duplicate detection.
        
        Duplicate detection strategy:
        - With company_name: same company_name + same headline = duplicate
        - Without company_name: same headline + same date + same symbol = duplicate
          (This allows different funds/companies with same headline to be stored separately)
        
        Args:
            announcement: Dictionary with announcement fields
            
        Returns:
            True if inserted, False if already exists (duplicate)
        """
        # Validate announcement has required ID
        if not announcement or not announcement.get("id"):
            logger.warning("Attempted to insert announcement without ID")
            return False
        
        conn = None
        try:
            conn = self._get_conn()
            
            company_name = announcement.get("company_name")
            news_headline = announcement.get("news_headline")
            trade_date = announcement.get("trade_date")
            
            # Check for duplicates based on company_name and news_headline
            # Only consider announcements where both fields match (case-insensitive, trimmed)
            if company_name and news_headline:
                # Normalize for comparison (trim and convert to lowercase)
                company_name_normalized = str(company_name).strip().lower()
                news_headline_normalized = str(news_headline).strip().lower()
                
                # Check if duplicate exists (case-insensitive comparison)
                existing = conn.execute("""
                    SELECT id FROM corporate_announcements 
                    WHERE LOWER(TRIM(company_name)) = ? 
                    AND LOWER(TRIM(news_headline)) = ?
                """, [company_name_normalized, news_headline_normalized]).fetchone()
                
                if existing:
                    # Duplicate found based on company_name and news_headline
                    logger.debug(f"Skipping duplicate announcement: company='{company_name}', headline='{news_headline[:50]}...'")
                    return False
            
            # Special case: If no company_name but headline is present, check for duplicates
            # based on headline + trade_date + symbol (to distinguish different funds/companies)
            # This prevents removing legitimate announcements from different sources with same headline
            if (not company_name or str(company_name).strip() == '') and news_headline:
                news_headline_normalized = str(news_headline).strip().lower()
                symbol_nse = announcement.get("symbol_nse")
                symbol_bse = announcement.get("symbol_bse")
                script_code = announcement.get("script_code")
                
                # Use symbol (NSE, BSE, or script_code) to differentiate announcements
                # Same headline + same date + same symbol = duplicate
                # Same headline + same date + different symbol = different announcement (e.g., different mutual funds)
                if trade_date:
                    # Normalize trade_date for comparison (extract date part only, ignore time)
                    try:
                        # Try to parse and normalize the date
                        if isinstance(trade_date, str):
                            # Extract date part (YYYY-MM-DD) from various formats
                            date_str = trade_date.split(' ')[0].split('T')[0]
                        else:
                            date_str = str(trade_date).split(' ')[0].split('T')[0]
                        
                        # Build query with symbol matching
                        query = """
                            SELECT id FROM corporate_announcements 
                            WHERE (company_name IS NULL OR TRIM(company_name) = '')
                            AND LOWER(TRIM(news_headline)) = ?
                            AND DATE(trade_date) = DATE(?)
                        """
                        params = [news_headline_normalized, date_str]
                        
                        # Add symbol conditions if available
                        if symbol_nse:
                            query += " AND symbol_nse = ?"
                            params.append(symbol_nse)
                        elif symbol_bse:
                            query += " AND symbol_bse = ?"
                            params.append(symbol_bse)
                        elif script_code:
                            query += " AND script_code = ?"
                            params.append(script_code)
                        else:
                            # No symbol available, fall back to headline + date only
                            # This is less ideal but needed for announcements without symbol
                            pass
                        
                        existing = conn.execute(query, params).fetchone()
                        
                        if existing:
                            logger.debug(f"Skipping duplicate announcement (no company, same symbol): headline='{news_headline[:50]}...', date='{date_str}', symbol='{symbol_nse or symbol_bse or script_code}'")
                            return False
                    except Exception as date_error:
                        logger.warning(f"Error parsing trade_date for duplicate check: {date_error}")
                        # Fall back to headline + symbol check if date parsing fails
                        query = """
                            SELECT id FROM corporate_announcements 
                            WHERE (company_name IS NULL OR TRIM(company_name) = '')
                            AND LOWER(TRIM(news_headline)) = ?
                        """
                        params = [news_headline_normalized]
                        
                        if symbol_nse:
                            query += " AND symbol_nse = ?"
                            params.append(symbol_nse)
                        elif symbol_bse:
                            query += " AND symbol_bse = ?"
                            params.append(symbol_bse)
                        elif script_code:
                            query += " AND script_code = ?"
                            params.append(script_code)
                        
                        existing = conn.execute(query, params).fetchone()
                        
                        if existing:
                            logger.debug(f"Skipping duplicate announcement (no company, headline+symbol only): headline='{news_headline[:50]}...'")
                            return False
                else:
                    # No trade_date, check headline + symbol only
                    query = """
                        SELECT id FROM corporate_announcements 
                        WHERE (company_name IS NULL OR TRIM(company_name) = '')
                        AND LOWER(TRIM(news_headline)) = ?
                    """
                    params = [news_headline_normalized]
                    
                    if symbol_nse:
                        query += " AND symbol_nse = ?"
                        params.append(symbol_nse)
                    elif symbol_bse:
                        query += " AND symbol_bse = ?"
                        params.append(symbol_bse)
                    elif script_code:
                        query += " AND script_code = ?"
                        params.append(script_code)
                    
                    existing = conn.execute(query, params).fetchone()
                    
                    if existing:
                        logger.debug(f"Skipping duplicate announcement (no company, no date, headline+symbol): headline='{news_headline[:50]}...'")
                        return False
            
            # Also check if ID already exists (for backward compatibility)
            existing_by_id = conn.execute(
                "SELECT id FROM corporate_announcements WHERE id = ?",
                [announcement.get("id")]
            ).fetchone()
            
            if existing_by_id:
                # Row already exists with same ID
                return False
            
            # Insert new row
            conn.execute("""
                INSERT INTO corporate_announcements (
                    id, trade_date, script_code, symbol_nse, symbol_bse,
                    company_name, file_status, news_headline, news_subhead,
                    news_body, descriptor_id, announcement_type, meeting_type,
                    date_of_meeting
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                announcement.get("id"),
                announcement.get("trade_date"),
                announcement.get("script_code"),
                announcement.get("symbol_nse"),
                announcement.get("symbol_bse"),
                announcement.get("company_name"),
                announcement.get("file_status"),
                announcement.get("news_headline"),
                announcement.get("news_subhead"),
                announcement.get("news_body"),
                announcement.get("descriptor_id"),
                announcement.get("announcement_type"),
                announcement.get("meeting_type"),
                announcement.get("date_of_meeting")
            ])
            
            conn.commit()
            logger.info(f"Inserted announcement: {announcement.get('id')}")
            
            # Broadcast new announcement via WebSocket (fire and forget)
            # This will be handled by the WebSocket service when it processes announcements
            # We don't broadcast here directly to avoid event loop issues
            # The announcements_websocket_service will handle broadcasting when it receives new announcements
            
            return True
        except Exception as e:
            logger.error(f"Error inserting announcement: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def get_announcements(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        symbol: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get announcements from database with optional filters and pagination
        
        Args:
            from_date: Filter from date (YYYY-MM-DD)
            to_date: Filter to date (YYYY-MM-DD)
            symbol: Filter by symbol (NSE or BSE)
            search: Search by headline or symbol (flexible/fuzzy match)
            limit: Maximum number of records (legacy, use page_size instead)
            offset: Offset for pagination (legacy, use page instead)
            page: Page number (1-indexed)
            page_size: Number of records per page
            
        Returns:
            Tuple of (list of announcement dictionaries, total count)
        """
        conn = self._get_conn()
        try:
            # Build base query for counting - use approximate count for large tables when no filters
            # For filtered queries, use exact count
            use_approximate_count = not from_date and not to_date and not symbol and not search
            
            # Build query for data - exclude large TEXT fields (news_body) for list view
            # This significantly improves performance as news_body can be very large
            query = """SELECT 
                id, trade_date, script_code, symbol_nse, symbol_bse,
                company_name, file_status, news_headline, news_subhead,
                descriptor_id, announcement_type, meeting_type,
                date_of_meeting, created_at, updated_at
                FROM corporate_announcements WHERE 1=1"""
            params = []
            
            # Build count query
            count_query = "SELECT COUNT(*) FROM corporate_announcements WHERE 1=1"
            count_params = []
            
            if from_date:
                query += " AND trade_date >= ?"
                count_query += " AND trade_date >= ?"
                params.append(from_date)
                count_params.append(from_date)
            
            if to_date:
                query += " AND trade_date <= ?"
                count_query += " AND trade_date <= ?"
                params.append(to_date + " 23:59:59")
                count_params.append(to_date + " 23:59:59")
            
            if symbol:
                # Fuzzy/similarity search for symbol and company name (case-insensitive, partial match)
                symbol_lower = symbol.lower().strip()
                # Use LIKE for partial matching on symbols and company name
                query += " AND (LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ? OR LOWER(company_name) LIKE ?)"
                count_query += " AND (LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ? OR LOWER(company_name) LIKE ?)"
                # Use % for partial matching (wildcard)
                symbol_pattern = f"%{symbol_lower}%"
                params.extend([symbol_pattern, symbol_pattern, symbol_pattern, symbol_pattern])
                count_params.extend([symbol_pattern, symbol_pattern, symbol_pattern, symbol_pattern])
            
            if search:
                # Flexible search: headline or symbol (case-insensitive, partial match)
                search_lower = search.lower().strip()
                search_pattern = f"%{search_lower}%"
                # Search in headline, NSE symbol, BSE symbol, and script_code
                query += " AND (LOWER(news_headline) LIKE ? OR LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ?)"
                count_query += " AND (LOWER(news_headline) LIKE ? OR LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ?)"
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
                count_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            
            # Get total count
            # For large tables without filters, COUNT(*) can be slow, but with indexes it should be acceptable
            # DuckDB is optimized for analytical queries, so COUNT(*) with indexes should be reasonably fast
            total_result = conn.execute(count_query, count_params).fetchone()
            total_before_dedup = total_result[0] if total_result else 0
            
            # Apply pagination
            query += " ORDER BY trade_date DESC"
            
            # Use page/page_size if provided, otherwise fall back to limit/offset
            if page is not None and page_size is not None:
                limit = page_size
                offset = (page - 1) * page_size
            elif limit is None:
                limit = 25  # Default page size
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            result = cursor.fetchall()
            
            announcements = []
            seen_ids = set()  # Track seen IDs to prevent true duplicates
            skipped_count = 0
            
            logger.info(f"Processing {len(result)} rows from database query")
            
            for row in result:
                ann = dict(zip(columns, row))
                
                # Convert timestamps to ISO format strings
                for key in ["trade_date", "date_of_meeting", "created_at", "updated_at"]:
                    if ann.get(key):
                        # Handle both datetime objects and strings
                        if isinstance(ann[key], datetime):
                            ann[key] = ann[key].isoformat()
                        elif isinstance(ann[key], str):
                            # Already a string, keep it as is
                            pass
                        else:
                            # Try to convert to string
                            ann[key] = str(ann[key]) if ann[key] is not None else None
                
                ann_id = ann.get("id")
                
                # Only skip if we've seen this exact ID before (true duplicate)
                # This can happen if there's a bug in data insertion, but should be rare
                if ann_id in seen_ids:
                    skipped_count += 1
                    logger.warning(f"Skipping duplicate ID announcement: ID={ann_id}")
                    continue
                
                seen_ids.add(ann_id)
                
                # Include all announcements - don't filter by headline/date
                # Different announcements can have the same headline (e.g., mutual fund NAV declarations)
                announcements.append(ann)
            
            # Use the actual database count for pagination
            total = total_before_dedup
            
            logger.info(f"Retrieved {len(announcements)} announcements (skipped {skipped_count} duplicate IDs), total in DB: {total_before_dedup}")
            return announcements, total
        finally:
            conn.close()
    
    def get_announcement_by_id(self, announcement_id: str) -> Optional[Dict[str, Any]]:
        """Get a single announcement by ID"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM corporate_announcements WHERE id = ?",
                [announcement_id]
            )
            result = cursor.fetchone()
            
            if not result:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            ann = dict(zip(columns, result))
            # Convert timestamps to ISO format strings
            for key in ["trade_date", "date_of_meeting", "created_at", "updated_at"]:
                if ann.get(key) and isinstance(ann[key], datetime):
                    ann[key] = ann[key].isoformat()
            
            return ann
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def store_attachment(self, announcement_id: str, attachment_data: bytes, content_type: str) -> bool:
        """
        Store attachment data in the database for an announcement
        
        Args:
            announcement_id: Announcement ID
            attachment_data: Binary attachment data
            content_type: Content type (e.g., 'application/pdf')
            
        Returns:
            True if stored successfully, False otherwise
        """
        conn = None
        try:
            conn = self._get_conn()
            
            # Check if announcement exists
            existing = conn.execute(
                "SELECT id FROM corporate_announcements WHERE id = ?",
                [announcement_id]
            ).fetchone()
            
            if not existing:
                logger.warning(f"Announcement {announcement_id} not found, cannot store attachment")
                return False
            
            # Update announcement with attachment data
            conn.execute("""
                UPDATE corporate_announcements 
                SET attachment_data = ?, 
                    attachment_content_type = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, [attachment_data, content_type, announcement_id])
            
            logger.info(f"Stored attachment for announcement {announcement_id} ({len(attachment_data)} bytes, {content_type})")
            return True
        except Exception as e:
            logger.error(f"Error storing attachment for announcement {announcement_id}: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def get_attachment(self, announcement_id: str) -> Optional[Dict[str, Any]]:
        """
        Get attachment data from database
        
        Args:
            announcement_id: Announcement ID
            
        Returns:
            Dictionary with 'data' (bytes) and 'content_type' (str), or None if not found
        """
        conn = None
        try:
            conn = self._get_conn()
            
            result = conn.execute("""
                SELECT attachment_data, attachment_content_type 
                FROM corporate_announcements 
                WHERE id = ? AND attachment_data IS NOT NULL
            """, [announcement_id]).fetchone()
            
            if not result:
                return None
            
            # DuckDB returns tuples, extract values
            attachment_data = result[0] if result[0] is not None else None
            content_type = result[1] if len(result) > 1 else None
            
            if not attachment_data:
                return None
            
            return {
                'data': attachment_data,
                'content_type': content_type or 'application/octet-stream'
            }
        except Exception as e:
            logger.error(f"Error getting attachment for announcement {announcement_id}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def fetch_from_truedata_rest(
        self,
        connection_id: int,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        symbol: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> int:
        """
        Fetch announcements from TrueData REST API and store in database
        
        Args:
            connection_id: TrueData connection ID
            from_date: From date (YYYY-MM-DD)
            to_date: To date (YYYY-MM-DD)
            symbol: Optional symbol filter
            top_n: Optional limit
            
        Returns:
            Number of announcements inserted
        """
        try:
            api_service = get_truedata_api_service(connection_id)
            
            # Build parameters for announcements endpoint
            # Try different endpoint names as TrueData API might vary
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            if symbol:
                params["symbol"] = symbol
            if top_n:
                params["top"] = top_n
            
            # Try different endpoint variations
            # Note: TrueData API endpoint name may vary - trying common variations
            endpoint_names = [
                "getAnnouncements",  # CamelCase version (most likely based on other TrueData endpoints)
                "announcements",     # Correct spelling
                "annoucements",      # Original typo version from docs
                "getCorporateAnnouncements",  # Full name
                "corporateAnnouncements"  # Alternative
            ]
            
            response = None
            last_error = None
            
            for endpoint in endpoint_names:
                try:
                    response = api_service.call_corporate_api(endpoint, params=params)
                    # Validate response is not empty
                    if not response:
                        logger.warning(f"Endpoint {endpoint} returned empty response, trying next...")
                        continue
                    logger.info(f"Successfully called TrueData endpoint: {endpoint}")
                    break
                except ValueError as ve:
                    # JSON parsing errors or empty responses
                    last_error = ve
                    logger.debug(f"Endpoint {endpoint} error: {str(ve)}, trying next...")
                    continue
                except Exception as e:
                    last_error = e
                    # Check if it's a 404
                    if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                        if e.response.status_code == 404:
                            logger.debug(f"Endpoint {endpoint} returned 404, trying next...")
                            continue
                    # For other errors, log but continue trying
                    logger.warning(f"Endpoint {endpoint} error: {str(e)}, trying next...")
                    continue
            
            if response is None:
                error_msg = (
                    f"TrueData announcements endpoint not available. "
                    f"Tried endpoints: {', '.join(endpoint_names)}. "
                    f"All endpoints returned errors or empty responses. "
                    f"Please verify: 1) Your TrueData plan includes announcements API, "
                    f"2) The endpoint name is correct, 3) Your token has proper permissions. "
                    f"Last error: {str(last_error) if last_error else 'Unknown'}"
                )
                raise Exception(error_msg)
            
            # Handle response - check if it's CSV format
            if isinstance(response, dict) and response.get("_format") == "csv":
                # Parse CSV data
                csv_data = response.get("_data", "")
                announcements_data = self._parse_csv_announcements(csv_data)
                logger.info(f"Parsed {len(announcements_data)} announcements from CSV")
            else:
                # Handle JSON response - could be list or dict with data field
                if not response:
                    logger.warning("TrueData API returned empty response")
                    return 0
                
                announcements_data = response
                if isinstance(response, dict):
                    # Check for error messages in response
                    if "error" in response or "message" in response:
                        error_msg = response.get("error") or response.get("message")
                        logger.warning(f"TrueData API returned error: {error_msg}")
                        raise Exception(f"TrueData API error: {error_msg}")
                    
                    # Check for data field
                    if "data" in response:
                        announcements_data = response["data"]
                    elif "result" in response:
                        announcements_data = response["result"]
                
                # Ensure we have a list
                if not isinstance(announcements_data, list):
                    if announcements_data:
                        announcements_data = [announcements_data]
                    else:
                        logger.warning("No announcements data in response")
                        return 0
            
            if not announcements_data:
                logger.info("TrueData API returned empty announcements list")
                return 0
            
            inserted_count = 0
            for ann_data in announcements_data:
                try:
                    # Map TrueData fields to our schema
                    announcement = self._map_truedata_to_schema(ann_data)
                    if self.insert_announcement(announcement):
                        inserted_count += 1
                except Exception as e:
                    logger.warning(f"Error processing announcement: {e}")
                    continue
            
            return inserted_count
        except Exception as e:
            logger.error(f"Error fetching from TrueData REST API: {e}")
            raise
    
    def _parse_csv_announcements(self, csv_data: str) -> List[Dict[str, Any]]:
        """
        Parse CSV format announcements from TrueData
        
        Expected CSV format:
        id,trade_date,scrip_code,symbol_nse,symbol_bse,company_name,file_status,news_headline,news_subhead,news_body,news_descriptor,announcement_type,meeting_type
        """
        announcements = []
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_data))
            
            for row in csv_reader:
                try:
                    # Map CSV columns to our schema
                    # Note: CSV uses 'scrip_code' but our DB uses 'script_code'
                    
                    # Handle script_code conversion
                    script_code = None
                    if row.get("scrip_code") and row["scrip_code"].strip():
                        try:
                            script_code = int(row["scrip_code"].strip())
                        except (ValueError, TypeError):
                            logger.debug(f"Could not convert scrip_code to int: {row.get('scrip_code')}")
                    
                    # Handle descriptor_id conversion
                    descriptor_id = None
                    if row.get("news_descriptor") and row["news_descriptor"].strip():
                        try:
                            descriptor_id = int(row["news_descriptor"].strip())
                        except (ValueError, TypeError):
                            logger.debug(f"Could not convert news_descriptor to int: {row.get('news_descriptor')}")
                    
                    announcement = {
                        "id": str(row.get("id", "").strip()),
                        "trade_date": row.get("trade_date", "").strip() if row.get("trade_date") and row.get("trade_date").strip() else None,
                        "script_code": script_code,
                        "symbol_nse": row.get("symbol_nse", "").strip() if row.get("symbol_nse") and row.get("symbol_nse").strip() else None,
                        "symbol_bse": row.get("symbol_bse", "").strip() if row.get("symbol_bse") and row.get("symbol_bse").strip() else None,
                        "company_name": row.get("company_name", "").strip() if row.get("company_name") and row.get("company_name").strip() else None,
                        "file_status": row.get("file_status", "").strip() if row.get("file_status") and row.get("file_status").strip() else None,
                        "news_headline": row.get("news_headline", "").strip() if row.get("news_headline") and row.get("news_headline").strip() else None,
                        "news_subhead": row.get("news_subhead", "").strip() if row.get("news_subhead") and row.get("news_subhead").strip() else None,
                        "news_body": row.get("news_body", "").strip() if row.get("news_body") and row.get("news_body").strip() else None,
                        "descriptor_id": descriptor_id,
                        "announcement_type": row.get("announcement_type", "").strip() if row.get("announcement_type") and row.get("announcement_type").strip() else None,
                        "meeting_type": row.get("meeting_type", "").strip() if row.get("meeting_type") and row.get("meeting_type").strip() else None,
                        "date_of_meeting": row.get("date_of_meeting", "").strip() if row.get("date_of_meeting") and row.get("date_of_meeting").strip() else None
                    }
                    
                    # Only add if we have an ID
                    if announcement["id"]:
                        announcements.append(announcement)
                except Exception as row_error:
                    logger.warning(f"Error parsing CSV row: {row_error}, Row: {row}")
                    continue
            
            logger.info(f"Successfully parsed {len(announcements)} announcements from CSV")
            return announcements
            
        except Exception as e:
            logger.error(f"Error parsing CSV announcements: {e}")
            raise Exception(f"Failed to parse CSV announcements: {str(e)}")
    
    def _map_truedata_to_schema(self, truedata_ann: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map TrueData announcement payload to our database schema
        
        Maps only documented fields, no inferred or additional fields
        Handles multiple field name variations (REST API, WebSocket, CSV)
        """
        # Validate input
        if not truedata_ann or not isinstance(truedata_ann, dict):
            raise ValueError(f"Invalid announcement data: expected dict, got {type(truedata_ann)}")
        
        # Debug logging (reduce once confirmed working)
        logger.debug(f"Mapping TrueData payload with keys: {list(truedata_ann.keys())}")
        
        # Helper to get first non-None value from multiple field names (case-insensitive)
        def get_first(*keys):
            # First try exact match
            for key in keys:
                val = truedata_ann.get(key)
                if val is not None and val != '':
                    return val
            # Then try case-insensitive match
            lower_dict = {k.lower(): v for k, v in truedata_ann.items()}
            for key in keys:
                val = lower_dict.get(key.lower())
                if val is not None and val != '':
                    return val
            return None
        
        # Helper to convert date formats to ISO format (YYYY-MM-DD HH:MM:SS)
        def convert_date(date_str):
            if not date_str or not isinstance(date_str, str):
                return None
            date_str = date_str.strip()
            if not date_str:
                return None
            
            # Try various date formats
            formats = [
                "%d/%m/%Y %H:%M:%S",      # 07/01/2026 18:20:21 (TrueData WebSocket)
                "%m/%d/%Y %I:%M:%S %p",   # 1/28/2026 12:00:00 AM (TrueData DateofMeeting)
                "%Y-%m-%dT%H:%M:%S%z",    # ISO with timezone
                "%Y-%m-%dT%H:%M:%S",      # ISO without timezone
                "%Y-%m-%d %H:%M:%S",      # Standard format
                "%d-%m-%Y %H:%M:%S",      # DD-MM-YYYY
                "%Y/%m/%d %H:%M:%S",      # YYYY/MM/DD
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            # If no format matched, return as-is (might fail but better than None)
            logger.warning(f"Could not parse date: {date_str}")
            return date_str
        
        # Get ID - try multiple possible field names
        announcement_id = get_first("id", "newsid", "news_id", "Id", "ID")
        if not announcement_id:
            raise ValueError("Announcement data missing required 'id' field")
        
        # Handle script_code from various field names (TrueData uses SCRIP_CD)
        script_code = get_first("script_code", "SCRIP_CD", "scrip_code", "scripcode", "scriptcode", "ScripCode")
        if script_code:
            if isinstance(script_code, str):
                try:
                    script_code = int(script_code.strip())
                except (ValueError, TypeError):
                    script_code = None
            elif not isinstance(script_code, int):
                script_code = None
        
        # Handle descriptor_id from various field names (TrueData uses DescriptorID)
        descriptor_id = get_first("descriptor_id", "DescriptorID", "news_descriptor", "descriptorid", "DescriptorId")
        if descriptor_id:
            if isinstance(descriptor_id, str):
                try:
                    descriptor_id = int(descriptor_id.strip())
                except (ValueError, TypeError):
                    descriptor_id = None
            elif not isinstance(descriptor_id, int):
                descriptor_id = None
        
        # Map all fields with multiple name variants
        # TrueData WebSocket uses: SCRIP_CD, CompanyName, Filestatus, Symbol_Bse, Symbol_Nse, 
        # HeadLine, NewsSub, NewsBody, TypeofAnnounce, TypeofMeeting, DateofMeeting, Tradedate
        
        raw_trade_date = get_first("trade_date", "Tradedate", "TradeDate", "tradedate", "newsdate", "NewsDate", "date", "Date", "timestamp", "Timestamp")
        raw_meeting_date = get_first("date_of_meeting", "DateofMeeting", "DateOfMeeting", "dateofmeeting", "meeting_date", "MeetingDate")
        
        return {
            "id": str(announcement_id).strip(),
            "trade_date": convert_date(raw_trade_date),
            "script_code": script_code,
            "symbol_nse": get_first("symbol_nse", "Symbol_Nse", "SymbolNSE", "symbolnse", "nse_symbol", "NSESymbol", "nsesymbol"),
            "symbol_bse": get_first("symbol_bse", "Symbol_Bse", "SymbolBSE", "symbolbse", "bse_symbol", "BSESymbol", "bsesymbol"),
            "company_name": get_first("company_name", "CompanyName", "companyname", "company", "Company", "name", "Name"),
            "file_status": get_first("file_status", "Filestatus", "FileStatus", "filestatus"),
            "news_headline": get_first("news_headline", "HeadLine", "NewsHeadline", "newsheadline", "headline", "Headline", "subject", "Subject", "title", "Title"),
            "news_subhead": get_first("news_subhead", "NewsSub", "NewsSubhead", "newssubhead", "subhead", "Subhead", "subtitle", "SubTitle"),
            "news_body": get_first("news_body", "NewsBody", "newsbody", "body", "Body", "content", "Content", "message", "Message"),
            "descriptor_id": descriptor_id,
            "announcement_type": get_first("announcement_type", "TypeofAnnounce", "AnnouncementType", "announcementtype", "type", "Type", "category", "Category"),
            "meeting_type": get_first("meeting_type", "TypeofMeeting", "MeetingType", "meetingtype"),
            "date_of_meeting": convert_date(raw_meeting_date)
        }
    
    def get_descriptor_metadata(self, descriptor_id: int) -> Optional[Dict[str, Any]]:
        """Get descriptor metadata from cache"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM descriptor_metadata WHERE descriptor_id = ?",
                [descriptor_id]
            )
            result = cursor.fetchone()
            
            if not result:
                return None
            
            columns = ["descriptor_id", "descriptor_name", "descriptor_category", "updated_at"]
            return dict(zip(columns, result))
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def get_descriptor_metadata_batch(self, descriptor_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get descriptor metadata for multiple IDs in a single query (batch lookup)"""
        if not descriptor_ids:
            return {}
        
        conn = self._get_conn()
        try:
            # Create placeholders for IN clause
            placeholders = ','.join(['?' for _ in descriptor_ids])
            cursor = conn.execute(
                f"SELECT descriptor_id, descriptor_name, descriptor_category, updated_at "
                f"FROM descriptor_metadata WHERE descriptor_id IN ({placeholders})",
                descriptor_ids
            )
            results = cursor.fetchall()
            
            # Build dictionary mapping descriptor_id to metadata
            metadata_dict = {}
            for row in results:
                metadata_dict[row[0]] = {
                    "descriptor_id": row[0],
                    "descriptor_name": row[1],
                    "descriptor_category": row[2],
                    "updated_at": row[3]
                }
            
            return metadata_dict
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def cache_descriptor_metadata(self, descriptors: List[Dict[str, Any]]):
        """Cache descriptor metadata from TrueData"""
        conn = self._get_conn()
        try:
            for desc in descriptors:
                conn.execute("""
                    INSERT OR REPLACE INTO descriptor_metadata 
                    (descriptor_id, descriptor_name, descriptor_category, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, [
                    desc.get("descriptor_id"),
                    desc.get("descriptor_name"),
                    desc.get("descriptor_category")
                ])
            conn.commit()
        except Exception as e:
            logger.error(f"Error caching descriptor metadata: {e}")
            try:
                conn.rollback()
            except:
                pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def fetch_descriptors_from_truedata(self, connection_id: int):
        """Fetch and cache descriptor metadata from TrueData"""
        try:
            api_service = get_truedata_api_service(connection_id)
            response = api_service.call_corporate_api("getdescriptors")
            
            descriptors = response
            if isinstance(response, dict) and "data" in response:
                descriptors = response["data"]
            elif not isinstance(descriptors, list):
                descriptors = [descriptors]
            
            self.cache_descriptor_metadata(descriptors)
        except Exception as e:
            logger.error(f"Error fetching descriptors from TrueData: {e}")
            raise


def get_announcements_service() -> AnnouncementsService:
    """Get announcements service instance"""
    return AnnouncementsService()

