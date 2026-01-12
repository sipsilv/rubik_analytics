
import sys
import os
import time
import asyncio
import logging

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.user import User
from app.core.config import settings
from app.core.database.connection_manager import ConnectionManager
from app.services.telegram_bot_service import TelegramBotService

# Configure logging
logging.basicConfig(level=logging.INFO)

async def fix_link():
    print("=== TELEGRAM LINK REPAIR ===")
    
    db = SessionLocal()
    user = db.query(User).filter(User.username == "sandeep").first()
    
    
    if not user:
        print("User 'sandeep' not found.")
        db.close()
        return

    print(f"User: {user.username}")
    print(f"Mobile: {user.mobile}")
    print(f"Current Chat ID: {user.telegram_chat_id}")
    
    user_mobile = user.mobile # Store for later use
    
    # Reset if currently set to dummy
    if user.telegram_chat_id == "123456789":
        print("⚠️ Found DUMMY Chat ID. Resetting to None...")
        user.telegram_chat_id = None
        db.commit()
        print("✅ Chat ID cleared.")
    
    db.close()

    print("\n---------------------------------------------------")
    print("👉 ACTION REQUIRED: Open Telegram App NOW")
    print(f"👉 Search for your bot: @Rubik_Analytics_Bot")
    print(f"👉 Send this command: /start {user_mobile}")
    print("---------------------------------------------------\n")
    print("Waiting for you to send the message... (Ctrl+C to cancel)")

    manager = ConnectionManager(settings.DATA_DIR)
    service = TelegramBotService(manager)

    # Poll for link
    for i in range(60): # Wait 2 minutes max
        db = SessionLocal()
        user = db.query(User).filter(User.username == "sandeep").first()
        if user.telegram_chat_id:
            print(f"\n✅ LINK DETECTED! Chat ID: {user.telegram_chat_id}")
            print("Sending test message...")
            success = await service.send_message(user.telegram_chat_id, "🚀 Your account is now successfully linked to Rubik Analytics!")
            if success:
                print("✅ Test message delivered!")
            else:
                print("❌ Test message failed to send.")
            db.close()
            return
        
        sys.stdout.write(".")
        sys.stdout.flush()
        db.close()
        await asyncio.sleep(2)

    print("\n❌ Timeout. Did you send the message?")

if __name__ == "__main__":
    asyncio.run(fix_link())
