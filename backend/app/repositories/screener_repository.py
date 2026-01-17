import duckdb
import os
import logging
import time
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class ScreenerRepository:
    def __init__(self):
        self.data_dir = os.path.abspath(settings.DATA_DIR)
        self.db_dir = os.path.join(self.data_dir, "Company Fundamentals")
        self.db_path = os.path.join(self.db_dir, "screener.duckdb")
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Initialize DB if needed (e.g. on first access)
        # We can call init_db on init or lazily. 
        # Original code called init on module load.
        if not os.path.exists(self.db_path):
             self.init_screener_database()

    def get_screener_db_path(self) -> str:
        return self.db_path

    def init_screener_database(self):
        """Initialize DuckDB database and create unified time-series table"""
        try:
            conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
            
            # Create unified time-series table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screener_data (
                    id INTEGER PRIMARY KEY,
                    entity_type VARCHAR NOT NULL,
                    parent_company_symbol VARCHAR,
                    symbol VARCHAR NOT NULL,
                    exchange VARCHAR NOT NULL,
                    period_type VARCHAR NOT NULL,
                    period_key VARCHAR NOT NULL,
                    statement_group VARCHAR NOT NULL,
                    metric_name VARCHAR NOT NULL,
                    metric_value DOUBLE,
                    unit VARCHAR,
                    consolidated_flag VARCHAR DEFAULT 'CONSOLIDATED',
                    source VARCHAR DEFAULT 'screener.in',
                    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Ensure id column auto-increments
            try:
                conn.execute("CREATE SEQUENCE IF NOT EXISTS screener_data_id_seq START 1")
            except:
                pass 
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_period 
                ON screener_data(symbol, period_type, period_key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_statement_group 
                ON screener_data(statement_group, symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_type 
                ON screener_data(entity_type, parent_company_symbol)
            """)
            
            # Create scraping logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screener_scraping_logs (
                    id INTEGER PRIMARY KEY,
                    job_id VARCHAR NOT NULL UNIQUE,
                    triggered_by VARCHAR,
                    started_at TIMESTAMP WITH TIME ZONE,
                    ended_at TIMESTAMP WITH TIME ZONE,
                    duration_seconds INTEGER,
                    total_symbols INTEGER DEFAULT 0,
                    symbols_processed INTEGER DEFAULT 0,
                    symbols_succeeded INTEGER DEFAULT 0,
                    symbols_failed INTEGER DEFAULT 0,
                    total_records_inserted INTEGER DEFAULT 0,
                    status VARCHAR DEFAULT 'PENDING',
                    error_summary TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create detailed symbol-level logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screener_detailed_logs (
                    id INTEGER PRIMARY KEY,
                    job_id VARCHAR NOT NULL,
                    connection_id INTEGER,
                    connection_name VARCHAR,
                    symbol VARCHAR,
                    exchange VARCHAR,
                    company_name VARCHAR,
                    symbol_index INTEGER,
                    total_symbols INTEGER,
                    action VARCHAR NOT NULL,
                    message TEXT,
                    records_count INTEGER,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add new columns if they don't exist
            current_columns_detailed = [col[0] for col in conn.execute("DESCRIBE screener_detailed_logs").fetchall()]
            if 'company_name' not in current_columns_detailed:
                 conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN company_name VARCHAR")
            if 'symbol_index' not in current_columns_detailed:
                 conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN symbol_index INTEGER")
            if 'total_symbols' not in current_columns_detailed:
                 conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN total_symbols INTEGER")
            if 'records_count' not in current_columns_detailed:
                 conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN records_count INTEGER")
            
            # Create indexes for detailed logs
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_detailed_logs_job_id 
                ON screener_detailed_logs(job_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_detailed_logs_connection 
                ON screener_detailed_logs(connection_id, timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_detailed_logs_timestamp 
                ON screener_detailed_logs(timestamp DESC)
            """)
            
            # Create connections table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screener_connections (
                    id INTEGER PRIMARY KEY,
                    connection_name VARCHAR NOT NULL,
                    connection_type VARCHAR NOT NULL,
                    website_name VARCHAR,
                    base_url VARCHAR,
                    api_provider_name VARCHAR,
                    auth_type VARCHAR,
                    status VARCHAR DEFAULT 'Idle',
                    last_run TIMESTAMP WITH TIME ZONE,
                    records_loaded INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            current_columns_conn = [col[0] for col in conn.execute("DESCRIBE screener_connections").fetchall()]
            if 'base_url' not in current_columns_conn:
                conn.execute("ALTER TABLE screener_connections ADD COLUMN base_url VARCHAR")
            
            self._ensure_default_connection(conn)
            
            conn.close()
            logger.info(f"Screener database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Screener database: {e}")
            raise

    def _ensure_default_connection(self, conn: duckdb.DuckDBPyConnection):
        """Ensure a default Screener.in connection exists"""
        try:
            existing_count = conn.execute("SELECT COUNT(*) FROM screener_connections").fetchone()[0]
            if existing_count == 0:
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_connections").fetchone()
                next_id = max_id_result[0] if max_id_result else 1
                
                now = datetime.now(timezone.utc)
                conn.execute("""
                    INSERT INTO screener_connections 
                    (id, connection_name, connection_type, base_url, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    next_id,
                    "Screener.in Default",
                    "WEBSITE_SCRAPING",
                    "https://www.screener.in/company/{symbol}/",
                    "Idle",
                    now,
                    now
                ])
                logger.info("Created default Screener.in connection")
        except Exception as e:
            logger.warning(f"Could not ensure default connection: {e}")

    def get_db_connection(self):
        """Get a DuckDB connection to the Screener database with proper configuration"""
        if not os.path.exists(self.db_path):
            self.init_screener_database()
        
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                conn = duckdb.connect(self.db_path, read_only=False, config={'allow_unsigned_extensions': True})
                conn.execute("SET enable_progress_bar=false")
                conn.execute("SET threads=1")
                try:
                    self._ensure_default_connection(conn)
                except Exception as e:
                    logger.warning(f"Could not ensure default connection: {e}")
                return conn
            except Exception as e:
                if attempt < max_retries - 1:
                    error_msg = str(e)
                    if "being used by another process" in error_msg or "Cannot open file" in error_msg:
                        logger.warning(f"[DB] Database file is locked (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Failed to connect to Screener database at {self.db_path}: {e}", exc_info=True)
                        raise
                else:
                    logger.error(f"Failed to connect to Screener database at {self.db_path} after {max_retries} attempts: {e}", exc_info=True)
                    raise

    def insert_metric(
        self,
        conn: duckdb.DuckDBPyConnection,
        entity_type: str,
        parent_company_symbol: Optional[str],
        symbol: str,
        exchange: str,
        period_type: str,
        period_key: str,
        statement_group: str,
        metric_name: str,
        metric_value: Optional[float],
        unit: Optional[str] = None,
        consolidated_flag: str = "CONSOLIDATED",
        metadata: Optional[str] = None
    ):
        """Insert a single metric into the unified table"""
        if metric_value is None and period_type != "EVENT":
            return
        
        try:
            try:
                next_id_result = conn.execute("SELECT nextval('screener_data_id_seq')").fetchone()
                next_id = next_id_result[0] if next_id_result else None
            except:
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_data").fetchone()
                next_id = max_id_result[0] if max_id_result else 1
            
            conn.execute("""
                INSERT INTO screener_data (
                    id, entity_type, parent_company_symbol, symbol, exchange,
                    period_type, period_key, statement_group, metric_name,
                    metric_value, unit, consolidated_flag, source, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                next_id, entity_type, parent_company_symbol, symbol, exchange,
                period_type, period_key, statement_group, metric_name,
                metric_value, unit, consolidated_flag, "screener.in", metadata
            ])
        except Exception as e:
            logger.warning(f"Failed to insert metric {metric_name} for {symbol}: {e}")

    def write_detailed_log(
        self,
        conn: duckdb.DuckDBPyConnection,
        job_id: str,
        connection_id: Optional[int],
        connection_name: Optional[str],
        symbol: Optional[str],
        exchange: Optional[str],
        action: str,
        message: str,
        company_name: Optional[str] = None,
        symbol_index: Optional[int] = None,
        total_symbols: Optional[int] = None,
        records_count: Optional[int] = None
    ):
        """Write detailed log entry"""
        try:
            try:
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM screener_detailed_logs").fetchone()
                next_id = (max_id_result[0] if max_id_result else 0) + 1
            except:
                next_id = 1
            
            conn.execute("""
                INSERT INTO screener_detailed_logs 
                (id, job_id, connection_id, connection_name, symbol, exchange, company_name, 
                 symbol_index, total_symbols, action, message, records_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                next_id, job_id, connection_id, connection_name, symbol, exchange, company_name,
                symbol_index, total_symbols, action, message, records_count
            ])
        except Exception as e:
            logger.warning(f"Failed to write detailed log: {e}")

    def save_scraping_log(
        self,
        conn,
        job_id: str,
        triggered_by: str,
        started_at: datetime,
        ended_at: datetime,
        status: str,
        total_symbols: int,
        symbols_processed: int,
        symbols_succeeded: int,
        symbols_failed: int,
        total_records: int,
        errors: list
    ):
        """Save or update scraping log"""
        if not conn:
            return
        
        try:
            duration = int((ended_at - started_at).total_seconds())
            error_summary = "; ".join(errors) if errors else None
            
            existing = conn.execute("SELECT id FROM screener_scraping_logs WHERE job_id = ?", [job_id]).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE screener_scraping_logs SET
                        triggered_by = ?, started_at = ?, ended_at = ?, duration_seconds = ?,
                        total_symbols = ?, symbols_processed = ?, symbols_succeeded = ?, symbols_failed = ?,
                        total_records_inserted = ?, status = ?, error_summary = ?
                    WHERE job_id = ?
                """, [
                    triggered_by, started_at, ended_at, duration,
                    total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                    total_records, status, error_summary, job_id
                ])
            else:
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM screener_scraping_logs").fetchone()
                next_id = (max_id_result[0] if max_id_result else 0) + 1
                
                conn.execute("""
                    INSERT INTO screener_scraping_logs (
                        id, job_id, triggered_by, started_at, ended_at, duration_seconds,
                        total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                        total_records_inserted, status, error_summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    next_id, job_id, triggered_by, started_at, ended_at, duration,
                    total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                    total_records, status, error_summary
                ])
        except Exception as e:
            logger.error(f"Failed to save scraping log: {e}")

    def get_active_symbols(self, conn: duckdb.DuckDBPyConnection) -> List[Dict[str, str]]:
        """Get active symbols from Symbols database for scraping"""
        symbols_db_path = os.path.join(
            os.path.abspath(settings.DATA_DIR),
            "symbols",
            "symbols.duckdb"
        )
        
        if not os.path.exists(symbols_db_path):
            logger.warning(f"Symbols database not found at {symbols_db_path}")
            return []
        
        try:
            logger.info(f"[SYMBOL_SELECTION] Loading symbols database from: {symbols_db_path}")
            conn.execute(f"ATTACH '{symbols_db_path}' AS symbols_db")
            
            query = conn.execute("""
                SELECT name, exchange, exchange_token, trading_symbol
                FROM symbols_db.symbols
                WHERE status = 'ACTIVE'
                AND (instrument_type = 'CASH' OR instrument_type = 'EQ')
                AND (
                    (exchange = 'NSE' AND name IS NOT NULL AND TRIM(name) != '') OR
                    (exchange = 'BSE' AND exchange_token IS NOT NULL AND TRIM(exchange_token) != '')
                )
                ORDER BY exchange, UPPER(COALESCE(name, exchange_token))
            """)
            
            rows = query.fetchall()
            conn.execute("DETACH symbols_db")
            
            symbols_list = []
            seen_symbols = set()
            
            for row in rows:
                name = row[0]
                exchange = row[1]
                exchange_token = row[2]
                
                exchange_str = str(exchange).strip().upper() if exchange else ""
                
                if exchange_str == 'NSE':
                    if name and str(name).strip():
                        symbol_value = str(name).strip()
                        unique_key = f"NSE:{symbol_value}"
                        if unique_key not in seen_symbols:
                            seen_symbols.add(unique_key)
                            symbols_list.append({
                                "symbol": symbol_value,
                                "exchange": exchange_str,
                                "display_name": symbol_value
                            })
                elif exchange_str == 'BSE':
                    if exchange_token and str(exchange_token).strip():
                        symbol_value = str(exchange_token).strip()
                        unique_key = f"BSE:{symbol_value}"
                        if unique_key not in seen_symbols:
                            seen_symbols.add(unique_key)
                            display_name = str(name).strip() if name and str(name).strip() else symbol_value
                            symbols_list.append({
                                "symbol": symbol_value,
                                "exchange": exchange_str,
                                "display_name": display_name
                            })
            
            return symbols_list
            
        except Exception as e:
            logger.error(f"[SYMBOL_SELECTION] Error getting active symbols: {e}", exc_info=True)
            try:
                conn.execute("DETACH symbols_db")
            except:
                pass
            return []

    def log_job_failure(self, job_id, triggered_by, started_at, error_msg):
        """Helper to log job failure when main connection isn't available"""
        try:
            conn = self.get_db_connection()
            self.save_scraping_log(
                conn, job_id, triggered_by, started_at,
                datetime.now(timezone.utc), "FAILED",
                0, 0, 0, 0, 0, [error_msg]
            )
            conn.close()
        except Exception as log_error:
            logger.error(f"Failed to save scraping log: {log_error}", exc_info=True)
