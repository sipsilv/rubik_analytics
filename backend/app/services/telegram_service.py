import logging
import json
import asyncio
from typing import List, Optional
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from app.models.connection import Connection, ConnectionType
from app.models.telegram_channel import TelegramChannel, ChannelStatus
from app.core.security import decrypt_data
from app.services.telegram_auth_service import TelegramAuthService

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, db: Session):
        self.db = db

    def _get_client(self, session_string: str, api_id: int, api_hash: str) -> TelegramClient:
        # Reuse the helper from Auth Service logic or creating new here
        # Using a fresh client instance for this short-lived operation
        from telethon.sessions import StringSession
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

    async def discover_channels(self, connection_id: int) -> List[dict]:
        """
        Connect to Telegram and fetch all available channels/supergroups.
        Returns a list of dicts with channel info.
        """
        connection = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not connection:
            raise ValueError("Connection not found")
        
        if connection.connection_type != ConnectionType.TELEGRAM_USER:
            raise ValueError("Discovery only supported for Telegram User connections")

        # Decrypt credentials
        try:
            creds_json = decrypt_data(connection.credentials)
            creds = json.loads(creds_json)
            session_string = creds.get("session_string")
            api_id = creds.get("api_id")
            api_hash = creds.get("api_hash")

            if not session_string or not api_id or not api_hash:
                raise ValueError("Incomplete credentials")
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for connection {connection_id}: {e}")
            raise ValueError("Invalid credentials")

        client = self._get_client(session_string, api_id, api_hash)
        
        discovered = []
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session expired or invalid")

            # Fetch dialogs
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                
                # Check if it's a channel or supergroup (megagroup)
                is_channel_or_group = isinstance(entity, (Channel, Chat))
                # For Channel type, check if it is a broadcast channel or megagroup
                if isinstance(entity, Channel):
                    # We want channels and supergroups
                    pass
                elif isinstance(entity, Chat):
                    # Legacy groups
                    pass
                else:
                    continue

                # Extract info
                # Note: telethon entity.id is usually positive, but for usage it might need adjustment if using as chat_id
                # Telethon handles the -100 prefix internally usually, but let's store the raw ID and handle logic later.
                # Actually, standard telegram IDs for channels are -100...
                # Telethon exposes .id as positive integer for Channel objects usually.
                # We will store what Telethon gives us.
                
                c_type = "unknown"
                if isinstance(entity, Channel):
                    c_type = "supergroup" if entity.megagroup else "channel"
                elif isinstance(entity, Chat):
                    c_type = "group"

                # Cast to int to ensure compatibility
                c_id = int(entity.id)

                # Check if already registered
                existing = self.db.query(TelegramChannel).filter(
                    TelegramChannel.connection_id == connection_id,
                    TelegramChannel.channel_id == c_id
                ).first()

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
        """
        Register a list of selected channels to the database.
        channels: list of dicts {id, title, username, type, member_count}
        """
        count = 0
        for ch_data in channels:
            # Check existence
            exists = self.db.query(TelegramChannel).filter(
                TelegramChannel.connection_id == connection_id,
                TelegramChannel.channel_id == ch_data['id']
            ).first()

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
            self.db.add(new_channel)
            count += 1
        
        self.db.commit()
        return count

    def get_registered_channels(self, connection_id: int) -> List[TelegramChannel]:
        return self.db.query(TelegramChannel).filter(
            TelegramChannel.connection_id == connection_id
        ).all()

    def toggle_channel(self, channel_id: int, is_enabled: bool) -> TelegramChannel:
        channel = self.db.query(TelegramChannel).filter(TelegramChannel.id == channel_id).first()
        if channel:
            channel.is_enabled = is_enabled
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def delete_channel(self, channel_id: int) -> bool:
        channel = self.db.query(TelegramChannel).filter(TelegramChannel.id == channel_id).first()
        if channel:
            self.db.delete(channel)
            self.db.commit()
            return True
        return False

    async def search_channels(self, connection_id: int, query: str, limit: int = 20) -> List[dict]:
        """
        Search for public channels and groups on Telegram globally.
        """

        
        connection = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not connection or connection.connection_type != ConnectionType.TELEGRAM_USER:
            raise ValueError("Invalid connection")
            
        # Decrypt credentials (duplicate logic, could be refactored)
        try:
            creds_json = decrypt_data(connection.credentials)
            creds = json.loads(creds_json)
            session_string = creds.get("session_string")
            api_id = creds.get("api_id")
            api_hash = creds.get("api_hash")
        except Exception:
             raise ValueError("Invalid credentials")
             
        client = self._get_client(session_string, api_id, api_hash)
        
        results = []

        try:
            await client.connect()
            if not await client.is_user_authorized():
                 raise ValueError("Session expired")
            
            # Perform global search
            from telethon.tl.functions.contacts import SearchRequest
            
            search_res = None
            try:
                # print(f"DEBUG: Performing search for '{query}'")
                search_res = await client(SearchRequest(q=query, limit=limit))
                # print(f"DEBUG: Search result type: {type(search_res)}")
            except Exception as api_err:
                logger.error(f"Telethon Search API failed: {api_err}")
                print(f"CRITICAL ERROR IN TELEGRAM SEARCH API: {api_err}")
                # Do not raise, return empty to prevent 500
                search_res = None
            
            if not search_res:
                return []

            # We are interested in channels and chats
            # Safely get chats, defaulting to empty list if not found
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
                        
                    # Cast to int to ensure compatibility
                    c_id = int(chat.id)

                    # Check existence
                    existing = self.db.query(TelegramChannel).filter(
                        TelegramChannel.connection_id == connection_id,
                        TelegramChannel.channel_id == c_id
                    ).first()
                    
                    status_str = "IDLE"
                    db_id = None
                    if existing:
                        status_str = "ALREADY_ADDED"
                        db_id = existing.id
                    
                    # Safe extraction of participants_count
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
                except Exception as inner_e:
                    logger.warning(f"Skipping malformed chat object in search: {inner_e}")
                    continue
                
            return results
        except Exception as e:
             # Log the full traceback for server debugging
             import traceback
             logger.error(f"Search failed: {e}\n{traceback.format_exc()}")
             
             # Print to console for immediate visibility in dev
             print(f"SEARCH ENDPOINT ERROR: {e}")
             
             # Return empty list instead of crashing with 500
             # This allows the UI to show "No results" or handle it gracefully
             return []
        finally:
             await client.disconnect()
             
        return results
