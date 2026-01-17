import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
import logging

logger = logging.getLogger(__name__)

class TelegramAuthService:
    def _get_client(self, api_id: int, api_hash: str, session_string: str = None) -> TelegramClient:
        """Helper to create client with consistent settings"""
        session = StringSession(session_string) if session_string else StringSession()
        return TelegramClient(
            session, 
            api_id, 
            api_hash,
            system_version="4.16.30-vxCustom",
            device_model="OpenAnalytics",
            app_version="1.0.0",
            connection_retries=2, # Fail faster so we can report error
            retry_delay=1
        )

    async def request_otp(self, api_id: int, api_hash: str, phone: str) -> tuple[str, str]:
        """
        Request OTP for a phone number.
        Returns the (phone_code_hash, session_string) needed for verification.
        """
        client = self._get_client(api_id, api_hash)
        
        try:
            await client.connect()
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise Exception(f"Connection to Telegram servers failed: {e}. Please check your internet connection or try again.")
        
        try:
            if not await client.is_user_authorized():
                # Send code
                logger.info(f"Sending OTP to {phone}")
                sent_code = await client.send_code_request(phone)
                # Return hash AND the current session string (to persist session ID)
                return sent_code.phone_code_hash, client.session.save()
            else:
                # Already authorized? Should not happen with empty session, but technically possible if session reused
                raise Exception("Client unexpectedly authorized")
        except Exception as e:
            logger.error(f"Error requesting OTP: {e}")
            raise e
        finally:
            await client.disconnect()

    async def verify_otp(self, api_id: int, api_hash: str, phone: str, code: str, phone_code_hash: str, session_string: str, password: str = None) -> str:
        """
        Verify the OTP and return the authorized session string.
        """
        client = self._get_client(api_id, api_hash, session_string)
        
        try:
            await client.connect()
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise Exception(f"Connection to Telegram servers failed: {e}. Please check your internet connection or try again.")
        
        try:
            # We must call sign_in
            try:
                user = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    raise Exception("Two-step verification enabled. Password required.")
                user = await client.sign_in(password=password)
            
            # If successful, get session string
            session_string = client.session.save()
            return session_string
            
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
            raise Exception(f"Invalid or expired OTP: {e}")
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            raise e
        finally:
            await client.disconnect()
