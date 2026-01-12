
import sys
import os
import json
import requests

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection
from app.core.security import decrypt_data

def test_token():
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(Connection.connection_type == 'TELEGRAM_BOT').first()
        if not conn:
            print("No TELEGRAM_BOT connection found.")
            return
        
        if not conn.credentials:
             print("No credentials found.")
             return

        decrypted = decrypt_data(conn.credentials)
        try:
            data = json.loads(decrypted)
            token = data.get("bot_token")
        except:
            token = decrypted

        if not token:
            print("No token found in credentials.")
            return

        print(f"Testing Token: {token[:4]}...{token[-4:]}")
        
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = requests.get(url)
        
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")

        if resp.status_code == 200:
            user_data = resp.json().get("result", {})
            print(f"✅ VALID! Bot Name: {user_data.get('first_name')} (@{user_data.get('username')})")
        elif resp.status_code == 401:
            print("❌ INVALID TOKEN (Unauthorized). Please generate a new token from @BotFather.")
        else:
            print("❌ Error communicating with Telegram.")

    finally:
        db.close()

if __name__ == "__main__":
    test_token()
