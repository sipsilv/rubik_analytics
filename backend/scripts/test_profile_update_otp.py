
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.telegram_notification_service import TelegramNotificationService
from app.models.user import User

async def test_profile_update_otp():
    """Test profile update OTP flow"""
    print("=" * 60)
    print("TEST 2: PROFILE UPDATE OTP FLOW")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "sandeep").first()
        if not user:
            print("❌ User not found")
            return
        
        print(f"\n📋 Test User Info:")
        print(f"   Username: {user.username}")
        print(f"   Current Email: {user.email}")
        print(f"   Current Mobile: {user.mobile}")
        print(f"   Telegram Linked: {'Yes ✅' if user.telegram_chat_id else 'No ❌'}")
        
        if not user.telegram_chat_id:
            print("\n⚠️  User not linked to Telegram. Cannot test OTP flow.")
            return
        
        # Simulate profile update scenario
        ns = TelegramNotificationService()
        
        print(f"\n🧪 Simulating Profile Update Request...")
        print(f"   Action: User wants to change email/mobile")
        print(f"   Flow: Generate OTP → Send to Telegram → Wait for verification")
        
        # Generate OTP
        otp = ns.generate_otp(user.mobile)
        print(f"\n✅ OTP Generated: {otp}")
        
        # Send formatted OTP message
        message = (
            f"🔐 <b>Profile Update Verification</b>\n\n"
            f"Hello <b>{user.username}</b>,\n\n"
            f"You are attempting to update sensitive information.\n"
            f"Your verification OTP is: <code>{otp}</code>\n\n"
            f"⏰ Valid for <b>5 minutes</b>\n"
            f"⚠️ If you didn't initiate this, secure your account immediately.\n\n"
            f"— Rubik Analytics Security Team"
        )
        
        success = await ns.bot_service.send_message(user.telegram_chat_id, message)
        
        if success:
            print("✅ Profile Update OTP sent to Telegram!")
            print("\n📱 CHECK YOUR TELEGRAM NOW!")
            print(f"   You should see a profile update verification message")
            print(f"   OTP Code: {otp}")
        else:
            print("❌ Failed to send OTP")
        
        print("\n" + "=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_profile_update_otp())
