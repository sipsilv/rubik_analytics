
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager
from app.models.user import User

async def test_formatted_message():
    db = SessionLocal()
    try:
        cm = ConnectionManager()
        service = TelegramBotService(cm)
        
        # Get user
        user = db.query(User).filter(User.username == "sandeep").first()
        if not user or not user.telegram_chat_id:
            print("User not found or not linked")
            return

        # Test message with HTML formatting
        message = (
            f"✅ <b>Test: New Message Format</b>\n\n"
            f"Hello <b>{user.username}</b>,\n\n"
            f"This message demonstrates the improved formatting:\n\n"
            f"📝 <b>Features:</b>\n"
            f"• Bold text using <b>HTML tags</b>\n"
            f"• Code blocks: <code>OTP123456</code>\n"
            f"• Emoji support 🚀\n"
            f"• Proper line breaks\n\n"
            f"⏰ Time sensitive notifications\n"
            f"⚠️ Security alerts\n\n"
            f"— Rubik Analytics Team"
        )
        
        success = await service.send_message(user.telegram_chat_id, message)
        
        if success:
            print("✅ Test message sent successfully!")
            print("Check your Telegram to see the improved formatting.")
        else:
            print("❌ Failed to send message")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_formatted_message())
