from typing import Optional
import json
import logging
import aiohttp
import asyncio
import secrets
import time

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.models.connection import Connection, ConnectionType
from app.core.security import decrypt_data
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# In-memory OTP store (safe single-instance use)
otp_store: dict[str, dict] = {}

class TelegramBotService:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    # ---------- OTP & CONNECT TOKENS ----------
    # In-memory store for OTPs: {mobile: {code: "123456", expires_at: 1234567890}}
    # In-memory store for Connect Tokens: {token: {user_id: 123, expires_at: 1234567890}}
    CONNECT_TOKEN_STORE: dict[str, dict] = {}

    def generate_otp(self, mobile: str) -> str:
        code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        otp_store[mobile] = {
            "code": code,
            "expires_at": time.time() + 300
        }
        return code

    def generate_connect_token(self, user_id: int) -> str:
        """Generate a secure, short-lived token for deep linking"""
        token = secrets.token_urlsafe(32)
        TelegramBotService.CONNECT_TOKEN_STORE[token] = {
            "user_id": user_id,
            "expires_at": time.time() + 300  # 5 minutes validity
        }
        return token

    def verify_otp(self, mobile: str, code: str) -> bool:
        data = otp_store.get(mobile)
        if not data:
            return False

        if time.time() > data["expires_at"]:
            otp_store.pop(mobile, None)
            return False

        if data["code"] == code:
            otp_store.pop(mobile, None)
            return True

        return False

    def verify_connect_token(self, token: str) -> Optional[int]:
        """Verify connect token and return user_id if valid"""
        data = TelegramBotService.CONNECT_TOKEN_STORE.get(token)
        if not data:
            return None
        
        if time.time() > data["expires_at"]:
            TelegramBotService.CONNECT_TOKEN_STORE.pop(token, None)
            return None
            
        # Single-use token (invalidate immediately after use)
        TelegramBotService.CONNECT_TOKEN_STORE.pop(token, None)
        return data["user_id"]

    def verify_otp(self, mobile: str, code: str) -> bool:
        data = otp_store.get(mobile)
        if not data:
            return False

        if time.time() > data["expires_at"]:
            otp_store.pop(mobile, None)
            return False

        if data["code"] == code:
            otp_store.pop(mobile, None)
            return True

        return False

    # ---------- BOT TOKEN ----------
    def _get_bot_token_sync(self) -> Optional[str]:
        db = SessionLocal()
        try:
            conn = (
                db.query(Connection)
                .filter(
                    Connection.connection_type == ConnectionType.TELEGRAM_BOT,
                    Connection.is_enabled == True
                )
                .first()
            )

            if not conn or not conn.credentials:
                return None

            decrypted = decrypt_data(conn.credentials)

            if decrypted.strip().startswith("{"):
                return json.loads(decrypted).get("bot_token")

            return decrypted.strip()

        except Exception as e:
            logger.exception(f"Bot token fetch failed: {e}")
            return None
        finally:
            db.close()

    async def _get_bot_token(self) -> Optional[str]:
        """Async wrapper for getting bot token"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_bot_token_sync)

    async def get_bot_username(self) -> Optional[str]:
        """Fetch bot username from Telegram API"""
        try:
            token = await self._get_bot_token()
            if not token:
                return None
            
            url = f"https://api.telegram.org/bot{token}/getMe"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            return data["result"]["username"]
            return None
        except Exception as e:
            logger.error(f"Error fetching bot username: {e}")
            return None

    # ---------- TELEGRAM SEND ----------
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML", reply_markup: dict = None) -> bool:
        try:
            token = await self._get_bot_token()
            if not token:
                logger.error("Error sending Telegram message: Bot token is missing or invalid")
                return False

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id, 
                "text": text,
                "parse_mode": parse_mode
            }
            
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        response_text = await resp.text()
                        logger.error(f"Failed to send Telegram message: {resp.status} - {response_text}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}", exc_info=True)
            return False


    # ---------- WEBHOOK ----------
    async def process_webhook_update(self, update: dict, db: Session):
        message = update.get("message")
        if not message:
            return

        chat_id = str(message["chat"]["id"])
        text = (message.get("text") or "").strip()
        contact = message.get("contact")
        
        # Check if sender is an admin (not handling /start commands)
        is_admin_sender = False
        sender_admin = None
        if not text.startswith("/start"):
            sender_admin = db.query(User).filter(
                User.telegram_chat_id == chat_id,
                User.role.in_(['admin', 'super_admin']),
                User.is_active == True
            ).first()
            is_admin_sender = sender_admin is not None

        # 1. Handle Shared Contact
        if contact:
            phone_number = contact.get("phone_number")
            if phone_number:
                # Normalize phone number (remove +)
                normalized_mobile = phone_number.replace("+", "")
                await self._link_user(chat_id, normalized_mobile, db)
            return

        # 2. Handle Text Commands (/start)
        if text.startswith("/start"):
            parts = text.split()
            if len(parts) == 2:
                payload = parts[1]
                
                # A. Attempt to link via Secure Token
                user_id = self.verify_connect_token(payload)
                if user_id:
                    await self._link_user_by_id(chat_id, user_id, db)
                    return

                # B. Check if payload looks like a mobile number (Legacy / Manual)
                is_mobile = payload.replace("+", "").isdigit() and len(payload) >= 10
                
                if is_mobile:
                    await self._link_user(chat_id, payload, db)
                else:
                    await self.send_message(
                        chat_id,
                        "❌ Invalid or expired connection link.\nPlease generate a new link from User Settings."
                    )
            else:
                # Welcome message with Share Contact button
                reply_markup = {
                    "keyboard": [
                        [{
                            "text": "📱 Share Contact to Connect",
                            "request_contact": True
                        }]
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True
                }
                
                await self.send_message(
                    chat_id,
                    "Welcome to Open Analytics! 👋\n\nTo connect your account:\n\n1. Use the **'Connect Telegram'** button in User Settings (Recommended).\n2. OR type: `/start <your_mobile_number>`\n(Example: `/start 9876543210`)",
                    reply_markup=reply_markup
                )
        elif is_admin_sender:
            # 3. Handle Admin Messages - Parse for user targeting
            # Format: @user_id message OR just message (broadcast to last active user)
            await self._handle_admin_message(chat_id, text, sender_admin, db)
        else:
            # 4. Store non-command messages from regular users
            await self._store_user_message(chat_id, text, db)
    # ---------- USER LINK (BY ID - NEW SECURE FLOW) ----------
    async def _link_user_by_id(self, chat_id: str, user_id: int, db: Session):
        """Link user by ID - Runs DB operations in thread pool"""
        try:
            loop = asyncio.get_event_loop()
            
            def link_logic():
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return None, None, "❌ User not found."

                # Check if already linked
                if user.telegram_chat_id == chat_id:
                     return None, None, "✅ Telegram is already connected to this account."

                # Unlink from any other user that might have this chat_id (unlikely but safe)
                # db.query(User).filter(User.telegram_chat_id == chat_id).update({"telegram_chat_id": None})
                
                user.telegram_chat_id = chat_id
                db.commit()
                return user.username, user.mobile, None

            username, mobile, error_msg = await loop.run_in_executor(None, link_logic)
            
            if error_msg:
                await self.send_message(chat_id, error_msg)
            elif username:
                await self.send_message(
                    chat_id,
                    f"✅ Telegram connected successfully for user: {username}\n📞 Mobile: {mobile}"
                )
        except Exception as e:
            logger.error(f"Error linking user by ID: {e}")
            await self.send_message(chat_id, "❌ Error linking account.")

    # ---------- USER LINK ----------
    async def _link_user(self, chat_id: str, mobile: str, db: Session):
        """Link user - Runs DB operations in thread pool to prevent blocking"""
        try:
            loop = asyncio.get_event_loop()
            
            def link_logic():
                # Synchronous DB operations
                user = db.execute(
                    select(User).where(User.mobile == mobile)
                ).scalar_one_or_none()

                if not user:
                    return None, None, "❌ Mobile number not found."

                # Check if already linked
                if user.telegram_chat_id == chat_id:
                    return None, None, "✅ Telegram is already connected to this mobile number."

                user.telegram_chat_id = chat_id
                db.commit()
                return user.username, user.mobile, None

            # Run DB logic in thread
            username, mobile, error_msg = await loop.run_in_executor(None, link_logic)
            
            if error_msg:
                await self.send_message(chat_id, error_msg)
            elif username:
                await self.send_message(
                    chat_id,
                    f"✅ Telegram linked successfully for user: {username}\n📞 Mobile: {mobile}"
                )
        except Exception as e:
            logger.error(f"Error linking user: {e}")
            await self.send_message(chat_id, "❌ Error processing request.")

    # ---------- HANDLE ADMIN MESSAGE ----------
    async def _handle_admin_message(self, admin_chat_id: str, message_text: str, admin: User, db: Session):
        """Handle messages from admin - route to specific user or show help"""
        try:
            from app.models.telegram_message import TelegramMessage
            
            # Parse message for user targeting
            # Format: @user_123 Your message here
            # OR: user_123 Your message here
            target_user_id = None
            actual_message = message_text
            
            # Check if message starts with @user_id or user_id
            parts = message_text.split(maxsplit=1)
            if len(parts) >= 1:
                first_part = parts[0].lstrip('@')
                # Check if it's a valid user_id format
                if first_part.startswith('user_') or first_part.isdigit():
                    target_user_id = first_part
                    actual_message = parts[1] if len(parts) > 1 else ""
            
            if not target_user_id or not actual_message.strip():
                # Send help message
                help_text = (
                    "📋 <b>Admin Message Format</b>\n\n"
                    "To send a message to a user, use:\n"
                    "<code>@user_123 Your message here</code>\n\n"
                    "Or:\n"
                    "<code>user_123 Your message here</code>\n\n"
                    "The user ID is shown in the notification you receive."
                )
                await self.send_message(admin_chat_id, help_text)
                return
            
            loop = asyncio.get_event_loop()
            
            def send_logic():
                # Find target user by user_id
                target_user = db.query(User).filter(User.user_id == target_user_id).first()
                if not target_user:
                    return None, "User not found"
                
                if not target_user.telegram_chat_id:
                    return None, "User has not connected Telegram"
                
                # Store message in database
                msg = TelegramMessage(
                    user_id=target_user.id,
                    chat_id=target_user.telegram_chat_id,
                    message_text=actual_message,
                    from_user=False,
                    admin_username=admin.username,
                    is_read=True
                )
                db.add(msg)
                db.commit()
                
                return target_user, None
            
            target_user, error = await loop.run_in_executor(None, send_logic)
            
            if error:
                await self.send_message(admin_chat_id, f"❌ {error}")
                return
            
            if target_user:
                # Send message to user
                formatted_message = (
                    f"📩 <b>Message from Admin ({admin.username})</b>\n\n"
                    f"{actual_message}\n\n"
                    f"— Open Analytics Support"
                )
                
                success = await self.send_message(target_user.telegram_chat_id, formatted_message)
                
                if success:
                    # Confirm to admin
                    await self.send_message(
                        admin_chat_id,
                        f"✅ Message sent to {target_user.username} ({target_user.user_id})"
                    )
                else:
                    await self.send_message(
                        admin_chat_id,
                        f"❌ Failed to send message to {target_user.username}"
                    )
                    
        except Exception as e:
            logger.error(f"Error handling admin message: {e}")
            await self.send_message(admin_chat_id, "❌ Error processing message.")

    # ---------- STORE USER MESSAGE ----------
    async def _store_user_message(self, chat_id: str, message_text: str, db: Session):
        """Store a message from user in database and notify admins"""
        try:
            from app.models.telegram_message import TelegramMessage
            
            loop = asyncio.get_event_loop()
            
            def store_logic():
                # Find user by chat_id
                user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
                if not user:
                    return None, []
                
                # Create message record
                msg = TelegramMessage(
                    user_id=user.id,
                    chat_id=chat_id,
                    message_text=message_text,
                    from_user=True,
                    is_read=False
                )
                db.add(msg)
                db.commit()
                
                # Get all admins with connected Telegram
                admins = db.query(User).filter(
                    User.role.in_(['admin', 'super_admin']),
                    User.telegram_chat_id.isnot(None),
                    User.is_active == True
                ).all()
                
                admin_chat_ids = [admin.telegram_chat_id for admin in admins]
                
                return user, admin_chat_ids
            
            # Store message and get admin list
            user, admin_chat_ids = await loop.run_in_executor(None, store_logic)
            
            if user and admin_chat_ids:
                # Notify all connected admins
                notification_message = (
                    f"📨 <b>New Message from User</b>\n\n"
                    f"<b>From:</b> {user.username} ({user.mobile})\n"
                    f"<b>User ID:</b> {user.user_id}\n\n"
                    f"<b>Message:</b>\n{message_text}\n\n"
                    f"💬 Reply via Admin Panel"
                )
                
                # Send to all admins
                for admin_chat_id in admin_chat_ids:
                    try:
                        await self.send_message(admin_chat_id, notification_message)
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_chat_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error storing user message: {e}")


    # ---------- POLLING (GET UPDATES) ----------
    last_update_id = 0

    async def get_updates(self) -> list[dict]:
        """Fetch new updates from Telegram (Polling)"""
        token = await self._get_bot_token()
        if not token:
            return []

        # Use class variable to track offset
        offset = TelegramBotService.last_update_id + 1 if TelegramBotService.last_update_id else 0
        
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        payload = {
            "offset": offset,
            "timeout": 30,  # Long polling timeout
            "allowed_updates": ["message"]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=40) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram getUpdates failed: {resp.status}")
                        return []
                    
                    data = await resp.json()
                    if not data.get("ok"):
                        return []
                    
                    updates = data.get("result", [])
                    if updates:
                        # Update offset to the highest update_id found
                        max_id = max(u["update_id"] for u in updates)
                        TelegramBotService.last_update_id = max(TelegramBotService.last_update_id, max_id)
                        
                    return updates
        except Exception as e:
            logger.error(f"Polling error: {e}")
            return []
