import logging
import os
import threading
from .config import RAW_DB_PATH, RAW_TABLE, SCORING_DB_PATH, SCORING_TABLE, DATA_DIR
from app.providers.shared_db import get_shared_db

logger = logging.getLogger(__name__)

def get_db():
    return get_shared_db()

def ensure_dirs():
    scoring_dir = os.path.dirname(SCORING_DB_PATH)
    if not os.path.exists(scoring_dir):
        os.makedirs(scoring_dir, exist_ok=True)

def ensure_schema():
    """Ensure scoring DB schema exists."""
    ensure_dirs()
    db = get_db()
    try:
        # Use simple execution for schema
        db.run_scoring_query(f"CREATE SEQUENCE IF NOT EXISTS seq_score_id START 1;")
        query = f"""
        CREATE TABLE IF NOT EXISTS {SCORING_TABLE} (
            score_id BIGINT DEFAULT nextval('seq_score_id') PRIMARY KEY,
            raw_id BIGINT,
            final_score INTEGER,
            structural_score INTEGER,
            keyword_score INTEGER,
            source_score INTEGER,
            content_score INTEGER,
            decision TEXT,
            scored_at TIMESTAMP
        );
        """
        db.run_scoring_query(query)
    except Exception as e:
        logger.error(f"Scoring Schema Error: {e}")
        raise

def get_recent_scores(limit=50):
    """Fetch recent scores for UI display."""
    db = get_db()
    try:
        score_query = f"""
            SELECT 
                score_id, raw_id, final_score, structural_score, keyword_score,
                source_score, content_score, decision, scored_at
            FROM {SCORING_TABLE}
            ORDER BY scored_at DESC
            LIMIT ?
        """
        score_rows = db.run_scoring_query(score_query, [limit], fetch='all')
        
        if not score_rows:
            return []

        raw_ids = [row[1] for row in score_rows]
        if not raw_ids:
            return []
            
        # Check if RAW_TABLE exists
        exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{RAW_TABLE}'", fetch='one')
        if not exists or exists[0] == 0:
            logger.info(f"Table {RAW_TABLE} does not exist yet. Using placeholders.")
            raw_data = {}
        else:
            raw_ids_str = ','.join(str(id) for id in raw_ids)
            raw_query = f"""
                SELECT raw_id, combined_text, link_text, source_handle, received_at
                FROM {RAW_TABLE}
                WHERE raw_id IN ({raw_ids_str})
            """
            raw_rows = db.run_raw_query(raw_query, fetch='all')
            raw_data = {row[0]: row for row in raw_rows} if raw_rows else {}
        
        result = []
        for score_row in score_rows:
            raw_id = score_row[1]
            raw_info = raw_data.get(raw_id)
            
            result.append({
                "score_id": score_row[0],
                "raw_id": raw_id,
                "final_score": score_row[2],
                "structural_score": score_row[3],
                "keyword_score": score_row[4],
                "source_score": score_row[5],
                "content_score": score_row[6],
                "decision": score_row[7],
                "scored_at": score_row[8].strftime("%Y-%m-%d %H:%M:%S") if score_row[8] else None,
                "combined_text": raw_info[1] if raw_info else "N/A",
                "link_text": raw_info[2] if raw_info else "",
                "source": raw_info[3] if raw_info else "Unknown",
                "received_at": raw_info[4].strftime("%Y-%m-%d %H:%M:%S") if (raw_info and raw_info[4]) else None
            })
        return result
    except Exception as e:
        logger.error(f"Error fetching recent scores: {e}")
        return []

def get_unscored_rows(limit=50):
    """Fetch unique, unscored rows from telegram_raw."""
    db = get_db()
    try:
        # Check if telegram_raw exists first to avoid Catalog Error during startup
        # (This avoids hitting shared_db.py error logger)
        try:
            raw_exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{RAW_TABLE}'", fetch='one')
            if not raw_exists or raw_exists[0] == 0:
                logger.info(f"Table '{RAW_TABLE}' not found yet. Skipping unscored rows fetch.")
                return []
        except Exception:
            return []

        query = f"""
            SELECT raw_id, source_handle, combined_text, received_at, link_text, image_ocr_text
            FROM {RAW_TABLE}
            WHERE is_duplicate = FALSE 
              AND is_scored = FALSE
              AND deduped_at IS NOT NULL
            ORDER BY received_at ASC
            LIMIT ?
        """
        return db.run_raw_query(query, [limit], fetch='all')
    except Exception as e:
        if "does not exist" in str(e).lower():
            return []
        logger.error(f"Error fetching unscored rows: {e}")
        return []

def update_raw_as_scored(raw_id):
    """Mark row as scored in telegram_raw."""
    db = get_db()
    try:
        # Check if RAW_TABLE exists first to avoid Catalog Error
        exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{RAW_TABLE}'", fetch='one')
        if not exists or exists[0] == 0:
             logger.warning(f"Metadata update for {raw_id} skipped: table {RAW_TABLE} not found")
             return
             
        db.run_raw_query(f"UPDATE {RAW_TABLE} SET is_scored = TRUE WHERE raw_id = ?", [raw_id])
    except Exception as e:
        logger.error(f"Failed to update raw as scored {raw_id}: {e}")

def insert_score_result(raw_id, score_data):
    """Insert scoring result into news_scores table."""
    db = get_db()
    try:
        query = f"""
            INSERT INTO {SCORING_TABLE} (
                raw_id, final_score, structural_score, keyword_score, 
                source_score, content_score, decision, scored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        db.run_scoring_query(query, [
            raw_id, 
            score_data['final_score'],
            score_data['structural_score'],
            score_data['keyword_score'],
            score_data['source_score'],
            score_data['content_score'],
            score_data['decision']
        ])
    except Exception as e:
        logger.error(f"Failed to insert score {raw_id}: {e}")
        raise
