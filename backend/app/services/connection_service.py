import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.auth.security import encrypt_data, decrypt_data
from app.core.config import settings
from app.models.connection import Connection, ConnectionStatus, ConnectionHealth
from app.repositories.connection_repository import ConnectionRepository

logger = logging.getLogger(__name__)

class ConnectionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ConnectionRepository(db)

    def decrypt_credentials(self, connection: Connection) -> Dict[str, Any]:
        if not connection.credentials:
            return {}
        try:
            return json.loads(decrypt_data(connection.credentials))
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for connection {connection.id}: {e}")
            return {}

    def encrypt_details(self, details: Dict[str, Any]) -> str:
        json_str = json.dumps(details)
        return encrypt_data(json_str)

    def validate_truedata_credentials(self, details: Dict[str, Any]) -> tuple[bool, str]:
        import requests
        username = details.get("username")
        password = details.get("password")
        auth_url = details.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
        
        if not username or not password:
            return False, "Username and password are required"
            
        try:
            response = requests.post(
                auth_url,
                data={
                    "username": username.strip(),
                    "password": password.strip(),
                    "grant_type": "password"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )
            response.raise_for_status()
            token_data = response.json()
            if not token_data.get("access_token"):
                return False, "No access_token in response"
            return True, "Credentials validated"
        except Exception as e:
            return False, f"Validation failed: {str(e)}"

    async def validate_telegram_bot_token(self, token: str) -> tuple[bool, str, Optional[str]]:
        import aiohttp
        clean_token = token.strip()
        if clean_token.lower().startswith("bot") and len(clean_token) > 3 and clean_token[3].isdigit():
            clean_token = clean_token[3:]
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/bot{clean_token}/getMe", timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            return True, "Valid", clean_token
                        return False, f"Telegram API Error: {data.get('description')}", None
                    elif resp.status == 401:
                        return False, "Invalid Bot Token (401)", None
                    else:
                        return False, f"HTTP Error {resp.status}", None
        except Exception as e:
            return False, str(e), None

    def create_connection(self, data: Any) -> Connection:
        # Note: 'data' is ConnectionCreate schema
        # Logic from controller moved here...
        # For brevity, I will focus on minimal move or full logic replication.
        # Given the complexity, I will keep complex validation in controller or fully move it.
        # Let's effectively move the core creation logic here.
        pass # To be implemented in controller integration
