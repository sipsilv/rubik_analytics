import duckdb
import logging
import os
import threading
from .config import RAW_DB_PATH, RAW_TABLE, SCORING_DB_PATH, SCORING_TABLE, DATA_DIR
from app.services.shared_db import get_shared_db

logger = logging.getLogger(__name__)

# Connection cache to prevent file locking
_scoring_conn_cache = None
_scoring_conn_lock = threading.Lock()

def get_db():
    return get_shared_db()

def get_scoring_conn():
    """Get cached scoring DB connection to prevent file locking"""
    global _scoring_conn_cache
    with _scoring_conn_lock:
        if _scoring_conn_cache is None:
            ensure_dirs()
            _scoring_conn_cache = duckdb.connect(SCORING_DB_PATH)
        return _scoring_conn_cache

def ensure_dirs():
    scoring_dir = os.path.dirname(SCORING_DB_PATH)
    if not os.path.exists(scoring_dir):
        os.makedirs(scoring_dir)

def ensure_schema():
    """
    Ensure scoring DB schema exists.
    """
    ensure_dirs()
    
    conn = get_scoring_conn()
    try:
        conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_score_id START 1;")
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
        conn.execute(query)
    except Exception as e:
        logger.error(f"Scoring Schema Error: {e}")
        raise
    # DON'T close cached connection!

def get_recent_scores(limit=50):
    """
    Fetch recent scores for UI display.
    Uses SharedDatabase to avoid connection conflicts.
    """
    try:
        # Use separate connection for scoring DB (it's not in SharedDatabase)
        # But we need data from raw DB too, so we'll query them separately
        scoring_conn = get_scoring_conn()
        db = get_db()
        
        try:
            # First, get scores
            score_query = f"""
                SELECT 
                    score_id, 
                    raw_id, 
                    final_score,
                    structural_score,
                    keyword_score,
                    source_score,
                    content_score, 
                    decision, 
                    scored_at
                FROM {SCORING_TABLE}
                ORDER BY scored_at DESC
                LIMIT ?
            """
            score_rows = scoring_conn.execute(score_query, [limit]).fetchall()
            
            if not score_rows:
                logger.warning("get_recent_scores: No scores found in news_scoring DB.")
                return []
            
            logger.info(f"get_recent_scores: Found {len(score_rows)} scores. Fetching raw data...")
            
            # Get raw_ids to fetch from raw DB
            raw_ids = [row[1] for row in score_rows]
            raw_ids_str = ','.join(str(id) for id in raw_ids)
            
            # Fetch corresponding raw data
            raw_query = f"""
                SELECT 
                    raw_id,
                    combined_text,
                    link_text,
                    source_handle,
                    received_at
                FROM {RAW_TABLE}
                WHERE raw_id IN ({raw_ids_str})
            """
            # Use safe query execution
            raw_rows = db.run_raw_query(raw_query, fetch='all')
            
            # Create lookup dict
            raw_data = {row[0]: row for row in raw_rows} if raw_rows else {}
            
            # Combine results
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
            # Fallback: return just scoring data without raw text
            try:
                fallback_query = f"""
                    SELECT 
                        score_id, 
                        raw_id, 
                        final_score,
                        structural_score,
                        keyword_score,
                        source_score,
                        content_score, 
                        decision, 
                        scored_at
                    FROM {SCORING_TABLE}
                    ORDER BY scored_at DESC
                    LIMIT ?
                """
                rows = scoring_conn.execute(fallback_query, [limit]).fetchall()
                result = []
                for row in rows:
                    result.append({
                        "score_id": row[0],
                        "raw_id": row[1],
                        "final_score": row[2],
                        "structural_score": row[3],
                        "keyword_score": row[4],
                        "source_score": row[5],
                        "content_score": row[6],
                        "decision": row[7],
                        "scored_at": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else None,
                        "combined_text": "N/A (Join Failed)",
                        "link_text": "",
                        "source": "Unknown",
                        "received_at": None
                    })
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback query also failed: {fallback_error}")
                return []
        finally:
            # DON'T close cached scoring connection
            # Do NOT close raw_conn (it's shared)
            pass
            
    except Exception as e:
        logger.error(f"Critical error in get_recent_scores: {e}")
        return []

def get_unscored_rows(limit=50):
    """
    Fetch unique, unscored rows from telegram_raw.
    """
    db = get_db()
    try:
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
        logger.error(f"Error fetching unscored rows: {e}")
        return []

def update_raw_as_scored(raw_id):
    """
    Mark row as scored in telegram_raw.
    """
    db = get_db()
    try:
        db.run_raw_query(f"UPDATE {RAW_TABLE} SET is_scored = TRUE WHERE raw_id = ?", [raw_id])
    except Exception as e:
        logger.error(f"Failed to update raw as scored {raw_id}: {e}")

def insert_score_result(raw_id, score_data):
    """
    Insert scoring result into news_scores table.
    """
    # Use separate connection for scoring DB writes to avoid conflicts if needed,
    # but based on ensure_schema/get_scoring_conn, it uses its own db file.
    conn = get_scoring_conn()
    try:
        query = f"""
            INSERT INTO {SCORING_TABLE} (
                raw_id, final_score, structural_score, keyword_score, 
                source_score, content_score, decision, scored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        conn.execute(query, [
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
    # DON'T close cached connection!
