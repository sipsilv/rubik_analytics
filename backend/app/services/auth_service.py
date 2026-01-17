from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from datetime import datetime
from typing import Optional

from app.models.user import User
from app.api.v1.auth import LoginRequest, ForgotPasswordResponse, ResetPasswordResponse, TokenResponse 
from app.core.auth.security import verify_password, create_access_token, get_password_hash
from app.providers.telegram_bot import TelegramBotService
from app.services.telegram_notification_service import TelegramNotificationService
from app.core.database import get_connection_manager
from app.core.config import settings
from app.repositories.user_repository import UserRepository

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository()

    async def login(self, login_data: LoginRequest) -> TokenResponse:
        # Identifier is now guaranteed to be set
        identifier = login_data.identifier.strip()
        if not identifier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Identifier is required"
            )
        
        user = None
        
        # Try User ID first (if identifier is numeric)
        if identifier.isdigit():
            user = self.user_repo.get_by_id(self.db, int(identifier))
            if user:
                print(f"[AUTH] User found by ID: {identifier}")
        
        # Try Email
        if not user:
            user = self.user_repo.get_by_email(self.db, identifier) # Repo is case sensitive usually, but original code used lower()
            if not user:
                # Manual case insensitive check if repo strictly strict
                # Reuse repo logic or do manual query here if repo doesn't support case insensitive
                # For now, let's assume we can do a query here or improve repo. 
                # Let's do raw query here to match original logic perfectly for now to avoid breaking changes
                user = self.db.query(User).filter(
                    User.email.isnot(None),
                    func.lower(User.email) == identifier.lower()
                ).first()
            if user:
                print(f"[AUTH] User found by email: {identifier}")
        
        # Try Mobile
        if not user:
             user = self.user_repo.get_by_mobile(self.db, identifier)
             if user:
                print(f"[AUTH] User found by mobile: {identifier}")
        
        # Try Username
        if not user:
            user = self.user_repo.get_by_username(self.db, identifier)
            if not user:
                user = self.db.query(User).filter(func.lower(User.username) == identifier.lower()).first()
            if user:
                print(f"[AUTH] User found by username: {identifier}")
        
        if not user:
            print(f"[AUTH] Login failed - User not found for identifier: '{identifier}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect identifier or password"
            )
        
        if not user.hashed_password:
            print(f"[AUTH] Login failed for username: {user.username} - No password hash found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account configuration error. Please contact administrator."
            )
        
        if not verify_password(login_data.password, user.hashed_password):
            print(f"[AUTH] Login failed for identifier: {identifier} (user: {user.username}) - Invalid password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect identifier or password"
            )
        
        # -------------------------------------------------------------
        # TELEGRAM OTP CHECK (Before any role bypass)
        # -------------------------------------------------------------
        # Only enforce if user has linked Telegram AND has enabled 2FA
        print(f"[AUTH DEBUG] Login - User: {user.username}, ChatID: {user.telegram_chat_id}, 2FA Enabled: {user.two_factor_enabled}")
        if user.telegram_chat_id and user.two_factor_enabled:
            manager = get_connection_manager(settings.DATA_DIR)
            bot_service = TelegramBotService(manager)
            
            if not login_data.otp:
                # Generate and send OTP
                code = bot_service.generate_otp(user.mobile)
                message = (
                    f"🔐 <b>Login Verification Required</b>\n\n"
                    f"Hello <b>{user.username}</b>,\n\n"
                    f"Your login OTP is: <code>{code}</code>\n\n"
                    f"⏰ Valid for <b>5 minutes</b>\n"
                    f"⚠️ If this wasn't you, secure your account immediately.\n\n"
                    f"— Open Analytics Security Team"
                )
                try:
                    sent = await bot_service.send_message(user.telegram_chat_id, message)
                except Exception as e:
                    print(f"[AUTH] Error sending OTP: {e}")
                    sent = False
                
                if sent:
                    print(f"[AUTH] OTP sent to Telegram user {user.username} (Chat ID: {user.telegram_chat_id})")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="OTP code sent to Telegram. Please enterthe code."
                    )
                else:
                    # Fallback if bot fails
                    print(f"[AUTH] Failed to send OTP to Telegram user {user.username}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to send security OTP. Please contact admin."
                    )
            else:
                # Verify OTP
                if not bot_service.verify_otp(user.mobile, login_data.otp):
                     print(f"[AUTH] Invalid OTP for user {user.username}")
                     raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired OTP code"
                    )
                print(f"[AUTH] OTP verified for user {user.username}")

        # CRITICAL: Check for Super User FIRST - bypass ALL status checks
        user_role_lower = user.role.lower() if user.role else ""
        is_super_admin = user_role_lower == "super_admin"
        
        print(f"[AUTH] Login attempt - User: {user.username}, Role: '{user.role}' (normalized: '{user_role_lower}'), Is Active: {user.is_active}, Is Super Admin: {is_super_admin}")
        
        if is_super_admin:
            print(f"[AUTH] [SUPER_USER] ===== SUPER USER DETECTED =====")
            
            # Force activate and normalize role (safety mechanism)
            needs_update = False
            if not user.is_active:
                user.is_active = True
                needs_update = True
            
            if user.role.lower() != "super_admin":
                user.role = "super_admin"
                needs_update = True
            
            if needs_update:
                self.db.commit()
            
            # Update last seen and last active
            user.last_seen = datetime.utcnow()
            user.last_active_at = datetime.utcnow()
            
            # Set dark theme as default if theme_preference is not set
            if not user.theme_preference:
                user.theme_preference = "dark"
            
            self.db.commit()
            
            print(f"[AUTH] [SUPER_USER] ===== LOGIN SUCCESSFUL - TOKEN GENERATED =====")
            
            # Generate token and return IMMEDIATELY
            return self._create_token_response(user)
        
        # For non-Super Users ONLY: Check is_active status and account_status
        if not user.is_active:
            print(f"[AUTH] [BLOCKED] Login blocked for {user.username} - Account is inactive")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        if user.account_status:
            account_status_upper = user.account_status.upper().strip()
            if account_status_upper and account_status_upper != "ACTIVE":
                print(f"[AUTH] [BLOCKED] Login blocked for {user.username} - Account status is {user.account_status}")
                # Sync is_active with account_status for consistency
                user.is_active = False
                self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User account is {user.account_status.lower()}"
                )
        
        # Update last seen and last active
        user.last_seen = datetime.utcnow()
        user.last_active_at = datetime.utcnow()
        if not user.theme_preference:
            user.theme_preference = "dark"
        
        self.db.commit()
        
        return self._create_token_response(user)

    def _create_token_response(self, user: User) -> TokenResponse:
        access_token = create_access_token(data={"sub": user.username})
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "mobile": user.mobile,
                "role": user.role,
                "is_active": user.is_active,
                "theme_preference": user.theme_preference or "dark",
            }
        )

    def logout(self, user: User):
        user.last_seen = datetime.utcnow()
        self.db.commit()

    async def forgot_password(self, request: ForgotPasswordRequest) -> ForgotPasswordResponse:
        # Try to find user by email first (backward compatibility)
        user = self.user_repo.get_by_email(self.db, request.email)
        
        # If not found by email, try as mobile number
        if not user:
             user = self.user_repo.get_by_mobile(self.db, request.email)
        
        # If still not found and it's numeric, try as user ID
        if not user and request.email.isdigit():
             user = self.user_repo.get_by_id(self.db, int(request.email))
        
        if not user:
            # Don't reveal if user exists
            return ForgotPasswordResponse(message="If your account exists, a password reset code has been sent.")
        
        # Telegram OTP Flow
        if user.telegram_chat_id:
            notification_service = TelegramNotificationService()
            otp = notification_service.generate_otp(user.mobile)
            
            message = (
                f"🔐 <b>Password Reset Request</b>\n\n"
                f"Hello <b>{user.username}</b>,\n\n"
                f"Your password reset OTP is: <code>{otp}</code>\n\n"
                f"⏰ This code is valid for <b>5 minutes</b>.\n"
                f"⚠️ If you didn't request this, please ignore this message.\n\n"
                f"— Open Analytics Security Team"
            )
            
            await notification_service.bot_service.send_message(user.telegram_chat_id, message)
            
            return ForgotPasswordResponse(message="A password reset code has been sent to your Telegram account.")
        
        return ForgotPasswordResponse(message="If your account exists, a password reset code has been sent.")

    async def reset_password(self, request: ResetPasswordRequest) -> ResetPasswordResponse:
        # Find user by identifier
        user = self.user_repo.get_by_email(self.db, request.identifier)
        
        if not user:
             user = self.user_repo.get_by_mobile(self.db, request.identifier)
        
        if not user and request.identifier.isdigit():
             user = self.user_repo.get_by_id(self.db, int(request.identifier))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Verify OTP
        notification_service = TelegramNotificationService()
        if not notification_service.verify_otp(user.mobile, request.otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
        
        # Update password
        user.hashed_password = get_password_hash(request.new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Send confirmation to Telegram
        if user.telegram_chat_id:
            try:
                now = datetime.now().strftime("%d-%b-%Y %I:%M %p")
                message = (
                    f"✅ <b>Password Reset Successful</b>\n\n"
                    f"Hello <b>{user.username}</b>,\n\n"
                    f"Your password has been successfully reset.\n\n"
                    f"🕐 Time: <code>{now}</code>\n\n"
                    f"⚠️ If you didn't make this change, contact support immediately.\n\n"
                    f"— Open Analytics Security Team"
                )
                await notification_service.bot_service.send_message(user.telegram_chat_id, message)
            except Exception as e:
                print(f"Failed to send password reset confirmation: {e}")
        
        return ResetPasswordResponse(message="Password reset successfully")

    def refresh_token(self, user: User) -> TokenResponse:
        return self._create_token_response(user)
