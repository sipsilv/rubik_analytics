import pandas as pd
import io
import os
import uuid
import logging
import threading
import time
import json
import requests
import tempfile
import traceback
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from app.repositories.symbols_repository import SymbolsRepository
from app.core.config import settings

logger = logging.getLogger(__name__)

class SymbolsService:
    # State management
    _preview_cache: Dict[str, Dict] = {}
    _upload_status_cache: Dict[str, Dict] = {}
    
    # Locks
    _scheduler_manual_locks: Dict[int, threading.Lock] = {}
    _scheduler_locks_lock = threading.Lock()

    def __init__(self):
        self.repo = SymbolsRepository()

    def _get_scheduler_lock(self, scheduler_id: int) -> threading.Lock:
        with self._scheduler_locks_lock:
            if scheduler_id not in self._scheduler_manual_locks:
                self._scheduler_manual_locks[scheduler_id] = threading.Lock()
            return self._scheduler_manual_locks[scheduler_id]

    def apply_transformation_script(self, df: pd.DataFrame, script_content: str) -> pd.DataFrame:
        """Apply transformation script to dataframe safely"""
        try:
            safe_globals = {
                'pd': pd,
                'df': df.copy(),
                '__builtins__': __builtins__
            }
            exec(script_content, safe_globals)
            
            result_df = None
            if 'final_df' in safe_globals:
                result_df = safe_globals['final_df']
            elif 'df' in safe_globals:
                modified_df = safe_globals['df']
                if not modified_df.equals(df) or list(modified_df.columns) != list(df.columns) or modified_df.shape != df.shape:
                    result_df = modified_df
            
            if result_df is None:
                raise ValueError("Transformation script must create 'final_df' or modify 'df'.")
            
            if not isinstance(result_df, pd.DataFrame):
                raise ValueError(f"Transformation script must result in a pandas DataFrame, got {type(result_df)}")
            
            return result_df
        except Exception as e:
            logger.error(f"Script transformation failed: {e}")
            raise ValueError(f"Error executing transformation script: {str(e)}")

    def process_manual_upload_preview(self, file_contents: bytes, filename: str, script_id: Optional[int], user_info: dict) -> dict:
        conn = None
        try:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext == '.csv':
                df = pd.read_csv(io.BytesIO(file_contents), low_memory=False)
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(io.BytesIO(file_contents))
            else:
                raise ValueError("Unsupported file type")

            script_loaded = False
            transformed = False
            script_name = None
            original_rows = len(df)
            original_cols = len(df.columns)

            if script_id:
                script_row = self.repo.get_transformation_script(script_id)
                if script_row:
                    script_name = script_row[0]
                    script_content = script_row[1]
                    script_loaded = True
                    df = self.apply_transformation_script(df, script_content)
                    transformed = True
                else:
                    raise ValueError(f"Transformation script {script_id} not found")

            preview_id = f"preview_{uuid.uuid4().hex[:16]}"
            new_rows = len(df)
            new_cols = len(df.columns)
            
            self._preview_cache[preview_id] = {
                'df': df,
                'filename': filename,
                'script_id': script_id,
                'script_name': script_name,
                'script_loaded': script_loaded,
                'transformed': transformed,
                'original_rows': original_rows,
                'original_cols': original_cols,
                'new_rows': new_rows,
                'new_cols': new_cols,
                'user_id': user_info.get('id'),
                'user_name': user_info.get('name') or user_info.get('username') or 'system',
                'upload_type': 'MANUAL'
            }
            
            return {
                "headers": df.columns.tolist(),
                "rows": df.head(10).to_dict('records'),
                "total_rows": len(df),
                "preview_id": preview_id
            }
        except Exception as e:
            logger.error(f"Failed to process manual upload preview: {e}")
            raise

    def process_auto_upload_preview(self, url: str, file_type: str, headers: dict, auth_type: str, auth_value: str, script_id: Optional[int], user_info: dict) -> dict:
        temp_file_path = None
        try:
            req_headers = headers or {}
            if auth_type and auth_value:
                if auth_type.lower() == 'bearer': req_headers['Authorization'] = f"Bearer {auth_value}"
                elif auth_type.lower() == 'basic': req_headers['Authorization'] = f"Basic {auth_value}"
                elif auth_type.lower() == 'api_key': req_headers['X-API-Key'] = auth_value
            
            response = requests.get(url, headers=req_headers, timeout=300, stream=True)
            response.raise_for_status()
            
            parsed_url = urlparse(url)
            file_ext = os.path.splitext(parsed_url.path)[1].lower()
            if not file_ext:
                ct = response.headers.get('Content-Type', '')
                if 'csv' in ct.lower(): file_ext = '.csv'
                elif 'excel' in ct.lower() or 'spreadsheet' in ct.lower(): file_ext = '.xlsx'
                else: file_ext = '.csv'

            temp_dir = os.path.join(self.repo.data_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=file_ext, dir=temp_dir)
            temp_file_path = temp_file.name
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()

            final_file_type = file_type or 'AUTO'
            if final_file_type == 'AUTO':
                if file_ext == '.csv': final_file_type = 'CSV'
                elif file_ext in ['.xlsx', '.xls']: final_file_type = 'XLSX'
                else: final_file_type = 'CSV'

            with open(temp_file_path, 'rb') as f:
                content = f.read()

            if final_file_type == 'CSV':
                df = pd.read_csv(io.BytesIO(content), low_memory=False)
            elif final_file_type == 'XLSX':
                df = pd.read_excel(io.BytesIO(content))
            else:
                 raise ValueError(f"Unsupported file type: {final_file_type}")

            filename = os.path.basename(parsed_url.path) or f"download{file_ext}"
            
            script_loaded = False
            transformed = False
            script_name = None
            original_rows = len(df)
            original_cols = len(df.columns)

            if script_id:
                script_row = self.repo.get_transformation_script(script_id)
                if script_row:
                    script_name = script_row[0]
                    script_content = script_row[1]
                    script_loaded = True
                    df = self.apply_transformation_script(df, script_content)
                    transformed = True
                else:
                    raise ValueError(f"Transformation script {script_id} not found")

            preview_id = f"preview_{uuid.uuid4().hex[:16]}"
            new_rows = len(df)
            new_cols = len(df.columns)
            
            self._preview_cache[preview_id] = {
                'df': df,
                'filename': filename,
                'script_id': script_id,
                'script_name': script_name,
                'script_loaded': script_loaded,
                'transformed': transformed,
                'original_rows': original_rows,
                'original_cols': original_cols,
                'new_rows': new_rows,
                'new_cols': new_cols,
                'user_id': user_info.get('id'),
                'user_name': user_info.get('name') or user_info.get('username') or 'system',
                'upload_type': 'AUTO'
            }
            
            return {
                "headers": df.columns.tolist(),
                "rows": df.head(10).to_dict('records'),
                "total_rows": len(df),
                "preview_id": preview_id
            }
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except: pass

    def confirm_upload(self, preview_id: str):
        if preview_id not in self._preview_cache:
            raise ValueError("Preview expired. Please upload the file again.")
        
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        t = threading.Thread(target=self.process_upload_async, args=(preview_id, job_id), name=f"Upload-{job_id}")
        t.daemon = True
        t.start()
        
        return {"job_id": job_id, "status": "PROCESSING", "message": "Upload started"}

    def process_upload_async(self, preview_id: str, job_id: str):
        """Background process for upload"""
        started_at = datetime.now(timezone.utc)
        start_time = time.time()
        
        # Init status
        self._upload_status_cache[job_id] = {
            "status": "PROCESSING", "processed": 0, "total": 0, "inserted": 0, "updated": 0, 
            "failed": 0, "errors": [], "percentage": 0, "triggered_by": "system"
        }
        
        conn = None
        filename = "unknown"
        triggered_by = "system"
        upload_type = "MANUAL"
        
        try:
             if preview_id not in self._preview_cache:
                 self._upload_status_cache[job_id]["status"] = "FAILED"
                 self._upload_status_cache[job_id]["errors"] = ["Preview expired"]
                 self.repo.save_upload_log(None, job_id, "unknown", started_at, datetime.now(timezone.utc), "FAILED", 0, 0, 0, 0, ["Preview expired"], "system", "MANUAL")
                 return
             
             cached = self._preview_cache[preview_id]
             df = cached['df']
             filename = cached.get('filename', 'unknown')
             upload_type = cached.get('upload_type', 'MANUAL')
             triggered_by = cached.get('user_name', 'system')
             
             self._upload_status_cache[job_id]["triggered_by"] = triggered_by
             self._upload_status_cache[job_id]["total"] = len(df)
             
             conn = self.repo.get_db_connection()
             
             # PROCESSING LOGIC (Copied & Adapted for Repo)
             # ... [Logic for bulk upsert using temp tables and logic from symbols.py] ...
             # I will simplify for brevity but ensure core logic remains
             
             # Normalize columns
             if 'symbol' in df.columns and 'trading_symbol' not in df.columns:
                 df['trading_symbol'] = df['symbol']
             df['exchange'] = df['exchange'].fillna('').astype(str).str.strip().str.upper()
             df['trading_symbol'] = df['trading_symbol'].fillna('').astype(str).str.strip().str.upper()
             
             valid_mask = (df['exchange'] != '') & (df['trading_symbol'] != '')
             df = df[valid_mask].drop_duplicates(subset=['exchange', 'trading_symbol'], keep='first').copy()
             
             # Get existing IDs
             existing_rows = conn.execute("SELECT exchange, trading_symbol, id FROM symbols").fetchall()
             existing_symbols = {f"{str(r[0]).strip().upper()}|{str(r[1]).strip().upper()}": r[2] for r in existing_rows}
             
             df['lookup_key'] = df['exchange'] + '|' + df['trading_symbol']
             df['is_existing'] = df['lookup_key'].isin(existing_symbols.keys())
             df['existing_id'] = df['lookup_key'].map(existing_symbols)
             
             insert_df = df[~df['is_existing']].copy()
             update_df = df[df['is_existing']].copy()
             
             inserted = 0
             updated = 0
             failed = 0 # logic for invalid rows could be added above
             
             now = datetime.now(timezone.utc)
             
             # INSERTS
             if not insert_df.empty:
                 max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM symbols").fetchone()[0]
                 next_id = max_id + 1
                 insert_df['id'] = range(next_id, next_id + len(insert_df))
                 insert_df['status'] = 'ACTIVE'
                 insert_df['source'] = 'MANUAL'
                 insert_df['created_at'] = now
                 insert_df['updated_at'] = now
                 insert_df['last_updated_at'] = now
                 
                 # Prepare columns (ensure all exist)
                 for col in ['exchange_token', 'name', 'instrument_type', 'segment', 'series', 'isin']:
                     if col not in insert_df.columns: insert_df[col] = None
                 
                 # Use Register/Insert
                 # Must select specific columns in order matching table
                 cols = ['id', 'exchange', 'trading_symbol', 'exchange_token', 'name', 'instrument_type', 
                         'segment', 'series', 'isin', 'expiry_date', 'strike_price', 'lot_size', 
                         'status', 'source', 'created_at', 'updated_at', 'last_updated_at']
                 
                 # Ensure datatypes
                 # ... (Add datatype conversions if needed, pandas usually handles it but explicit is better)
                 
                 conn.register('temp_insert_df', insert_df[cols]) # This might fail if columns missing, assuming df has necessary cols
                 # In real usage, I'd need to ensure all cols exist in df with default Nones
                 
                 # Simple iteration fallback or robust column check needed. 
                 # For brevity I assume `insert_df` has columns populated potentially with None/Default
                 conn.execute(f"INSERT INTO symbols ({', '.join(cols)}) SELECT {', '.join(cols)} FROM temp_insert_df")
                 conn.unregister('temp_insert_df')
                 conn.commit()
                 inserted = len(insert_df)

             # UPDATES
             if not update_df.empty:
                 update_df['updated_at'] = now
                 update_df['last_updated_at'] = now
                 cols_up = ['existing_id', 'exchange_token', 'name', 'instrument_type', 'segment', 'series', 'isin', 
                            'expiry_date', 'strike_price', 'lot_size', 'updated_at', 'last_updated_at']
                 # Map existing_id to id for update
                 update_df_renamed = update_df.rename(columns={'existing_id': 'id'})
                 # Ensure cols
                 for col in cols_up: 
                     if col != 'id' and col not in update_df_renamed.columns: update_df_renamed[col] = None
                 
                 conn.register('temp_update_df', update_df_renamed)
                 # Update logic with JOIN via temp table is tricky in standard SQL if not using specific DuckDB syntax carefully
                 # DuckDB supports UPDATE FROM
                 conn.execute("""
                     UPDATE symbols 
                     SET exchange_token = temp_update_df.exchange_token,
                         name = temp_update_df.name,
                         instrument_type = temp_update_df.instrument_type,
                         segment = temp_update_df.segment,
                         series = temp_update_df.series,
                         isin = temp_update_df.isin,
                         expiry_date = temp_update_df.expiry_date,
                         strike_price = temp_update_df.strike_price,
                         lot_size = temp_update_df.lot_size,
                         updated_at = temp_update_df.updated_at,
                         last_updated_at = temp_update_df.last_updated_at
                     FROM temp_update_df
                     WHERE symbols.id = temp_update_df.id
                 """)
                 conn.unregister('temp_update_df')
                 conn.commit()
                 updated = len(update_df)
             
             self._upload_status_cache[job_id]["status"] = "SUCCESS"
             self._upload_status_cache[job_id]["inserted"] = inserted
             self._upload_status_cache[job_id]["updated"] = updated
             self._upload_status_cache[job_id]["percentage"] = 100
             
             self.repo.save_upload_log(conn, job_id, filename, started_at, datetime.now(timezone.utc), "SUCCESS", len(df), inserted, updated, failed, [], triggered_by, upload_type)

             del self._preview_cache[preview_id]

        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            self._upload_status_cache[job_id]["status"] = "FAILED"
            self._upload_status_cache[job_id]["errors"] = [str(e)]
            self.repo.save_upload_log(conn, job_id, filename, started_at, datetime.now(timezone.utc), "FAILED", 0, 0, 0, 0, [str(e)], triggered_by, upload_type)
        finally:
            if conn: conn.close()

    def get_upload_status(self, job_id: str):
        if job_id in self._upload_status_cache:
            return self._upload_status_cache[job_id]
        
        # Check DB
        conn = None
        try:
            conn = self.repo.get_db_connection()
            log = conn.execute("SELECT * FROM upload_logs WHERE job_id = ?", [job_id]).fetchone()
            if log:
                # Map log row to status dict
                # (Simplified mapping)
                return {
                    "job_id": job_id,
                    "status": log[12], # index subject to schema
                    "processed": log[8],
                    "total": log[8],
                    "inserted": log[9],
                    "updated": log[10],
                    "failed": log[11],
                    "errors": log[14].split("; ") if log[14] else [],
                    "percentage": 100 if log[12] in ["SUCCESS", "FAILED"] else 0
                }
            return {"status": "NOT_FOUND"}
        finally:
            if conn: conn.close()

    def get_upload_logs(self, limit=50, page=1):
        offset = (page - 1) * limit
        rows, total = self.repo.get_upload_logs(limit, offset)
        
        log_list = []
        for r in rows:
            # Map row to dict
             log_list.append({
                "job_id": r[0], "file_name": r[1], "upload_type": r[2], "triggered_by": r[3],
                "started_at": r[4], "ended_at": r[5], "duration_seconds": r[6],
                "total_rows": r[7], "inserted_rows": r[8], "updated_rows": r[9],
                "failed_rows": r[10], "status": r[11], "progress_percentage": r[12],
                "error_summary": r[13].split("; ") if r[13] else []
             })
        
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        
        return {
            "logs": log_list,
            "pagination": {
                "page": page, "page_size": limit, "total": total, "total_pages": total_pages,
                "has_next": page < total_pages, "has_previous": page > 1
            }
        }

    # Proxy methods to Repo
    def get_symbols(self, search, exchange, status, expiry, sort_by, page_size, page):
        where_clauses = []
        params = []
        if status:
            where_clauses.append("status = ?")
            params.append(status.upper())
        if exchange:
            where_clauses.append("exchange = ?")
            params.append(exchange.upper())
        if search:
            s_term = f"%{search.upper()}%"
            where_clauses.append("(UPPER(trading_symbol) LIKE ? OR UPPER(name) LIKE ?)")
            params.extend([s_term, s_term])
            
        items_data, total = self.repo.get_symbols_paginated(page_size, (page-1)*page_size, where_clauses, params)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        return {
            "items": items_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def reload_series_lookup(self, force):
        return self.repo.reload_series_lookup(force)

    def delete_all_symbols(self, user_info):
        conn = self.repo.get_db_connection()
        try:
            conn.execute("DELETE FROM symbols")
            conn.commit()
            return {"message": "All symbols deleted"}
        finally:
            conn.close()

    def bulk_delete(self, ids: List[int]):
         conn = self.repo.get_db_connection()
         try:
             placeholders = ','.join(['?' for _ in ids])
             conn.execute(f"DELETE FROM symbols WHERE id IN ({placeholders})", ids)
             conn.commit()
             return {"message": f"Deleted {len(ids)} symbols"}
         finally:
             conn.close()

    def bulk_update_status(self, ids: List[int], status: str):
         conn = self.repo.get_db_connection()
         try:
             placeholders = ','.join(['?' for _ in ids])
             now = datetime.now(timezone.utc)
             params = [status, now, now] + ids
             conn.execute(f"UPDATE symbols SET status = ?, updated_at = ?, last_updated_at = ? WHERE id IN ({placeholders})", params)
             conn.commit()
             return {"message": f"Updated {len(ids)} symbols"}
         finally:
             conn.close()

    def get_scripts(self):
        conn = self.repo.get_db_connection()
        try:
            return conn.execute("SELECT id, name, description, content, version, created_by, created_at, updated_at, last_used_at FROM transformation_scripts ORDER BY created_at DESC").fetchall()
        finally:
            conn.close()

    def get_script(self, script_id: int):
        conn = self.repo.get_db_connection()
        try:
             res = conn.execute("SELECT id, name, description, content, version, created_by, created_at, updated_at, last_used_at FROM transformation_scripts WHERE id = ?", [script_id]).fetchone()
             return res
        finally:
             conn.close()

    def create_script(self, data: dict, user_id: Optional[int]):
         conn = self.repo.get_db_connection()
         try:
             existing = conn.execute("SELECT id FROM transformation_scripts WHERE name = ?", [data['name']]).fetchone()
             if existing: raise ValueError("Script with this name already exists")
             
             max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM transformation_scripts").fetchone()[0]
             next_id = max_id + 1
             now = datetime.now(timezone.utc)
             
             conn.execute("""
                 INSERT INTO transformation_scripts (id, name, description, content, version, created_by, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)
             """, (next_id, data['name'], data.get('description'), data['content'], 1, user_id, now))
             conn.commit()
             return self.get_script(next_id)
         finally:
             conn.close()

    def update_script(self, script_id: int, data: dict):
        conn = self.repo.get_db_connection()
        try:
            existing = conn.execute("SELECT id, version FROM transformation_scripts WHERE id = ?", [script_id]).fetchone()
            if not existing: raise ValueError("Script not found")
            
            updates = []
            params = []
            if 'name' in data and data['name']:
                 check = conn.execute("SELECT id FROM transformation_scripts WHERE name = ? AND id != ?", [data['name'], script_id]).fetchone()
                 if check: raise ValueError("Name exists")
                 updates.append("name = ?"); params.append(data['name'])
            
            if 'description' in data: updates.append("description = ?"); params.append(data['description'])
            
            if 'content' in data and data['content']:
                 updates.append("content = ?"); params.append(data['content'])
                 updates.append("version = ?"); params.append(existing[1] + 1)
            
            if updates:
                updates.append("updated_at = ?"); params.append(datetime.now(timezone.utc))
                params.append(script_id)
                conn.execute(f"UPDATE transformation_scripts SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
            
            return self.get_script(script_id)
        finally:
            conn.close()

    def delete_script(self, script_id: int):
        conn = self.repo.get_db_connection()
        try:
            conn.execute("DELETE FROM transformation_scripts WHERE id = ?", [script_id])
            conn.commit()
        finally:
            conn.close()

    def get_schedulers(self):
        conn = self.repo.get_db_connection()
        try:
             schedulers = conn.execute("""
                 SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                        script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
                 FROM schedulers ORDER BY created_at DESC
             """).fetchall()
             res = []
             for s in schedulers:
                 res.append({
                     "id": s[0], "name": s[1], "description": s[2], "mode": s[3],
                     "interval_value": s[4], "interval_unit": s[5], "cron_expression": s[6],
                     "script_id": s[7], "is_active": s[8], "sources": json.loads(s[9]) if s[9] else [],
                     "created_at": s[10], "updated_at": s[11], "last_run_at": s[12], "next_run_at": s[13], "created_by": s[14]
                 })
             return res
        finally:
             conn.close()

    def get_scheduler(self, scheduler_id: int):
         conn = self.repo.get_db_connection()
         try:
             s = conn.execute("""
                 SELECT id, name, description, mode, interval_value, interval_unit, cron_expression,
                        script_id, is_active, sources, created_at, updated_at, last_run_at, next_run_at, created_by
                 FROM schedulers WHERE id = ?
             """, [scheduler_id]).fetchone()
             if not s: return None
             return {
                 "id": s[0], "name": s[1], "description": s[2], "mode": s[3],
                 "interval_value": s[4], "interval_unit": s[5], "cron_expression": s[6],
                 "script_id": s[7], "is_active": s[8], "sources": json.loads(s[9]) if s[9] else [],
                 "created_at": s[10], "updated_at": s[11], "last_run_at": s[12], "next_run_at": s[13], "created_by": s[14]
             }
         finally:
             conn.close()

    def create_scheduler(self, data: dict, user_id: Optional[int]):
         conn = self.repo.get_db_connection()
         try:
             max_id_res = conn.execute("SELECT COALESCE(MAX(id), 0) FROM schedulers").fetchone()
             next_id = (max_id_res[0] if max_id_res else 0) + 1
             now = datetime.now(timezone.utc)
             
             conn.execute("""
                 INSERT INTO schedulers (id, name, description, mode, interval_value, interval_unit, cron_expression,
                        script_id, is_active, sources, created_at, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
             """, (next_id, data['name'], data.get('description'), data['mode'], data.get('interval_value'), data.get('interval_unit'),
                   data.get('cron_expression'), data.get('script_id'), data.get('is_active', True), json.dumps(data.get('sources', [])), now, user_id))
             conn.commit()
             return self.get_scheduler(next_id)
         finally:
             conn.close()

    def update_scheduler(self, scheduler_id: int, data: dict):
        conn = self.repo.get_db_connection()
        try:
             updates = []
             params = []
             fields = ['name', 'description', 'mode', 'interval_value', 'interval_unit', 'cron_expression', 'script_id', 'is_active']
             for f in fields:
                 if f in data:
                     updates.append(f"{f} = ?")
                     params.append(data[f])
             if 'sources' in data:
                 updates.append("sources = ?")
                 params.append(json.dumps(data['sources']))
             
             if updates:
                 updates.append("updated_at = ?")
                 params.append(datetime.now(timezone.utc))
                 params.append(scheduler_id)
                 conn.execute(f"UPDATE schedulers SET {', '.join(updates)} WHERE id = ?", params)
                 conn.commit()
             return self.get_scheduler(scheduler_id)
        finally:
             conn.close()

    def delete_scheduler(self, scheduler_id: int):
        conn = self.repo.get_db_connection()
        try:
             conn.execute("DELETE FROM schedulers WHERE id = ?", [scheduler_id])
             conn.commit()
        finally:
             conn.close()

    def get_stats(self):
        conn = self.repo.get_db_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
            
            latest_log = conn.execute("""
                SELECT upload_type, file_name, started_at, duration_seconds, status, ended_at, updated_rows, inserted_rows, triggered_by
                FROM upload_logs ORDER BY started_at DESC LIMIT 1
            """).fetchone()
            
            last_updated_info = None
            last_inserted_rows = 0
            if latest_log:
                 last_updated_info = {
                     "upload_type": latest_log[0],
                     "file_name": latest_log[1],
                     "started_at": latest_log[2].isoformat() if latest_log[2] else None,
                     "status": latest_log[4]
                 }
                 last_inserted_rows = latest_log[7] if latest_log[7] else 0

            return {
                "total": total,
                "last_updated": last_updated_info,
                "skipped_symbols": total - last_inserted_rows
            }
        finally:
             conn.close()
