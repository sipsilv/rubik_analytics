import duckdb
import logging
from .config import RAW_DB_PATH, RAW_TABLE
from app.providers.shared_db import get_shared_db

logger = logging.getLogger(__name__)

def get_db():
    return get_shared_db()

def ensure_schema():
    """
    Ensures telegram_raw table has deduplication columns.
    """
    db = get_db()
    try:
        # 1. Fetch existing columns
        try:
            # Check if table exists using information_schema
            table_exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{RAW_TABLE}'", fetch='one')
            if not table_exists or table_exists[0] == 0:
                logger.info(f"Table {RAW_TABLE} does not exist yet. Skipping migration.")
                return

            cols = db.run_raw_query(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{RAW_TABLE}'", fetch='all')
            if cols:
                col_names = [c[0] for c in cols]
            else:
                return # Should have been caught by table_exists but safe check
        except Exception as e:
            logger.warning(f"Could not check schema for {RAW_TABLE}: {e}")
            return

        # 2. Add columns if missing
        columns_to_add = [
            ('content_hash', 'TEXT'),
            ('is_duplicate', 'BOOLEAN DEFAULT FALSE'),
            ('duplicate_of_raw_id', 'BIGINT'),
            ('deduped_at', 'TIMESTAMP'),
            ('is_scored', 'BOOLEAN DEFAULT FALSE'),
            ('file_id', 'TEXT')
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in col_names:
                try:
                    db.run_raw_query(f"ALTER TABLE {RAW_TABLE} ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Added column {col_name} to {RAW_TABLE}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to add column {col_name}: {e}")

    except Exception as e:
        logger.error(f"Schema Migration Error: {e}")

def get_unprocessed_rows(limit=50):
    """
    Fetch rows that haven't been deduped yet.
    """
    db = get_db()
    try:
        # Check if telegram_raw exists first to avoid Catalog Error during startup
        try:
            raw_exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{RAW_TABLE}'", fetch='one')
            if not raw_exists or raw_exists[0] == 0:
                logger.info(f"Table '{RAW_TABLE}' not found yet. Skipping unprocessed rows fetch.")
                return []
        except Exception:
            return []

        query = f"""
            SELECT raw_id, normalized_text, file_id, received_at 
            FROM {RAW_TABLE} 
            WHERE deduped_at IS NULL 
            ORDER BY received_at ASC 
            LIMIT ?
        """
        return db.run_raw_query(query, [limit], fetch='all')
    except Exception as e:
        if "does not exist" in str(e).lower():
            return []
        logger.error(f"Error fetching unprocessed rows: {e}")
        return []

def check_exact_duplicate(content_hash, lookback_hours=24):
    """
    Check for existing hash within the lookback window.
    Returns raw_id of the duplicate source if found, else None.
    """
    db = get_db()
    try:
        query = f"""
            SELECT raw_id 
            FROM {RAW_TABLE} 
            WHERE content_hash = ? 
              AND received_at >= (CURRENT_TIMESTAMP - INTERVAL '{lookback_hours} HOURS')
            ORDER BY raw_id ASC 
            LIMIT 1
        """
        result = db.run_raw_query(query, [content_hash], fetch='one')
        return result[0] if result else None
    except Exception as e:
        if "does not exist" in str(e).lower():
            return None
        logger.error(f"Error checking exact duplicate: {e}")
        return None

def get_recent_non_duplicates(limit=200, lookback_hours=24):
    """
    Fetch recent non-duplicate rows for similarity checking.
    """
    db = get_db()
    try:
        query = f"""
            SELECT raw_id, normalized_text 
            FROM {RAW_TABLE} 
            WHERE is_duplicate = FALSE 
              AND deduped_at IS NOT NULL
              AND received_at >= (CURRENT_TIMESTAMP - INTERVAL '{lookback_hours} HOURS')
            ORDER BY received_at DESC 
            LIMIT ?
        """
        return db.run_raw_query(query, [limit], fetch='all')
    except Exception as e:
        if "does not exist" in str(e).lower():
            return []
        logger.error(f"Error fetching recent non-duplicates: {e}")
        return []

def update_deduplication_status(raw_id, content_hash, is_duplicate, duplicate_of_raw_id=None):
    """
    Update row with deduplication result.
    """
    db = get_db()
    try:
        db.run_raw_query(f"""
            UPDATE {RAW_TABLE} 
            SET content_hash = ?, 
                is_duplicate = ?, 
                duplicate_of_raw_id = ?, 
                deduped_at = CURRENT_TIMESTAMP 
            WHERE raw_id = ?
        """, [content_hash, is_duplicate, duplicate_of_raw_id, raw_id])
    except Exception as e:
        logger.error(f"Error updating deduplication status: {e}")
