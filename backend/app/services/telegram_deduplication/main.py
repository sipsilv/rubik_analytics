import time
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TelegramDeduplicationWorker")

from .db import (
    ensure_schema, 
    get_unprocessed_rows, 
    check_exact_duplicate, 
    get_recent_non_duplicates, 
    update_deduplication_status
)
from .deduplicator import compute_hash, find_near_duplicate
from .config import BATCH_SIZE, SIMILARITY_LOOKBACK_LIMIT, SIMILARITY_LOOKBACK_HOURS

def process_batch():
    rows = get_unprocessed_rows(limit=BATCH_SIZE)
    if not rows:
        return 0
    
    processed_count = 0
    
    # Pre-fetch candidates for near-dup check to avoid repeated DB hits?
    # Actually, for each row, the set of candidates might change (if we process sequentially).
    # But since we only check against 'deduped and non-duplicate' rows, and current batch is not yet deduped,
    # the candidates set is static relative to the *already processed* rows in DB.
    # However, within the batch, if row 2 is dup of row 1, we should catch it.
    # Approach: 
    # 1. Fetch recent non-duplicates from DB.
    # 2. Maintain a local cache of "seen in this batch" to catch duplicates within the batch.
    
    candidates = get_recent_non_duplicates(limit=SIMILARITY_LOOKBACK_LIMIT, lookback_hours=SIMILARITY_LOOKBACK_HOURS)
    # candidates is list of (raw_id, normalized_text)
    
    # Create a mutable list to append valid unique items from current batch
    active_candidates = list(candidates)
    
    for row in rows:
        raw_id, text, file_id, received_at = row
        
        # 1. Compute Hash (Include file_id to distinguishing images)
        content_hash = compute_hash(text, file_id)
        
        # 2. Exact Duplicate Check (DB)
        exact_dup_id = check_exact_duplicate(content_hash, lookback_hours=SIMILARITY_LOOKBACK_HOURS)
        
        is_duplicate = False
        duplicate_of_id = None
        
        if exact_dup_id:
            is_duplicate = True
            duplicate_of_id = exact_dup_id
            logger.info(f"Row {raw_id}: Exact duplicate of {exact_dup_id}")
        else:
            # Check against active_candidates (both DB and local batch) for Hash?
            # check_exact_duplicate only checks DB. We should also check within batch if we want perfect strictness.
            # But let's stick to the prompt's order: "Check DuckDB for same hash".
            # If prompt implies strictly DB check, we might miss dupes within same batch if processing parallel.
            # But we are sequential.
            # Let's check Similarity.
            
            # 3. Near Duplicate Check
            near_dup_id = find_near_duplicate(text, active_candidates)
            if near_dup_id:
                is_duplicate = True
                duplicate_of_id = near_dup_id
                logger.info(f"Row {raw_id}: Near duplicate of {near_dup_id}")
            
        # 4. Update DB
        update_deduplication_status(raw_id, content_hash, is_duplicate, duplicate_of_id)
        
        # 5. Update local candidates if NOT duplicate
        if not is_duplicate:
            # Prepend to candidates so it's freshest
            active_candidates.insert(0, (raw_id, text))
            # Keep limit
            if len(active_candidates) > SIMILARITY_LOOKBACK_LIMIT:
                active_candidates.pop()
        
        processed_count += 1

    return processed_count

def run_worker():
    logger.info("Starting Telegram Deduplication Worker...")
    
    # 1. Ensure Schema
    try:
        ensure_schema()
        logger.info("Schema verified.")
    except Exception as e:
        logger.critical(f"Failed to initialize schema: {e}")
        return

    # 2. Worker Loop
    while True:
        try:
            count = process_batch()
            if count == 0:
                time.sleep(5)  # Wait if no new data
            else:
                logger.info(f"Processed {count} items.")
                time.sleep(1)  # Brief pause between batches
        except KeyboardInterrupt:
            logger.info("Worker stopped by user.")
            break
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
