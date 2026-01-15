import duckdb
import logging
from .config import INPUT_DB_PATH, OUTPUT_DB_PATH, INPUT_TABLE, OUTPUT_TABLE
from app.services.shared_db import get_shared_db

logger = logging.getLogger(__name__)

def get_db():
    return get_shared_db()

def ensure_schema():
    """
    Ensures input table has tracking columns and output table exists.
    """
    db = get_shared_db()
    
    # 1. Input DB Migration
    # Use shared connection to avoid file locking
    try:
        try:
            # Check if columns exist
            cols = db.run_listing_query(f"DESCRIBE {INPUT_TABLE}", fetch='all')
            if cols:
                col_names = [c[0] for c in cols]
                
                if 'is_extracted' not in col_names:
                    try:
                        logger.info(f"Migrating {INPUT_TABLE}: Adding is_extracted column")
                        db.run_listing_query(f"ALTER TABLE {INPUT_TABLE} ADD COLUMN is_extracted BOOLEAN DEFAULT FALSE")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to add is_extracted: {e}")
                    
                if 'extracted_at' not in col_names:
                    try:
                        logger.info(f"Migrating {INPUT_TABLE}: Adding extracted_at column")
                        db.run_listing_query(f"ALTER TABLE {INPUT_TABLE} ADD COLUMN extracted_at TIMESTAMP")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to add extracted_at: {e}")
        except Exception as e:
            logger.error(f"Input DB Schema Migration error: {e}")
    except Exception as e:
        logger.warning(f"Input DB Schema Migration skipped: {e}")

    # 2. Output DB Creation
    try:
        db.run_raw_query(f"CREATE SEQUENCE IF NOT EXISTS seq_raw_id START 1;")
        query = f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            raw_id BIGINT DEFAULT nextval('seq_raw_id') PRIMARY KEY,
            listing_id BIGINT,
            telegram_chat_id TEXT,
            telegram_msg_id TEXT,
            source_handle TEXT,
            telegram_text TEXT,
            caption_text TEXT,
            link_text TEXT,
            image_ocr_text TEXT,
            combined_text TEXT,
            normalized_text TEXT,
            file_id TEXT,
            received_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.run_raw_query(query)
    except Exception as e:
        logger.error(f"Output DB Creation Error: {e}")
        # raise # Dont raise if table exists
    finally:
        pass # Shared connection, do not close

def mark_extracted(listing_id):
    """
    Updates the input table to mark a row as extracted.
    """
    # Use Shared DB to avoid locking issues!
    try:
        db = get_shared_db()
        db.run_listing_query(f"""
            UPDATE {INPUT_TABLE} 
            SET is_extracted = TRUE, extracted_at = CURRENT_TIMESTAMP 
            WHERE listing_id = ?
        """, [listing_id])
    except Exception as e:
        logger.error(f"Failed to mark extracted {listing_id}: {e}")

def get_global_stats():
    """
    Returns dict with stats: total, processed, pending.
    Uses SharedDatabase to avoid connection conflicts.
    """
    try:
        db = get_shared_db()
        
        # Check if table exists (listener might not have run yet)
        try:
            total = db.run_listing_query(f"SELECT COUNT(*) FROM {INPUT_TABLE}", fetch='one')[0]
            processed = db.run_listing_query(f"SELECT COUNT(*) FROM {INPUT_TABLE} WHERE is_extracted = TRUE", fetch='one')[0]
            pending = total - processed
            
            try:
                duplicates = db.run_raw_query(f"SELECT COUNT(*) FROM {OUTPUT_TABLE} WHERE is_duplicate = TRUE", fetch='one')[0]
            except Exception:
                duplicates = 0
                
        except Exception:
            return {"total": 0, "processed": 0, "pending": 0, "duplicates": 0}
            
        return {
            "total": total,
            "processed": processed,
            "pending": pending,
            "duplicates": duplicates
        }
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        return {"total": 0, "processed": 0, "pending": 0, "duplicates": 0}

def get_recent_extractions(limit=50):
    """
    Fetch recent extracted rows for UI display.
    Uses SharedDatabase to avoid connection conflicts.
    """
    try:
        db = get_shared_db()
        try:
            query = f"""
            SELECT 
                raw_id, telegram_chat_id, telegram_msg_id, source_handle, 
                normalized_text, link_text, image_ocr_text,
                received_at, is_duplicate, duplicate_of_raw_id, is_scored
            FROM {OUTPUT_TABLE}
            ORDER BY received_at DESC
            LIMIT ?
            """
            rows = db.run_raw_query(query, [limit], fetch='all')
            
            result = []
            if rows:
                for row in rows:
                    result.append({
                        "raw_id": row[0],
                        "telegram_chat_id": row[1],
                        "telegram_msg_id": row[2],
                        "source_handle": row[3],
                        "normalized_text": row[4],
                        "link_text": row[5],
                        "image_ocr_text": row[6],
                        "received_at": row[7].strftime("%Y-%m-%d %H:%M:%S") if row[7] else None,
                        "is_duplicate": row[8] if len(row) > 8 else False,
                        "duplicate_of": row[9] if len(row) > 9 else None,
                        "is_scored": row[10] if len(row) > 10 else False
                    })
            return result
        except Exception as e:
            logger.error(f"Error fetching extractions for UI: {e}")
            return []
    except Exception as e:
         logger.error(f"DB Connect Error (UI): {e}")
         return []

def insert_raw_result(data: dict):
    """
    Inserts extracted data into the output table.
    """
    db = get_shared_db()
    try:
        query = f"""
        INSERT INTO {OUTPUT_TABLE} (
            listing_id, telegram_chat_id, telegram_msg_id, source_handle,
            telegram_text, caption_text, link_text, image_ocr_text,
            combined_text, normalized_text, file_id, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        db.run_raw_query(query, [
            data['listing_id'],
            data['telegram_chat_id'],
            data['telegram_msg_id'],
            data['source_handle'],
            data['telegram_text'],
            data['caption_text'],
            data['link_text'],
            data['image_ocr_text'],
            data['combined_text'],
            data['normalized_text'],
            data.get('file_id'),
            data['received_at']
        ])
    except Exception as e:
        logger.error(f"Failed to insert raw result: {e}")
        raise
    finally:
        pass # Shared connection
