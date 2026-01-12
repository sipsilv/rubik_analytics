
import sys
import os
import json
import logging

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection
from app.core.security import decrypt_data

def debug_creds():
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(Connection.connection_type == 'TELEGRAM_BOT').first()
        if not conn:
            print("No TELEGRAM_BOT connection found.")
            return

        print(f"Connection ID: {conn.id}")
        print(f"Name: {conn.name}")
        
        if conn.credentials:
            decrypted = decrypt_data(conn.credentials)
            try:
                data = json.loads(decrypted)
                print("Decrypted Credentials Keys:", list(data.keys()))
                print(f"Bot Token value: {data.get('bot_token')[:5]}... (length: {len(data.get('bot_token', ''))})")
            except:
                print("Credentials are not JSON:", decrypted)
        else:
            print("No credentials stored.")
            
    finally:
        db.close()

if __name__ == "__main__":
    debug_creds()
