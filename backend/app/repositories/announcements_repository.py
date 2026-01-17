import os
import duckdb
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class AnnouncementsRepository:
    _init_lock = threading.Lock()
    _initialized = False

    def __init__(self):
        self.data_dir = os.path.abspath(settings.DATA_DIR)
        self.db_dir = os.path.join(self.data_dir, "Company Fundamentals")
        self.db_path = os.path.join(self.db_dir, "corporate_announcements.duckdb")
        os.makedirs(self.db_dir, exist_ok=True)
        self.ensure_initialized()

    def get_connection(self):
        """Get DuckDB connection"""
        try:
            conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
            conn.execute("PRAGMA enable_progress_bar=false")
            return conn
        except Exception as e:
            logger.error(f"Error connecting to announcements database: {e}")
            # Retry initialization
            self._initialized = False
            self.ensure_initialized()
            conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
            conn.execute("PRAGMA enable_progress_bar=false")
            return conn

    def ensure_initialized(self):
        if self._initialized: return
        with self._init_lock:
            if self._initialized: return
            try:
                conn = duckdb.connect(self.db_path, config={'allow_unsigned_extensions': True})
                conn.execute("PRAGMA enable_progress_bar=false")
                
                # Check table
                exists = False
                try:
                    res = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'corporate_announcements'").fetchall()
                    if res: exists = True
                except: pass
                
                if not exists:
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
                    conn.execute("CREATE TABLE IF NOT EXISTS descriptor_metadata (descriptor_id INTEGER PRIMARY KEY, descriptor_name VARCHAR NOT NULL, descriptor_category VARCHAR, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)")
                    
                    # Indexes
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_date ON corporate_announcements(trade_date DESC)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_nse ON corporate_announcements(symbol_nse)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_bse ON corporate_announcements(symbol_bse)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_name ON corporate_announcements(company_name)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_descriptor_id ON corporate_announcements(descriptor_id)")
                
                conn.close()
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to init announcements DB: {e}")

    def insert_announcement(self, announcement: Dict[str, Any]) -> bool:
        if not announcement.get("id"): return False
        conn = self.get_connection()
        try:
            # Duplicate checks
            if announcement.get("company_name") and announcement.get("news_headline"):
                 c_name = str(announcement["company_name"]).strip().lower()
                 headline = str(announcement["news_headline"]).strip().lower()
                 exist = conn.execute("SELECT id FROM corporate_announcements WHERE LOWER(TRIM(company_name)) = ? AND LOWER(TRIM(news_headline)) = ?", [c_name, headline]).fetchone()
                 if exist: return False

            exist_id = conn.execute("SELECT id FROM corporate_announcements WHERE id = ?", [announcement["id"]]).fetchone()
            if exist_id: return False

            conn.execute("""
                INSERT INTO corporate_announcements (
                    id, trade_date, script_code, symbol_nse, symbol_bse,
                    company_name, file_status, news_headline, news_subhead,
                    news_body, descriptor_id, announcement_type, meeting_type,
                    date_of_meeting
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                announcement.get("id"), announcement.get("trade_date"), announcement.get("script_code"),
                announcement.get("symbol_nse"), announcement.get("symbol_bse"), announcement.get("company_name"),
                announcement.get("file_status"), announcement.get("news_headline"), announcement.get("news_subhead"),
                announcement.get("news_body"), announcement.get("descriptor_id"), announcement.get("announcement_type"),
                announcement.get("meeting_type"), announcement.get("date_of_meeting")
            ])
            conn.commit()
            return True
        finally:
            conn.close()

    def get_announcements(self, from_date=None, to_date=None, symbol=None, search=None, limit=None, offset=0) -> Tuple[List[Dict], int]:
        conn = self.get_connection()
        try:
            where = ["1=1"]
            params = []
            c_params = []
            
            if from_date:
                where.append("trade_date >= ?")
                params.append(from_date)
                c_params.append(from_date)
            if to_date:
                where.append("trade_date <= ?")
                params.append(to_date + " 23:59:59")
                c_params.append(to_date + " 23:59:59")
            if symbol:
                s = symbol.lower().strip()
                pat = f"%{s}%"
                where.append("(LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ? OR LOWER(company_name) LIKE ?)")
                params.extend([pat, pat, pat, pat])
                c_params.extend([pat, pat, pat, pat])
            if search:
                s = search.lower().strip()
                pat = f"%{s}%"
                where.append("(LOWER(news_headline) LIKE ? OR LOWER(symbol_nse) LIKE ? OR LOWER(symbol_bse) LIKE ? OR CAST(script_code AS VARCHAR) LIKE ?)")
                params.extend([pat, pat, pat, pat])
                c_params.extend([pat, pat, pat, pat])

            where_clause = " AND ".join(where)
            
            count = conn.execute(f"SELECT COUNT(*) FROM corporate_announcements WHERE {where_clause}", c_params).fetchone()[0]
            
            limit_clause = ""
            if limit:
                limit_clause = "LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            query = f"""
                SELECT id, trade_date, script_code, symbol_nse, symbol_bse,
                       company_name, file_status, news_headline, news_subhead,
                       descriptor_id, announcement_type, meeting_type,
                       date_of_meeting, created_at, updated_at
                FROM corporate_announcements
                WHERE {where_clause}
                ORDER BY trade_date DESC
                {limit_clause}
            """
            
            cursor = conn.execute(query, params)
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            
            res = []
            for r in rows:
                d = dict(zip(cols, r))
                for k in ["trade_date", "date_of_meeting", "created_at", "updated_at"]:
                     if d.get(k): d[k] = d[k].isoformat() if hasattr(d[k], 'isoformat') else str(d[k])
                res.append(d)
            
            return res, count
        finally:
            conn.close()

    def get_announcement(self, id: str):
        conn = self.get_connection()
        try:
            r = conn.execute("SELECT * FROM corporate_announcements WHERE id = ?", [id]).fetchone()
            if not r: return None
            desc = conn.description
            cols = [d[0] for d in desc]
            d = dict(zip(cols, r))
            for k in ["trade_date", "date_of_meeting", "created_at", "updated_at"]:
                 if d.get(k) and hasattr(d[k], 'isoformat'): d[k] = d[k].isoformat()
            return d
        finally:
            conn.close()

    def update_attachment(self, id: str, data: bytes, ctype: str):
        conn = self.get_connection()
        try:
            conn.execute("UPDATE corporate_announcements SET attachment_data = ?, attachment_content_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [data, ctype, id])
            conn.commit()
            return True
        finally:
            conn.close()

    def get_attachment(self, id: str):
        conn = self.get_connection()
        try:
            r = conn.execute("SELECT attachment_data, attachment_content_type FROM corporate_announcements WHERE id = ?", [id]).fetchone()
            if r and r[0]: return {'data': r[0], 'content_type': r[1]}
            return None
        finally:
            conn.close()

    def get_descriptor_metadata(self, descriptor_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            r = conn.execute("SELECT * FROM descriptor_metadata WHERE descriptor_id = ?", [descriptor_id]).fetchone()
            if not r: return None
            return {"descriptor_id": r[0], "descriptor_name": r[1], "descriptor_category": r[2], "updated_at": r[3].isoformat() if r[3] else None}
        finally:
            conn.close()

    def get_descriptor_metadata_batch(self, descriptor_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not descriptor_ids: return {}
        conn = self.get_connection()
        try:
            placeholders = ','.join(['?' for _ in descriptor_ids])
            rows = conn.execute(f"SELECT descriptor_id, descriptor_name, descriptor_category, updated_at FROM descriptor_metadata WHERE descriptor_id IN ({placeholders})", descriptor_ids).fetchall()
            res = {}
            for r in rows:
                res[r[0]] = {"descriptor_id": r[0], "descriptor_name": r[1], "descriptor_category": r[2], "updated_at": r[3].isoformat() if r[3] else None}
            return res
        finally:
            conn.close()
            
    def cache_descriptor_metadata(self, descriptors: List[Dict[str, Any]]):
        conn = self.get_connection()
        try:
            for d in descriptors:
                conn.execute(
                    "INSERT OR REPLACE INTO descriptor_metadata (descriptor_id, descriptor_name, descriptor_category, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    [d.get("descriptor_id"), d.get("descriptor_name"), d.get("descriptor_category")]
                )
            conn.commit()
        finally:
            conn.close()
