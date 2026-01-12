
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager

async def manual_link():
    chat_id = "465736878"
    mobile = "8686504620"
    
    db = SessionLocal()
    try:
        cm = ConnectionManager()
        service = TelegramBotService(cm)
        
        # Link user
        await service._link_user(chat_id, mobile, db)
        
        print(f"✅ Linked Chat ID {chat_id} to mobile {mobile}")
        
        # Verify
        from app.models.user import User
        user = db.query(User).filter(User.mobile == mobile).first()
        if user:
            print(f"User: {user.username}")
            print(f"Chat ID: {user.telegram_chat_id}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(manual_link())
