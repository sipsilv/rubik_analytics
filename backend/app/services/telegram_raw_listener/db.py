import duckdb
import logging
import os
from datetime import datetime, timedelta, timezone
from .config import DB_PATH, TABLE_NAME, RETENTION_HOURS
from app.services.shared_db import get_shared_db

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
            UNIQUE(telegram_chat_id, telegram_msg_id)
        );
        """
        db.run_listing_query(query)
        
        # Migration: Ensure file_path column exists for existing tables
        try:
            cols = db.run_listing_query(f"DESCRIBE {TABLE_NAME}", fetch='all')
            col_names = [c[0] for c in cols]
            if 'file_path' not in col_names:
                logger.info(f"Migrating {TABLE_NAME}: Adding file_path column")
                db.run_listing_query(f"ALTER TABLE {TABLE_NAME} ADD COLUMN file_path TEXT")
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
