import json
import logging
import sys
import os

# Add backend directory to path if not already added, to allow imports from app
# Assumes this script might be run from backend/ or backend/app/services/telegram_raw_listener/
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.connection import Connection, ConnectionType
from app.models.telegram_channel import TelegramChannel
from app.core.security import decrypt_data

logger = logging.getLogger("telegram_listener.config_loader")

def load_telegram_config():
    """
    Fetches Telegram configuration from the main database.
    Returns a dict with:
        - api_id
        - api_hash
        - session_string
        - channels: list of channel IDs (int)
    Raises ValueError if no valid config found.
    """
    
    # Get a database session
    # get_db is a generator
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # 1. Fetch Active Telegram User Connection
        connection = db.query(Connection).filter(
            Connection.connection_type == ConnectionType.TELEGRAM_USER,
            Connection.is_enabled == True
        ).first()

        if not connection:
            logger.warning("No enabled TELEGRAM_USER connection found.")
            raise ValueError("No enabled TELEGRAM_USER connection found.")

        # 2. Decrypt Credentials
        try:
            creds_json = decrypt_data(connection.credentials)
            creds = json.loads(creds_json)
            
            api_id = creds.get("api_id")
            api_hash = creds.get("api_hash")
            session_string = creds.get("session_string")

            if not all([api_id, api_hash, session_string]):
                raise ValueError("Incomplete credentials in connection.")
                
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for connection {connection.id}: {e}")
            raise ValueError("Invalid credentials.")

        # 3. Fetch Enabled Channels
        channels = db.query(TelegramChannel).filter(
            TelegramChannel.connection_id == connection.id,
            TelegramChannel.is_enabled == True
        ).all()
        
        # Extract Channel IDs
        # Ensure they are integers. Telethon needs int IDs.
        # If they are stored as strings or huge ints, confirm type. 
        # Model default is BigInteger, so Python int.
        channel_ids = [ch.channel_id for ch in channels]
        
        if not channel_ids:
            logger.warning(f"No enabled channels found for connection {connection.name}.")

        logger.info(f"Loaded config for {connection.name}: {len(channel_ids)} channels.")

        return {
            "api_id": int(api_id),
            "api_hash": str(api_hash),
            "session_string": str(session_string),
            "channels": channel_ids
        }

    finally:
        db.close()
