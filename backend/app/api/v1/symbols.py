from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks, Request, Query
from typing import List, Optional, Dict
import os
import pandas as pd
import io
import uuid
import duckdb
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import asyncio
import logging
import requests
import tempfile
import json
import threading
from urllib.parse import urlparse
from pydantic import BaseModel

from app.core.permissions import get_admin_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.symbol import SymbolResponse, PaginatedSymbolResponse, PreviewResponse, ScriptResponse, ScriptCreate, ScriptUpdate, AutoUploadRequest, SchedulerCreate, SchedulerUpdate, SchedulerResponse, SchedulerSource

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level lock dictionary for manual scheduler triggers
# This persists across all requests
_scheduler_manual_locks: Dict[int, threading.Lock] = {}
_scheduler_locks_lock = threading.Lock()  # Lock to protect the locks dictionary

# Get symbols database path
def get_symbols_db_path() -> str:
    """Get the path to the symbols DuckDB database file"""
    data_dir = os.path.abspath(settings.DATA_DIR)
    db_dir = os.path.join(data_dir, "symbols")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "symbols.duckdb")
    return db_path

def init_symbols_database():
    """Initialize DuckDB database and create symbols table if it doesn't exist"""
    db_path = get_symbols_db_path()
    
    try:
        # Use consistent connection configuration (same as get_db_connection)
        conn = duckdb.connect(db_path, config={'allow_unsigned_extensions': True})
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
        
        # Create series_lookup table for series descriptions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS series_lookup (
                series_code VARCHAR PRIMARY KEY,
                description VARCHAR NOT NULL
            )
        """)
        
        # Create metadata table to track CSV load time
        conn.execute("""
            CREATE TABLE IF NOT EXISTS series_lookup_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                csv_last_modified TIMESTAMP,
                last_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get the CSV file path
        csv_path = os.path.join(
            os.path.dirname(db_path),
            "Series.csv"
        )
        
        # Load or reload series data from CSV
        try:
            should_reload = False
            
            # Check if CSV exists
            if os.path.exists(csv_path):
                # Get CSV file modification time
                csv_mtime = os.path.getmtime(csv_path)
                csv_mtime_dt = datetime.fromtimestamp(csv_mtime, tz=timezone.utc)
                
                # Check if table is empty or CSV is newer than last load
                row_count = conn.execute("SELECT COUNT(*) FROM series_lookup").fetchone()[0]
                
                if row_count == 0:
                    # Table is empty, definitely load
                    should_reload = True
                    logger.info(f"Series lookup table is empty, loading from CSV: {csv_path}")
                else:
                    # Check last load time from metadata
                    try:
                        metadata = conn.execute("SELECT csv_last_modified, last_loaded_at FROM series_lookup_metadata WHERE id = 1").fetchone()
                        if metadata:
                            last_csv_mtime = metadata[0] if metadata[0] else None
                            
                            # Ensure last_csv_mtime is timezone-aware for comparison
                            if last_csv_mtime and last_csv_mtime.tzinfo is None:
                                last_csv_mtime = last_csv_mtime.replace(tzinfo=timezone.utc)
                                
                            if last_csv_mtime is None:
                                should_reload = True
                                logger.info(f"No CSV modification time in metadata, reloading from: {csv_path}")
                            elif csv_mtime_dt > last_csv_mtime:
                                should_reload = True
                                logger.info(f"CSV file has been modified (CSV: {csv_mtime_dt}, Last: {last_csv_mtime}), reloading series lookup data from: {csv_path}")
                            else:
                                logger.info(f"Series lookup data is up to date (CSV: {csv_mtime_dt}, Last: {last_csv_mtime})")
                        else:
                            # No metadata, reload to be safe
                            should_reload = True
                            logger.info(f"No metadata found, loading series lookup data from: {csv_path}")
                    except Exception as e:
                        # If metadata check fails, reload to be safe
                        logger.warning(f"Error checking metadata, forcing reload: {e}")
                        should_reload = True
                
                if should_reload:
                    # Reload series lookup data inline (avoiding circular import)
                    # We'll reload it after module initialization completes
                    logger.info("Series lookup data needs reloading, will reload after module initialization")
                    should_reload = False  # Defer to avoid circular import
            else:
                logger.warning(f"Series CSV file not found at: {csv_path}")
        except Exception as e:
            logger.warning(f"Could not load series lookup data: {e}", exc_info=True)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON symbols(exchange)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_trading_symbol ON symbols(trading_symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_status ON symbols(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_logs_job_id ON upload_logs(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_logs_created_at ON upload_logs(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transformation_scripts_name ON transformation_scripts(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_lookup_code ON series_lookup(series_code)")
        
        conn.close()
    except Exception as e:
        raise Exception(f"Failed to initialize symbols database: {e}")

# Initialize database on module load
try:
    init_symbols_database()
except Exception as e:
    logger.warning(f"Could not initialize symbols database on module load: {e}", exc_info=True)
    # Will be created on first use

def reload_series_lookup(force: bool = False):
    """Reload series lookup data from CSV file
    
    Args:
        force: If True, force reload even if CSV hasn't changed
    """
    conn = None
    try:
        # Use get_db_connection() for consistent configuration
        conn = get_db_connection()
        db_path = get_symbols_db_path()
        
        csv_path = os.path.join(
            os.path.dirname(db_path),
            "Series.csv"
        )
        
        if not os.path.exists(csv_path):
            logger.warning(f"Series CSV file not found at: {csv_path}")
            return {"success": False, "message": f"CSV file not found at {csv_path}"}
        
        # Get CSV file modification time
        csv_mtime = os.path.getmtime(csv_path)
        csv_mtime_dt = datetime.fromtimestamp(csv_mtime, tz=timezone.utc)
        
        row_count = conn.execute("SELECT COUNT(*) FROM series_lookup").fetchone()[0]
        
        # Check if reload is needed
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
            return {"success": True, "message": "Series lookup data is already up to date", "reloaded": False}
        
        # Clear existing data
        if row_count > 0:
            conn.execute("DELETE FROM series_lookup")
        
        logger.info(f"Loading series lookup data from {csv_path}")
        
        # Load CSV data
        import csv
        import re
        loaded_count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                series_code = row.get('Series Code', '').strip()
                description = row.get('Description', '').strip()
                if series_code and description:
                    # Handle range notation like "N0-N9/NA-NZ"
                    if '-' in series_code and ('/' in series_code or len(series_code) > 5):
                        # Expand ranges
                        parts = series_code.split('/')
                        for part in parts:
                            part = part.strip()
                            if '-' in part:
                                match = re.match(r'^([A-Z]+)([0-9A-Z])-([A-Z]+)([0-9A-Z])$', part)
                                if match:
                                    prefix1 = match.group(1)
                                    start_suffix = match.group(2)
                                    prefix2 = match.group(3)
                                    end_suffix = match.group(4)
                                    
                                    if prefix1 == prefix2:
                                        prefix = prefix1
                                        if start_suffix.isdigit() and end_suffix.isdigit():
                                            # Numeric range: N0-N9
                                            for i in range(int(start_suffix), int(end_suffix) + 1):
                                                code = f"{prefix}{i}"
                                                conn.execute(
                                                    "INSERT OR REPLACE INTO series_lookup (series_code, description) VALUES (?, ?)",
                                                    [code, description]
                                                )
                                                loaded_count += 1
                                        elif start_suffix.isalpha() and end_suffix.isalpha():
                                            # Alphabetic range: NA-NZ
                                            for i in range(ord(start_suffix.upper()), ord(end_suffix.upper()) + 1):
                                                code = f"{prefix}{chr(i)}"
                                                conn.execute(
                                                    "INSERT OR REPLACE INTO series_lookup (series_code, description) VALUES (?, ?)",
                                                    [code, description]
                                                )
                                                loaded_count += 1
                        # Store original range pattern
                        conn.execute(
                            "INSERT OR REPLACE INTO series_lookup (series_code, description) VALUES (?, ?)",
                            [series_code, description]
                        )
                        loaded_count += 1
                    else:
                        # Simple code
                        conn.execute(
                            "INSERT OR REPLACE INTO series_lookup (series_code, description) VALUES (?, ?)",
                            [series_code, description]
                        )
                        loaded_count += 1
        
        # Update metadata
        conn.execute("""
            INSERT OR REPLACE INTO series_lookup_metadata (id, csv_last_modified, last_loaded_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
        """, [csv_mtime_dt])
        
        logger.info(f"Series lookup data reloaded successfully ({loaded_count} entries)")
        return {
            "success": True,
            "message": f"Successfully loaded {loaded_count} series entries",
            "reloaded": True,
            "entries_count": loaded_count
        }
    except Exception as e:
        logger.error(f"Error reloading series lookup data: {e}", exc_info=True)
        return {"success": False, "message": f"Error reloading data: {str(e)}"}
    finally:
        if conn:
            conn.close()

def get_db_connection():
    """Get a DuckDB connection to the symbols database with consistent configuration"""
    try:
        db_path = get_symbols_db_path()
        if not os.path.exists(db_path):
            logger.info(f"Symbols database not found at {db_path}, initializing...")
            init_symbols_database()
        # Use consistent configuration - no read_only parameter (defaults to False)
        # All connections must use the same config to avoid conflicts
        # Set allow_unsigned_extensions to true to match potential other connections (like duckdb-engine)
        conn = duckdb.connect(db_path, config={'allow_unsigned_extensions': True})
        # Set consistent PRAGMA settings for all connections
        conn.execute("PRAGMA enable_progress_bar=false")
        return conn
    except Exception as e:
        logger.error(f"Failed to get database connection: {str(e)}", exc_info=True)
        raise

# In-memory cache for preview data (simple implementation)
_preview_cache = {}

# In-memory cache for upload status
_upload_status_cache = {}

def _save_upload_log(conn, job_id: str, filename: str, started_at: datetime, ended_at: datetime,
                     status: str, total_rows: int, inserted: int, updated: int, failed: int,
                     errors: List[str], triggered_by: str = "system", upload_type: str = "MANUAL"):
    """Save upload log to database"""
    close_conn = False
    try:
        if conn is None:
            conn = get_db_connection()
            close_conn = True
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM upload_logs LIMIT 1")
        except Exception:
            init_symbols_database()
            if close_conn:
                conn.close()
                conn = get_db_connection()
        
        duration = int((ended_at - started_at).total_seconds())
        error_summary = "; ".join(errors[:5]) if errors else None
        progress_pct = 100 if status in ["SUCCESS", "PARTIAL", "FAILED"] else 0
        
        # Check if log already exists
        try:
            existing = conn.execute("SELECT id FROM upload_logs WHERE job_id = ?", [job_id]).fetchone()
        except Exception:
            existing = None
        
        if existing:
            conn.execute("""
                UPDATE upload_logs SET
                    file_name = ?, upload_type = ?, triggered_by = ?, started_at = ?, ended_at = ?,
                    duration_seconds = ?, total_rows = ?, inserted_rows = ?, updated_rows = ?, failed_rows = ?,
                    status = ?, progress_percentage = ?, error_summary = ?
                WHERE job_id = ?
            """, (
                filename, upload_type, triggered_by, started_at, ended_at,
                duration, total_rows, inserted, updated, failed,
                status, progress_pct, error_summary, job_id
            ))
        else:
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM upload_logs").fetchone()
            next_log_id = (max_id_result[0] if max_id_result else 0) + 1
            
            conn.execute("""
                INSERT INTO upload_logs (
                    id, job_id, file_name, upload_type, triggered_by, started_at, ended_at,
                    duration_seconds, total_rows, inserted_rows, updated_rows, failed_rows,
                    status, progress_percentage, error_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                next_log_id, job_id, filename, upload_type, triggered_by, started_at, ended_at,
                duration, total_rows, inserted, updated, failed, status,
                progress_pct, error_summary, started_at
            ))
        
        conn.commit()
        logger.info(f"[UPLOAD] Saved upload log: {job_id} - {status}")
    except Exception as e:
        logger.error(f"[UPLOAD] Failed to save upload log: {e}")
    finally:
        if close_conn and conn:
            try:
                conn.close()
            except Exception:
                pass

def apply_transformation_script(df: pd.DataFrame, script_content: str) -> pd.DataFrame:
    """Apply transformation script to dataframe safely"""
    try:
        # Create a safe execution environment with a copy of the dataframe
        safe_globals = {
            'pd': pd,
            'df': df.copy(),
            '__builtins__': __builtins__
        }
        
        # Store original df reference to check if it was modified
        original_df_id = id(safe_globals['df'])
        
        # Execute the script
        exec(script_content, safe_globals)
        
        # Check if script created final_df, otherwise use modified df
        result_df = None
        
        # First check for final_df (preferred)
        if 'final_df' in safe_globals:
            result_df = safe_globals['final_df']
        # Then check if df was modified
        elif 'df' in safe_globals:
            modified_df = safe_globals['df']
            # Check if df was actually modified by comparing columns or shape
            if not modified_df.equals(df) or list(modified_df.columns) != list(df.columns) or modified_df.shape != df.shape:
                result_df = modified_df
            else:
                result_df = None
        
        # If no result, return original
        if result_df is None:
            raise ValueError("Transformation script must create 'final_df' or modify 'df'. Script execution completed but no transformed dataframe was found.")
        
        # Ensure it's a DataFrame
        if not isinstance(result_df, pd.DataFrame):
            raise ValueError(f"Transformation script must result in a pandas DataFrame, got {type(result_df)}")
        
        print(f"[UPLOAD] Script transformation applied successfully")
        return result_df
    except Exception as e:
        print(f"[UPLOAD] Script transformation failed: {str(e)}")
        raise ValueError(f"Error executing transformation script: {str(e)}")

@router.post("/upload/manual", response_model=PreviewResponse)
async def upload_manual(
    file: UploadFile = File(...),
    script_id: Optional[str] = Form(None),  # Accept as string to handle Form data properly
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    request: Request = None
):
    """Upload symbols from CSV/Excel file - returns preview"""
    conn = None
    try:
        # Read file
        contents = await file.read()
        
        # Parse file based on extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext == '.csv':
            df = pd.read_csv(io.BytesIO(contents), low_memory=False)
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use CSV or Excel files.")
        
        # Apply transformation script if provided
        # Handle script_id as string (Form data always comes as string)
        script_id_int = None
        if script_id is not None and str(script_id).strip():
            try:
                script_id_str = str(script_id).strip()
                if script_id_str:
                    script_id_int = int(script_id_str)
            except (ValueError, TypeError):
                script_id_int = None
        
        script_loaded = False
        transformed = False
        script_name = None
        original_rows = len(df)
        original_cols = len(df.columns)
        
        if script_id_int:
            try:
                conn = get_db_connection()
                script = conn.execute("""
                    SELECT name, content FROM transformation_scripts WHERE id = ?
                """, [script_id_int]).fetchone()
                
                if script:
                    script_name = script[0]
                    script_content = script[1]
                    script_loaded = True
                    
                    try:
                        df = apply_transformation_script(df, script_content)
                        transformed = True
                    except Exception as transform_error:
                        raise
                else:
                    raise HTTPException(status_code=404, detail=f"Transformation script {script_id_int} not found")
            except HTTPException:
                raise
            except Exception as script_error:
                raise HTTPException(status_code=500, detail=f"Error applying transformation script: {str(script_error)}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
        
        # Store script and transformation info for logging during upload
        new_rows = len(df)
        new_cols = len(df.columns)
        
        # Generate preview ID
        preview_id = f"preview_{uuid.uuid4().hex[:16]}"
        
        # Cache the dataframe for confirm step
        # Store user name (prefer name, fallback to username, then email)
        user_name = "system"
        if current_user:
            user_name = current_user.name or current_user.username or current_user.email or f"User-{current_user.id}"
        
        _preview_cache[preview_id] = {
            'df': df,
            'filename': file.filename,
            'script_id': script_id_int if script_id_int else script_id,
            'script_name': script_name,
            'script_loaded': script_loaded,
            'transformed': transformed,
            'original_rows': original_rows,
            'original_cols': original_cols,
            'new_rows': new_rows,
            'new_cols': new_cols,
            'user_id': current_user.id if current_user else None,
            'user_name': user_name,
            'upload_type': 'MANUAL'
        }
        
        # Return preview data (only top 10 rows for preview)
        return PreviewResponse(
            headers=df.columns.tolist(),
            rows=df.head(10).to_dict('records'),
            total_rows=len(df),
            preview_id=preview_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.post("/upload/auto", response_model=PreviewResponse)
async def upload_auto(
    request_data: AutoUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Download file from URL/API and process same as manual upload"""
    conn = None
    temp_file_path = None
    try:
        # Prepare headers for download
        headers = request_data.headers or {}
        
        # Add authentication if provided
        if request_data.auth_type and request_data.auth_value:
            if request_data.auth_type.lower() == 'bearer':
                headers['Authorization'] = f"Bearer {request_data.auth_value}"
            elif request_data.auth_type.lower() == 'basic':
                headers['Authorization'] = f"Basic {request_data.auth_value}"
            elif request_data.auth_type.lower() == 'api_key':
                headers['X-API-Key'] = request_data.auth_value
        
        # If connection_id is provided, fetch connection details
        # For now, we'll use the provided headers/auth directly
        # TODO: Implement connection lookup if needed
        
        # Download file to temporary location
        logger.info(f"Downloading file from URL: {request_data.url}")
        response = requests.get(request_data.url, headers=headers, timeout=300, stream=True)
        response.raise_for_status()
        
        # Create temporary file
        temp_dir = os.path.join(os.path.abspath(settings.DATA_DIR), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Determine file extension from URL or content type
        parsed_url = urlparse(request_data.url)
        url_path = parsed_url.path
        file_ext = os.path.splitext(url_path)[1].lower()
        
        # If no extension in URL, try content type
        if not file_ext:
            content_type = response.headers.get('Content-Type', '')
            if 'csv' in content_type.lower():
                file_ext = '.csv'
            elif 'excel' in content_type.lower() or 'spreadsheet' in content_type.lower():
                file_ext = '.xlsx'
            else:
                file_ext = '.csv'  # Default to CSV
        
        # Create temp file with proper extension
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            delete=False,
            suffix=file_ext,
            dir=temp_dir
        )
        temp_file_path = temp_file.name
        
        # Write downloaded content to temp file
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        # Determine file type
        file_type = request_data.file_type or 'AUTO'
        if file_type == 'AUTO':
            if file_ext == '.csv':
                file_type = 'CSV'
            elif file_ext in ['.xlsx', '.xls']:
                file_type = 'XLSX'
            else:
                file_type = 'CSV'  # Default
        
        # Read file based on type
        with open(temp_file_path, 'rb') as f:
            contents = f.read()
        
        if file_type == 'CSV':
            df = pd.read_csv(io.BytesIO(contents), low_memory=False)
        elif file_type == 'XLSX':
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
        
        # Get filename from URL
        filename = os.path.basename(url_path) or f"download{file_ext}"
        
        # Apply transformation script if provided
        script_id_int = request_data.script_id  # Already int from schema
        script_loaded = False
        transformed = False
        script_name = None
        original_rows = len(df)
        original_cols = len(df.columns)
        
        if script_id_int:
            try:
                conn = get_db_connection()
                script = conn.execute("""
                    SELECT name, content FROM transformation_scripts WHERE id = ?
                """, [script_id_int]).fetchone()
                
                if script:
                    script_name = script[0]
                    script_content = script[1]
                    script_loaded = True
                    
                    try:
                        df = apply_transformation_script(df, script_content)
                        transformed = True
                    except Exception as transform_error:
                        raise
                else:
                    raise HTTPException(status_code=404, detail=f"Transformation script {script_id_int} not found")
            except HTTPException:
                raise
            except Exception as script_error:
                raise HTTPException(status_code=500, detail=f"Error applying transformation script: {str(script_error)}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
        
        # Store script and transformation info for logging
        new_rows = len(df)
        new_cols = len(df.columns)
        
        # Generate preview ID
        preview_id = f"preview_{uuid.uuid4().hex[:16]}"
        
        # Store user name
        user_name = "system"
        if current_user:
            user_name = current_user.name or current_user.username or current_user.email or f"User-{current_user.id}"
        
        _preview_cache[preview_id] = {
            'df': df,
            'filename': filename,
            'script_id': script_id_int,
            'script_name': script_name,
            'script_loaded': script_loaded,
            'transformed': transformed,
            'original_rows': original_rows,
            'original_cols': original_cols,
            'new_rows': new_rows,
            'new_cols': new_cols,
            'user_id': current_user.id if current_user else None,
            'user_name': user_name,
            'upload_type': 'AUTO'
        }
        
        # Return preview data (only top 10 rows for preview)
        return PreviewResponse(
            headers=df.columns.tolist(),
            rows=df.head(10).to_dict('records'),
            total_rows=len(df),
            preview_id=preview_id
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file from URL: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download file from URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing auto upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file_path}: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def process_upload_async(preview_id: str, job_id: str):
    """Process upload in background and update status cache"""
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    started_at = datetime.now(timezone.utc)
    start_time = time.time()
    filename = "unknown"
    triggered_by = "system"
    script_loaded = False
    transformed = False
    
    try:
        # Initialize status
        _upload_status_cache[job_id] = {
            "status": "PROCESSING",
            "processed": 0,
            "total": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "errors": [],
            "percentage": 0,
            "triggered_by": "system"  # Will be updated when we get cached data
        }
        
        
        # Get cached data
        if preview_id not in _preview_cache:
            _upload_status_cache[job_id]["status"] = "FAILED"
            _upload_status_cache[job_id]["errors"] = ["Preview expired"]
            # Save failed log
            _save_upload_log(conn=None, job_id=job_id, filename="unknown", started_at=started_at, 
                           ended_at=datetime.now(timezone.utc), status="FAILED", total_rows=0,
                           inserted=0, updated=0, failed=0, errors=["Preview expired"], triggered_by="system", upload_type="MANUAL")
            return
        
        cached_data = _preview_cache[preview_id]
        df = cached_data['df']
        filename = cached_data.get('filename', 'unknown')
        script_id = cached_data.get('script_id')
        script_name = cached_data.get('script_name')
        script_loaded = cached_data.get('script_loaded', False)
        transformed = cached_data.get('transformed', False)
        original_rows = cached_data.get('original_rows', len(df))
        original_cols = cached_data.get('original_cols', len(df.columns))
        new_rows = cached_data.get('new_rows', len(df))
        new_cols = cached_data.get('new_cols', len(df.columns))
        upload_type = cached_data.get('upload_type', 'MANUAL')
        scheduler_id = cached_data.get('scheduler_id')
        manually_triggered = cached_data.get('manually_triggered', False)
        
        # Use user_name if available, otherwise fallback to user_id or 'system'
        # If scheduler_id exists, format triggered_by based on whether it was manually triggered
        if scheduler_id:
            if manually_triggered:
                # Manually triggered - show the user who clicked the play button
                user_name = cached_data.get('user_name', 'Unknown User')
                triggered_by = user_name
            else:
                # Auto-triggered by scheduler - show scheduler name with timing info
                scheduler_name = cached_data.get('user_name', f"Scheduler-{scheduler_id}")
                # Remove "Scheduler-" prefix if it already exists to avoid duplication
                if scheduler_name.startswith("Scheduler-"):
                    scheduler_name = scheduler_name[len("Scheduler-"):]
                
                # Get timing information
                mode = cached_data.get('scheduler_mode')
                interval_value = cached_data.get('scheduler_interval_value')
                interval_unit = cached_data.get('scheduler_interval_unit')
                cron_expression = cached_data.get('scheduler_cron_expression')
                
                # Format timing info
                timing_info = ""
                if mode == 'INTERVAL' and interval_value and interval_unit:
                    # Format interval unit nicely
                    unit_display = interval_unit.lower()
                    if unit_display.endswith('s'):
                        unit_display = unit_display[:-1]  # Remove plural 's'
                    timing_info = f" ({interval_value} {unit_display})"
                elif mode == 'CRON' and cron_expression:
                    timing_info = f" (cron: {cron_expression})"
                elif mode == 'RUN_ONCE':
                    timing_info = " (run once)"
                
                triggered_by = f"Scheduler-{scheduler_name}{timing_info}"
        else:
            triggered_by = cached_data.get('user_name') or cached_data.get('user_id') or 'system'
        
        # Print script loaded status
        if script_loaded and script_name:
            print(f"[UPLOAD] Script loaded: {script_name} (ID: {script_id})")
        else:
            print(f"[UPLOAD] Script loaded: None (no transformation script)")
        
        # Print data manipulated status
        if transformed:
            print(f"[UPLOAD] Data manipulated: {original_rows} rows, {original_cols} cols → {new_rows} rows, {new_cols} cols")
        else:
            print(f"[UPLOAD] Data manipulated: {original_rows} rows, {original_cols} cols → {original_rows} rows, {original_cols} cols (no changes)")
        
        # Update triggered_by in status cache
        _upload_status_cache[job_id]["triggered_by"] = triggered_by
        total_rows = len(df)
        
        _upload_status_cache[job_id]["total"] = total_rows
        
        # Print uploading status
        print(f"[UPLOAD] Uploading: {total_rows} total rows")
        
        conn = None
        try:
            conn = get_db_connection()
            
            inserted = 0
            updated = 0
            failed = 0
            errors = []
            
            # Process in batches for better performance
            batch_size = 100000  # Larger batches for better performance
            now = datetime.now(timezone.utc)
            
            # Performance timing
            perf_timings = {}
            perf_start = time.time()
            
            # Use UPSERT (INSERT OR REPLACE) for better performance with DuckDB
            # First, get max ID
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM symbols").fetchone()
            next_id = (max_id_result[0] if max_id_result else 0) + 1
            
            # Process in batches to avoid memory issues
            total_rows = len(df)
            processed = 0
            
            # Get all existing symbols once (more efficient than per-row checks)
            existing_query = "SELECT exchange, trading_symbol, id FROM symbols"
            existing_symbols = {}
            try:
                existing_rows = conn.execute(existing_query).fetchall()
                # Normalize keys to match the normalized lookup (uppercase, stripped)
                for row in existing_rows:
                    exchange = str(row[0]).strip().upper() if row[0] else ''
                    trading_symbol = str(row[1]).strip().upper() if row[1] else ''
                    if exchange and trading_symbol:
                        key = f"{exchange}|{trading_symbol}"
                        existing_symbols[key] = row[2]
            except Exception:
                existing_symbols = {}
            
            # Normalize column names
            if 'symbol' in df.columns and 'trading_symbol' not in df.columns:
                df['trading_symbol'] = df['symbol']
            
            # Vectorized string operations (much faster)
            df['exchange'] = df['exchange'].fillna('').astype(str).str.strip().str.upper()
            df['trading_symbol'] = df['trading_symbol'].fillna('').astype(str).str.strip().str.upper()
            
            # Filter invalid rows upfront
            valid_mask = (df['exchange'] != '') & (df['trading_symbol'] != '')
            invalid_count = (~valid_mask).sum()
            if invalid_count > 0:
                failed += invalid_count
                if len(errors) < 10:
                    errors.append(f"{invalid_count} rows missing exchange or trading_symbol")
            df = df[valid_mask].copy()
            
            # Remove duplicates within the dataframe (keep first occurrence)
            df = df.drop_duplicates(subset=['exchange', 'trading_symbol'], keep='first').copy()
            
            # Create lookup keys vectorized
            df['lookup_key'] = df['exchange'] + '|' + df['trading_symbol']
            df['is_existing'] = df['lookup_key'].isin(existing_symbols.keys())
            df['existing_id'] = df['lookup_key'].map(existing_symbols)
            
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end].copy()
                batch_num = batch_start // batch_size + 1
                total_batches = (len(df) + batch_size - 1) // batch_size
                
                # Split into inserts and updates using vectorized operations
                insert_df = batch_df[~batch_df['is_existing']].copy()
                update_df = batch_df[batch_df['is_existing']].copy()
                
                # Process inserts using bulk VALUES clause (ultra-fast)
                if len(insert_df) > 0:
                    
                    # Prepare insert data vectorized
                    insert_df['id'] = range(next_id, next_id + len(insert_df))
                    insert_df['status'] = 'ACTIVE'
                    insert_df['source'] = 'MANUAL'
                    insert_df['created_at'] = now
                    insert_df['updated_at'] = now
                    insert_df['last_updated_at'] = now
                    
                    # Handle NaN values efficiently
                    for col in ['exchange_token', 'name', 'instrument_type', 'segment', 'series', 'isin']:
                        if col in insert_df.columns:
                            insert_df[col] = insert_df[col].fillna('').astype(str)
                    
                    # Convert numeric columns
                    if 'strike_price' in insert_df.columns:
                        insert_df['strike_price'] = pd.to_numeric(insert_df['strike_price'], errors='coerce')
                    if 'lot_size' in insert_df.columns:
                        insert_df['lot_size'] = pd.to_numeric(insert_df['lot_size'], errors='coerce').astype('Int64')
                    
                    # Convert expiry_date to date format if present
                    if 'expiry_date' in insert_df.columns:
                        insert_df['expiry_date'] = pd.to_datetime(insert_df['expiry_date'], errors='coerce').dt.date
                    
                    # Use bulk insert with VALUES clause - process in large chunks
                    bulk_insert_size = 50000  # Large bulk inserts
                    for chunk_start in range(0, len(insert_df), bulk_insert_size):
                        chunk_end = min(chunk_start + bulk_insert_size, len(insert_df))
                        chunk_df = insert_df.iloc[chunk_start:chunk_end]
                        
                        # Build VALUES clause for bulk insert
                        # IMPORTANT: Column order must match table schema:
                        # id, exchange, trading_symbol, exchange_token, name, instrument_type,
                        # segment, series, isin, expiry_date, strike_price, lot_size,
                        # status, source, created_at, updated_at, last_updated_at
                        values_list = []
                        for _, row in chunk_df.iterrows():
                            values_list.append([
                                int(row['id']),
                                str(row['exchange']),
                                str(row['trading_symbol']),
                                str(row.get('exchange_token', '')) if pd.notna(row.get('exchange_token')) else None,
                                str(row.get('name', '')) if pd.notna(row.get('name')) else None,
                                str(row.get('instrument_type', '')) if pd.notna(row.get('instrument_type')) else None,
                                str(row.get('segment', '')) if pd.notna(row.get('segment')) else None,
                                str(row.get('series', '')) if pd.notna(row.get('series')) else None,
                                str(row.get('isin', '')) if pd.notna(row.get('isin')) else None,
                                row.get('expiry_date') if pd.notna(row.get('expiry_date')) and row.get('expiry_date') != '' else None,
                                float(row.get('strike_price')) if pd.notna(row.get('strike_price')) else None,
                                int(row.get('lot_size')) if pd.notna(row.get('lot_size')) else None,
                                'ACTIVE',  # status
                                'MANUAL',  # source
                                now,  # created_at
                                now,  # updated_at
                                now   # last_updated_at
                            ])
                        
                        # Use DuckDB's register method for fastest bulk insert
                        # Column order MUST match table schema exactly
                        temp_df = pd.DataFrame(values_list, columns=[
                            'id', 'exchange', 'trading_symbol', 'exchange_token', 'name', 'instrument_type',
                            'segment', 'series', 'isin', 'expiry_date', 'strike_price', 'lot_size',
                            'status', 'source', 'created_at', 'updated_at', 'last_updated_at'
                        ])
                        conn.register('temp_bulk_insert', temp_df)
                        # Try INSERT, if duplicate key error, update existing rows instead
                        try:
                            conn.execute("INSERT INTO symbols SELECT * FROM temp_bulk_insert")
                            conn.commit()
                        except Exception as insert_error:
                            error_msg = str(insert_error).lower()
                            # Check if it's a UNIQUE constraint violation
                            if "unique" in error_msg or "duplicate" in error_msg or "constraint" in error_msg:
                                # Rollback the failed insert
                                conn.rollback()
                                # Update existing rows instead
                                conn.execute("""
                                    UPDATE symbols 
                                    SET exchange_token = temp_bulk_insert.exchange_token,
                                        name = temp_bulk_insert.name,
                                        instrument_type = temp_bulk_insert.instrument_type,
                                        segment = temp_bulk_insert.segment,
                                        series = temp_bulk_insert.series,
                                        isin = temp_bulk_insert.isin,
                                        expiry_date = temp_bulk_insert.expiry_date,
                                        strike_price = temp_bulk_insert.strike_price,
                                        lot_size = temp_bulk_insert.lot_size,
                                        status = temp_bulk_insert.status,
                                        source = temp_bulk_insert.source,
                                        updated_at = temp_bulk_insert.updated_at,
                                        last_updated_at = temp_bulk_insert.last_updated_at
                                    FROM temp_bulk_insert
                                    WHERE symbols.exchange = temp_bulk_insert.exchange 
                                      AND symbols.trading_symbol = temp_bulk_insert.trading_symbol
                                """)
                                conn.commit()
                                # Count these as updates instead of inserts
                                chunk_inserted = len(chunk_df)
                                inserted -= chunk_inserted
                                updated += chunk_inserted
                            else:
                                # Re-raise if it's a different error
                                raise
                        finally:
                            conn.unregister('temp_bulk_insert')
                    
                    # Update existing_symbols and next_id
                    lookup_keys = insert_df['lookup_key'].values
                    ids = insert_df['id'].values
                    for i in range(len(lookup_keys)):
                        existing_symbols[lookup_keys[i]] = ids[i]
                    next_id += len(insert_df)
                    inserted += len(insert_df)
                
                # Process updates using bulk operations
                if len(update_df) > 0:
                    
                    # Prepare update data vectorized
                    update_df['updated_at'] = now
                    update_df['last_updated_at'] = now
                    
                    # Handle NaN values efficiently
                    for col in ['exchange_token', 'name', 'instrument_type', 'segment', 'series', 'isin']:
                        if col in update_df.columns:
                            update_df[col] = update_df[col].fillna('').astype(str)
                    
                    # Convert numeric columns
                    if 'strike_price' in update_df.columns:
                        update_df['strike_price'] = pd.to_numeric(update_df['strike_price'], errors='coerce')
                    if 'lot_size' in update_df.columns:
                        update_df['lot_size'] = pd.to_numeric(update_df['lot_size'], errors='coerce').astype('Int64')
                    
                    # Use bulk update with DuckDB register method - process in large chunks
                    bulk_update_size = 50000
                    for chunk_start in range(0, len(update_df), bulk_update_size):
                        chunk_end = min(chunk_start + bulk_update_size, len(update_df))
                        chunk_df = update_df.iloc[chunk_start:chunk_end].copy()
                        
                        # Prepare update dataframe with only needed columns
                        update_df_clean = chunk_df[[
                            'existing_id', 'exchange_token', 'name', 'instrument_type',
                            'segment', 'series', 'isin', 'expiry_date',
                            'strike_price', 'lot_size', 'updated_at', 'last_updated_at'
                        ]].copy()
                        update_df_clean.columns = [
                            'id', 'exchange_token', 'name', 'instrument_type',
                            'segment', 'series', 'isin', 'expiry_date',
                            'strike_price', 'lot_size', 'updated_at', 'last_updated_at'
                        ]
                        
                        # Use DuckDB's register for bulk update
                        conn.register('temp_bulk_update', update_df_clean)
                        # Use UPDATE with JOIN for better performance
                        conn.execute("""
                            UPDATE symbols 
                            SET exchange_token = temp_bulk_update.exchange_token,
                                name = temp_bulk_update.name,
                                instrument_type = temp_bulk_update.instrument_type,
                                segment = temp_bulk_update.segment,
                                series = temp_bulk_update.series,
                                isin = temp_bulk_update.isin,
                                expiry_date = temp_bulk_update.expiry_date,
                                strike_price = temp_bulk_update.strike_price,
                                lot_size = temp_bulk_update.lot_size,
                                updated_at = temp_bulk_update.updated_at,
                                last_updated_at = temp_bulk_update.last_updated_at
                            FROM temp_bulk_update
                            WHERE symbols.id = temp_bulk_update.id
                        """)
                        conn.unregister('temp_bulk_update')
                        conn.commit()
                    
                    updated += len(update_df)
                
                processed += len(batch_df)
                percentage = (processed * 100) // total_rows if total_rows > 0 else 0
                
                # Update status cache
                if job_id in _upload_status_cache:
                    _upload_status_cache[job_id]["processed"] = processed
                    _upload_status_cache[job_id]["inserted"] = inserted
                    _upload_status_cache[job_id]["updated"] = updated
                    _upload_status_cache[job_id]["failed"] = failed
                    _upload_status_cache[job_id]["percentage"] = percentage
            
            # Clean up cache
            del _preview_cache[preview_id]
            
            # Update final status
            final_status = "SUCCESS" if failed == 0 else "PARTIAL"
            
            if job_id in _upload_status_cache:
                _upload_status_cache[job_id]["status"] = final_status
                _upload_status_cache[job_id]["errors"] = errors
            
            # Performance summary
            total_time = time.time() - start_time
            uploaded_rows = inserted + updated
            
            # Print finished status
            print(f"[UPLOAD] Finished: {uploaded_rows} rows uploaded in {total_time:.1f}s")
            
            # Store values for finally block
            upload_success = True
            upload_final_status = final_status
            upload_total = total_rows
            upload_inserted = inserted
            upload_updated = updated
            upload_failed = failed
            upload_errors = errors
            
        except Exception as e:
            total_time = time.time() - start_time
            uploaded_rows = inserted if 'inserted' in locals() else 0
            uploaded_rows += updated if 'updated' in locals() else 0
            print(f"[UPLOAD] Finished: Failed after {total_time:.1f}s - Error: {str(e)}")
            
            if job_id in _upload_status_cache:
                _upload_status_cache[job_id]["status"] = "FAILED"
                _upload_status_cache[job_id]["errors"] = [str(e)]
            
            # Don't save log here - will be saved in finally block
            try:
                if conn:
                    conn.rollback()
            except:
                pass  # Ignore rollback errors if no transaction is active
        finally:
            # Save upload log before closing connection
            try:
                ended_at = datetime.now(timezone.utc)
                upload_success_exists = 'upload_success' in locals()
                
                if upload_success_exists and upload_success:
                    _save_upload_log(conn=None, job_id=job_id, filename=filename, started_at=started_at,
                                   ended_at=ended_at, status=upload_final_status, total_rows=upload_total,
                                   inserted=upload_inserted, updated=upload_updated, failed=upload_failed,
                                   errors=upload_errors, triggered_by=str(triggered_by), upload_type=upload_type if 'upload_type' in locals() else 'MANUAL')
                else:
                    status_to_save = "FAILED"
                    total_to_save = total_rows if 'total_rows' in locals() else 0
                    inserted_to_save = inserted if 'inserted' in locals() else 0
                    updated_to_save = updated if 'updated' in locals() else 0
                    failed_to_save = failed if 'failed' in locals() else 0
                    error_msg = str(e) if 'e' in locals() else "Unknown error"
                    errors_to_save = [error_msg]
                    
                    _save_upload_log(conn=None, job_id=job_id, filename=filename, started_at=started_at,
                                   ended_at=ended_at, status=status_to_save, total_rows=total_to_save,
                                   inserted=inserted_to_save, updated=updated_to_save, failed=failed_to_save,
                                   errors=errors_to_save, triggered_by=str(triggered_by), upload_type=upload_type)
            except Exception:
                pass  # Silent fail for log saving
            
            # Ensure connection is ALWAYS closed
            if conn:
                try:
                    conn.close()
                except Exception:
                    conn = None
    except Exception as e:
        total_time = time.time() - start_time if 'start_time' in locals() else 0
        print(f"[UPLOAD] Finished: Failed after {total_time:.1f}s - Error: {str(e)}")
        
        if job_id in _upload_status_cache:
            _upload_status_cache[job_id]["status"] = "FAILED"
            _upload_status_cache[job_id]["errors"] = [str(e)]
        
        # Save failed log
        try:
            ended_at = datetime.now(timezone.utc)
            _save_upload_log(conn=None, job_id=job_id, filename=filename, started_at=started_at,
                           ended_at=ended_at, status="FAILED", total_rows=0,
                           inserted=0, updated=0, failed=0, errors=[str(e)], triggered_by=str(triggered_by), upload_type="MANUAL")
        except Exception:
            pass

@router.post("/upload/confirm")
async def confirm_upload(
    data: dict = Body(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Confirm and save symbols to database - returns immediately, processes in background"""
    preview_id = data.get("preview_id")
    if not preview_id:
        raise HTTPException(status_code=400, detail="preview_id is required")
    
    if preview_id not in _preview_cache:
        raise HTTPException(status_code=404, detail="Preview expired. Please upload the file again.")
    
    # Generate job ID
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    
    # Start background processing
    import threading
    thread = threading.Thread(target=process_upload_async, args=(preview_id, job_id), name=f"Upload-{job_id}")
    thread.daemon = True
    thread.start()
    
    return {
        "job_id": job_id,
        "status": "PROCESSING",
        "message": "Upload started. Processing in background..."
    }

@router.get("/upload/status/{job_id}")
async def get_upload_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get upload status by job ID - Returns status for a single job (no pagination needed for single job lookup)"""
    # Handle placeholder job_id (e.g., "0" or empty)
    if not job_id or job_id == "0" or job_id.strip() == "":
        return {
            "job_id": job_id or "0",
            "status": "PENDING",
            "processed": 0,
            "total": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "errors": [],
            "percentage": 0,
            "progress_percentage": 0,
            "uploaded_rows": 0,
            "triggered_by": "system"
        }
    
    # First check in-memory cache
    if job_id in _upload_status_cache:
        status = _upload_status_cache[job_id]
        return {
            "job_id": job_id,
            "status": status["status"],
            "processed": status["processed"],
            "total": status["total"],
            "inserted": status["inserted"],
            "updated": status["updated"],
            "failed": status["failed"],
            "errors": status["errors"],
            "percentage": status["percentage"],
            "progress_percentage": status["percentage"],
            "uploaded_rows": status["inserted"] + status["updated"],
            "triggered_by": status.get("triggered_by", "system")
        }
    
    # If not in cache, check database
    conn = None
    try:
        conn = get_db_connection()
        # Get full log with all fields
        log = conn.execute(
            "SELECT job_id, file_name, upload_type, triggered_by, started_at, ended_at, "
            "duration_seconds, total_rows, inserted_rows, updated_rows, failed_rows, "
            "status, progress_percentage, error_summary, created_at "
            "FROM upload_logs WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
            [job_id]
        ).fetchone()
        
        if not log:
            # Return a "not found" status instead of 404 error
            return {
                "job_id": job_id,
                "status": "NOT_FOUND",
                "processed": 0,
                "total": 0,
                "inserted": 0,
                "updated": 0,
                "failed": 0,
                "errors": ["Job not found"],
                "percentage": 0,
                "progress_percentage": 0,
                "uploaded_rows": 0,
                "triggered_by": "system"
            }
        
        # Error handling: Parse error_summary safely
        errors = []
        if log[13]:  # error_summary
            try:
                errors = log[13].split("; ") if log[13] and log[13].strip() else []
            except Exception as e:
                errors = [f"Error parsing error summary: {str(e)}"]
        
        # Convert to response format
        return {
            "job_id": log[0],
            "status": log[11] if log[11] else "UNKNOWN",
            "processed": log[7] if log[7] is not None else 0,  # total_rows
            "total": log[7] if log[7] is not None else 0,
            "inserted": log[8] if log[8] is not None else 0,
            "updated": log[9] if log[9] is not None else 0,
            "failed": log[10] if log[10] is not None else 0,
            "errors": errors,
            "percentage": log[12] if log[12] is not None else 0,
            "progress_percentage": log[12] if log[12] is not None else 0,
            "uploaded_rows": (log[8] if log[8] is not None else 0) + (log[9] if log[9] is not None else 0),
            "triggered_by": log[3] if log[3] else "system",
            "file_name": log[1] if log[1] else "unknown",
            "started_at": log[4].isoformat() if log[4] else None,
            "ended_at": log[5].isoformat() if log[5] else None,
            "duration_seconds": log[6] if log[6] is not None else None
        }
    except HTTPException:
        raise
    except Exception as e:
        # Error handler: Catch any unexpected errors and return a safe response
        logger.error(f"Error fetching upload status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch upload status: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.get("/upload/logs")
async def get_upload_logs(
    limit: int = 50,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get upload logs with enhanced pagination
    
    Args:
        limit: Number of logs per page (default: 50, max: 1000)
        page: Page number (default: 1, starts from 1)
    
    Returns:
        Response with logs and pagination metadata including:
        - logs: List of upload log entries
        - pagination: Object with page info, navigation flags, and indices
            - page: Current page number
            - page_size: Items per page
            - total: Total number of logs
            - total_pages: Total number of pages
            - has_next: Whether there's a next page
            - has_previous: Whether there's a previous page
            - next_page: Next page number (null if no next page)
            - previous_page: Previous page number (null if no previous page)
            - start_index: Starting index of current page (1-based)
            - end_index: Ending index of current page (1-based)
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM upload_logs LIMIT 1")
        except Exception:
            # Table doesn't exist, initialize it
            init_symbols_database()
            # Reconnect after initialization
            conn.close()
            conn = get_db_connection()
        
        # Get total count
        try:
            total = conn.execute("SELECT COUNT(*) FROM upload_logs").fetchone()[0]
        except Exception:
            total = 0
        
        # Calculate pagination with validation
        if page < 1:
            page = 1
        if limit < 1:
            limit = 50
        if limit > 1000:  # Maximum limit to prevent performance issues
            limit = 1000
        
        offset = (page - 1) * limit
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        
        # Ensure page doesn't exceed total_pages
        if page > total_pages and total_pages > 0:
            page = total_pages
            offset = (page - 1) * limit
        
        # Fetch logs
        try:
            logs = conn.execute("""
                SELECT job_id, file_name, upload_type, triggered_by, started_at, ended_at,
                       duration_seconds, total_rows, inserted_rows, updated_rows, failed_rows,
                       status, progress_percentage, error_summary, created_at
                FROM upload_logs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, [limit, offset]).fetchall()
        except Exception:
            logs = []
        
        # Convert to response format and deduplicate by job_id
        log_list = []
        seen_job_ids = set()  # Track seen job_ids to avoid duplicates
        
        for log in logs:
            # Ensure job_id and file_name are valid strings (required by frontend validation)
            job_id = str(log[0]).strip() if log[0] else ""
            file_name = str(log[1]).strip() if log[1] else "unknown"
            
            # Skip if job_id or file_name is empty (will fail frontend validation)
            if not job_id or not file_name:
                continue
            
            # Skip if we've already processed this job_id (deduplicate)
            if job_id in seen_job_ids:
                continue
            seen_job_ids.add(job_id)
            
            error_summary = log[13].split("; ") if log[13] and log[13].strip() else []
            log_entry = {
                "job_id": job_id,
                "file_name": file_name,
                "upload_type": str(log[2]).strip() if log[2] else "MANUAL",
                "triggered_by": str(log[3]).strip() if log[3] else "system",
                "started_at": log[4].isoformat() if log[4] else None,
                "ended_at": log[5].isoformat() if log[5] else None,
                "duration_seconds": int(log[6]) if log[6] is not None else None,
                "total_rows": int(log[7]) if log[7] is not None else 0,
                "inserted_rows": int(log[8]) if log[8] is not None else 0,
                "updated_rows": int(log[9]) if log[9] is not None else 0,
                "failed_rows": int(log[10]) if log[10] is not None else 0,
                "status": str(log[11]).strip().upper() if log[11] else "UNKNOWN",
                "progress_percentage": int(log[12]) if log[12] is not None else 0,
                "error_summary": error_summary
            }
            log_list.append(log_entry)
        
        # Enhanced pagination metadata
        has_next = page < total_pages
        has_previous = page > 1
        next_page = page + 1 if has_next else None
        previous_page = page - 1 if has_previous else None
        
        return {
            "logs": log_list,
            "pagination": {
                "page": page,
                "page_size": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_page": next_page,
                "previous_page": previous_page,
                "start_index": offset + 1 if total > 0 else 0,
                "end_index": min(offset + limit, total) if total > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Error fetching upload logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch upload logs: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.get("/", response_model=PaginatedSymbolResponse)
async def get_symbols(
    search: Optional[str] = None,
    exchange: Optional[str] = None,
    status: Optional[str] = None,
    expiry: Optional[str] = None,
    sort_by: Optional[str] = None,
    page_size: int = 25,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get symbols with pagination and filtering"""
    conn = None
    try:
        conn = get_db_connection()

        # Build WHERE clause
        where_conditions = []
        params = []
        
        if status and status.upper() in ["ACTIVE", "INACTIVE"]:
            where_conditions.append("status = ?")
            params.append(status.upper())
        
        if exchange:
            where_conditions.append("exchange = ?")
            params.append(exchange.upper())
        
        # Handle expiry filter
        if expiry:
            expiry_lower = expiry.lower()
            if expiry_lower == "today":
                # Symbols expiring today
                where_conditions.append("expiry_date = CURRENT_DATE")
            elif expiry_lower == "skipped":
                # Symbols with NULL or past expiry dates (skipped/expired)
                where_conditions.append("(expiry_date IS NULL OR expiry_date < CURRENT_DATE)")
        
        if search:
            search_term = f"%{search.upper()}%"
            # Comprehensive search across all relevant text fields
            # Search in: trading_symbol, exchange, name, exchange_token, isin, instrument_type, segment, series
            where_conditions.append(
                "(UPPER(COALESCE(trading_symbol, '')) LIKE ? OR "
                "UPPER(COALESCE(exchange, '')) LIKE ? OR "
                "UPPER(COALESCE(name, '')) LIKE ? OR "
                "UPPER(COALESCE(exchange_token, '')) LIKE ? OR "
                "UPPER(COALESCE(isin, '')) LIKE ? OR "
                "UPPER(COALESCE(instrument_type, '')) LIKE ? OR "
                "UPPER(COALESCE(segment, '')) LIKE ? OR "
                "UPPER(COALESCE(series, '')) LIKE ?)"
            )
            # Add search_term for each field (8 fields total)
            params.extend([search_term] * 8)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Determine ORDER BY clause
        order_by = "ORDER BY id DESC"  # Default
        if sort_by:
            sort_by_lower = sort_by.lower()
            if sort_by_lower == "last_updated":
                order_by = "ORDER BY last_updated_at DESC NULLS LAST, id DESC"
            elif sort_by_lower == "name":
                order_by = "ORDER BY name ASC NULLS LAST, id DESC"
            elif sort_by_lower == "symbol":
                order_by = "ORDER BY trading_symbol ASC NULLS LAST, id DESC"
        
        # Get total count (need to copy params for count query)
        count_params = params.copy()
        count_query = f"SELECT COUNT(*) FROM symbols WHERE {where_clause}"
        total = conn.execute(count_query, count_params).fetchone()[0]
        
        # Calculate pagination
        offset = (page - 1) * page_size
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        # Fetch paginated results with series description lookup
        query = f"""
            SELECT s.id, s.exchange, s.trading_symbol, s.exchange_token, s.name, s.instrument_type,
                   s.segment, s.series, s.isin, s.expiry_date, s.strike_price, s.lot_size,
                   s.status, s.source, s.created_at, s.updated_at, s.last_updated_at,
                   sl.description as series_description
            FROM symbols s
            LEFT JOIN series_lookup sl ON s.series = sl.series_code
            WHERE {where_clause}
            {order_by}
            LIMIT ? OFFSET ?
        """
        params.extend([page_size, offset])
        rows = conn.execute(query, params).fetchall()
        
        # Convert to response
        items = []
        for row in rows:
            items.append(SymbolResponse(
                id=row[0],
                exchange=row[1],
                trading_symbol=row[2],
                exchange_token=row[3],
                name=row[4],
                instrument_type=row[5],
                segment=row[6],
                series=row[7],
                isin=row[8],
                expiry_date=row[9],
                strike_price=row[10],
                lot_size=row[11],
                status=row[12],
                source=row[13],
                created_at=row[14],
                updated_at=row[15],
                last_updated_at=row[16],
                series_description=row[17] if len(row) > 17 else None
            ))
        
        return PaginatedSymbolResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error fetching symbols: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching symbols: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.post("/series-lookup/reload")
async def reload_series_lookup_endpoint(
    force: bool = Query(False, description="Force reload even if CSV hasn't changed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Reload series lookup data from CSV file
    
    Query Parameters:
        force: If True, force reload even if CSV hasn't changed (default: False)
    
    Returns:
        Result of the reload operation with entry count
    """
    try:
        result = reload_series_lookup(force=force)
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Failed to reload series lookup data"))
    except Exception as e:
        logger.error(f"Error reloading series lookup data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error reloading series lookup data: {str(e)}")

@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get symbols statistics"""
    conn = None
    try:
        conn = get_db_connection()
    
        # Get total count
        total = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        
        # Get last updated info from upload_logs (most recent upload)
        last_updated_info = None
        last_update_duration = None
        last_status = None
        last_run_datetime = None
        last_upload_type = None
        last_triggered_by = None
        last_updated_rows = 0
        last_inserted_rows = 0
        try:
            latest_log = conn.execute("""
                SELECT upload_type, file_name, started_at, duration_seconds, status, ended_at, updated_rows, inserted_rows, triggered_by
                FROM upload_logs
                ORDER BY started_at DESC
                LIMIT 1
            """).fetchone()
            
            if latest_log:
                log_status = latest_log[4] if latest_log[4] else None
                ended_at = latest_log[5] if len(latest_log) > 5 else None
                started_at = latest_log[2] if latest_log[2] else None
                upload_type = latest_log[0] if latest_log[0] else "MANUAL"
                triggered_by = latest_log[8] if len(latest_log) > 8 else None
                
                # Store last run datetime and upload type
                if started_at:
                    last_run_datetime = started_at.isoformat() if hasattr(started_at, 'isoformat') else str(started_at)
                last_upload_type = upload_type
                last_triggered_by = triggered_by
                
                # Normalize status for display
                if log_status:
                    status_upper = str(log_status).upper()
                    if status_upper in ['SUCCESS', 'COMPLETED']:
                        last_status = 'Completed'
                    elif status_upper == 'FAILED':
                        last_status = 'Failed'
                    elif status_upper == 'PARTIAL':
                        last_status = 'Completed (Partial)'
                    elif status_upper == 'CANCELLED':
                        last_status = 'Cancelled'
                    elif status_upper in ['CRASHED', 'INTERRUPTED', 'STOPPED']:
                        last_status = 'Crashed'
                    elif not ended_at and status_upper in ['PENDING', 'PROCESSING', 'QUEUED', 'RUNNING']:
                        last_status = 'Running' if status_upper in ['PROCESSING', 'RUNNING'] else 'Queued'
                    else:
                        last_status = status_upper
                
                last_updated_info = {
                    "upload_type": upload_type,
                    "file_name": latest_log[1] if latest_log[1] else "unknown",
                    "started_at": started_at.isoformat() if started_at and hasattr(started_at, 'isoformat') else (str(started_at) if started_at else None),
                    "status": last_status
                }
                # Get duration in seconds
                if latest_log[3] is not None:
                    last_update_duration = latest_log[3]
                
                # Get updated_rows count
                if len(latest_log) > 6 and latest_log[6] is not None:
                    last_updated_rows = int(latest_log[6])
                
                # Get inserted_rows count
                if len(latest_log) > 7 and latest_log[7] is not None:
                    last_inserted_rows = int(latest_log[7])
        except Exception:
            # upload_logs table might not exist or be empty
            pass
        
        # Calculate skipped symbols: total symbols - new inserted
        skipped_symbols = total - last_inserted_rows
        
        return {
            "total": total,
            "skipped_symbols": skipped_symbols,
            "last_updated": last_updated_info,
            "last_update_duration": last_update_duration,
            "last_status": last_status,
            "last_run_datetime": last_run_datetime,
            "last_upload_type": last_upload_type,
            "last_triggered_by": last_triggered_by,
            "last_updated_rows": last_updated_rows,
            "last_inserted_rows": last_inserted_rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")
    finally:
        if conn:
            conn.close()

# Bulk operation request schemas
class BulkDeleteRequest(BaseModel):
    ids: List[int]
    hard_delete: bool = False

class BulkStatusRequest(BaseModel):
    ids: List[int]
    status: str

@router.delete("/delete_all")
async def delete_all_symbols(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete all symbols from the database"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Get count before deletion for response
        count_result = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
        total_count = count_result[0] if count_result else 0
        
        # Delete all symbols
        conn.execute("DELETE FROM symbols")
        conn.commit()
        
        logger.info(f"[DELETE] User {current_user.id if current_user else 'system'} deleted all {total_count} symbols")
        
        return {
            "message": f"Successfully deleted all {total_count} symbol(s)",
            "deleted_count": total_count
        }
    except Exception as e:
        logger.error(f"Error deleting all symbols: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting all symbols: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.post("/delete/bulk")
async def bulk_delete_symbols(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete multiple symbols by their IDs"""
    conn = None
    try:
        if not request.ids or len(request.ids) == 0:
            raise HTTPException(status_code=400, detail="No symbol IDs provided")
        
        # Validate IDs are integers
        try:
            ids = [int(id) for id in request.ids]
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid symbol IDs provided")
        
        conn = get_db_connection()
        
        # Use parameterized query - create placeholders for IN clause
        placeholders = ','.join(['?' for _ in ids])
        
        # Validate IDs exist using parameterized query
        existing_count = conn.execute(
            f"SELECT COUNT(*) FROM symbols WHERE id IN ({placeholders})",
            ids
        ).fetchone()[0]
        
        if existing_count == 0:
            raise HTTPException(status_code=404, detail="No symbols found with the provided IDs")
        
        # Delete symbols using parameterized query
        conn.execute(
            f"DELETE FROM symbols WHERE id IN ({placeholders})",
            ids
        )
        conn.commit()
        
        logger.info(f"[DELETE] User {current_user.id if current_user else 'system'} deleted {existing_count} symbol(s)")
        
        return {
            "message": f"Successfully deleted {existing_count} symbol(s)",
            "deleted_count": existing_count,
            "requested_count": len(request.ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting symbols: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting symbols: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.patch("/status/bulk")
async def bulk_update_status(
    request: BulkStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update status for multiple symbols"""
    conn = None
    try:
        if not request.ids or len(request.ids) == 0:
            raise HTTPException(status_code=400, detail="No symbol IDs provided")
        
        # Validate IDs are integers
        try:
            ids = [int(id) for id in request.ids]
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid symbol IDs provided")
        
        # Validate status
        valid_statuses = ["ACTIVE", "INACTIVE"]
        status_upper = request.status.upper()
        if status_upper not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        conn = get_db_connection()
        
        # Use parameterized query - create placeholders for IN clause
        placeholders = ','.join(['?' for _ in ids])
        
        # Validate IDs exist using parameterized query
        existing_count = conn.execute(
            f"SELECT COUNT(*) FROM symbols WHERE id IN ({placeholders})",
            ids
        ).fetchone()[0]
        
        if existing_count == 0:
            raise HTTPException(status_code=404, detail="No symbols found with the provided IDs")
        
        # Update status using parameterized query
        now = datetime.now(timezone.utc)
        # For UPDATE with IN clause, we need to build the query with placeholders
        update_params = [status_upper, now, now] + ids
        conn.execute(
            f"UPDATE symbols SET status = ?, updated_at = ?, last_updated_at = ? WHERE id IN ({placeholders})",
            update_params
        )
        conn.commit()
        
        logger.info(f"[STATUS] User {current_user.id if current_user else 'system'} updated status to {status_upper} for {existing_count} symbol(s)")
        
        return {
            "message": f"Successfully updated status to {status_upper} for {existing_count} symbol(s)",
            "updated_count": existing_count,
            "requested_count": len(request.ids),
            "status": status_upper
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk updating status: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating status: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.get("/template")
async def get_template(
    current_user: User = Depends(get_admin_user)
):
    """Get CSV template for symbol upload with sample data"""
    import csv
    import io
    from datetime import datetime, timedelta
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Column headers matching the database schema
    headers = [
        "exchange",           # Required: Stock exchange code (NSE, BSE, etc.)
        "trading_symbol",     # Required: Full trading symbol (RELIANCE-EQ, etc.)
        "exchange_token",     # Optional: Exchange-specific token ID
        "name",               # Optional: Full name of the symbol
        "instrument_type",    # Optional: Type (EQ, FUT, OPT, INDEX)
        "segment",            # Optional: Market segment (Equity, F&O, etc.)
        "series",             # Optional: Series (EQ, BE, etc.)
        "isin",               # Optional: ISIN code
        "expiry_date",        # Optional: Expiry date (YYYY-MM-DD) for FUT/OPT
        "strike_price",       # Optional: Strike price for options
        "lot_size"            # Optional: Lot size
    ]
    writer.writerow(headers)
    
    # Sample data rows showing different instrument types
    # Equity example
    writer.writerow([
        "NSE",                              # exchange
        "RELIANCE-EQ",                      # trading_symbol
        "2885",                             # exchange_token
        "Reliance Industries Limited",      # name
        "EQ",                               # instrument_type
        "Equity",                           # segment
        "EQ",                               # series
        "INE002A01018",                     # isin
        "",                                 # expiry_date (empty for equity)
        "",                                 # strike_price (empty for equity)
        "1"                                 # lot_size
    ])
    
    # Futures example
    next_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    writer.writerow([
        "NSE",                              # exchange
        "NIFTY23DECFUT",                    # trading_symbol
        "99926000",                         # exchange_token
        "NIFTY 50",                         # name
        "FUT",                              # instrument_type
        "F&O",                              # segment
        "",                                 # series
        "",                                 # isin
        next_expiry,                        # expiry_date
        "",                                 # strike_price (empty for futures)
        "50"                                # lot_size
    ])
    
    # Options Call example
    writer.writerow([
        "NSE",                              # exchange
        "NIFTY23DEC19500CE",                # trading_symbol
        "99926001",                         # exchange_token
        "NIFTY 50",                         # name
        "OPT",                              # instrument_type
        "F&O",                              # segment
        "",                                 # series
        "",                                 # isin
        next_expiry,                        # expiry_date
        "19500",                            # strike_price
        "50"                                # lot_size
    ])
    
    # Options Put example
    writer.writerow([
        "NSE",                              # exchange
        "NIFTY23DEC19500PE",                # trading_symbol
        "99926002",                         # exchange_token
        "NIFTY 50",                         # name
        "OPT",                              # instrument_type
        "F&O",                              # segment
        "",                                 # series
        "",                                 # isin
        next_expiry,                        # expiry_date
        "19500",                            # strike_price
        "50"                                # lot_size
    ])
    
    # Index example
    writer.writerow([
        "NSE",                              # exchange
        "NIFTY 50",                         # trading_symbol
        "99926000",                         # exchange_token
        "NIFTY 50",                         # name
        "INDEX",                            # instrument_type
        "Index",                            # segment
        "",                                 # series
        "",                                 # isin
        "",                                 # expiry_date (empty for index)
        "",                                 # strike_price (empty for index)
        "1"                                 # lot_size
    ])
    
    csv_content = output.getvalue()
    output.close()
    
    return {
        "content": csv_content,
        "filename": "symbols_template.csv",
        "headers": headers
    }

# Script Management Endpoints
@router.get("/scripts", response_model=List[ScriptResponse])
async def get_scripts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get all transformation scripts"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM transformation_scripts LIMIT 1")
        except Exception:
            init_symbols_database()
            conn.close()
            conn = get_db_connection()
        
        scripts = conn.execute("""
            SELECT id, name, description, content, version, created_by, 
                   created_at, updated_at, last_used_at
            FROM transformation_scripts
            ORDER BY created_at DESC
        """).fetchall()
        
        result = []
        for script in scripts:
            result.append(ScriptResponse(
                id=script[0],
                name=script[1],
                description=script[2],
                content=script[3],
                version=script[4],
                created_by=script[5],
                created_at=script[6],
                updated_at=script[7],
                last_used_at=script[8]
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scripts: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.get("/scripts/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific transformation script by ID"""
    conn = None
    try:
        conn = get_db_connection()
        
        script = conn.execute("""
            SELECT id, name, description, content, version, created_by, 
                   created_at, updated_at, last_used_at
            FROM transformation_scripts
            WHERE id = ?
        """, [script_id]).fetchone()
        
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")
        
        return ScriptResponse(
            id=script[0],
            name=script[1],
            description=script[2],
            content=script[3],
            version=script[4],
            created_by=script[5],
            created_at=script[6],
            updated_at=script[7],
            last_used_at=script[8]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching script: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.post("/scripts", response_model=ScriptResponse)
async def create_script(
    script_data: ScriptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new transformation script"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM transformation_scripts LIMIT 1")
        except Exception:
            init_symbols_database()
            conn.close()
            conn = get_db_connection()
        
        # Check if script name already exists
        existing = conn.execute("SELECT id FROM transformation_scripts WHERE name = ?", [script_data.name]).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Script with this name already exists")
        
        # Get next ID
        max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM transformation_scripts").fetchone()
        next_id = (max_id_result[0] if max_id_result else 0) + 1
        
        # Insert new script
        now = datetime.now(timezone.utc)
        conn.execute("""
            INSERT INTO transformation_scripts (
                id, name, description, content, version, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            next_id,
            script_data.name,
            script_data.description,
            script_data.content,
            1,
            current_user.id if current_user else None,
            now
        ))
        
        conn.commit()
        
        # Fetch the created script
        script = conn.execute("""
            SELECT id, name, description, content, version, created_by, 
                   created_at, updated_at, last_used_at
            FROM transformation_scripts
            WHERE id = ?
        """, [next_id]).fetchone()
        
        return ScriptResponse(
            id=script[0],
            name=script[1],
            description=script[2],
            content=script[3],
            version=script[4],
            created_by=script[5],
            created_at=script[6],
            updated_at=script[7],
            last_used_at=script[8]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating script: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.put("/scripts/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: int,
    script_data: ScriptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update an existing transformation script"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if script exists
        existing = conn.execute("SELECT id, version FROM transformation_scripts WHERE id = ?", [script_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Script not found")
        
        current_version = existing[1]
        
        # Check if name is being changed and if new name already exists
        if script_data.name:
            name_check = conn.execute("SELECT id FROM transformation_scripts WHERE name = ? AND id != ?", 
                                    [script_data.name, script_id]).fetchone()
            if name_check:
                raise HTTPException(status_code=400, detail="Script with this name already exists")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        if script_data.name is not None:
            update_fields.append("name = ?")
            params.append(script_data.name)
        
        if script_data.description is not None:
            update_fields.append("description = ?")
            params.append(script_data.description)
        
        if script_data.content is not None:
            update_fields.append("content = ?")
            params.append(script_data.content)
            # Increment version when content changes
            update_fields.append("version = ?")
            params.append(current_version + 1)
        
        if update_fields:
            update_fields.append("updated_at = ?")
            params.append(datetime.now(timezone.utc))
            params.append(script_id)
            
            query = f"UPDATE transformation_scripts SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
        
        # Fetch updated script
        script = conn.execute("""
            SELECT id, name, description, content, version, created_by, 
                   created_at, updated_at, last_used_at
            FROM transformation_scripts
            WHERE id = ?
        """, [script_id]).fetchone()
        
        return ScriptResponse(
            id=script[0],
            name=script[1],
            description=script[2],
            content=script[3],
            version=script[4],
            created_by=script[5],
            created_at=script[6],
            updated_at=script[7],
            last_used_at=script[8]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating script: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.delete("/scripts/{script_id}")
async def delete_script(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete a transformation script"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if script exists
        existing = conn.execute("SELECT id FROM transformation_scripts WHERE id = ?", [script_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Script not found")
        
        # Delete script
        conn.execute("DELETE FROM transformation_scripts WHERE id = ?", [script_id])
        conn.commit()
        
        return {"message": "Script deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting script: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

# Scheduler Management Endpoints
@router.get("/schedulers", response_model=List[SchedulerResponse])
async def get_schedulers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get all schedulers"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM schedulers LIMIT 1")
        except Exception:
            init_symbols_database()
            conn.close()
            conn = get_db_connection()
        
        schedulers = conn.execute("""
            SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                   script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
            FROM schedulers
            ORDER BY created_at DESC
        """).fetchall()
        
        result = []
        for sched in schedulers:
            scheduler_id = sched[0]
            sources = json.loads(sched[9]) if sched[9] else []
            
            # Get last run status and current status from upload_logs
            # Look for uploads triggered by this scheduler
            last_run_status = None
            last_run_at_from_logs = None
            current_status = None  # For active runs (running/queued)
            scheduler_trigger_pattern = f"Scheduler-{sched[1]}"  # Scheduler-{name}
            
            try:
                # Get the most recent upload log for this scheduler
                last_log = conn.execute("""
                    SELECT status, started_at, ended_at, upload_type
                    FROM upload_logs
                    WHERE triggered_by LIKE ? AND upload_type = 'AUTO'
                    ORDER BY started_at DESC
                    LIMIT 1
                """, [f"%{scheduler_trigger_pattern}%"]).fetchone()
                
                if last_log:
                    log_status = last_log[0]  # status
                    last_run_at_from_logs = last_log[1]  # started_at
                    ended_at = last_log[2]  # ended_at
                    
                    # Normalize status for frontend
                    status_upper = str(log_status).upper() if log_status else ''
                    
                    # Check if this is an active run (not ended yet)
                    if not ended_at and status_upper in ['PENDING', 'PROCESSING', 'QUEUED', 'RUNNING']:
                        current_status = 'running' if status_upper in ['PROCESSING', 'RUNNING'] else 'queued'
                    else:
                        # This is a completed run, normalize status for last_run_status
                        if status_upper in ['SUCCESS', 'COMPLETED']:
                            last_run_status = 'completed'
                        elif status_upper == 'FAILED':
                            last_run_status = 'failed'
                        elif status_upper == 'PARTIAL':
                            last_run_status = 'completed'  # Partial success is still completed
                        elif status_upper == 'CANCELLED':
                            last_run_status = 'cancelled'
                        elif status_upper in ['CRASHED', 'INTERRUPTED', 'STOPPED']:
                            last_run_status = 'crashed'
                        else:
                            last_run_status = status_upper.lower() if status_upper else None
                    
                    # Use last_run_at from logs if scheduler's last_run_at is None or older
                    if not sched[12] or (last_run_at_from_logs and last_run_at_from_logs > sched[12]):
                        # Update scheduler's last_run_at if it's missing or older
                        conn.execute("""
                            UPDATE schedulers SET last_run_at = ? WHERE id = ?
                        """, [last_run_at_from_logs, scheduler_id])
                        conn.commit()
            except Exception as e:
                logger.warning(f"Error fetching last run status for scheduler {scheduler_id}: {e}")
            
            # Create response with last_run_status
            scheduler_response = SchedulerResponse(
                id=scheduler_id,
                name=sched[1],
                description=sched[2],
                mode=sched[3],
                interval_value=sched[4],
                interval_unit=sched[5],
                cron_expression=sched[6],
                script_id=sched[7],
                is_active=bool(sched[8]) if sched[8] is not None else True,
                sources=sources,
                created_at=sched[10],
                updated_at=sched[11],
                last_run_at=last_run_at_from_logs if last_run_at_from_logs else sched[12],
                next_run_at=sched[13],
                created_by=sched[14],
                last_run_status=last_run_status
            )
            
            # Add current status as a dynamic field (for active runs)
            scheduler_dict = scheduler_response.dict()
            if current_status:
                scheduler_dict['status'] = current_status
            result.append(scheduler_dict)
        
        return result
    except Exception as e:
        logger.error(f"Error fetching schedulers: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching schedulers: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.get("/schedulers/{scheduler_id}", response_model=SchedulerResponse)
async def get_scheduler(
    scheduler_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific scheduler by ID"""
    conn = None
    try:
        conn = get_db_connection()
        
        scheduler = conn.execute("""
            SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                   script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
            FROM schedulers
            WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        if not scheduler:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        sources = json.loads(scheduler[9]) if scheduler[9] else []
        
        # Get last run status from upload_logs
        last_run_status = None
        current_status = None
        scheduler_trigger_pattern = f"Scheduler-{scheduler[1]}"  # Scheduler-{name}
        
        try:
            last_log = conn.execute("""
                SELECT status, started_at, ended_at
                FROM upload_logs
                WHERE triggered_by LIKE ? AND upload_type = 'AUTO'
                ORDER BY started_at DESC
                LIMIT 1
            """, [f"%{scheduler_trigger_pattern}%"]).fetchone()
            
            if last_log:
                log_status = last_log[0]  # status
                ended_at = last_log[2]  # ended_at
                
                # Normalize status for frontend
                status_upper = str(log_status).upper() if log_status else ''
                
                # Check if this is an active run (not ended yet)
                if not ended_at and status_upper in ['PENDING', 'PROCESSING', 'QUEUED', 'RUNNING']:
                    current_status = 'running' if status_upper in ['PROCESSING', 'RUNNING'] else 'queued'
                else:
                    # This is a completed run, normalize status for last_run_status
                    if status_upper in ['SUCCESS', 'COMPLETED']:
                        last_run_status = 'completed'
                    elif status_upper == 'FAILED':
                        last_run_status = 'failed'
                    elif status_upper == 'PARTIAL':
                        last_run_status = 'completed'  # Partial success is still completed
                    elif status_upper == 'CANCELLED':
                        last_run_status = 'cancelled'
                    elif status_upper in ['CRASHED', 'INTERRUPTED', 'STOPPED']:
                        last_run_status = 'crashed'
                    else:
                        last_run_status = status_upper.lower() if status_upper else None
        except Exception as e:
            logger.warning(f"Error fetching last run status for scheduler {scheduler_id}: {e}")
        
        scheduler_response = SchedulerResponse(
            id=scheduler[0],
            name=scheduler[1],
            description=scheduler[2],
            mode=scheduler[3],
            interval_value=scheduler[4],
            interval_unit=scheduler[5],
            cron_expression=scheduler[6],
            script_id=scheduler[7],
            is_active=bool(scheduler[8]) if scheduler[8] is not None else True,
            sources=sources,
            created_at=scheduler[10],
            updated_at=scheduler[11],
            last_run_at=scheduler[12],
            next_run_at=scheduler[13],
            created_by=scheduler[14],
            last_run_status=last_run_status
        )
        
        # Add current status as a dynamic field (for active runs)
        scheduler_dict = scheduler_response.dict()
        if current_status:
            scheduler_dict['status'] = current_status
        return scheduler_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching scheduler: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.post("/schedulers", response_model=SchedulerResponse)
async def create_scheduler(
    scheduler_data: SchedulerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Ensure table exists
        try:
            conn.execute("SELECT 1 FROM schedulers LIMIT 1")
        except Exception:
            init_symbols_database()
            conn.close()
            conn = get_db_connection()
        
        # Validate mode and required fields
        if scheduler_data.mode not in ['RUN_ONCE', 'INTERVAL', 'CRON']:
            raise HTTPException(status_code=400, detail="Invalid mode. Must be RUN_ONCE, INTERVAL, or CRON")
        
        if scheduler_data.mode == 'INTERVAL' and (not scheduler_data.interval_value or not scheduler_data.interval_unit):
            raise HTTPException(status_code=400, detail="interval_value and interval_unit are required for INTERVAL mode")
        
        if scheduler_data.mode == 'CRON' and not scheduler_data.cron_expression:
            raise HTTPException(status_code=400, detail="cron_expression is required for CRON mode")
        
        if not scheduler_data.sources or len(scheduler_data.sources) == 0:
            raise HTTPException(status_code=400, detail="At least one source is required")
        
        # Get next ID
        max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM schedulers").fetchone()
        next_id = (max_id_result[0] if max_id_result else 0) + 1
        
        # Serialize sources to JSON
        sources_json = json.dumps([source.dict() for source in scheduler_data.sources])
        
        now = datetime.now(timezone.utc)
        
        # Calculate next_run_at based on mode
        next_run_at = None
        if scheduler_data.is_active:
            if scheduler_data.mode == 'INTERVAL' and scheduler_data.interval_value and scheduler_data.interval_unit:
                # Calculate next run time for interval (case-insensitive)
                unit_lower = scheduler_data.interval_unit.lower() if scheduler_data.interval_unit else 'hours'
                if unit_lower in ['seconds', 'second']:
                    delta = timedelta(seconds=scheduler_data.interval_value)
                elif unit_lower in ['minutes', 'minute']:
                    delta = timedelta(minutes=scheduler_data.interval_value)
                elif unit_lower in ['hours', 'hour']:
                    delta = timedelta(hours=scheduler_data.interval_value)
                elif unit_lower in ['days', 'day']:
                    delta = timedelta(days=scheduler_data.interval_value)
                else:
                    logger.warning(f"Unknown interval_unit '{scheduler_data.interval_unit}', defaulting to 1 hour")
                    delta = timedelta(hours=1)  # Default
                next_run_at = now + delta
            elif scheduler_data.mode == 'CRON' and scheduler_data.cron_expression:
                # Calculate next run time from cron expression
                try:
                    from croniter import croniter
                    cron = croniter(scheduler_data.cron_expression, now)
                    next_run_at = cron.get_next(datetime)
                    if next_run_at.tzinfo is None:
                        next_run_at = next_run_at.replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.warning(f"Error parsing cron expression: {e}")
            elif scheduler_data.mode == 'RUN_ONCE':
                # Run once schedulers run immediately
                next_run_at = now
        
        # Insert new scheduler
        conn.execute("""
            INSERT INTO schedulers (
                id, name, description, mode, interval_value, interval_unit, cron_expression,
                script_id, is_active, sources, created_at, created_by, next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_id,
            scheduler_data.name,
            scheduler_data.description,
            scheduler_data.mode,
            scheduler_data.interval_value,
            scheduler_data.interval_unit,
            scheduler_data.cron_expression,
            scheduler_data.script_id,
            scheduler_data.is_active,
            sources_json,
            now,
            current_user.id if current_user else None,
            next_run_at
        ))
        
        conn.commit()
        
        # Fetch the created scheduler
        scheduler = conn.execute("""
            SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                   script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
            FROM schedulers
            WHERE id = ?
        """, [next_id]).fetchone()
        
        sources = json.loads(scheduler[9]) if scheduler[9] else []
        return SchedulerResponse(
            id=scheduler[0],
            name=scheduler[1],
            description=scheduler[2],
            mode=scheduler[3],
            interval_value=scheduler[4],
            interval_unit=scheduler[5],
            cron_expression=scheduler[6],
            script_id=scheduler[7],
            is_active=bool(scheduler[8]) if scheduler[8] is not None else True,
            sources=sources,
            created_at=scheduler[10],
            updated_at=scheduler[11],
            last_run_at=scheduler[12],
            next_run_at=scheduler[13],
            created_by=scheduler[14]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating scheduler: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.put("/schedulers/{scheduler_id}", response_model=SchedulerResponse)
async def update_scheduler(
    scheduler_id: int,
    scheduler_data: SchedulerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update a scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if scheduler exists
        existing = conn.execute("SELECT id FROM schedulers WHERE id = ?", [scheduler_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        # Build update query
        update_fields = []
        params = []
        
        if scheduler_data.name is not None:
            update_fields.append("name = ?")
            params.append(scheduler_data.name)
        
        if scheduler_data.description is not None:
            update_fields.append("description = ?")
            params.append(scheduler_data.description)
        
        if scheduler_data.mode is not None:
            if scheduler_data.mode not in ['RUN_ONCE', 'INTERVAL', 'CRON']:
                raise HTTPException(status_code=400, detail="Invalid mode. Must be RUN_ONCE, INTERVAL, or CRON")
            update_fields.append("mode = ?")
            params.append(scheduler_data.mode)
        
        if scheduler_data.interval_value is not None:
            update_fields.append("interval_value = ?")
            params.append(scheduler_data.interval_value)
        
        if scheduler_data.interval_unit is not None:
            update_fields.append("interval_unit = ?")
            params.append(scheduler_data.interval_unit)
        
        if scheduler_data.cron_expression is not None:
            update_fields.append("cron_expression = ?")
            params.append(scheduler_data.cron_expression)
        
        if scheduler_data.script_id is not None:
            update_fields.append("script_id = ?")
            params.append(scheduler_data.script_id)
        
        if scheduler_data.is_active is not None:
            update_fields.append("is_active = ?")
            params.append(scheduler_data.is_active)
        
        if scheduler_data.sources is not None:
            sources_json = json.dumps([source.dict() for source in scheduler_data.sources])
            update_fields.append("sources = ?")
            params.append(sources_json)
        
        # Recalculate next_run_at if mode, interval, cron, or is_active changed
        recalculate_next_run = False
        if (scheduler_data.mode is not None or 
            scheduler_data.interval_value is not None or 
            scheduler_data.interval_unit is not None or 
            scheduler_data.cron_expression is not None or 
            scheduler_data.is_active is not None):
            recalculate_next_run = True
        
        # Calculate next_run_at if needed
        next_run_at = None
        if recalculate_next_run:
            # Get current scheduler state to determine mode
            current_sched = conn.execute("""
                SELECT mode, interval_value, interval_unit, cron_expression, is_active
                FROM schedulers WHERE id = ?
            """, [scheduler_id]).fetchone()
            
            mode = scheduler_data.mode if scheduler_data.mode is not None else current_sched[0]
            interval_value = scheduler_data.interval_value if scheduler_data.interval_value is not None else current_sched[1]
            interval_unit = scheduler_data.interval_unit if scheduler_data.interval_unit is not None else current_sched[2]
            cron_expression = scheduler_data.cron_expression if scheduler_data.cron_expression is not None else current_sched[3]
            is_active = scheduler_data.is_active if scheduler_data.is_active is not None else current_sched[4]
            
            if is_active:
                now = datetime.now(timezone.utc)
                if mode == 'INTERVAL' and interval_value and interval_unit:
                    # Case-insensitive matching
                    unit_lower = interval_unit.lower() if interval_unit else 'hours'
                    if unit_lower in ['seconds', 'second']:
                        delta = timedelta(seconds=interval_value)
                    elif unit_lower in ['minutes', 'minute']:
                        delta = timedelta(minutes=interval_value)
                    elif unit_lower in ['hours', 'hour']:
                        delta = timedelta(hours=interval_value)
                    elif unit_lower in ['days', 'day']:
                        delta = timedelta(days=interval_value)
                    else:
                        logger.warning(f"Unknown interval_unit '{interval_unit}', defaulting to 1 hour")
                        delta = timedelta(hours=1)
                    next_run_at = now + delta
                elif mode == 'CRON' and cron_expression:
                    try:
                        from croniter import croniter
                        cron = croniter(cron_expression, now)
                        next_run_at = cron.get_next(datetime)
                        if next_run_at.tzinfo is None:
                            next_run_at = next_run_at.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Error parsing cron expression: {e}")
                elif mode == 'RUN_ONCE':
                    next_run_at = now
        
        if next_run_at is not None:
            update_fields.append("next_run_at = ?")
            params.append(next_run_at)
        
        if update_fields:
            update_fields.append("updated_at = ?")
            params.append(datetime.now(timezone.utc))
            params.append(scheduler_id)
            
            query = f"UPDATE schedulers SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
        
        # Fetch updated scheduler
        scheduler = conn.execute("""
            SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                   script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
            FROM schedulers
            WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        sources = json.loads(scheduler[9]) if scheduler[9] else []
        return SchedulerResponse(
            id=scheduler[0],
            name=scheduler[1],
            description=scheduler[2],
            mode=scheduler[3],
            interval_value=scheduler[4],
            interval_unit=scheduler[5],
            cron_expression=scheduler[6],
            script_id=scheduler[7],
            is_active=bool(scheduler[8]) if scheduler[8] is not None else True,
            sources=sources,
            created_at=scheduler[10],
            updated_at=scheduler[11],
            last_run_at=scheduler[12],
            next_run_at=scheduler[13],
            created_by=scheduler[14]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating scheduler: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.delete("/schedulers/{scheduler_id}")
async def delete_scheduler(
    scheduler_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete a scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if scheduler exists
        existing = conn.execute("SELECT id FROM schedulers WHERE id = ?", [scheduler_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        conn.execute("DELETE FROM schedulers WHERE id = ?", [scheduler_id])
        conn.commit()
        
        return {"message": "Scheduler deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting scheduler: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.post("/schedulers/{scheduler_id}/trigger")
async def trigger_scheduler(
    scheduler_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Trigger a scheduler to run now (for testing)"""
    return {"message": "Scheduler triggered", "scheduler_id": scheduler_id}

@router.post("/test-connection")
async def test_connection(
    url: str = Form(...),
    source_type: str = Form(...),
    method: Optional[str] = Form(None),
    headers: Optional[str] = Form(None),
    auth_type: Optional[str] = Form(None),
    auth_value: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Test connection to URL/API endpoint for scheduler configuration"""
    try:
        # Parse headers if provided
        request_headers = {}
        if headers:
            try:
                request_headers = json.loads(headers)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid headers JSON format")
        
        # Add authentication if provided
        if auth_type and auth_value:
            if auth_type.lower() == 'bearer':
                request_headers['Authorization'] = f"Bearer {auth_value}"
            elif auth_type.lower() == 'basic':
                request_headers['Authorization'] = f"Basic {auth_value}"
            elif auth_type.lower() == 'api_key':
                # Default header name for API key
                request_headers['X-API-Key'] = auth_value
        
        # Determine HTTP method
        http_method = (method or 'GET').upper()
        if http_method not in ['GET', 'POST', 'PUT', 'PATCH']:
            http_method = 'GET'
        
        # Test the connection
        logger.info(f"Testing connection to {url} with method {http_method}")
        
        if http_method == 'GET':
            response = requests.get(url, headers=request_headers, timeout=10, stream=True)
        elif http_method == 'POST':
            response = requests.post(url, headers=request_headers, timeout=10, stream=True)
        elif http_method == 'PUT':
            response = requests.put(url, headers=request_headers, timeout=10, stream=True)
        elif http_method == 'PATCH':
            response = requests.patch(url, headers=request_headers, timeout=10, stream=True)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {http_method}")
        
        response.raise_for_status()
        
        # Check if response is a file (for DOWNLOADABLE_URL)
        if source_type == 'DOWNLOADABLE_URL':
            content_type = response.headers.get('Content-Type', '')
            content_length = response.headers.get('Content-Length')
            
            # Try to read a small chunk to verify it's downloadable
            chunk = next(response.iter_content(chunk_size=1024), None)
            
            return {
                "success": True,
                "status": "success",
                "message": "Connection test successful",
                "url": url,
                "content_type": content_type,
                "content_length": content_length,
                "status_code": response.status_code,
                "downloadable": True
            }
        else:
            # For API endpoints, just verify connection
            return {
                "success": True,
                "status": "success",
                "message": "Connection test successful",
                "url": url,
                "status_code": response.status_code,
                "method": http_method
            }
    
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Connection timeout - URL did not respond within 10 seconds")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Connection failed - Unable to reach the URL")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error: {e.response.status_code} - {e.response.reason}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

@router.post("/schedulers/{scheduler_id}/run-now")
async def run_scheduler_now(
    scheduler_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Run scheduler immediately - executes full flow: download, script, preview, upload"""
    from datetime import timezone
    import threading
    import uuid
    
    # Generate execution ID for tracking this specific request
    execution_id = str(uuid.uuid4())[:8]
    
    # CRITICAL: Acquire lock FIRST, before any database operations
    # Use module-level lock dictionary to prevent concurrent manual triggers
    with _scheduler_locks_lock:
        if scheduler_id not in _scheduler_manual_locks:
            _scheduler_manual_locks[scheduler_id] = threading.Lock()
        lock = _scheduler_manual_locks[scheduler_id]
    
    # Try to acquire lock (non-blocking) - this is the FIRST check
    print(f"[MANUAL TRIGGER-{execution_id}] Attempting to acquire lock for scheduler {scheduler_id}")
    if not lock.acquire(blocking=False):
        print(f"[MANUAL TRIGGER-{execution_id}] FAILED: Lock already held for scheduler {scheduler_id}, rejecting duplicate request")
        logger.warning(f"[MANUAL TRIGGER-{execution_id}] Scheduler {scheduler_id} is already being triggered, rejecting duplicate request")
        raise HTTPException(
            status_code=409,
            detail="Scheduler is already being triggered. Please wait for the current operation to complete."
        )
    
    print(f"[MANUAL TRIGGER-{execution_id}] SUCCESS: Lock acquired for scheduler {scheduler_id} by user {current_user.username}")
    logger.info(f"[MANUAL TRIGGER-{execution_id}] Lock acquired for scheduler {scheduler_id} by user {current_user.username}")
    
    conn = None
    try:
        conn = get_db_connection()
        
        # Get scheduler with all needed fields
        scheduler = conn.execute("""
            SELECT id, name, mode, interval_value, interval_unit, cron_expression,
                   sources, script_id FROM schedulers WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        if not scheduler:
            lock.release()
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        scheduler_id_db = scheduler[0]
        name = scheduler[1]
        mode = scheduler[2]
        interval_value = scheduler[3]
        interval_unit = scheduler[4]
        cron_expression = scheduler[5]
        sources_json = scheduler[6]
        script_id = scheduler[7]
        
        sources = json.loads(sources_json) if sources_json else []
        if not sources or len(sources) == 0:
            lock.release()
            print(f"[MANUAL TRIGGER-{execution_id}] ERROR: Scheduler has no sources")
            raise HTTPException(status_code=400, detail="Scheduler has no sources")
        
        print(f"[MANUAL TRIGGER-{execution_id}] Scheduler {name} has {len(sources)} source(s) - will process all sources in ONE execution")
        logger.info(f"[MANUAL TRIGGER-{execution_id}] Scheduler {name} has {len(sources)} source(s) - will process all sources in ONE execution")
        
        # CRITICAL: Use atomic UPDATE with WHERE clause to prevent duplicate triggers
        # Only update if last_run_at is NULL or older than 10 seconds (increased from 5)
        # This ensures only ONE request can succeed at a time
        try:
            now = datetime.now(timezone.utc)
            ten_seconds_ago = now - timedelta(seconds=10)  # Increased to 10 seconds
            
            # Check current last_run_at
            last_run = conn.execute("""
                SELECT last_run_at FROM schedulers WHERE id = ?
            """, [scheduler_id_db]).fetchone()
            
            if last_run and last_run[0]:
                last_run_time = last_run[0].replace(tzinfo=timezone.utc) if last_run[0].tzinfo is None else last_run[0]
                time_since_last = now - last_run_time
                if time_since_last < timedelta(seconds=10):  # Increased to 10 seconds
                    lock.release()  # Release lock before raising exception
                    logger.warning(f"[MANUAL TRIGGER] Scheduler {scheduler_id_db} ran {time_since_last.total_seconds():.1f} seconds ago, rejecting")
                    raise HTTPException(
                        status_code=409,
                        detail=f"Scheduler just ran {time_since_last.total_seconds():.1f} seconds ago. Please wait before running again."
                    )
            
            # Atomic update: only update if last_run_at is NULL or older than 10 seconds
            result = conn.execute("""
                UPDATE schedulers 
                SET last_run_at = ? 
                WHERE id = ? 
                AND (last_run_at IS NULL OR last_run_at < ?)
            """, [now, scheduler_id_db, ten_seconds_ago])
            
            # For DuckDB, check if update actually happened by reading back immediately
            verify_run = conn.execute("""
                SELECT last_run_at FROM schedulers WHERE id = ?
            """, [scheduler_id_db]).fetchone()
            
            if not verify_run or not verify_run[0]:
                # No last_run_at found - this shouldn't happen, but release lock and fail
                lock.release()
                logger.error(f"[MANUAL TRIGGER] Could not verify last_run_at update for scheduler {scheduler_id_db}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to update scheduler status"
                )
            
            verify_time = verify_run[0].replace(tzinfo=timezone.utc) if verify_run[0].tzinfo is None else verify_run[0]
            time_diff = abs((verify_time - now).total_seconds())
            
            if time_diff > 2:  # Allow 2 second tolerance
                # Update didn't work, another request must have updated it
                lock.release()  # Release lock before raising exception
                logger.warning(f"[MANUAL TRIGGER] Scheduler {scheduler_id_db} last_run_at mismatch (diff: {time_diff}s), another request updated it")
                raise HTTPException(
                    status_code=409,
                    detail="Scheduler is already running. Please wait for it to complete."
                )
            
            logger.info(f"[MANUAL TRIGGER] Successfully updated last_run_at for scheduler {scheduler_id_db}")
            # Recalculate next_run_at based on scheduler mode to continue with normal interval
            from app.services.scheduler_service import get_scheduler_service
            scheduler_service = get_scheduler_service()
            
            if mode == 'INTERVAL' and interval_value and interval_unit:
                next_run_at = scheduler_service._calculate_next_run_interval(now, interval_value, interval_unit)
                conn.execute("""
                    UPDATE schedulers SET next_run_at = ? WHERE id = ?
                """, [next_run_at, scheduler_id_db])
            elif mode == 'CRON' and cron_expression:
                next_run_at = scheduler_service._calculate_next_run_cron(now, cron_expression)
                if next_run_at:
                    conn.execute("""
                        UPDATE schedulers SET next_run_at = ? WHERE id = ?
                    """, [next_run_at, scheduler_id_db])
            # For RUN_ONCE, don't update next_run_at (it won't run again automatically)
            
            # CRITICAL: Commit BEFORE starting thread to ensure database is updated
            conn.commit()
            logger.info(f"[MANUAL TRIGGER] Scheduler {name} (ID: {scheduler_id_db}) triggered by user {current_user.username} at {now}")
            
            # Prepare user info for manual trigger
            triggered_by_user = {
                'id': current_user.id,
                'name': current_user.name,
                'username': current_user.username,
                'email': current_user.email
            }
            
            # Execute scheduler in background thread with user info for manual trigger
            import threading
            print(f"[MANUAL TRIGGER-{execution_id}] Starting execution thread for scheduler {scheduler_id_db} (lock will be held until completion)")
            logger.info(f"[MANUAL TRIGGER-{execution_id}] Starting execution thread for scheduler {scheduler_id_db} (lock will be held until completion)")
            thread = threading.Thread(
                target=scheduler_service._execute_scheduler,
                args=(scheduler_id_db, name, sources_json, script_id, mode, interval_value, interval_unit, cron_expression, triggered_by_user, lock),
                daemon=True,
                name=f"RunNow-{scheduler_id_db}-{execution_id}"
            )
            thread.start()
            
            # DON'T release lock here - let the execution thread release it when done
            # This ensures only one execution can happen at a time
            # The lock will be released by the scheduler service after execution completes
            print(f"[MANUAL TRIGGER-{execution_id}] Execution thread started for scheduler {scheduler_id_db}, lock will be held until execution completes")
            logger.info(f"[MANUAL TRIGGER-{execution_id}] Execution thread started for scheduler {scheduler_id_db}, lock will be held until execution completes")
            
        except HTTPException:
            # Re-raise HTTP exceptions (lock already released above if needed)
            raise
        except Exception as e:
            # Release lock on any other error
            if lock.locked():
                lock.release()
            raise
        
        return {
            "message": "Scheduler execution started",
            "scheduler_id": scheduler_id,
            "status": "PROCESSING"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Error running scheduler: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.post("/schedulers/{scheduler_id}/sources")
async def add_scheduler_source(
    scheduler_id: int,
    source_data: SchedulerSource,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Add a source to a scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if scheduler exists
        scheduler = conn.execute("""
            SELECT id, sources FROM schedulers WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        if not scheduler:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        # Get current sources
        current_sources_json = scheduler[1]
        current_sources = json.loads(current_sources_json) if current_sources_json else []
        
        # Add new source
        new_source = source_data.dict()
        current_sources.append(new_source)
        
        # Update scheduler with new sources
        updated_sources_json = json.dumps(current_sources)
        conn.execute("""
            UPDATE schedulers 
            SET sources = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [updated_sources_json, scheduler_id])
        conn.commit()
        
        return {
            "message": "Source added successfully",
            "scheduler_id": scheduler_id,
            "source": new_source
        }
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid sources format in scheduler")
    except Exception as e:
        logger.error(f"Error adding source to scheduler: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding source: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.put("/schedulers/{scheduler_id}/sources/{source_id}")
async def update_scheduler_source(
    scheduler_id: int,
    source_id: int,
    source_data: SchedulerSource,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update a source in a scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if scheduler exists
        scheduler = conn.execute("""
            SELECT id, sources FROM schedulers WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        if not scheduler:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        # Get current sources
        current_sources_json = scheduler[1]
        current_sources = json.loads(current_sources_json) if current_sources_json else []
        
        # Validate source_id (index)
        if source_id < 0 or source_id >= len(current_sources):
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Update source at index
        updated_source = source_data.dict()
        current_sources[source_id] = updated_source
        
        # Update scheduler with updated sources
        updated_sources_json = json.dumps(current_sources)
        conn.execute("""
            UPDATE schedulers 
            SET sources = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [updated_sources_json, scheduler_id])
        conn.commit()
        
        return {
            "message": "Source updated successfully",
            "scheduler_id": scheduler_id,
            "source_id": source_id,
            "source": updated_source
        }
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid sources format in scheduler")
    except Exception as e:
        logger.error(f"Error updating source in scheduler: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating source: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.delete("/schedulers/{scheduler_id}/sources/{source_id}")
async def delete_scheduler_source(
    scheduler_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete a source from a scheduler"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Check if scheduler exists
        scheduler = conn.execute("""
            SELECT id, sources FROM schedulers WHERE id = ?
        """, [scheduler_id]).fetchone()
        
        if not scheduler:
            raise HTTPException(status_code=404, detail="Scheduler not found")
        
        # Get current sources
        current_sources_json = scheduler[1]
        current_sources = json.loads(current_sources_json) if current_sources_json else []
        
        # Validate source_id (index)
        if source_id < 0 or source_id >= len(current_sources):
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Remove source at index
        deleted_source = current_sources.pop(source_id)
        
        # Update scheduler with updated sources
        updated_sources_json = json.dumps(current_sources)
        conn.execute("""
            UPDATE schedulers 
            SET sources = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [updated_sources_json, scheduler_id])
        conn.commit()
        
        return {
            "message": "Source deleted successfully",
            "scheduler_id": scheduler_id,
            "source_id": source_id,
            "deleted_source": deleted_source
        }
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid sources format in scheduler")
    except Exception as e:
        logger.error(f"Error deleting source from scheduler: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting source: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

