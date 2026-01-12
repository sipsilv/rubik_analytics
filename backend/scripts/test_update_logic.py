
import sys
import os
import json
import logging
from datetime import datetime, timezone

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection, ConnectionType
from app.core.security import encrypt_data, decrypt_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection_update():
    db = SessionLocal()
    conn_id = None
    try:
        # 1. Create a dummy TELEGRAM_BOT connection
        logger.info("=== 1. Creating dummy connection ===")
        initial_details = {"bot_token": "TOKEN_A"}
        encrypted = encrypt_data(json.dumps(initial_details))
        
        conn = Connection(
            name="Test_Telegram_Bot",
            connection_type="TELEGRAM_BOT",
            provider="Telegram",
            is_enabled=True,
            credentials=encrypted,
            status="CONNECTED",
            health="HEALTHY"
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        conn_id = conn.id
        logger.info(f"Created connection ID: {conn_id} with TOKEN_A")
        
        # Verify creation
        saved_conn = db.query(Connection).filter(Connection.id == conn_id).first()
        saved_creds = json.loads(decrypt_data(saved_conn.credentials))
        logger.info(f"Saved token: {saved_creds.get('bot_token')}")
        if saved_creds.get('bot_token') != "TOKEN_A":
             logger.error("❌ CREATE FAILED: Token mismatch")
             return

        # 2. Simulate UPDATE (like the API endpoint logic)
        logger.info("\n=== 2. Updating connection to TOKEN_B ===")
        
        # This mirrors the logic in api/v1/connections.py update_connection
        update_data_details = {"bot_token": "TOKEN_B"}
        
        # -- START logic from endpoint --
        existing_config = {}
        if saved_conn.credentials:
            existing_config = json.loads(decrypt_data(saved_conn.credentials))
            
        merged_details = existing_config.copy()
        
        for key, value in update_data_details.items():
            if value is not None and value != "":
                merged_details[key] = value
                
        # Simulating the validation logic (simplified logic)
        final_details = merged_details
        
        # Save back to DB
        saved_conn.credentials = encrypt_data(json.dumps(final_details))
        saved_conn.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(saved_conn)
        # -- END logic from endpoint --
        
        # 3. Verify Update
        logger.info("\n=== 3. Verifying Update ===")
        updated_conn = db.query(Connection).filter(Connection.id == conn_id).first()
        updated_creds = json.loads(decrypt_data(updated_conn.credentials))
        final_token = updated_creds.get('bot_token')
        
        logger.info(f"Updated token in DB: {final_token}")
        
        if final_token == "TOKEN_B":
            logger.info("✅ UPDATE SUCCESS: Token changed to TOKEN_B")
        else:
            logger.error(f"❌ UPDATE FAILED: Expected TOKEN_B, got {final_token}")

    finally:
        # Cleanup
        if conn_id:
            logger.info("\n=== Cleanup ===")
            db.query(Connection).filter(Connection.id == conn_id).delete()
            db.commit()
            logger.info("Test connection deleted")
        db.close()

if __name__ == "__main__":
    test_connection_update()
