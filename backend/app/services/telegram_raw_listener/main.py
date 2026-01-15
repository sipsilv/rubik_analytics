import asyncio
import logging
import sys
import os

# Add backend directory to path if not already added
# This allows running this script directly like `python app/services/telegram_raw_listener/main.py`
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from app.services.telegram_raw_listener.db import init_db, run_cleanup
from app.services.telegram_raw_listener.config_loader import load_telegram_config
from app.services.telegram_raw_listener.listener import TelegramListener

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("listener_debug.log")
    ]
)

logger = logging.getLogger("telegram_listener.main")

async def cleanup_loop():
    """Runs data cleanup every hour."""
    while True:
        try:
            logger.info("Running scheduled cleanup...")
            run_cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        # Wait 1 hour
        await asyncio.sleep(3600)

async def main():
    print("\n\n================================================")
    print("   TELEGRAM RAW LISTENER STARTED (LOGGING ON)   ")
    print("================================================\n\n")
    logger.info("Starting Telegram Raw Listener Service...")
    
    # 1. Initialize Database
    init_db()
    
    # 2. Load Configuration
    try:
        config = load_telegram_config()
    except Exception as e:
        logger.critical(f"Failed to load configuration: {e}")
        # We exit because we can't listen without credentials
        return

    # 3. Initialize Listener
    listener = TelegramListener(config)
    
    # 4. Start Cleanup Task (Background)
    asyncio.create_task(cleanup_loop())
    
    # 5. Start Listener (Blocking)
    try:
        await listener.start()
    except KeyboardInterrupt:
        logger.info("Stopping service...")
    except Exception as e:
        logger.critical(f"Service crashed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
