
import sys
import os
import requests
import json

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection
from app.core.security import decrypt_data

API_URL = "http://localhost:8000/api/v1/admin/connections"

def real_update_test():
    # 1. Get real token from DB
    db = SessionLocal()
    conn = db.query(Connection).filter(Connection.id == 8).first()
    if not conn:
        print("Connection 8 not found")
        return
        
    real_token = ""
    if conn.credentials:
        decrypted = decrypt_data(conn.credentials)
        try:
            real_token = json.loads(decrypted).get("bot_token")
        except:
            real_token = decrypted
            
    db.close()
    
    if not real_token:
        print("Could not retrieve real token from DB. Aborting.")
        return

    print(f"Retrieved Real Token: {real_token[:5]}...")

    # 2. Call API to update
    print("\nCalling API Update...")
    headers = {
        "Content-Type": "application/json"
        # Assuming no auth or token needed for localhost/testing context if auth middleware allows,
        # otherwise might need to login. But let's try.
        # Check if auth required? Yes.
        # We need a token.
    }
    
    # We can rely on the fact that we are running locally? 
    # Or we can generate a token using `create_access_token` since we have backend access?
    from app.core.security import create_access_token
    token = create_access_token({"sub": "sandeep", "id": 1, "is_admin": True})
    headers["Authorization"] = f"Bearer {token}"
    
    payload = {
        "name": "Telegram Bot", # Reset name
        "connection_type": "TELEGRAM_BOT",
        "provider": "Telegram",
        "is_enabled": True,
        "details": {
            "bot_token": real_token
        }
    }
    
    try:
        resp = requests.put(f"{API_URL}/8", json=payload, headers=headers)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"API Returned Status: {data.get('status')}")
            print(f"API Returned Health: {data.get('health')}")
            if data.get('status') == 'CONNECTED':
                print("✅ API Validation SUCCESS!")
            else:
                print("❌ API Validation FAILED (Status not CONNECTED)")
        else:
             print(f"API Error: {resp.text}")
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    real_update_test()
