import asyncio
import os
import json
import duckdb
from telethon import TelegramClient, events
from PIL import Image
import pytesseract

from app.core.database.connection_manager import ConnectionManager

DATA_DIR = "data"
NEWS_DB_PATH = os.path.join(DATA_DIR, "news", "telegram_news.duckdb")
MEDIA_DIR = os.path.join(DATA_DIR, "analytics", "media", "telegram")

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(NEWS_DB_PATH), exist_ok=True)

class TelegramIngestor:
    def __init__(self):
        self.manager = ConnectionManager(DATA_DIR)
        self.conn = self._load_conn()
        self.client = None

    def _load_conn(self):
        self.manager.load_connections()
        for c in self.manager.connections.values():
            if c.get("connection_type") == "TELEGRAM_USER":
                creds = json.loads(c["credentials"])
                return creds
        raise RuntimeError("TELEGRAM_USER connection missing")

    def _db(self):
        return duckdb.connect(NEWS_DB_PATH)

    async def start(self):
        self.client = TelegramClient(
            self.conn["session_file_path"],
            self.conn["api_id"],
            self.conn["api_hash"]
        )
        await self.client.start()

        @self.client.on(events.NewMessage)
        async def handler(event):
            await self.process(event)

        await self.client.run_until_disconnected()

    async def process(self, event):
        msg = event.message
        text = msg.text
        image_path = None

        if msg.photo:
            image_path = await msg.download_media(MEDIA_DIR)
            if not text:
                text = pytesseract.image_to_string(Image.open(image_path)).strip()

        if text:
            self.save(msg.chat.username or "unknown", text, image_path, msg.id, msg.date)

    def save(self, channel, text, image, msg_id, dt):
        db = self._db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_news (
                message_id BIGINT PRIMARY KEY,
                channel_name TEXT,
                headline_text TEXT,
                image_path TEXT,
                posted_at TIMESTAMP
            )
        """)
        try:
            db.execute(
                "INSERT INTO telegram_news VALUES (?, ?, ?, ?, ?)",
                (msg_id, channel, text, image, dt)
            )
        except:
            pass
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(TelegramIngestor().start())
