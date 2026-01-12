
import asyncio
import sys
import os
import requests

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User

async def test_forgot_password():
    """Test forgot password OTP flow"""
    print("=" * 60)
    print("TEST 1: FORGOT PASSWORD OTP FLOW")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "sandeep").first()
        if not user:
            print("❌ User not found")
            return
        
        print(f"\n📋 Test User Info:")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Mobile: {user.mobile}")
        print(f"   User ID: {user.id}")
        print(f"   Telegram Linked: {'Yes ✅' if user.telegram_chat_id else 'No ❌'}")
        
        if not user.telegram_chat_id:
            print("\n⚠️  User not linked to Telegram. Cannot test OTP flow.")
            return
        
        # Test with mobile number
        print(f"\n🧪 Testing forgot password with MOBILE: {user.mobile}")
        response = requests.post(
            "http://localhost:8000/api/v1/auth/forgot-password",
            json={"email": user.mobile}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        if response.status_code == 200:
            print("   ✅ OTP should be sent to Telegram!")
            print("   📱 Check your Telegram for the password reset OTP")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Test with email
        if user.email:
            print(f"\n🧪 Testing forgot password with EMAIL: {user.email}")
            response = requests.post(
                "http://localhost:8000/api/v1/auth/forgot-password",
                json={"email": user.email}
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            
            if response.status_code == 200:
                print("   ✅ OTP should be sent to Telegram!")
                print("   📱 Check your Telegram for the password reset OTP")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Test with user ID
        print(f"\n🧪 Testing forgot password with USER ID: {user.id}")
        response = requests.post(
            "http://localhost:8000/api/v1/auth/forgot-password",
            json={"email": str(user.id)}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        if response.status_code == 200:
            print("   ✅ OTP should be sent to Telegram!")
            print("   📱 Check your Telegram for the password reset OTP")
        
        print("\n" + "=" * 60)
        print("📱 CHECK YOUR TELEGRAM NOW!")
        print("You should have received 3 password reset OTP messages")
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_forgot_password())
