
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager
from app.models.user import User

async def send_hello():
    db = SessionLocal()
    try:
        cm = ConnectionManager()
        service = TelegramBotService(cm)
        
        # Get user
        user = db.query(User).filter(User.username == "sandeep").first()
        if not user:
            print("User 'sandeep' not found!")
            return

        chat_id = user.telegram_chat_id
        mobile = user.mobile
        
        print(f"User: {user.username}")
        print(f"Mobile: {mobile}")
        print(f"Chat ID: {chat_id}")
        
        if not chat_id:
            print("\n❌ User is NOT linked to Telegram.")
            print(f"👉 Please open your bot in Telegram and send: /start {mobile}")
            print("   (This will link your Chat ID to your account)")
            return

        # Try to send message
        print(f"\nAttempting to send message to Chat ID: {chat_id}...")
        try:
            success = await service.send_message(chat_id, "🔔 Hello! This is a test message from Rubik Analytics.")
            if success:
                print("✅ Message Sent Successfully!")
            else:
                print("❌ Failed to send message (Check logs/token validity)")
        except Exception as e:
            print(f"❌ Error sending message: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(send_hello())
