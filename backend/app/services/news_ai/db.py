import logging
import sqlite3
import os
import json
from typing import Optional, Tuple, Dict, List, Any
from datetime import datetime, timedelta, timezone
from .config import SCORING_DB_PATH, SCORING_TABLE, AI_DB_PATH, AI_TABLE, FINAL_TABLE
from app.providers.shared_db import get_shared_db
from app.core.websocket.manager import manager
from .similarity import is_duplicate, calculate_combined_similarity

logger = logging.getLogger(__name__)

# Global in-memory cache for deduplication (fingerprint -> (news_id, timestamp))
_recent_processed_cache = {}

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
        
        # Final Table for curated data
        query_final = f"""
        CREATE TABLE IF NOT EXISTS {FINAL_TABLE} (
            news_id BIGINT PRIMARY KEY,
            received_date TIMESTAMP,
            headline TEXT,
            summary TEXT,
            company_name TEXT,
            ticker TEXT,
            exchange TEXT,
            country_code TEXT,
            sentiment TEXT,
            url TEXT,
            impact_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.run_final_query(query_final)
        
        # System Settings Table
        query_settings = """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.run_final_query(query_settings)
        
        # Initialize default news_sync status if not exists
        db.run_final_query("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('news_sync_enabled', 'true')")

        # Migration: Check for missing columns in news_ai
        cols = db.run_ai_query(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{AI_TABLE}'", fetch='all')
        existing_cols = [c[0] for c in cols]
        
        if 'impact_score' not in existing_cols:
            logger.info("Adding impact_score column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN impact_score INTEGER DEFAULT 0")
            
        if 'latency_ms' not in existing_cols:
            logger.info("Adding latency_ms column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN latency_ms INTEGER DEFAULT 0")

        if 'is_duplicate' not in existing_cols:
            logger.info("Adding is_duplicate column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE")

        if 'duplicate_of_id' not in existing_cols:
            logger.info("Adding duplicate_of_id column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN duplicate_of_id BIGINT")

        if 'similarity_score' not in existing_cols:
            logger.info("Adding similarity_score column to news_ai")
            db.run_ai_query(f"ALTER TABLE {AI_TABLE} ADD COLUMN similarity_score DOUBLE DEFAULT 0.0")

        # Migration: Check for missing columns in final_news
        final_cols = db.run_final_query(f"PRAGMA table_info({FINAL_TABLE})", fetch='all')
        existing_final_cols = [c[1] for c in final_cols]
        
        if 'is_duplicate' not in existing_final_cols:
            logger.info("Adding is_duplicate column to final_news")
            db.run_final_query(f"ALTER TABLE {FINAL_TABLE} ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE")
            
        if 'duplicate_of_id' not in existing_final_cols:
            logger.info("Adding duplicate_of_id column to final_news")
            db.run_final_query(f"ALTER TABLE {FINAL_TABLE} ADD COLUMN duplicate_of_id BIGINT")
            
        if 'source_count' not in existing_final_cols:
            logger.info("Adding source_count column to final_news")
            db.run_final_query(f"ALTER TABLE {FINAL_TABLE} ADD COLUMN source_count INTEGER DEFAULT 1")
            
        if 'additional_sources' not in existing_final_cols:
            logger.info("Adding additional_sources column to final_news")
            db.run_final_query(f"ALTER TABLE {FINAL_TABLE} ADD COLUMN additional_sources TEXT") # JSON array
            
        if 'source_handle' not in existing_final_cols:
            logger.info("Adding source_handle column to final_news")
            db.run_final_query(f"ALTER TABLE {FINAL_TABLE} ADD COLUMN source_handle TEXT")

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

        where_clause = "WHERE 1=1"
        if existing_ids_list:
            ids_str = ",".join(map(str, existing_ids_list))
            where_clause += f" AND score_id NOT IN ({ids_str})"

        # 2. Fetch new scores from scoring DB
        # Exclude items explicitly marked as 'drop' (case-insensitive)
        scoring_query = f"SELECT score_id FROM {SCORING_TABLE} {where_clause} AND (decision IS NULL OR lower(decision) != 'drop') ORDER BY scored_at ASC LIMIT 100"
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

        # Check if telegram_raw exists first to avoid Catalog Error during startup
        # (This avoids hitting shared_db.py error logger)
        try:
            raw_exists = db.run_raw_query("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'telegram_raw'", fetch='one')
            if not raw_exists or raw_exists[0] == 0:
                logger.info("Table 'telegram_raw' not found yet. Skipping eligible news fetch.")
                return []
        except Exception:
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
            raw_row = db.run_raw_query("SELECT combined_text, received_at, source_url FROM telegram_raw WHERE raw_id = ?", [raw_id], fetch='one')
            
            if raw_row:
                results.append((news_id, raw_row[1], raw_row[0], raw_row[2]))
            
        return results
        
    except Exception as e:
        if "does not exist" in str(e).lower():
            return []
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

def has_valid_content(ai_data: Dict) -> bool:
    """Check if news has meaningful content (not just headline)."""
    summary = ai_data.get('summary', '').strip()
    return len(summary) > 50  # Minimum content length

def find_duplicate_in_window(ai_data: Dict, window_minutes: int = 60) -> Optional[Tuple[int, float]]:
    """
    Check for duplicate news within time window.
    check both in-memory cache (for race conditions) and database (for persistence).
    
    Returns:
        Tuple of (duplicate_news_id, similarity_score) if duplicate found, None otherwise
    """
    # 1. Generate fingerprint for fast in-memory check
    headline = ai_data.get('headline', '').strip().lower()
    if not headline:
        return None
        
    import hashlib
    fingerprint = hashlib.md5(headline.encode('utf-8')).hexdigest()
    
    # 2. Check in-memory cache first
    now = datetime.now(timezone.utc)
    if fingerprint in _recent_processed_cache:
        cached_id, cached_time = _recent_processed_cache[fingerprint]
        # Check if within window
        if (now - cached_time).total_seconds() < (window_minutes * 60):
            logger.info(f"Duplicate found in memory cache: {cached_id}")
            return (cached_id, 1.0) # 1.0 similarity for exact fingerprint match

    db = get_db()
    try:
        # Get recent news from last N minutes
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        
        query = f"""
        SELECT news_id, headline, summary, company_name, ticker, exchange
        FROM {FINAL_TABLE}
        WHERE created_at >= ?
        AND is_duplicate = FALSE
        ORDER BY created_at DESC
        LIMIT 50
        """
        
        recent_news = db.run_final_query(query, [cutoff_time], fetch='all')
        
        if not recent_news:
            return None
        
        # Check similarity against each recent news item
        for row in recent_news:
            existing_news = {
                'news_id': row[0],
                'headline': row[1] or '',
                'summary': row[2] or '',
                'company_name': row[3] or '',
                'ticker': row[4] or '',
                'exchange': row[5] or ''
            }
            
            is_dup, similarity_score = is_duplicate(ai_data, existing_news, threshold=0.60)
            
            if is_dup:
                logger.info(f"Found duplicate: news_id {existing_news['news_id']} (similarity: {similarity_score:.2f})")
                return (existing_news['news_id'], similarity_score)
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking for duplicates: {e}")
        return None

def update_source_count(original_news_id: int, new_source_handle: str):
    """Update original news with additional source."""
    db = get_db()
    try:
        # Get current additional_sources
        result = db.run_final_query(
            f"SELECT additional_sources, source_count, source_handle FROM {FINAL_TABLE} WHERE news_id = ?",
            [original_news_id],
            fetch='one'
        )
        
        if not result:
            return
        
        additional_sources_json, source_count, original_source = result
        
        # Parse existing sources
        if additional_sources_json:
            try:
                additional_sources = json.loads(additional_sources_json)
            except:
                additional_sources = []
        else:
            additional_sources = []
        
        # Add new source if not already present
        if new_source_handle and new_source_handle not in additional_sources:
            if original_source and new_source_handle != original_source:
                additional_sources.append(new_source_handle)
        
        # Update database
        new_count = 1 + len(additional_sources)
        db.run_final_query(
            f"UPDATE {FINAL_TABLE} SET source_count = ?, additional_sources = ? WHERE news_id = ?",
            [new_count, json.dumps(additional_sources), original_news_id]
        )
        
        logger.info(f"Updated source count for news {original_news_id}: {new_count} sources")
        
        # Broadcast update to frontend
        try:
            update_data = {
                "type": "update_news",
                "news_id": original_news_id,
                "source_count": new_count,
                "additional_sources": additional_sources
            }
            manager.broadcast_news_sync(update_data)
        except Exception as e:
            logger.warning(f"Failed to broadcast source update: {e}")
            
    except Exception as e:
        logger.error(f"Failed to update source count: {e}")

def insert_enriched_news(news_id, received_date, ai_data, ai_model, ai_config_id, latency_ms=0, original_url=None):
    """Save AI enriched news to DB and mark queue as COMPLETED."""
    db = get_db()
    try:
        query = f"""
        INSERT INTO {AI_TABLE} (
            news_id, received_date, category_code, sub_type_code, company_name,
            ticker, exchange, country_code, headline, summary, sentiment,
            language_code, url, ai_model, ai_config_id, impact_score, latency_ms,
            is_duplicate, duplicate_of_id, similarity_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        impact_score = ai_data.get('impact_score', 0)
        # Handle cases where impact_score might be a string
        try:
            impact_score = int(impact_score)
        except:
            impact_score = 0

        # Duplicate check before insert
        duplicate_result = find_duplicate_in_window(ai_data, window_minutes=60)
        is_duplicate_flag = False
        duplicate_of_id_val = None
        similarity_score_val = 0.0
        if duplicate_result:
            duplicate_of_id_val, similarity_score_val = duplicate_result
            is_duplicate_flag = True

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
            latency_ms,
            is_duplicate_flag,
            duplicate_of_id_val,
            similarity_score_val
        ])
        
        # Mark as COMPLETED
        db.run_ai_query("UPDATE ai_queue SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE news_id = ?", [news_id])
        
        # 3. Handle duplicates for final table sync
        # We already checked for duplicate_result above during AI_TABLE insert
        # No need to re-fetch if we have it
        # Actually duplicate_result is already computed above
        
        # Get source handle from original URL or news data
        source_handle = None
        if original_url:
            # Extract source from URL (e.g., moneycontrol.com, livemint.com)
            import re
            match = re.search(r'//(?:www\.)?([^/]+)', original_url)
            if match:
                source_handle = match.group(1).replace('www.', '')
        
        if duplicate_result:
            # Duplicate found - update original and mark this as duplicate
            original_news_id, similarity_score = duplicate_result
            
            try:
                # Insert as duplicate
                final_query = f"""
                INSERT INTO {FINAL_TABLE} (
                    news_id, received_date, headline, summary, company_name,
                    ticker, exchange, country_code, sentiment, url, impact_score,
                    is_duplicate, duplicate_of_id, source_handle
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?, ?)
                """
                db.run_final_query(final_query, [
                    news_id,
                    received_date,
                    ai_data.get('headline', ''),
                    ai_data.get('summary', ''),
                    ai_data.get('company_name', ''),
                    ai_data.get('ticker', ''),
                    ai_data.get('exchange', ''),
                    ai_data.get('country_code', ''),
                    ai_data.get('sentiment', ''),
                    url,
                    impact_score,
                    original_news_id,
                    source_handle
                ])
                
                # Update original with source count
                update_source_count(original_news_id, source_handle)
                
                logger.info(f"Marked news {news_id} as duplicate of {original_news_id} (similarity: {similarity_score:.2f})")
                # Don't broadcast duplicates
                return
                
            except Exception as dup_err:
                logger.error(f"Failed to handle duplicate: {dup_err}")
                # Continue with normal insert if duplicate handling fails
        
        # 4. Sync to Final Database (unique news)
        try:
            # Validate content before inserting
            if not has_valid_content(ai_data):
                logger.info(f"Skipping news {news_id} - no meaningful content (summary too short)")
                # Still mark as completed but don't insert to final or broadcast
                return
            
            final_query = f"""
            INSERT INTO {FINAL_TABLE} (
                news_id, received_date, headline, summary, company_name,
                ticker, exchange, country_code, sentiment, url, impact_score,
                source_handle, source_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """
            db.run_final_query(final_query, [
                news_id,
                received_date,
                ai_data.get('headline', ''),
                ai_data.get('summary', ''),
                ai_data.get('company_name', ''),
                ai_data.get('ticker', ''),
                ai_data.get('exchange', ''),
                ai_data.get('country_code', ''),
                ai_data.get('sentiment', ''),
                url,
                impact_score,
                source_handle
            ])
            logger.info(f"Successfully synced news {news_id} to final database.")
            
            # Update in-memory cache
            try:
                headline = ai_data.get('headline', '').strip().lower()
                if headline:
                    import hashlib
                    fingerprint = hashlib.md5(headline.encode('utf-8')).hexdigest()
                    now = datetime.now(timezone.utc)
                    _recent_processed_cache[fingerprint] = (news_id, now)
                    
                    # Cleanup old entries (simple)
                    if len(_recent_processed_cache) > 1000:
                        cutoff = now - timedelta(hours=2)
                        to_remove = [k for k, v in _recent_processed_cache.items() if v[1] < cutoff]
                        for k in to_remove:
                            del _recent_processed_cache[k]
            except Exception as cache_err:
                logger.warning(f"Failed to update memory cache: {cache_err}")
            
            # 5. Broadcast to frontend (only for unique news with content)
            try:
                broadcast_data = {
                    "type": "new_news",
                    "news_id": news_id,
                    "received_date": received_date.isoformat() if hasattr(received_date, 'isoformat') else str(received_date),
                    "headline": ai_data.get('headline', ''),
                    "summary": ai_data.get('summary', ''),
                    "company_name": ai_data.get('company_name', ''),
                    "ticker": ai_data.get('ticker', ''),
                    "exchange": ai_data.get('exchange', ''),
                    "country_code": ai_data.get('country_code', ''),
                    "sentiment": ai_data.get('sentiment', ''),
                    "url": url,
                    "impact_score": impact_score,
                    "source_handle": source_handle,
                    "source_count": 1
                }
                manager.broadcast_news_sync(broadcast_data)
            except Exception as broadcast_err:
                logger.warning(f"Failed to broadcast news {news_id}: {broadcast_err}")
                
        except Exception as final_err:
            logger.error(f"Failed to sync news {news_id} to final database: {final_err}")
            # We don't raise here to avoid failing the main process if only the sync fails
        
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
                impact_score, ai_model, latency_ms, summary, url,
                is_duplicate, duplicate_of_id, similarity_score
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
                "url": row[9],
                "is_duplicate": row[10],
                "duplicate_of": row[11],
                "similarity_score": row[12]
            })
        return result
    except Exception as e:
        logger.error(f"Error fetching recent enrichments: {e}")
        return []

def get_final_news(limit=20, offset=0, search: Optional[str] = None):
    """Fetch AI-enriched news from final database with pagination and fuzzy search."""
    db = get_shared_db()
    try:
        where_parts = ["(is_duplicate IS NULL OR is_duplicate = FALSE)"]  # Exclude duplicates
        params = []
        
        if search and search.strip():
            tokens = search.strip().split()
            search_parts = []
            for token in tokens:
                pattern = f"%{token}%"
                # Substring match (ILIKE) + Fuzzy match (jaro_winkler) for better relevance
                search_parts.append("""
                    (headline ILIKE ? 
                    OR summary ILIKE ? 
                    OR ticker ILIKE ? 
                    OR company_name ILIKE ?
                    OR jaro_winkler_similarity(lower(ticker), lower(?)) > 0.8
                    OR jaro_winkler_similarity(lower(company_name), lower(?)) > 0.8)
                """)
                params.extend([pattern, pattern, pattern, pattern, token.lower(), token.lower()])
            where_parts.append("(" + " AND ".join(search_parts) + ")")
        
        where_clause = "WHERE " + " AND ".join(where_parts)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM {FINAL_TABLE} {where_clause}"
        total_count = db.run_final_query(count_query, params, fetch='one')[0]
        
        # Get paginated data
        # Get paginated data
        data_params = params + [limit, offset]
        query = f"""
            SELECT 
                news_id, received_date, headline, summary, company_name,
                ticker, exchange, country_code, sentiment, url, impact_score, created_at,
                source_count, additional_sources, source_handle
            FROM {FINAL_TABLE}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        rows = db.run_final_query(query, data_params, fetch='all')
        
        result = []
        for row in rows:
            # Parse additional_sources JSON if present
            additional_sources = []
            if row[13]:
                try:
                    import json
                    additional_sources = json.loads(row[13])
                except:
                    additional_sources = []

            result.append({
                "news_id": row[0],
                "received_date": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else None,
                "headline": row[2],
                "summary": row[3],
                "company_name": row[4],
                "ticker": row[5],
                "exchange": row[6],
                "country_code": row[7],
                "sentiment": row[8],
                "url": row[9],
                "impact_score": row[10],
                "created_at": row[11].strftime("%Y-%m-%d %H:%M:%S") if row[11] else None,
                "source_count": row[12] if row[12] else 1,
                "additional_sources": additional_sources,
                "source_handle": row[14]
            })
        return result, total_count
    except Exception as e:
        logger.error(f"Error fetching final news with pagination: {e}")
        return [], 0
def get_system_setting(key, default=None):
    """Retrieve a system setting."""
    db = get_db()
    try:
        res = db.run_final_query("SELECT value FROM system_settings WHERE key = ?", [key], fetch='one')
        return res[0] if res else default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return default

def set_system_setting(key, value):
    """Update a system setting."""
    db = get_db()
    try:
        db.run_final_query(
            "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            [key, str(value).lower()]
        )
        return True
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")
        return False

def get_pipeline_backlog():
    """Get counts of unprocessed items across all stages."""
    db = get_db()
    stats = {
        "listing_unextracted": 0,
        "raw_undeduplicated": 0,
        "raw_unscored": 0,
        "ai_pending": 0,
        "final_total": 0
    }
    
    try:
        # 1. Listing (Unextracted)
        exists = db.run_listing_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'telegram_listing'", fetch='one')
        if exists and exists[0] > 0:
            res = db.run_listing_query("SELECT COUNT(*) FROM telegram_listing WHERE is_extracted = FALSE", fetch='one')
            stats["listing_unextracted"] = res[0] if res else 0
    except Exception as e:
        logger.warning(f"Backlog error (listing): {e}")

    try:
        # 2. Raw (Undeduplicated & Unscored)
        exists = db.run_raw_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{SCORING_TABLE.replace('news_scoring', 'telegram_raw')}'", fetch='one')
        # Wait, SCORING_TABLE is news_scoring, but we want telegram_raw from raw connection
        exists = db.run_raw_query("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'telegram_raw'", fetch='one')
        if exists and exists[0] > 0:
            res_dedup = db.run_raw_query("SELECT COUNT(*) FROM telegram_raw WHERE is_deduplicated = FALSE", fetch='one')
            stats["raw_undeduplicated"] = res_dedup[0] if res_dedup else 0
            
            res_score = db.run_raw_query("SELECT COUNT(*) FROM telegram_raw WHERE is_scored = FALSE AND is_duplicate = FALSE", fetch='one')
            stats["raw_unscored"] = res_score[0] if res_score else 0
    except Exception as e:
         logger.warning(f"Backlog error (raw): {e}")

    try:
        # 3. AI Queue (Pending)
        exists = db.run_ai_query("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'ai_queue'", fetch='one')
        if exists and exists[0] > 0:
            res = db.run_ai_query("SELECT COUNT(*) FROM ai_queue WHERE status = 'PENDING'", fetch='one')
            stats["ai_pending"] = res[0] if res else 0
    except Exception as e:
         logger.warning(f"Backlog error (ai): {e}")

    try:
        # 4. Final Total
        exists = db.run_final_query(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{FINAL_TABLE}'", fetch='one')
        if exists and exists[0] > 0:
            res = db.run_final_query(f"SELECT COUNT(*) FROM {FINAL_TABLE}", fetch='one')
            stats["final_total"] = res[0] if res else 0
    except Exception as e:
         logger.warning(f"Backlog error (final): {e}")

    return stats
