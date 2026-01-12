
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
from cryptography.fernet import Fernet
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_connections():
    print("=== DIAGNOSING CONNECTIONS ===")
    print(f"Encryption Key (First 5 chars): {settings.ENCRYPTION_KEY[:5]}...")
    
    try:
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        print("✅ Fernet Key initialized successfully.")
    except Exception as e:
        print(f"❌ Failed to initialize Fernet Key: {e}")
        return

    db = SessionLocal()
    try:
        connections = db.query(Connection).all()
        print(f"\nFound {len(connections)} connections in DB.")
        
        for conn in connections:
            print(f"\n[ID: {conn.id}] {conn.name} ({conn.connection_type})")
            if not conn.credentials:
                print("   - No credentials stored.")
                continue
                
            try:
                decrypted = f.decrypt(conn.credentials.encode()).decode()
                print("   ✅ Decryption SUCCESS")
                try:
                    data = json.loads(decrypted)
                    # Mask token for display
                    if "bot_token" in data:
                        token = data["bot_token"]
                        masked = f"{token[:5]}...{token[-5:]}" if len(token) > 10 else "***"
                        print(f"   - bot_token: {masked}")
                    print(f"   - Keys: {list(data.keys())}")
                except:
                    print(f"   - Content: {decrypted}")
                    
            except Exception as e:
                print(f"   ❌ Decryption FAILED: {e}")
                
    finally:
        db.close()
    print("\n=== DIAGNOSIS COMPLETE ===")

if __name__ == "__main__":
    diagnose_connections()
