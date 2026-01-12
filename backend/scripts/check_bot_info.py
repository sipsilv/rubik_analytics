
import asyncio
import sys
import os
import aiohttp

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager

async def check_bot():
    cm = ConnectionManager()
    service = TelegramBotService(cm)
    token = await service._get_bot_token()
    
    if not token:
        print("No token found.")
        return

    print(f"Token: {token[:10]}...{token[-4:]}")
    
    async with aiohttp.ClientSession() as session:
        # Get Bot Info
        async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
            data = await resp.json()
            print(f"\nBot Info: {data}")
        
        # Get Webhook Info
        async with session.get(f"https://api.telegram.org/bot{token}/getWebhookInfo") as resp:
            data = await resp.json()
            print(f"\nWebhook Info: {data}")
        
        # Get Updates (last 5)
        async with session.get(f"https://api.telegram.org/bot{token}/getUpdates?limit=5") as resp:
            data = await resp.json()
            print(f"\nRecent Updates: {data}")
            if data.get('result'):
                print(f"Number of updates: {len(data['result'])}")
                for update in data['result']:
                    print(f"  Update ID: {update.get('update_id')}")
                    if 'message' in update:
                        print(f"    Message: {update['message'].get('text')}")
                        print(f"    From: {update['message'].get('from', {}).get('username')}")
                        print(f"    Chat ID: {update['message'].get('chat', {}).get('id')}")

if __name__ == "__main__":
    asyncio.run(check_bot())
