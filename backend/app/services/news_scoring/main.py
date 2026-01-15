import time
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NewsScoringEngine")

from .db import ensure_schema, get_unscored_rows, insert_score_result, update_raw_as_scored
from .scorer import score_news
from .config import BATCH_SIZE

def process_batch():
    rows = get_unscored_rows(limit=BATCH_SIZE)
    if not rows:
        return 0
        
    count = 0
    for row in rows:
        # Schema: raw_id, source_handle, combined_text, received_at, link_text, image_ocr_text
        raw_id, source, text, _, link_text, ocr_text = row
        
        try:
            # Score
            result = score_news(raw_id, source, text, link_text, ocr_text)
            
            # Log decision
            logger.info(f"Row {raw_id} Scored: {result['final_score']} ({result['decision']})")
            
            # Save Result
            insert_score_result(raw_id, result)
            
            # Update Status
            update_raw_as_scored(raw_id)
            
            count += 1
        except Exception as e:
            logger.error(f"Error scoring row {raw_id}: {e}")
            # Do NOT crash. Skip marking as scored so it retries? 
            # Or mark as scored but with error? 
            # Prompt says "DB errors -> log, do not crash".
            # If scoring fails, we probably shouldn't advance, so let it retry or stay stuck until fix.
            
    return count

def run_worker():
    logger.info("Starting News Scoring Engine...")
    
    try:
        ensure_schema()
        logger.info("Scoring DB Schema verified.")
    except Exception as e:
        logger.critical(f"Schema Init Failed: {e}")
        return
        
    while True:
        try:
            count = process_batch()
            if count == 0:
                time.sleep(5)
            else:
                logger.info(f"Scored {count} items.")
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopped.")
            break
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
