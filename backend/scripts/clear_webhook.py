
import asyncio
import sys
import os
import aiohttp

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager

async def clear_webhook():
    cm = ConnectionManager()
    service = TelegramBotService(cm)
    token = await service._get_bot_token()
    
    if not token:
        print("No token found.")
        return

    print(f"Token: {token[:4]}...")
    
    async with aiohttp.ClientSession() as session:
        # Delete Webhook
        async with session.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=False") as resp:
            data = await resp.json()
            print(f"Delete Webhook Status: {data}")

if __name__ == "__main__":
    asyncio.run(clear_webhook())
