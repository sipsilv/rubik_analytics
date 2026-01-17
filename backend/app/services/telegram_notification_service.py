
import logging
from app.providers.telegram_bot import TelegramBotService
from app.core.database import get_connection_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

class TelegramNotificationService:
    """
    Service for sending notifications via Telegram.
    Uses the underlying TelegramBotService for actual delivery.
    Fails silently (logs only) to avoid blocking business logic.
    """
    def __init__(self):
        # Initialize the underlying bot service
        # We don't strictly need the connection manager for sending messages if the bot service 
        # fetches credentials directly from DB as seen in its code.
        # However, we pass it to respect the constructor signature.
        manager = get_connection_manager(settings.DATA_DIR)
        self.bot_service = TelegramBotService(manager)

    def generate_otp(self, mobile: str) -> str:
        """
        Generate OTP and store it in the bot service's memory store.
        """
        return self.bot_service.generate_otp(mobile)

    def verify_otp(self, mobile: str, otp: str) -> bool:
        """
        Verify OTP using the bot service's memory store.
        """
        return self.bot_service.verify_otp(mobile, otp)

    async def send_otp_notification(self, user, otp: str) -> bool:
        """
        Send OTP to a user via Telegram.
        
        Args:
            user: User model instance
            otp: The OTP code string
            
        Returns:
            bool: True if sent successfully (or accepted for delivery), False otherwise.
        """
        if not user.telegram_chat_id:
            logger.debug(f"Skipping Telegram OTP for {user.username}: No Chat ID linked.")
            return False
            
        message = f"🔐 <b>Login OTP</b>\n\nYour code is: <code>{otp}</code>\nValid for 5 minutes."
        
        try:
            # We assume user.telegram_chat_id works.
            # The bot_service.send_message handles fetching the token internally.
            success = await self.bot_service.send_message(user.telegram_chat_id, message)
            if success:
                logger.info(f"OTP sent to Telegram user {user.username}")
            else:
                logger.warning(f"Telegram API returned failure for OTP to {user.username}")
            return success
        except Exception as e:
            logger.error(f"Failed to send Telegram OTP to {user.username}: {e}")
            return False

    async def send_info_notification(self, user, message: str) -> bool:
        """
        Send an informational notification to a user via Telegram.
        
        Args:
            user: User model instance
            message: The message text (HTML supported)
            
        Returns:
            bool: True if sent, False otherwise.
        """
        if not user.telegram_chat_id:
            return False
            
        try:
            success = await self.bot_service.send_message(user.telegram_chat_id, message)
            return success
        except Exception as e:
            logger.error(f"Failed to send Telegram notification to {user.username}: {e}")
            return False
