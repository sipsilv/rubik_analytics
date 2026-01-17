import asyncio
import logging
from app.services.telegram_raw_listener.listener import TelegramListener
from app.services.telegram_raw_listener.config_loader import load_telegram_config
from app.services.telegram_raw_listener.db import init_db as init_listener_db, run_cleanup as run_listener_cleanup

from app.services.telegram_extractor.main import process_batch as process_extraction_batch
from app.services.telegram_extractor.db import ensure_schema as init_extractor_db

from app.services.telegram_deduplication.main import process_batch as process_dedup_batch
from app.services.telegram_deduplication.db import ensure_schema as init_dedup_db

from app.services.news_scoring.main import process_batch as process_scoring_batch
from app.services.news_scoring.db import ensure_schema as init_scoring_db

from app.services.news_ai.processor import run_once as process_ai_batch
from app.services.news_ai.db import ensure_schema as init_ai_db

logger = logging.getLogger("WorkerManager")

async def run_listener_service():
    """Runs the Telegram Listener Service (Async)."""
    try:
        logger.info("[Listener] Initializing DB...")
        try:
           await asyncio.to_thread(init_listener_db)
        except Exception as e:
             logger.error(f"[Listener] DB Init failed (likely concurrent access): {e}")

        logger.info("[Listener] Loading Config...")
        try:
            config = load_telegram_config()
        except Exception as e:
            logger.warning(f"[Listener] Failed to load config (Auth missing?): {e}")
            return

        listener = TelegramListener(config)
        logger.info("[Listener] Starting Client...")
        await listener.start() # This blocks until disconnected
    except Exception as e:
        logger.error(f"[Listener] Crashed: {e}")

async def run_extraction_service():
    """Runs the Extraction Worker (Loop)."""
    try:
        logger.info("[Extractor] Initializing DB...")
        await asyncio.to_thread(init_extractor_db)
    except Exception as e:
        logger.error(f"[Extractor] DB Init failed: {e}")

    logger.info("[Extractor] Started loop.")
    while True:
        try:
            # Run blocking DB operation in thread
            count = await asyncio.to_thread(process_extraction_batch)
            if count == 0:
                await asyncio.sleep(0.5)
            else:
                logger.info(f"[Extractor] Processed {count} items.")
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"[Extractor] Error: {e}")
            await asyncio.sleep(2)

async def run_dedup_service():
    """Runs the Deduplication Worker (Loop)."""
    try:
        logger.info("[Dedup] Initializing DB...")
        await asyncio.to_thread(init_dedup_db)
    except Exception as e:
        logger.error(f"[Dedup] DB Init failed: {e}")

    logger.info("[Dedup] Started loop.")
    while True:
        try:
            count = await asyncio.to_thread(process_dedup_batch)
            if count == 0:
                await asyncio.sleep(0.5)
            else:
                logger.info(f"[Dedup] Processed {count} items.")
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"[Dedup] Error: {e}")
            await asyncio.sleep(2)

async def run_scoring_service():
    """Runs the Scoring Worker (Loop)."""
    try:
        logger.info("[Scorer] Initializing DB...")
        await asyncio.to_thread(init_scoring_db)
    except Exception as e:
        logger.error(f"[Scorer] DB Init failed: {e}")

    logger.info("[Scorer] Started loop.")
    while True:
        try:
            count = await asyncio.to_thread(process_scoring_batch)
            if count == 0:
                await asyncio.sleep(0.5)
            else:
                logger.info(f"[Scorer] Processed {count} items.")
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"[Scorer] Error: {e}")
            await asyncio.sleep(2)

async def run_ai_enrichment_service():
    """Runs the AI Enrichment Worker (Loop)."""
    try:
        logger.info("[AI Enrichment] Initializing DB...")
        await asyncio.to_thread(init_ai_db)
    except Exception as e:
        logger.error(f"[AI Enrichment] DB Init failed: {e}")

    logger.info("[AI Enrichment] Started loop.")
    while True:
        try:
            count = await asyncio.to_thread(process_ai_batch)
            if count == 0:
                await asyncio.sleep(1) # Reduced from 3s
            else:
                logger.info(f"[AI Enrichment] Enriched {count} items.")
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[AI Enrichment] Error: {e}")
            await asyncio.sleep(5)


async def run_cleanup_task():
    """Runs periodic cleanup for listener DB."""
    while True:
         try:
             await asyncio.to_thread(run_listener_cleanup)
         except Exception as e:
             logger.error(f"[Cleanup] Error: {e}")
         await asyncio.sleep(3600)

class WorkerManager:
    def __init__(self):
        self.tasks = []

    def start_all(self):
        """Starts all worker tasks."""
        logger.info("Starting all background workers...")
        
        # 1. Listener
        self.tasks.append(asyncio.create_task(run_listener_service()))
        self.tasks.append(asyncio.create_task(run_cleanup_task()))
        
        # 2. Extractor
        self.tasks.append(asyncio.create_task(run_extraction_service()))
        
        # 3. Deduplicator
        self.tasks.append(asyncio.create_task(run_dedup_service()))
        
        # 4. Scorer
        self.tasks.append(asyncio.create_task(run_scoring_service()))
        
        # 5. AI Enrichment
        self.tasks.append(asyncio.create_task(run_ai_enrichment_service()))
        
        logger.info("All workers started in background.")

    def stop_all(self):
        """Stops all worker tasks."""
        logger.info("Stopping all background workers...")
        for task in self.tasks:
            task.cancel()
        self.tasks = []
        logger.info("All workers stopped.")

worker_manager = WorkerManager()
