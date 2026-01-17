import duckdb
import logging
import os
from datetime import datetime, timedelta, timezone
from .config import DB_PATH, TABLE_NAME, RETENTION_HOURS
from app.providers.shared_db import get_shared_db

logger = logging.getLogger("telegram_listener.db")

def get_db():
    """Returns the shared database instance."""
    return get_shared_db()

def init_db():
    """Initializes the database schema."""
    db = get_db()
    try:
        # Create Sequence for ID if needed, or just use BIGINT
        # We'll use a sequence for listing_id
        db.run_listing_query(f"CREATE SEQUENCE IF NOT EXISTS seq_{TABLE_NAME}_id START 1;")
        
        # Create Table
        # received_at is TIMESTAMP (UTC)
        query = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            listing_id BIGINT DEFAULT nextval('seq_{TABLE_NAME}_id') PRIMARY KEY,
            telegram_chat_id TEXT,
            telegram_msg_id TEXT,
            source_handle TEXT,
            message_text TEXT,
            caption_text TEXT,
            media_type TEXT,
            has_media BOOLEAN,
            file_id TEXT,
            file_name TEXT,
            file_path TEXT,
            urls TEXT,
            received_at TIMESTAMP,
            is_extracted BOOLEAN DEFAULT FALSE,
            UNIQUE(telegram_chat_id, telegram_msg_id)
        );
        """
        db.run_listing_query(query)
        
        # Migration: Ensure columns exist
        try:
            # Check columns using information_schema to avoid DESCRIBE parsing issues
            cols = db.run_listing_query(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{TABLE_NAME}'", fetch='all')
            col_names = [c[0] for c in cols]
            
            if 'file_path' not in col_names:
                try:
                    logger.info(f"Migrating {TABLE_NAME}: Adding file_path column")
                    db.run_listing_query(f"ALTER TABLE {TABLE_NAME} ADD COLUMN file_path TEXT")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to add file_path: {e}")

            if 'is_extracted' not in col_names:
                try:
                    logger.info(f"Migrating {TABLE_NAME}: Adding is_extracted column")
                    db.run_listing_query(f"ALTER TABLE {TABLE_NAME} ADD COLUMN is_extracted BOOLEAN DEFAULT FALSE")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to add is_extracted: {e}")

            if 'extracted_at' not in col_names:
                try:
                    logger.info(f"Migrating {TABLE_NAME}: Adding extracted_at column")
                    db.run_listing_query(f"ALTER TABLE {TABLE_NAME} ADD COLUMN extracted_at TIMESTAMP")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to add extracted_at: {e}")
        except Exception as e:
             logger.warning(f"Migration check failed (minor): {e}")
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # raise # Don't raise, allowing shared db to handle it if already init
    finally:
        pass # Do NOT close shared connection

def insert_message(data: dict):
    """
    Inserts a message into DuckDB.
    Silently skips if (telegram_chat_id, telegram_msg_id) already exists.
    """
    db = get_db()
    try:
        # Prepare query (DuckDB support parameter substitution)
        # We use INSERT OR IGNORE (DuckDB supports INSERT OR IGNORE since recent versions or ON CONFLICT DO NOTHING)
        # Syntax: INSERT OR IGNORE INTO table ... works in SQLite, DuckDB uses params ?
        
        query = f"""
        INSERT OR IGNORE INTO {TABLE_NAME} (
            telegram_chat_id, telegram_msg_id, source_handle, 
            message_text, caption_text, media_type, has_media, 
            file_id, file_name, file_path, urls, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        db.run_listing_query(query, [
            str(data['telegram_chat_id']),
            str(data['telegram_msg_id']),
            data.get('source_handle'),
            data.get('message_text'),
            data.get('caption_text'),
            data.get('media_type', 'none'),
            data.get('has_media', False),
            data.get('file_id'),
            data.get('file_name'),
            data.get('file_path'),
            data.get('urls'),
            data.get('received_at') # Should be datetime object
        ])
    except Exception as e:
        logger.error(f"Error inserting message: {e}")
        # distinct error handling? User said "Insert failures must NOT crash listener"
    finally:
        pass # Do NOT close shared connection

def run_cleanup():
    """
    Deletes messages older than RETENTION_HOURS.
    """
    db = get_db()
    try:
        # Check if table exists before cleanup
        exists = db.run_listing_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{TABLE_NAME}'", fetch='one')
        if not exists or exists[0] == 0:
            # Table doesn't exist yet, skip cleanup
            logger.info(f"Table {TABLE_NAME} doesn't exist yet, skipping cleanup")
            return
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)
        # DuckDB timestamp comparison
        query = f"DELETE FROM {TABLE_NAME} WHERE received_at < ?"
        db.run_listing_query(query, [cutoff_time])
        
        # Check how many rows deleted? (DuckDB doesn't always return rowcount easily in all clients, but no big deal)
        logger.info(f"Cleanup run completed. Retention: {RETENTION_HOURS}h")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
    finally:
        pass # Do NOT close shared connection

def get_last_msg_id(chat_id: str) -> int:
    """Returns the highest telegram_msg_id for a given chat_id."""
    db = get_db()
    try:
        # We cast to BIGINT because telegram_msg_id is stored as TEXT for flexibility
        query = f"SELECT MAX(CAST(telegram_msg_id AS BIGINT)) FROM {TABLE_NAME} WHERE telegram_chat_id = ?"
        result = db.run_listing_query(query, [str(chat_id)], fetch='one')
        if result and result[0]:
            return int(result[0])
    except Exception as e:
        logger.error(f"Error getting last msg id for {chat_id}: {e}")
    return 0
