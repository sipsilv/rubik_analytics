
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_bot_service import TelegramBotService
from app.core.database.connection_manager import ConnectionManager
from app.models.user import User
from datetime import datetime

async def test_security_alerts():
    """Test security alert messages"""
    print("=" * 60)
    print("TEST 3: SECURITY ALERT MESSAGES")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        cm = ConnectionManager()
        service = TelegramBotService(cm)
        
        user = db.query(User).filter(User.username == "sandeep").first()
        if not user or not user.telegram_chat_id:
            print("❌ User not found or not linked")
            return
        
        print(f"\n📋 Test User: {user.username}")
        print(f"   Telegram Chat ID: {user.telegram_chat_id}")
        
        # Test 1: Profile Update Success Alert
        print(f"\n🧪 Test 1: Profile Update Success Alert")
        changes_str = "Email, Mobile"
        message = (
            f"✅ <b>Profile Updated Successfully</b>\n\n"
            f"Hello <b>{user.username}</b>,\n\n"
            f"The following details have been updated:\n"
            f"📝 {changes_str}\n\n"
            f"⚠️ If you didn't make these changes, contact support immediately.\n\n"
            f"— Rubik Analytics"
        )
        success = await service.send_message(user.telegram_chat_id, message)
        print(f"   Status: {'✅ Sent' if success else '❌ Failed'}")
        await asyncio.sleep(2)
        
        # Test 2: Password Change Alert
        print(f"\n🧪 Test 2: Password Change Security Alert")
        now = datetime.now().strftime("%d-%b-%Y %I:%M %p")
        message = (
            f"🚨 <b>Security Alert: Password Changed</b>\n\n"
            f"Hello <b>{user.username}</b>,\n\n"
            f"Your account password was successfully changed.\n\n"
            f"🕐 Time: <code>{now}</code>\n\n"
            f"⚠️ <b>If you didn't make this change:</b>\n"
            f"• Someone may have accessed your account\n"
            f"• Contact support immediately\n"
            f"• Secure all your linked accounts\n\n"
            f"— Rubik Analytics Security Team"
        )
        success = await service.send_message(user.telegram_chat_id, message)
        print(f"   Status: {'✅ Sent' if success else '❌ Failed'}")
        await asyncio.sleep(2)
        
        # Test 3: Login OTP
        print(f"\n🧪 Test 3: Login OTP Message")
        otp = "123456"  # Dummy OTP for testing
        message = (
            f"🔐 <b>Login Verification Required</b>\n\n"
            f"Hello <b>{user.username}</b>,\n\n"
            f"Your login OTP is: <code>{otp}</code>\n\n"
            f"⏰ Valid for <b>5 minutes</b>\n"
            f"⚠️ If this wasn't you, secure your account immediately.\n\n"
            f"— Rubik Analytics Security Team"
        )
        success = await service.send_message(user.telegram_chat_id, message)
        print(f"   Status: {'✅ Sent' if success else '❌ Failed'}")
        
        print("\n" + "=" * 60)
        print("📱 CHECK YOUR TELEGRAM NOW!")
        print("You should have received 3 messages:")
        print("  1. Profile Update Success")
        print("  2. Password Change Security Alert")
        print("  3. Login OTP")
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_security_alerts())
