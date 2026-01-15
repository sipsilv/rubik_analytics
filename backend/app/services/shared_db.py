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

logger = logging.getLogger(__name__)

class SharedDatabase:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.raw_conn = None
        self.listing_conn = None
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

    # Locks for query execution
    listing_lock = threading.Lock()
    raw_lock = threading.Lock()

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

# Global Accessor
def get_shared_db():
    return SharedDatabase.get_instance()
