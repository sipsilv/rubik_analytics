
import sys
import os
# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

import logging
from app.core.database import SessionLocal
from app.models.connection import Connection
from app.core.security import decrypt_data
import json

def check_status():
    db = SessionLocal()
    conns = db.query(Connection).all()
    print(f"\n{'ID':<5} | {'Name':<30} | {'Status':<15} | {'Health':<10}")
    print("-" * 70)
    for c in conns:
        print(f"{c.id:<5} | {c.name:<30} | {str(c.status):<15} | {str(c.health):<10}")
        if c.id == 8: # Telegram
             if c.credentials:
                 try:
                     d = decrypt_data(c.credentials)
                     j = json.loads(d)
                     tok = j.get('bot_token', 'MISSING')
                     print(f"      -> Token in DB: {tok[:5]}...{tok[-5:] if len(tok)>10 else ''}")
                 except:
                     print("      -> Token: (Decryption Failed)")
    db.close()

if __name__ == "__main__":
    check_status()
