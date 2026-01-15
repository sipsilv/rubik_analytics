import time
import logging
import sys
import os

# Add parent directory to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.news_ai.processor import AIEnrichmentProcessor
from app.services.news_ai.db import ensure_schema

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NewsAIWorker")

def run_worker():
    logger.info("Starting News AI Enrichment Worker...")
    
    try:
        ensure_schema()
        logger.info("AI DB Schema verified.")
    except Exception as e:
        logger.critical(f"Schema Init Failed: {e}")
        return
        
    processor = AIEnrichmentProcessor()
    
    from app.services.shared_db import get_shared_db
    last_cleanup = 0
    cleanup_interval = 3600  # 1 hour
    
    while True:
        try:
            # Check for cleanup
            current_time = time.time()
            if current_time - last_cleanup > cleanup_interval:
                logger.info("Triggering periodic pipeline cleanup...")
                get_shared_db().run_pipeline_cleanup(hours=24)
                last_cleanup = current_time

            count = processor.process_batch()
            if count == 0:
                time.sleep(5)
            else:
                logger.info(f"Enriched {count} items.")
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopped.")
            break
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
