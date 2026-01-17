import duckdb
import logging
import os
import threading
import time

# Import paths from existing configs (easiest via importing config loader or hardcoding if consistent)
# We need paths for all DBs that are shared:
# 1. telegram_listing.duckdb (Extractor Reads, Listener Writes - Listener is separate process? No, threaded in worker_manager)
# 2. telegram_raw.duckdb (Extractor Writes, Dedup Writes, Scorer Writes)
# 3. news_scoring.duckdb (Scorer Writes) -> Less contention but good to standardize.

# For now, let's focus on RAW_DB which is the contention point.

from app.services.telegram_extractor.config import OUTPUT_DB_PATH as RAW_DB_PATH
from app.services.telegram_extractor.config import INPUT_DB_PATH as LISTING_DB_PATH
from app.services.news_ai.config import AI_DB_PATH, AI_TABLE, FINAL_DB_PATH
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
        self.final_conn = None
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
        Includes recovery logic for WAL corruption.
        """
        with self._lock:
            if self.raw_conn is None:
                logger.info(f"Opening SHARED connection to {RAW_DB_PATH}")
                try:
                    os.makedirs(os.path.dirname(RAW_DB_PATH), exist_ok=True)
                    self.raw_conn = duckdb.connect(RAW_DB_PATH, read_only=False)
                except Exception as e:
                    err_msg = str(e)
                    # Check for Lock Error (Concurrent access)
                    if "lock" in err_msg.lower() or "resource temporarily unavailable" in err_msg.lower():
                        logger.warning(f"Raw DB is locked. Falling back to READ-ONLY mode.")
                        try:
                            self.raw_conn = duckdb.connect(RAW_DB_PATH, read_only=True)
                            return self.raw_conn
                        except Exception as ro_err:
                            logger.error(f"Failed to open Raw DB in Read-Only mode: {ro_err}")
                            raise ro_err
                    
                    # Self-Healing for WAL/Binder Errors (Catalog does not exist)
                    if "binder error" in err_msg.lower() and "catalog" in err_msg.lower() and "does not exist" in err_msg.lower():
                        logger.warning(f"Detected inconsistent WAL for Raw DB. Attempting self-healing recovery...")
                        try:
                            wal_path = f"{RAW_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                                logger.info(f"Deleted inconsistent WAL: {wal_path}")
                            # Retry connection
                            self.raw_conn = duckdb.connect(RAW_DB_PATH, read_only=False)
                            logger.info("Self-healing Raw DB connection successful.")
                            return self.raw_conn
                        except Exception as retry_err:
                            logger.error(f"Self-healing Raw DB recovery failed: {retry_err}")
                            raise e

                    if "corrupt" in err_msg.lower() or "wal" in err_msg.lower():
                        logger.error(f"Detected Raw DB corruption signal: {e}. AUTO-RECOVERY DISABLED.")
                        raise e
                    else:
                        logger.error(f"Failed to open shared Raw DB {RAW_DB_PATH}: {e}")
                        raise e
            return self.raw_conn

    def get_listing_connection(self):
        """
        Returns shared read-write connection to listing DB
        """
        with self._lock:
            if self.listing_conn is None:
                logger.info(f"Opening SHARED connection to {LISTING_DB_PATH}")
                try:
                    os.makedirs(os.path.dirname(LISTING_DB_PATH), exist_ok=True)
                    # Opened as RW so Listener can write and Extractor can migrate
                    self.listing_conn = duckdb.connect(LISTING_DB_PATH, read_only=False)
                    self.listing_conn.execute("PRAGMA checkpoint_threshold='10MB'")
                except Exception as e:
                    err_msg = str(e)
                    if "lock" in err_msg.lower() or "resource temporarily unavailable" in err_msg.lower():
                        logger.warning(f"Listing DB is locked. Falling back to READ-ONLY mode.")
                        try:
                            self.listing_conn = duckdb.connect(LISTING_DB_PATH, read_only=True)
                            return self.listing_conn
                        except Exception as ro_err:
                            logger.error(f"Failed to open Listing DB in Read-Only mode: {ro_err}")
                            raise ro_err

                    # Self-Healing for WAL/Binder Errors (Catalog does not exist)
                    if "binder error" in err_msg.lower() and "catalog" in err_msg.lower() and "does not exist" in err_msg.lower():
                        logger.warning(f"Detected inconsistent WAL for Listing DB. Attempting self-healing recovery...")
                        try:
                            wal_path = f"{LISTING_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                                logger.info(f"Deleted inconsistent WAL: {wal_path}")
                            # Retry connection
                            self.listing_conn = duckdb.connect(LISTING_DB_PATH, read_only=False)
                            logger.info("Self-healing Listing DB connection successful.")
                            return self.listing_conn
                        except Exception as retry_err:
                            logger.error(f"Self-healing Listing DB recovery failed: {retry_err}")
                            raise e

                    if "corrupt" in err_msg.lower() or "wal" in err_msg.lower():
                         logger.error(f"Detected Listing DB corruption signal: {e}. AUTO-RECOVERY DISABLED.")
                         raise e
                    else:
                        logger.warning(f"Shared Listing DB connect failed: {e}")
                        raise e
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
                    self.ai_conn = duckdb.connect(AI_DB_PATH, read_only=False)
                except Exception as e:
                    err_msg = str(e)
                    if "lock" in err_msg.lower() or "resource temporarily unavailable" in err_msg.lower():
                        logger.warning(f"AI DB is locked. Falling back to READ-ONLY mode.")
                        try:
                            self.ai_conn = duckdb.connect(AI_DB_PATH, read_only=True)
                            return self.ai_conn
                        except Exception as ro_err:
                            logger.error(f"Failed to open AI DB in Read-Only mode: {ro_err}")
                            raise ro_err
                    
                    # Self-Healing for WAL/Binder Errors (Catalog does not exist)
                    if "binder error" in err_msg.lower() and "catalog" in err_msg.lower() and "does not exist" in err_msg.lower():
                        logger.warning(f"Detected inconsistent WAL for AI DB. Attempting self-healing recovery...")
                        try:
                            wal_path = f"{AI_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                                logger.info(f"Deleted inconsistent WAL: {wal_path}")
                            # Retry connection
                            self.ai_conn = duckdb.connect(AI_DB_PATH, read_only=False)
                            logger.info("Self-healing AI DB connection successful.")
                            return self.ai_conn
                        except Exception as retry_err:
                            logger.error(f"Self-healing AI DB recovery failed: {retry_err}")
                            raise e

                    if "corrupt" in err_msg.lower() or "wal" in err_msg.lower():
                        logger.error(f"Detected AI DB corruption signal: {e}. AUTO-RECOVERY DISABLED.")
                        raise e
                    else:
                        logger.error(f"Failed to open shared AI DB {AI_DB_PATH}: {e}")
                        raise e
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
                    self.scoring_conn = duckdb.connect(SCORING_DB_PATH, read_only=False)
                except Exception as e:
                    err_msg = str(e)
                    if "lock" in err_msg.lower() or "resource temporarily unavailable" in err_msg.lower():
                        logger.warning(f"Scoring DB is locked. Falling back to READ-ONLY mode.")
                        try:
                            self.scoring_conn = duckdb.connect(SCORING_DB_PATH, read_only=True)
                            return self.scoring_conn
                        except Exception as ro_err:
                            logger.error(f"Failed to open Scoring DB in Read-Only mode: {ro_err}")
                            raise ro_err

                    # Self-Healing for WAL/Binder Errors (Catalog does not exist)
                    if "binder error" in err_msg.lower() and "catalog" in err_msg.lower() and "does not exist" in err_msg.lower():
                        logger.warning(f"Detected inconsistent WAL for Scoring DB. Attempting self-healing recovery...")
                        try:
                            wal_path = f"{SCORING_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                                logger.info(f"Deleted inconsistent WAL: {wal_path}")
                            # Retry connection
                            self.scoring_conn = duckdb.connect(SCORING_DB_PATH, read_only=False)
                            logger.info("Self-healing Scoring DB connection successful.")
                            return self.scoring_conn
                        except Exception as retry_err:
                            logger.error(f"Self-healing Scoring DB recovery failed: {retry_err}")
                            raise e

                    if "corrupt" in err_msg.lower() or "wal" in err_msg.lower():
                        logger.error(f"Detected Scoring DB corruption signal: {e}. AUTO-RECOVERY DISABLED.")
                        raise e
                    else:
                        logger.error(f"Failed to open shared Scoring DB {SCORING_DB_PATH}: {e}")
                        raise e
            return self.scoring_conn

    def get_final_connection(self):
        """
        Returns shared connection to final_news DB.
        Attempts Read-Write first. If locked, falls back to Read-Only.
        Only triggers recovery if actual corruption is detected.
        """
        with self._lock:
            if self.final_conn is None:
                logger.info(f"Opening SHARED connection to {FINAL_DB_PATH}")
                try:
                    os.makedirs(os.path.dirname(FINAL_DB_PATH), exist_ok=True)
                    self.final_conn = duckdb.connect(FINAL_DB_PATH, read_only=False)
                except Exception as e:
                    err_msg = str(e)
                    # Check for Lock Error (Concurrent access)
                    if "lock" in err_msg.lower() or "resource temporarily unavailable" in err_msg.lower():
                        logger.warning(f"Final DB is locked by another process. Falling back to READ-ONLY mode.")
                        try:
                            self.final_conn = duckdb.connect(FINAL_DB_PATH, read_only=True)
                            return self.final_conn
                        except Exception as ro_err:
                            logger.error(f"Failed to open Final DB in Read-Only mode: {ro_err}")
                            raise ro_err

                    # Self-Healing for WAL/Binder Errors (Catalog does not exist)
                    if "binder error" in err_msg.lower() and "catalog" in err_msg.lower() and "does not exist" in err_msg.lower():
                        logger.warning(f"Detected inconsistent WAL for Final DB. Attempting self-healing recovery...")
                        try:
                            wal_path = f"{FINAL_DB_PATH}.wal"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                                logger.info(f"Deleted inconsistent WAL: {wal_path}")
                            # Retry connection
                            self.final_conn = duckdb.connect(FINAL_DB_PATH, read_only=False)
                            logger.info("Self-healing Final DB connection successful.")
                            return self.final_conn
                        except Exception as retry_err:
                            logger.error(f"Self-healing Final DB recovery failed: {retry_err}")
                            raise e

                    # Strict Corruption Check
                    # Only recover if explicitly corrupt, not just "WAL" in path
                    is_corrupt = False
                    if "corrupt" in err_msg.lower() or "mismatch" in err_msg.lower() or "not a duckdb file" in err_msg.lower():
                        is_corrupt = True
                    elif ("WAL" in err_msg or "Binder Error" in err_msg) and "lock" not in err_msg.lower():
                        # Ambiguous legacy check - be careful
                        # If it mentions WAL but not Lock, implies WAL issues
                        is_corrupt = True
                    
                    if is_corrupt:
                        logger.error(f"Detected Final DB corruption signal: {e}. AUTO-RECOVERY DISABLED to protect data.")
                        # Disable auto-recovery to prevent looping wipes
                        # try:
                        #     if self.final_conn: self.final_conn.close()
                        #     self.final_conn = None
                        #     import time
                        #     ts = int(time.time())
                        #     if os.path.exists(FINAL_DB_PATH):
                        #         os.rename(FINAL_DB_PATH, f"{FINAL_DB_PATH}.corrupt.{ts}")
                        #     wal_path = f"{FINAL_DB_PATH}.wal"
                        #     if os.path.exists(wal_path):
                        #         os.rename(wal_path, f"{wal_path}.corrupt.{ts}")
                        #     logger.info("Corrupted Final DB moved to backup. Creating fresh DB...")
                        #     self.final_conn = duckdb.connect(FINAL_DB_PATH)
                        # except Exception as recovery_err:
                        #     logger.error(f"Final DB Recovery Failed: {recovery_err}")
                        raise e
                    else:
                        # Genuine other error
                        logger.error(f"Failed to open shared Final DB {FINAL_DB_PATH}: {e}")
                        raise
            return self.final_conn

    # Locks for query execution
    listing_lock = threading.Lock()
    raw_lock = threading.Lock()
    ai_lock = threading.Lock()
    scoring_lock = threading.Lock()
    final_lock = threading.Lock()

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
                err_msg = str(e).lower()
                if "does not exist" in err_msg and "catalog" in err_msg:
                    logger.info("Listing DB Query: Table not found (expected during startup)")
                else:
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
                err_msg = str(e).lower()
                if "does not exist" in err_msg and "catalog" in err_msg:
                    logger.info("Raw DB Query: Table not found (expected during startup)")
                else:
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
                err_msg = str(e).lower()
                if "does not exist" in err_msg and "catalog" in err_msg:
                    logger.info("AI DB Query: Table not found (expected during startup)")
                else:
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
                err_msg = str(e).lower()
                if "does not exist" in err_msg and "catalog" in err_msg:
                    logger.info("Scoring DB Query: Table not found (expected during startup)")
                else:
                    logger.error(f"Scoring DB Query Failed: {e}")
                raise

    def run_final_query(self, query, params=None, fetch='none'):
        """Executes a query on the Final DB with thread safety."""
        with self.final_lock:
            conn = self.get_final_connection()
            try:
                result = conn.execute(query, params if params is not None else [])
                if fetch == 'all': return result.fetchall()
                elif fetch == 'one': return result.fetchone()
                else: return None
            except Exception as e:
                err_msg = str(e).lower()
                if "does not exist" in err_msg and "catalog" in err_msg:
                    logger.info("Final DB Query: Table not found (expected during startup)")
                else:
                    logger.error(f"Final DB Query Failed: {e}")
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

            with self.final_lock:
                if self.final_conn:
                    try:
                        self.final_conn.close()
                    except:
                        pass
                    self.final_conn = None

# Global Accessor
def get_shared_db():
    return SharedDatabase.get_instance()
