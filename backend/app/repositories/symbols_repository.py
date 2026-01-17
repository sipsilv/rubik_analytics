import duckdb
import os
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class SymbolsRepository:
    def __init__(self):
        self.data_dir = os.path.abspath(settings.DATA_DIR)
        self.db_dir = os.path.join(self.data_dir, "symbols")
        self.db_path = os.path.join(self.db_dir, "symbols.duckdb")
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Initialize DB if needed
        if not os.path.exists(self.db_path):
             self.init_symbols_database()

    def get_symbols_db_path(self) -> str:
        return self.db_path

    def get_db_connection(self):
        """Get a DuckDB connection with consistent configuration"""
        try:
            if not os.path.exists(self.db_path):
                self.init_symbols_database()
            conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
            conn.execute("PRAGMA enable_progress_bar=false")
            return conn
        except Exception as e:
            logger.error(f"Failed to get database connection: {str(e)}", exc_info=True)
            raise

    def init_symbols_database(self):
        """Initialize DuckDB database and create tables"""
        try:
            conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
            conn.execute("PRAGMA enable_progress_bar=false")
            
            # Create symbols table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY,
                    exchange VARCHAR NOT NULL,
                    trading_symbol VARCHAR NOT NULL,
                    exchange_token VARCHAR,
                    name VARCHAR,
                    instrument_type VARCHAR,
                    segment VARCHAR,
                    series VARCHAR,
                    isin VARCHAR,
                    expiry_date DATE,
                    strike_price DOUBLE,
                    lot_size INTEGER,
                    status VARCHAR DEFAULT 'ACTIVE',
                    source VARCHAR DEFAULT 'MANUAL',
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    last_updated_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(exchange, trading_symbol)
                )
            """)
            
            # Create upload_logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS upload_logs (
                    id INTEGER PRIMARY KEY,
                    job_id VARCHAR NOT NULL UNIQUE,
                    file_name VARCHAR NOT NULL,
                    upload_type VARCHAR DEFAULT 'MANUAL',
                    triggered_by VARCHAR,
                    started_at TIMESTAMP WITH TIME ZONE,
                    ended_at TIMESTAMP WITH TIME ZONE,
                    duration_seconds INTEGER,
                    total_rows INTEGER DEFAULT 0,
                    inserted_rows INTEGER DEFAULT 0,
                    updated_rows INTEGER DEFAULT 0,
                    failed_rows INTEGER DEFAULT 0,
                    status VARCHAR DEFAULT 'PENDING',
                    progress_percentage INTEGER DEFAULT 0,
                    error_summary VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create schedulers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedulers (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    description VARCHAR,
                    mode VARCHAR NOT NULL,
                    interval_value INTEGER,
                    interval_unit VARCHAR,
                    cron_expression VARCHAR,
                    script_id INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    sources TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    last_run_at TIMESTAMP WITH TIME ZONE,
                    next_run_at TIMESTAMP WITH TIME ZONE,
                    created_by INTEGER
                )
            """)
            
            # Create transformation_scripts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transformation_scripts (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    description VARCHAR,
                    content TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    created_by INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    last_used_at TIMESTAMP WITH TIME ZONE
                )
            """)
            
            # Create series_lookup table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS series_lookup (
                    series_code VARCHAR PRIMARY KEY,
                    description VARCHAR NOT NULL
                )
            """)
            
            # Create metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS series_lookup_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    csv_last_modified TIMESTAMP,
                    last_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON symbols(exchange)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_trading_symbol ON symbols(trading_symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_status ON symbols(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_logs_job_id ON upload_logs(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_logs_created_at ON upload_logs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transformation_scripts_name ON transformation_scripts(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_series_lookup_code ON series_lookup(series_code)")
            
            conn.close()
            # self.reload_series_lookup() # Ideally called separately to avoid circular dependencies/long startup
        except Exception as e:
             logger.error(f"Failed to initialize symbols database: {e}")
             raise

    def reload_series_lookup(self, force: bool = False):
        """Reload series lookup data from CSV file"""
        conn = None
        try:
            conn = self.get_db_connection()
            csv_path = os.path.join(os.path.dirname(self.db_path), "Series.csv")
            
            if not os.path.exists(csv_path):
                logger.warning(f"Series CSV file not found at: {csv_path}")
                return {"success": False, "message": f"CSV file not found at {csv_path}"}
            
            csv_mtime = os.path.getmtime(csv_path)
            csv_mtime_dt = datetime.fromtimestamp(csv_mtime, tz=timezone.utc)
            
            row_count = conn.execute("SELECT COUNT(*) FROM series_lookup").fetchone()[0]
            
            should_reload = force
            if not should_reload:
                if row_count == 0:
                    should_reload = True
                else:
                    try:
                        metadata = conn.execute("SELECT csv_last_modified FROM series_lookup_metadata WHERE id = 1").fetchone()
                        last_csv_mtime = metadata[0] if metadata and metadata[0] else None
                        if last_csv_mtime and last_csv_mtime.tzinfo is None:
                            last_csv_mtime = last_csv_mtime.replace(tzinfo=timezone.utc)
                            
                        if last_csv_mtime is None or csv_mtime_dt > last_csv_mtime:
                            should_reload = True
                    except:
                        should_reload = True
            
            if not should_reload:
                return {"success": True, "message": "Series lookup data up to date", "reloaded": False}
            
            if row_count > 0:
                conn.execute("DELETE FROM series_lookup")
            
            # Load CSV logic (simplified here, assumes CSV format is correct)
            # Replicating the range expansion logic from original file
            import csv
            import re
            loaded_count = 0
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    series_code = row.get('Series Code', '').strip()
                    description = row.get('Description', '').strip()
                    if series_code and description:
                         if '-' in series_code and ('/' in series_code or len(series_code) > 5):
                             parts = series_code.split('/')
                             for part in parts:
                                 part = part.strip()
                                 if '-' in part:
                                     match = re.match(r'^([A-Z]+)([0-9A-Z])-([A-Z]+)([0-9A-Z])$', part)
                                     if match:
                                         prefix = match.group(1)
                                         start_sub = match.group(2)
                                         end_sub = match.group(4)
                                         if start_sub.isdigit() and end_sub.isdigit():
                                             for i in range(int(start_sub), int(end_sub) + 1):
                                                 conn.execute("INSERT OR REPLACE INTO series_lookup VALUES (?, ?)", [f"{prefix}{i}", description])
                                                 loaded_count += 1
                                         elif start_sub.isalpha() and end_sub.isalpha():
                                              for i in range(ord(start_sub.upper()), ord(end_sub.upper()) + 1):
                                                 conn.execute("INSERT OR REPLACE INTO series_lookup VALUES (?, ?)", [f"{prefix}{chr(i)}", description])
                                                 loaded_count += 1
                             conn.execute("INSERT OR REPLACE INTO series_lookup VALUES (?, ?)", [series_code, description])
                             loaded_count += 1
                         else:
                             conn.execute("INSERT OR REPLACE INTO series_lookup VALUES (?, ?)", [series_code, description])
                             loaded_count += 1

            conn.execute("INSERT OR REPLACE INTO series_lookup_metadata (id, csv_last_modified, last_loaded_at) VALUES (1, ?, CURRENT_TIMESTAMP)", [csv_mtime_dt])
            return {"success": True, "message": f"Loaded {loaded_count} entries", "reloaded": True, "entries_count": loaded_count}
        except Exception as e:
            logger.error(f"Error reloading series lookup: {e}")
            return {"success": False, "message": str(e)}
        finally:
            if conn: conn.close()

    def save_upload_log(self, conn, job_id, filename, started_at, ended_at, status, total_rows, inserted, updated, failed, errors, triggered_by, upload_type):
        """Save upload log to database"""
        close_conn = False
        try:
            if conn is None:
                conn = self.get_db_connection()
                close_conn = True
            
            # Ensure table exists (lazy check)
            try: conn.execute("SELECT 1 FROM upload_logs LIMIT 1")
            except: self.init_symbols_database()
            
            duration = int((ended_at - started_at).total_seconds())
            error_summary = "; ".join(errors[:5]) if errors else None
            progress_pct = 100 if status in ["SUCCESS", "PARTIAL", "FAILED"] else 0
            
            existing = conn.execute("SELECT id FROM upload_logs WHERE job_id = ?", [job_id]).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE upload_logs SET
                        file_name = ?, upload_type = ?, triggered_by = ?, started_at = ?, ended_at = ?,
                        duration_seconds = ?, total_rows = ?, inserted_rows = ?, updated_rows = ?, failed_rows = ?,
                        status = ?, progress_percentage = ?, error_summary = ?
                    WHERE job_id = ?
                """, (filename, upload_type, triggered_by, started_at, ended_at, duration, total_rows, inserted, updated, failed, status, progress_pct, error_summary, job_id))
            else:
                max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM upload_logs").fetchone()[0]
                next_id = max_id + 1
                conn.execute("""
                    INSERT INTO upload_logs (
                        id, job_id, file_name, upload_type, triggered_by, started_at, ended_at,
                        duration_seconds, total_rows, inserted_rows, updated_rows, failed_rows,
                        status, progress_percentage, error_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (next_id, job_id, filename, upload_type, triggered_by, started_at, ended_at, duration, total_rows, inserted, updated, failed, status, progress_pct, error_summary, started_at))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to save upload log: {e}")
        finally:
            if close_conn and conn: conn.close()
    
    def get_transformation_script(self, script_id: int):
        conn = None
        try:
            conn = self.get_db_connection()
            return conn.execute("SELECT name, content FROM transformation_scripts WHERE id = ?", [script_id]).fetchone()
        finally:
            if conn: conn.close()

    def get_symbols_paginated(self, limit=25, offset=0, where_clauses=[], params=[]):
        conn = None
        try:
            conn = self.get_db_connection()
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            count_sql = f"SELECT COUNT(*) FROM symbols WHERE {where_sql}"
            total = conn.execute(count_sql, params).fetchone()[0]
            
            sql = f"""
                SELECT id, exchange, trading_symbol, exchange_token, name, instrument_type, 
                       segment, series, isin, expiry_date, strike_price, lot_size, status, 
                       source, updated_at
                FROM symbols
                WHERE {where_sql}
                ORDER BY exchange, trading_symbol
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(sql, params + [limit, offset]).fetchall()
            
            col_names = ['id', 'exchange', 'trading_symbol', 'exchange_token', 'name', 'instrument_type', 
                         'segment', 'series', 'isin', 'expiry_date', 'strike_price', 'lot_size', 'status', 
                         'source', 'updated_at']
            
            result = []
            for row in rows:
                d = dict(zip(col_names, row))
                # Convert dates/timestamps to string/isoformat if needed
                if d['updated_at']: d['updated_at'] = d['updated_at'].isoformat() if hasattr(d['updated_at'], 'isoformat') else str(d['updated_at'])
                if d['expiry_date']: d['expiry_date'] = str(d['expiry_date'])
                result.append(d)
                
            return result, total
        finally:
            if conn: conn.close()

    def get_upload_logs(self, limit=50, offset=0):
        # Implementation similar to original get_upload_logs
        conn = None
        try:
            conn = self.get_db_connection()
            total = conn.execute("SELECT COUNT(*) FROM upload_logs").fetchone()[0]
            
            rows = conn.execute("""
                SELECT job_id, file_name, upload_type, triggered_by, started_at, ended_at,
                       duration_seconds, total_rows, inserted_rows, updated_rows, failed_rows,
                       status, progress_percentage, error_summary, created_at
                FROM upload_logs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, [limit, offset]).fetchall()
            
            return rows, total
        finally:
            if conn: conn.close()
