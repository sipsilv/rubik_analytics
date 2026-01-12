
import asyncio
import sys
import os
import aiohttp
import logging
import json

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BotPolling")

async def run_polling():
    cm = ConnectionManager()
    service = TelegramBotService(cm)
    
    # Get Token
    token = await service._get_bot_token()
    if not token:
        logger.error("No Telegram Bot Token found or enabled in DB!")
        return

    logger.info(f"Starting Polling for Bot (Token ends in ...{token[-4:]})")
    
    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Long Polling with 30s timeout
                params = {"offset": offset + 1, "timeout": 30}
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Error getting updates: {resp.status} {await resp.text()}")
                        await asyncio.sleep(5)
                        continue
                    
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.error(f"API Error: {data}")
                        await asyncio.sleep(5)
                        continue
                        
                    results = data.get("result", [])
                    for update in results:
                        update_id = update.get("update_id")
                        offset = max(offset, update_id)
                        
                        logger.info(f"Processing update {update_id}...")
                        
                        # Process using existing service logic
                        db = SessionLocal()
                        try:
                            await service.process_webhook_update(update, db)
                            logger.info("Update processed successfully.")
                        except Exception as e:
                            logger.error(f"Error processing update: {e}")
                        finally:
                            db.close()
                            
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        logger.info("Polling stopped by user.")
