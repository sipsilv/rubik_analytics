import duckdb
import logging
import os
import threading

# Import paths from existing configs (easiest via importing config loader or hardcoding if consistent)
# We need paths for all DBs that are shared:
# 1. telegram_listing.duckdb (Extractor Reads, Listener Writes - Listener is separate process? No, threaded in worker_manager)
# 2. telegram_raw.duckdb (Extractor Writes, Dedup Writes, Scorer Writes)
# 3. news_scoring.duckdb (Scorer Writes) -> Less contention but good to standardize.

# For now, let's focus on RAW_DB which is the contention point.

from app.services.telegram_extractor.config import OUTPUT_DB_PATH as RAW_DB_PATH
from app.services.telegram_extractor.config import INPUT_DB_PATH as LISTING_DB_PATH
from app.services.news_ai.config import AI_DB_PATH, AI_TABLE
from app.services.news_ai.config import SCORING_DB_PATH

logger = logging.getLogger(__name__)

class SharedDatabase:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.raw_conn = None
        self.listing_conn = None
        self.ai_conn = None
        self.scoring_conn = None
        self.db_lock = threading.Lock() # Protect connection access if needed
        
    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def get_raw_connection(self):
        """
        Returns the shared read-write connection to telegram_raw.duckdb
        """
        with self._lock:
            if self.raw_conn is None:
                logger.info(f"Opening SHARED connection to {RAW_DB_PATH}")
                try:
                    self.raw_conn = duckdb.connect(RAW_DB_PATH)
                except Exception as e:
                    logger.error(f"Failed to open shared DB {RAW_DB_PATH}: {e}")
                    raise
            return self.raw_conn

    def get_listing_connection(self):
        """
        Returns shared read-write connection to listing DB
        """
        with self._lock:
            if self.listing_conn is None:
                logger.info(f"Opening SHARED connection to {LISTING_DB_PATH}")
                try:
                    # Opened as RW so Listener can write and Extractor can migrate
                    self.listing_conn = duckdb.connect(LISTING_DB_PATH, read_only=False)
                except Exception as e:
                     # Fallback if file doesn't exist yet or locked
                     logger.warning(f"Shared Listing DB connect failed: {e}")
                     return None
            return self.listing_conn

    def get_ai_connection(self):
        """
        Returns shared read-write connection to news_ai DB.
        Includes recovery logic for WAL corruption.
        """
        with self._lock:
            if self.ai_conn is None:
                logger.info(f"Opening SHARED connection to {AI_DB_PATH}")
                try:
                    os.makedirs(os.path.dirname(AI_DB_PATH), exist_ok=True)
                    self.ai_conn = duckdb.connect(AI_DB_PATH)
                except Exception as e:
                    err_msg = str(e)
                    if "WAL" in err_msg or "Catalog" in err_msg or "Binder Error" in err_msg:
                        logger.warning(f"Detected AI DB corruption or WAL error: {e}. Attempting recovery...")
                        try:
                            # Close any partial handles
                            if self.ai_conn: self.ai_conn.close()
                            self.ai_conn = None
                            
                            # Move corrupted file and wal to backup
                            import time
                            ts = int(time.time())
                            if os.path.exists(AI_DB_PATH):
                                os.rename(AI_DB_PATH, f"{AI_DB_PATH}.corrupt.{ts}")
                            wal_path = f"{AI_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.rename(wal_path, f"{wal_path}.corrupt.{ts}")
                            
                            logger.info("Corrupted AI DB moved to backup. Creating fresh DB...")
                            self.ai_conn = duckdb.connect(AI_DB_PATH)
                        except Exception as recovery_err:
                            logger.error(f"AI DB Recovery Failed: {recovery_err}")
                            raise
                    else:
                        logger.error(f"Failed to open shared AI DB {AI_DB_PATH}: {e}")
                        raise
            return self.ai_conn

    def get_scoring_connection(self):
        """
        Returns shared read-write connection to news_scoring DB.
        Includes recovery logic for WAL corruption.
        """
        with self._lock:
            if self.scoring_conn is None:
                logger.info(f"Opening SHARED connection to {SCORING_DB_PATH}")
                try:
                    os.makedirs(os.path.dirname(SCORING_DB_PATH), exist_ok=True)
                    self.scoring_conn = duckdb.connect(SCORING_DB_PATH)
                except Exception as e:
                    err_msg = str(e)
                    if "WAL" in err_msg or "Catalog" in err_msg or "Binder Error" in err_msg:
                        logger.warning(f"Detected Scoring DB corruption or WAL error: {e}. Attempting recovery...")
                        try:
                            if self.scoring_conn: self.scoring_conn.close()
                            self.scoring_conn = None
                            
                            import time
                            ts = int(time.time())
                            if os.path.exists(SCORING_DB_PATH):
                                os.rename(SCORING_DB_PATH, f"{SCORING_DB_PATH}.corrupt.{ts}")
                            wal_path = f"{SCORING_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.rename(wal_path, f"{wal_path}.corrupt.{ts}")
                            
                            logger.info("Corrupted Scoring DB moved to backup. Creating fresh DB...")
                            self.scoring_conn = duckdb.connect(SCORING_DB_PATH)
                        except Exception as recovery_err:
                            logger.error(f"Scoring DB Recovery Failed: {recovery_err}")
                            raise
                    else:
                        logger.error(f"Failed to open shared Scoring DB {SCORING_DB_PATH}: {e}")
                        raise
            return self.scoring_conn

    # Locks for query execution
    listing_lock = threading.Lock()
    raw_lock = threading.Lock()
    ai_lock = threading.Lock()
    scoring_lock = threading.Lock()

    def run_listing_query(self, query, params=None, fetch='none'):
        """
        Executes a query on the listing DB with thread safety.
        fetch: 'all', 'one', 'none'
        """
        with self.listing_lock:
            conn = self.get_listing_connection()
            if not conn:
                raise Exception("Listing Database Connection not available")
            
            try:
                # cursor() is not strictly needed for DuckDB conn.execute, but safer for some drivers
                # We use conn.execute directly as per DuckDB python api
                result = conn.execute(query, params if params is not None else [])
                
                if fetch == 'all':
                    return result.fetchall()
                elif fetch == 'one':
                    return result.fetchone()
                else:
                    return None
            except Exception as e:
                logger.error(f"Listing DB Query Failed: {e}")
                raise

    def run_raw_query(self, query, params=None, fetch='none'):
        """
        Executes a query on the raw DB with thread safety.
        fetch: 'all', 'one', 'none'
        """
        with self.raw_lock:
            conn = self.get_raw_connection()
            if not conn:
                raise Exception("Raw Database Connection not available")
            
            try:
                result = conn.execute(query, params if params is not None else [])
                
                if fetch == 'all':
                    return result.fetchall()
                elif fetch == 'one':
                    return result.fetchone()
                else:
                    return None
            except Exception as e:
                logger.error(f"Raw DB Query Failed: {e}")
                raise

    def run_ai_query(self, query, params=None, fetch='none'):
        """Executes a query on the AI DB with thread safety."""
        with self.ai_lock:
            conn = self.get_ai_connection()
            try:
                result = conn.execute(query, params if params is not None else [])
                if fetch == 'all': return result.fetchall()
                elif fetch == 'one': return result.fetchone()
                else: return None
            except Exception as e:
                logger.error(f"AI DB Query Failed: {e}")
                raise

    def run_scoring_query(self, query, params=None, fetch='none'):
        """Executes a query on the Scoring DB with thread safety."""
        with self.scoring_lock:
            conn = self.get_scoring_connection()
            try:
                result = conn.execute(query, params if params is not None else [])
                if fetch == 'all': return result.fetchall()
                elif fetch == 'one': return result.fetchone()
                else: return None
            except Exception as e:
                logger.error(f"Scoring DB Query Failed: {e}")
                raise

    def run_pipeline_cleanup(self, hours=24):
        """Unified cleanup for the entire news pipeline."""
        logger.info(f"Starting pipeline-wide cleanup (older than {hours} hours)...")
        try:
            # 1. Extraction (telegram_raw)
            with self.raw_lock:
                conn = self.get_raw_connection()
                from app.services.telegram_extractor.config import OUTPUT_TABLE as RAW_TABLE
                conn.execute(f"DELETE FROM {RAW_TABLE} WHERE received_at < CURRENT_TIMESTAMP - INTERVAL '{hours}' HOUR")

            # 2. Scoring (news_scoring)
            with self.scoring_lock:
                conn = self.get_scoring_connection()
                from app.services.news_scoring.config import SCORING_TABLE
                conn.execute(f"DELETE FROM {SCORING_TABLE} WHERE scored_at < CURRENT_TIMESTAMP - INTERVAL '{hours}' HOUR")

            # 3. AI Enrichment (news_ai & ai_queue)
            with self.ai_lock:
                conn = self.get_ai_connection()
                # news_ai
                conn.execute(f"DELETE FROM {AI_TABLE} WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '{hours}' HOUR")
                # ai_queue
                conn.execute(f"DELETE FROM ai_queue WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '{hours}' HOUR")

            logger.info("Pipeline-wide cleanup completed successfully.")
        except Exception as e:
            logger.error(f"Pipeline cleanup failed: {e}")

    def close_all(self):
        with self._lock:
            # Acquire operation locks too to ensure no query is running
            with self.raw_lock:
                if self.raw_conn:
                    try:
                        self.raw_conn.close()
                    except:
                        pass
                    self.raw_conn = None
            
            with self.listing_lock:
                if self.listing_conn:
                    try:
                        self.listing_conn.close()
                    except:
                        pass
                    self.listing_conn = None
            
            with self.ai_lock:
                if self.ai_conn:
                    try:
                        self.ai_conn.close()
                    except:
                        pass
                    self.ai_conn = None

            with self.scoring_lock:
                if self.scoring_conn:
                    try:
                        self.scoring_conn.close()
                    except:
                        pass
                    self.scoring_conn = None

# Global Accessor
def get_shared_db():
    return SharedDatabase.get_instance()
