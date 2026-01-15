import logging
import asyncio
import re
import os
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from .db import insert_message

logger = logging.getLogger("telegram_listener.core")

# URL Regex for fallback extraction
URL_REGEX = r'(https?://\S+)'

class TelegramListener:
    def __init__(self, config):
        self.api_id = config['api_id']
        self.api_hash = config['api_hash']
        self.session_string = config['session_string']
        self.channels = config['channels'] # List of int IDs
        self.client = None

    async def start(self):
        """Starts the Telethon client and event loop."""
        logger.info("Initializing Telegram Client...")
        
        self.client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash,
            # Connection settings for stability
            connection_retries=None, # Infinite retries
            retry_delay=5
        )

        await self.client.start()
        
        if not await self.client.is_user_authorized():
            logger.error("Session is invalid or expired.")
            raise Exception("Telegram Session Invalid")
        
        logger.info(f"Connected as: { (await self.client.get_me()).username }")
        logger.info(f"Listening to {len(self.channels)} channels...")

        # Register Event Handler
        # We listen to incoming messages from the specific channels
        # channels list can be empty if we just want to listen to everything, but requirements said "Subscribe only to ENABLED channels"
        # optimizing: pass chats to events.NewMessage
        @self.client.on(events.NewMessage())
        async def handler(event):
            try:
                chat = await event.get_chat()
                chat_id = chat.id
                
                # Debug logging
                # logger.info(f"Incoming msg from {chat_id} ({getattr(chat, 'title', 'NoTitle')})")
                
                # Manual filtering to debug ID mismatch
                # We check raw ID, or with -100 prefix
                # self.channels contains int IDs (e.g. 12345 or 10012345)
                
                # Telethon chat.id for channels is usually positive unique ID.
                # Sometimes we need to check if it matches our list.
                # Let's try flexible matching
                
                # Standardize comparison
                # Robust Channel ID matching
                # Create a set of stringified normalized IDs for comparison
                valid_ids = set()
                for c in self.channels:
                    c_str = str(c)
                    valid_ids.add(c_str)
                    valid_ids.add(c_str.replace("-100", ""))
                    if not c_str.startswith("-100"):
                         valid_ids.add(f"-100{c_str}")

                current_id_str = str(chat_id)
                
                if current_id_str in valid_ids or current_id_str.replace("-100", "") in valid_ids:
                    await self._process_message(event)
                else:
                    logger.warning(f"Ignored msg from {chat_id} ({getattr(chat, 'title', 'NoTitle')}) - Not in enabled list.")
                    pass
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        # Start the client but DONT block
        # run_until_disconnected() blocks the event loop if awaited here.
        # Since we are running in an asyncio loop in WorkerManager, we just need to be connected.
        # The client will keep running receiving events in the background.
        logger.info("[Listener] Client started and listening (non-blocking).")
        # await self.client.run_until_disconnected() <--- REMOVED BLOCKING CALL

    async def _process_message(self, event):
        """Extracts raw data and saves to DB."""
        msg = event.message
        chat = await event.get_chat()
        
        # Determine Source Handle (username or title)
        source_handle = getattr(chat, 'username', None) or getattr(chat, 'title', 'Unknown')
        
        # Determine Media Type
        media_type = "none"
        has_media = False
        file_id = None
        file_name = None
        
        if msg.photo:
            media_type = "image"
            has_media = True
            # file_id in Telethon is complex, we might store the access_hash or just "present"
            # Requirement: "file_id (if media exists)"
            # Telethon doesn't expose a simple "file_id" like Bot API. 
            # We'll store the media ID if possible, or leave blank if not easily available string.
            # Using msg.id represents the message, but media has its own ID.
            file_id = str(msg.photo.id)
            
        elif msg.video:
            media_type = "video"
            has_media = True
            file_id = str(msg.video.id)
            # Try to get filename
            for checkout in msg.video.attributes:
                if hasattr(checkout, 'file_name'):
                    file_name = checkout.file_name
                    
        elif msg.document:
             # Could be other file types, treat as 'file' or 'media'
             media_type = "document"
             has_media = True
             file_id = str(msg.document.id)
             for checkout in msg.document.attributes:
                if hasattr(checkout, 'file_name'):
                    file_name = checkout.file_name

        if msg.entities:
            for entity in msg.entities:
                pass
                
        # Simple extraction combined from text and caption
        full_text = (msg.message or "") + " " + (msg.text or "")
        
        extracted_urls = re.findall(URL_REGEX, full_text)
        urls_str = ",".join(list(set(extracted_urls))) if extracted_urls else None

        # Download Media if present (Async)
        file_path = None
        if has_media:
            try:
                # Setup Media Dir
                BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
                MEDIA_DIR = os.path.join(BASE_DIR, "data", "News", "media_cache")
                if not os.path.exists(MEDIA_DIR):
                    os.makedirs(MEDIA_DIR, exist_ok=True)

                fname = f"{chat.id}_{msg.id}"
                path = os.path.join(MEDIA_DIR, fname)
                
                saved_path = await msg.download_media(file=path)
                if saved_path:
                     file_path = saved_path
            except Exception as e:
                logger.error(f"Media download failed for msg {msg.id}: {e}")

        # Prepare Data Dict
        data = {
            "telegram_chat_id": str(chat.id),
            "telegram_msg_id": str(msg.id),
            "source_handle": source_handle,
            "message_text": msg.message, # Raw text
            "caption_text": msg.message if has_media else None, # In Telegram, text is caption for media
            "media_type": media_type,
            "has_media": has_media,
            "file_id": file_id,
            "file_name": file_name,
            "file_path": file_path,
            "urls": urls_str,
            "received_at": datetime.now(timezone.utc)
        }
        
        # Insert
        try:
            await asyncio.to_thread(insert_message, data)
            logger.info(f"Captured msg {msg.id} from {source_handle} (Media: {bool(file_path)})")
        except Exception as e:
            logger.error(f"DB Insert Failed: {e}")

