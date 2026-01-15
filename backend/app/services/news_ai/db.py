import logging
import os
from .config import SCORING_DB_PATH, SCORING_TABLE, AI_DB_PATH, AI_TABLE
from app.services.shared_db import get_shared_db

logger = logging.getLogger(__name__)

def get_db():
    return get_shared_db()

def ensure_schema():
    """Ensure news_ai and ai_queue tables exist and handle migrations."""
    db = get_db()
    try:
        # Main Enriched Table
        query_ai = f"""
        CREATE TABLE IF NOT EXISTS {AI_TABLE} (
            news_id BIGINT PRIMARY KEY,
            received_date TIMESTAMP,
            category_code TEXT,
            sub_type_code TEXT,
            company_name TEXT,
            ticker TEXT,
            exchange TEXT,
            country_code TEXT,
            headline TEXT,
            summary TEXT,
            sentiment TEXT,
            language_code TEXT,
            url TEXT,
            impact_score INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ai_model TEXT,
            ai_config_id INTEGER
        );
        """
        db.run_ai_query(query_ai)

        # Queue Table for state management
        query_queue = """
        CREATE TABLE IF NOT EXISTS ai_queue (
            news_id BIGINT PRIMARY KEY,
            status TEXT DEFAULT 'PENDING',
            retries INTEGER DEFAULT 0,
            error_log TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.run_ai_query(query_queue)

        # Migration: Check for missing columns in news_ai
        cols = db.run_ai_query(f"PRAGMA table_info({AI_TABLE})", fetch='all')
        existing_cols = [c[1] for c in cols]
        
        if 'impact_score' not in existing_cols:
            logger.info("Adding impact_score column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN impact_score INTEGER DEFAULT 0")
            
        if 'latency_ms' not in existing_cols:
            logger.info("Adding latency_ms column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN latency_ms INTEGER DEFAULT 0")

    except Exception as e:
        logger.error(f"AI Schema Error during migration: {e}")
        raise

def sync_queue():
    """Sync missing scores from news_scoring to ai_queue."""
    db = get_db()
    try:
        # 1. Get IDs already in news_ai or ai_queue to avoid duplicates
        existing_ids = db.run_ai_query(f"SELECT news_id FROM {AI_TABLE} UNION SELECT news_id FROM ai_queue", fetch='all')
        existing_ids_list = [row[0] for row in existing_ids]

        where_clause = ""
        if existing_ids_list:
            ids_str = ",".join(map(str, existing_ids_list))
            where_clause = f"WHERE score_id NOT IN ({ids_str})"

        # 2. Fetch new scores from scoring DB
        scoring_query = f"SELECT score_id FROM {SCORING_TABLE} {where_clause} ORDER BY scored_at ASC LIMIT 100"
        new_scores = db.run_scoring_query(scoring_query, fetch='all')

        if new_scores:
            for row in new_scores:
                db.run_ai_query("INSERT OR IGNORE INTO ai_queue (news_id) VALUES (?)", [row[0]])
            logger.info(f"Synced {len(new_scores)} items to AI queue.")
    except Exception as e:
        logger.error(f"Error syncing AI queue: {e}")

def get_eligible_news(limit=1):
    """
    Fetch news from ai_queue that are PENDING.
    Marks them as PROCESSING immediately.
    """
    db = get_db()
    sync_queue()
    
    try:
        # 1. Fetch next PENDING item
        query = "SELECT news_id FROM ai_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT ?"
        pending_items = db.run_ai_query(query, [limit], fetch='all')
        
        if not pending_items:
            return []

        results = []
        for (news_id,) in pending_items:
            # Mark as PROCESSING
            db.run_ai_query("UPDATE ai_queue SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP WHERE news_id = ?", [news_id])
            
            # Get the text from raw DB
            # We need raw_id from scoring_db first
            scoring_row = db.run_scoring_query(f"SELECT raw_id FROM {SCORING_TABLE} WHERE score_id = ?", [news_id], fetch='one')
            if not scoring_row:
                continue
            
            raw_id = scoring_row[0]
            raw_row = db.run_raw_query("SELECT combined_text, received_at, link_text FROM telegram_raw WHERE raw_id = ?", [raw_id], fetch='one')
            
            if raw_row:
                results.append((news_id, raw_row[1], raw_row[0], raw_row[2]))
            
        return results
        
    except Exception as e:
        logger.error(f"Error fetching eligible news from queue: {e}")
        return []

def mark_failed(news_id, error_msg):
    """Mark a news item as failed in the queue."""
    db = get_db()
    try:
        db.run_ai_query("""
            UPDATE ai_queue 
            SET status = 'FAILED', 
                retries = retries + 1,
                error_log = ?,
                updated_at = CURRENT_TIMESTAMP 
            WHERE news_id = ?
        """, [error_msg, news_id])
    except Exception as e:
        logger.error(f"Failed to mark news {news_id} as failed: {e}")

def insert_enriched_news(news_id, received_date, ai_data, ai_model, ai_config_id, latency_ms=0, original_url=None):
    """Save AI enriched news to DB and mark queue as COMPLETED."""
    db = get_db()
    try:
        query = f"""
        INSERT INTO {AI_TABLE} (
            news_id, received_date, category_code, sub_type_code, company_name,
            ticker, exchange, country_code, headline, summary, sentiment,
            language_code, url, ai_model, ai_config_id, impact_score, latency_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        impact_score = ai_data.get('impact_score', 0)
        # Handle cases where impact_score might be a string
        try:
            impact_score = int(impact_score)
        except:
            impact_score = 0

        # Use original URL if available, otherwise get from AI data
        url = original_url if original_url else ai_data.get('url', '')

        db.run_ai_query(query, [
            news_id,
            received_date,
            ai_data.get('category_code', ''),
            ai_data.get('sub_type_code', ''),
            ai_data.get('company_name', ''),
            ai_data.get('ticker', ''),
            ai_data.get('exchange', ''),
            ai_data.get('country_code', ''),
            ai_data.get('headline', ''),
            ai_data.get('summary', ''),
            ai_data.get('sentiment', ''),
            ai_data.get('language_code', ''),
            url,
            ai_model,
            ai_config_id,
            impact_score,
            latency_ms
        ])
        
        # Mark as COMPLETED
        db.run_ai_query("UPDATE ai_queue SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE news_id = ?", [news_id])
        
    except Exception as e:
        logger.error(f"Failed to insert enriched news {news_id}: {e}")
        # Mark as FAILED in queue
        mark_failed(news_id, str(e))
        raise

def get_recent_enrichments(limit=50):
    """Fetch recent AI enriched news formatted for the frontend table."""
    try:
        ensure_schema()
    except:
        pass

    db = get_db()
    try:
        query = f"""
            SELECT 
                news_id, created_at, headline, category_code, sentiment, 
                impact_score, ai_model, latency_ms, summary, url
            FROM {AI_TABLE}
            ORDER BY created_at DESC
            LIMIT ?
        """
        rows = db.run_ai_query(query, [limit], fetch='all')
        
        result = []
        for row in rows:
            result.append({
                "final_id": row[0],
                "processed_at": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else None,
                "headline": row[2],
                "category": row[3],
                "sentiment": row[4],
                "impact_score": row[5],
                "ai_model": row[6],
                "latency": row[7],
                "summary": row[8],
                "url": row[9]
            })
        return result
    except Exception as e:
        logger.error(f"Error fetching recent enrichments: {e}")
        return []
