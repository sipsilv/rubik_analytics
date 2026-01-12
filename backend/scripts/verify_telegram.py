
import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager
from app.models.user import User
from app.models.connection import Connection
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_flow():
    print("=== TELEGRAM INTEGRATION DIAGNOSTICS ===")
    
    # 1. Check Connection
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(Connection.connection_type == "TELEGRAM_BOT", Connection.is_enabled == True).first()
        if not conn:
            print("❌ No ENABLED 'TELEGRAM_BOT' connection found in database.")
            print("   -> Go to Admin Panel > Connections and add a Telegram Bot.")
            return
        print(f"✅ Found Connection: {conn.name} (ID: {conn.id})")
    finally:
        db.close()

    # 2. Check Service Initialization
    try:
        manager = ConnectionManager(settings.DATA_DIR)
        service = TelegramBotService(manager)
        token = await service._get_bot_token()
        
        if not token:
            print("❌ Could not retrieve or decrypt Bot Token.")
            return
        print(f"✅ Bot Token retrieved (starts with: {token[:4]}...)")
    except Exception as e:
        print(f"❌ Service Initialization Failed: {e}")
        return

    # 3. Check Linked Users
    db = SessionLocal()
    try:
        # Find ANY user with a telegram_chat_id
        linked_user = db.query(User).filter(User.telegram_chat_id != None).first()
        
        # Find ANY user to simulate linking with (if no linked user exists)
        target_user = linked_user if linked_user else db.query(User).first()
        
        if not target_user:
            print("❌ No users found in database.")
            return

        print(f"\n✅ Target User Selected: {target_user.username} (Mobile: {target_user.mobile})")
        if linked_user:
             print(f"   -> Already Linked! Chat ID: {linked_user.telegram_chat_id}")
        else:
             print("   -> Not yet linked to Telegram.")

        print("\n--- AUTOMATIC TEST ---")
        
        if linked_user:
            # Case A: User is already linked - Just send a message
            print(f"Attempting to send message to existing Chat ID: {linked_user.telegram_chat_id}...")
            success = await service.send_message(linked_user.telegram_chat_id, "🔔 Automatic Test Message from Rubik Analytics")
            if success:
                print("✅ Message Sent Successfully to Telegram!")
            else:
                print("❌ Message Failed (Check Bot Token or if User blocked bot)")

            print("\n--- MANUAL DIAGNOSTIC TEST ---")
            print("1. Skip manual test")
            print("2. Send a custom message to a specific chat ID (for detailed error diagnostics)")
            choice = input("Enter your choice (1 or 2): ").strip()

            if choice == "2":
                chat_id = input("Enter Target Chat ID: ").strip()
                msg = "🔔 This is a test message from your Rubik Analytics System."
                print(f"Sending to {chat_id}...")
            
                # Call API directly to see error
                import aiohttp
                token = await service._get_bot_token()
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": msg}
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            print("✅ Message Sent Successfully!")
                        else:
                            print(f"❌ Failed (HTTP {resp.status})")
                            print(f"Response: {await resp.text()}")
        else:
            # Case B: Simulate the Linking Process (Backend Logic Test)
            print("User not linked. Please send /start to your bot in Telegram to link.")
            # print("User not linked. Simulating the /start command logic...")
            
            # Use a dummy chat ID for simulation if we don't have a real one
            # dummy_chat_id = "123456789" 
            # print(f"Simulating webhook: User {target_user.mobile} sends '/start {target_user.mobile}'")
            
            # payload = {
            #     "message": {
            #         "chat": {"id": dummy_chat_id},
            #         "text": f"/start {target_user.mobile}"
            #     }
            # }
            
            # await service.process_webhook_update(payload, db)
            
            # Verify it was saved
            # db.expire_all() # Refresh
            # updated_user = db.query(User).filter(User.id == target_user.id).first()
            # if updated_user.telegram_chat_id == dummy_chat_id:
            #     print(f"✅ Linking Logic Verified: User {updated_user.username} is now linked to Chat ID {dummy_chat_id}")
            #     print("   (Note: This was a simulation. For real notifications, the user must actually send /start to your bot.)")
            # else:
            #     print("❌ Linking Logic Failed: Database was not updated.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_flow())
