
import sys
import os
import json

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection
from app.core.security import decrypt_data

def inspect_bot_token():
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(Connection.connection_type == 'TELEGRAM_BOT').first()
        if not conn:
            print("No TELEGRAM_BOT connection found.")
            return
        
        print(f"Connection Name: {conn.name}")
        print(f"Enabled: {conn.is_enabled}")
        
        if conn.credentials:
            decrypted = decrypt_data(conn.credentials)
            print(f"Raw Decrypted Credentials: {decrypted}")
            
            try:
                data = json.loads(decrypted)
                print(f"Parsed JSON: {data}")
                if "bot_token" in data:
                    token = data["bot_token"]
                    print(f"Token Found: {token[:4]}...{token[-4:]}")
                else:
                    print("ERROR: 'bot_token' key missing in JSON.")
            except json.JSONDecodeError:
                print("WARNING: Credentials are NOT valid JSON. (This might be the issue if the code expects JSON)")
        else:
            print("Credentials field is empty.")
            
    finally:
        db.close()

if __name__ == "__main__":
    inspect_bot_token()
