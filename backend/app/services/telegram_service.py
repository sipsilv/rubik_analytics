import logging
import json
import asyncio
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from telethon.sessions import StringSession

from app.models.connection import Connection, ConnectionType
from app.models.telegram_channel import TelegramChannel, ChannelStatus
from app.core.auth.security import decrypt_data
from app.repositories.telegram_repository import TelegramRepository
from app.services.telegram_raw_listener.config import TABLE_NAME
from app.providers.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TelegramRepository(db)

    def _get_client(self, session_string: str, api_id: int, api_hash: str) -> TelegramClient:
        return TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            system_version="4.16.30-vxCustom",
            device_model="OpenAnalytics-Discovery",
            app_version="1.0.0",
            connection_retries=2,
            retry_delay=1
        )

    def _get_credentials(self, connection_id: int):
        connection = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not connection:
            raise ValueError("Connection not found")
        
        if connection.connection_type != ConnectionType.TELEGRAM_USER:
            raise ValueError("Discovery only supported for Telegram User connections")

        try:
            creds_json = decrypt_data(connection.credentials)
            creds = json.loads(creds_json)
            session_string = creds.get("session_string")
            api_id = creds.get("api_id")
            api_hash = creds.get("api_hash")

            if not session_string or not api_id or not api_hash:
                raise ValueError("Incomplete credentials")
            
            return session_string, api_id, api_hash
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for connection {connection_id}: {e}")
            raise ValueError("Invalid credentials")

    async def discover_channels(self, connection_id: int) -> List[dict]:
        session_string, api_id, api_hash = self._get_credentials(connection_id)
        client = self._get_client(session_string, api_id, api_hash)
        
        discovered = []
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session expired or invalid")

            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if not isinstance(entity, (Channel, Chat)):
                    continue

                # Identify type
                c_type = "unknown"
                if isinstance(entity, Channel):
                    c_type = "supergroup" if entity.megagroup else "channel"
                elif isinstance(entity, Chat):
                    c_type = "group"
                else: 
                    continue # Should not happen given check above

                c_id = int(entity.id)

                # Check existence
                existing = self.repository.get_channel_by_telegram_id(connection_id, c_id)
                status = ChannelStatus.IDLE
                db_id = None
                if existing:
                    status = "ALREADY_ADDED"
                    db_id = existing.id

                discovered.append({
                    "id": c_id,
                    "db_id": db_id,
                    "title": entity.title,
                    "username": getattr(entity, 'username', None),
                    "type": c_type,
                    "participants_count": getattr(entity, 'participants_count', None),
                    "status": status
                })

        except Exception as e:
            import traceback
            logger.error(f"Error during channel discovery: {e}\n{traceback.format_exc()}")
            raise e
        finally:
            await client.disconnect()

        return discovered

    def register_channels(self, connection_id: int, channels: List[dict]) -> int:
        count = 0
        for ch_data in channels:
            exists = self.repository.get_channel_by_telegram_id(connection_id, ch_data['id'])
            if exists:
                continue

            new_channel = TelegramChannel(
                connection_id=connection_id,
                channel_id=ch_data['id'],
                title=ch_data['title'],
                username=ch_data.get('username'),
                type=ch_data['type'],
                member_count=ch_data.get('member_count'),
                is_enabled=True,
                status=ChannelStatus.IDLE
            )
            self.repository.create_channel(new_channel)
            count += 1
        
        return count

    def get_registered_channels_with_stats(self, connection_id: int) -> List[dict]:
        channels = self.repository.get_channels_by_connection(connection_id)
        if not channels:
            return []

        channel_ids = [c.channel_id for c in channels]
        stats = self.repository.get_channel_stats(channel_ids, TABLE_NAME)

        response = []
        for c in channels:
            status_str = "ACTIVE" if c.is_enabled else "IDLE"
            count = stats.get(c.channel_id, 0)
            
            response.append({
                "id": c.id,
                "connection_id": c.connection_id,
                "channel_id": c.channel_id,
                "title": c.title,
                "username": c.username,
                "type": c.type,
                "member_count": c.member_count,
                "is_enabled": c.is_enabled,
                "status": status_str,
                "today_count": count
            })
        return response

    def toggle_channel(self, channel_id: int, is_enabled: bool) -> Optional[TelegramChannel]:
        channel = self.repository.get_channel_by_id(channel_id)
        if channel:
            channel.is_enabled = is_enabled
            return self.repository.update_channel(channel)
        return None

    def delete_channel(self, channel_id: int) -> bool:
        channel = self.repository.get_channel_by_id(channel_id)
        if channel:
            self.repository.delete_channel(channel)
            return True
        return False

    async def search_channels(self, connection_id: int, query: str, limit: int = 20) -> List[dict]:
        session_string, api_id, api_hash = self._get_credentials(connection_id)
        client = self._get_client(session_string, api_id, api_hash)
        
        results = []
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session expired")
            
            from telethon.tl.functions.contacts import SearchRequest
            
            try:
                search_res = await client(SearchRequest(q=query, limit=limit))
            except Exception as api_err:
                logger.error(f"Telethon Search API failed: {api_err}")
                return []
            
            if not search_res:
                return []

            chats = getattr(search_res, 'chats', [])
            
            for chat in chats:
                try:
                    c_type = "unknown"
                    if isinstance(chat, Channel):
                        c_type = "supergroup" if getattr(chat, 'megagroup', False) else "channel"
                    elif isinstance(chat, Chat):
                        c_type = "group"
                    else:
                        continue
                        
                    c_id = int(chat.id)

                    existing = self.repository.get_channel_by_telegram_id(connection_id, c_id)
                    status_str = "IDLE"
                    db_id = None
                    if existing:
                        status_str = "ALREADY_ADDED"
                        db_id = existing.id
                    
                    p_count = getattr(chat, 'participants_count', None)
                    if p_count is not None:
                        try:
                            p_count = int(p_count)
                        except:
                            p_count = None
                        
                    results.append({
                        "id": c_id,
                        "db_id": db_id,
                        "title": str(getattr(chat, 'title', 'Unknown') or 'Unknown'),
                        "username": getattr(chat, 'username', None),
                        "type": c_type,
                        "participants_count": p_count,
                        "status": status_str
                    })
                except Exception:
                    continue
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
        finally:
            await client.disconnect()
             
        return results

    # --- Connection Helpers (Refactored from telegram_connect.py) ---
    
    async def generate_connect_token(self, user_id: int) -> dict:
        """Generates token and returns {token, bot_username, deep_link}"""
        # We need TelegramBotService for token generation (it accesses redis/cache)
        # Assuming TelegramBotService is in app.providers.telegram_bot
        # But wait, TelegramBotService expects connection_manager? 
        # In telegram_connect.py it was initialized with None.
        
        bot_service = TelegramBotService(None)
        token = bot_service.generate_connect_token(user_id)
        bot_username = await bot_service.get_bot_username()
        
        if not bot_username:
             # Try to get from DB connection settings if available
             from app.providers.telegram_bot import get_bot_username_from_db
             bot_username = get_bot_username_from_db(self.db)

        if not bot_username:
            raise ValueError("Telegram Bot Connection not configured")

        return {
            "token": token,
            "bot_username": bot_username,
            "deep_link": f"https://t.me/{bot_username}?start={token}"
        }

    def disconnect_user(self, user: 'User'):
        user.telegram_chat_id = None
        self.db.commit()
