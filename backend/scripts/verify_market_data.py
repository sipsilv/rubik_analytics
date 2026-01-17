import sys
import os
import logging

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.announcements_service import get_announcements_service
from app.services.news_service import get_news_service
from app.services.symbols_service import get_symbols_service
from app.services.screener_service import get_screener_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_announcements():
    logger.info("Verifying Announcements Service...")
    service = get_announcements_service()
    
    # Test DB connection and simple retrieval
    try:
        anns, total = service.get_announcements(limit=5)
        logger.info(f"Retrieved {len(anns)} announcements (Total: {total})")
        return True
    except Exception as e:
        logger.error(f"Announcements verification failed: {e}")
        return False

def verify_news():
    logger.info("Verifying News Service...")
    service = get_news_service()
    
    try:
        news_data = service.get_news(page=1, page_size=5)
        logger.info(f"Retrieved {len(news_data.get('news', []))} news items")
        
        status = service.get_status()
        logger.info(f"News Status: {status}")
        return True
    except Exception as e:
        logger.error(f"News verification failed: {e}")
        return False

def verify_symbols():
    logger.info("Verifying Symbols Service...")
    service = get_symbols_service()
    
    try:
        stats = service.get_stats()
        logger.info(f"Symbols Stats: {stats}")
        return True
    except Exception as e:
        logger.error(f"Symbols verification failed: {e}")
        return False

def verify_screener():
    logger.info("Verifying Screener Service...")
    service = get_screener_service()
    
    try:
        stats = service.get_stats()
        logger.info(f"Screener Stats: {stats}")
        return True
    except Exception as e:
        logger.error(f"Screener verification failed: {e}")
        return False

if __name__ == "__main__":
    success = True
    success &= verify_announcements()
    success &= verify_news()
    success &= verify_symbols()
    success &= verify_screener()
    
    if success:
        logger.info("All Market Data Modules Verification PASSED")
        sys.exit(0)
    else:
        logger.error("Some verifications FAILED")
        sys.exit(1)
