from sqlalchemy.orm import Session
from fastapi import HTTPException, status, BackgroundTasks
from datetime import datetime
from typing import Optional, List

from app.models.user import User
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest
from app.schemas.user import UserUpdate, PasswordChange
from app.schemas.admin import FeatureRequestCreate

from app.repositories.user_repository import UserRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.feature_request_repository import FeatureRequestRepository

from app.services.telegram_notification_service import TelegramNotificationService
from app.providers.telegram_bot import TelegramBotService
from app.core.auth.security import verify_password, get_password_hash
from app.core.database import get_connection_manager, get_db_router
from app.core.config import settings

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository()
        self.feedback_repo = FeedbackRepository()
        self.feature_request_repo = FeatureRequestRepository()
        self.telegram_service = TelegramNotificationService()

    def update_last_active(self, user: User) -> User:
        user.last_active_at = datetime.utcnow()
        return self.user_repo.update(self.db, user)

    async def update_profile(self, user: User, user_update: UserUpdate) -> User:
        # Check for sensitive changes requiring OTP
        sensitive_change = False
        if (user_update.email and user_update.email != user.email) or \
           (user_update.mobile and user_update.mobile != user.mobile):
            sensitive_change = True
            
        if sensitive_change and user.telegram_chat_id:
            if not user_update.otp:
                 # Generate and send OTP
                 otp = self.telegram_service.generate_otp(user.mobile)
                 message = (
                     f"🔐 <b>Profile Update Verification</b>\n\n"
                     f"Hello <b>{user.username}</b>,\n\n"
                     f"You are attempting to update sensitive information.\n"
                     f"Your verification OTP is: <code>{otp}</code>\n\n"
                     f"⏰ Valid for <b>5 minutes</b>\n"
                     f"⚠️ If you didn't initiate this, secure your account immediately.\n\n"
                     f"— Open Analytics Security Team"
                 )
                 # Accessing bot_service via telegram_service if exposed, or recreating/using helper
                 await self.telegram_service.bot_service.send_message(user.telegram_chat_id, message)
                 raise HTTPException(
                     status_code=status.HTTP_403_FORBIDDEN,
                     detail="OTP verification required for sensitive changes. Check your Telegram."
                 )
            else:
                 # Verify OTP
                 if not self.telegram_service.verify_otp(user.mobile, user_update.otp):
                     raise HTTPException(
                         status_code=status.HTTP_400_BAD_REQUEST,
                         detail="Invalid or expired OTP"
                     )

        # Track changes for notification BEFORE updating
        changes_detail = []
        old_email = user.email
        old_mobile = user.mobile
        old_name = user.name
        
        # Update name if provided
        if user_update.name is not None:
            user.name = user_update.name
            if old_name != user_update.name:
                changes_detail.append(f"Name: {old_name or 'None'} → {user_update.name}")
        
        if user_update.email is not None:
            # Check if email is already taken (if provided)
            if user_update.email:
                existing = self.user_repo.get_by_email(self.db, user_update.email)
                if existing and existing.id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
            if old_email != user_update.email:
                changes_detail.append(f"Email: {old_email or 'None'} → {user_update.email}")
            user.email = user_update.email
        
        if user_update.mobile is not None:
            # Validate mobile is not empty
            if not user_update.mobile or not user_update.mobile.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mobile number is required"
                )
            # Check if mobile is already taken
            existing = self.user_repo.get_by_mobile(self.db, user_update.mobile)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mobile number already registered"
                )
            if old_mobile != user_update.mobile:
                changes_detail.append(f"Mobile: {old_mobile or 'None'} → {user_update.mobile}")
            user.mobile = user_update.mobile.strip()
        
        if user_update.theme_preference is not None:
            if user_update.theme_preference not in ["dark", "light"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Theme preference must be 'dark' or 'light'"
                )
            user.theme_preference = user_update.theme_preference

        if user_update.two_factor_enabled is not None:
            if user_update.two_factor_enabled != user.two_factor_enabled:
                action = "Enabled" if user_update.two_factor_enabled else "Disabled"
                changes_detail.append(f"Two-Factor Auth: {action}")
            user.two_factor_enabled = user_update.two_factor_enabled
        
        # TELEGRAM ALERT - Send detailed changes
        if user.telegram_chat_id and changes_detail:
            try:
                # Build detailed change list
                changes_text = "\n".join([f"• {change}" for change in changes_detail])
                
                message = (
                    f"✅ <b>Profile Updated Successfully</b>\n\n"
                    f"Hello <b>{user.username}</b>,\n\n"
                    f"The following changes have been made:\n\n"
                    f"{changes_text}\n\n"
                    f"⚠️ If you didn't make these changes, contact support immediately.\n\n"
                    f"— Open Analytics"
                )
                await self.telegram_service.send_info_notification(user, message)
            except Exception as e:
                print(f"Failed to send profile update alert: {e}")

        user.updated_at = datetime.utcnow()
        return self.user_repo.update(self.db, user)

    async def change_password(self, user: User, password_data: PasswordChange):
        # Verify current password
        if not verify_password(password_data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Verify new password matches confirmation
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match"
            )
        
        # Update password
        user.hashed_password = get_password_hash(password_data.new_password)
        user.updated_at = datetime.utcnow()
        self.user_repo.update(self.db, user)
        
        # TELEGRAM ALERT
        if user.telegram_chat_id:
            try:
                manager = get_connection_manager(settings.DATA_DIR)
                bot = TelegramBotService(manager)
                
                now = datetime.now().strftime("%d-%b-%Y %I:%M %p")
                message = (
                    f"🚨 <b>Security Alert: Password Changed</b>\n\n"
                    f"Hello <b>{user.username}</b>,\n\n"
                    f"Your account password was successfully changed.\n\n"
                    f"🕐 Time: <code>{now}</code>\n\n"
                    f"⚠️ <b>If you didn't make this change:</b>\n"
                    f"• Someone may have accessed your account\n"
                    f"• Contact support immediately\n"
                    f"• Secure all your linked accounts\n\n"
                    f"— Open Analytics Security Team"
                )
                await bot.send_message(user.telegram_chat_id, message)
            except Exception as e:
                print(f"Failed to send password alert: {e}")
        
    def create_feedback(self, user: User, subject: str, message: str) -> Feedback:
        feedback = Feedback(
            user_id=user.id,
            subject=subject,
            message=message,
            status="open"
        )
        return self.feedback_repo.create(self.db, feedback)

    def create_feature_request(self, user: User, request_data: FeatureRequestCreate, background_tasks: BackgroundTasks) -> FeatureRequest:
        # Sanitize input
        description = request_data.description.strip()
        if not description or len(description) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feature description must be at least 10 characters"
            )
        
        if len(description) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feature description is too long (max 5000 characters)"
            )
        
        # Create feature request
        context_dict = None
        if request_data.context:
            context_dict = {
                "page": request_data.context.page,
                "module": request_data.context.module,
                "issue_type": request_data.context.issue_type
            }
        
        feature_request = FeatureRequest(
            user_id=user.id,
            description=description,
            context=context_dict,
            status="pending"
        )
        created_request = self.feature_request_repo.create(self.db, feature_request)
        
        # Process AI analysis in background (non-blocking)
        background_tasks.add_task(
            process_ai_analysis,
            created_request.id,
            description,
            context_dict or {}
        )
        
        return created_request

    def get_user_feature_requests(self, user: User) -> List[FeatureRequest]:
        return self.feature_request_repo.get_by_user(self.db, user.id)


async def process_ai_analysis(feature_request_id: int, description: str, context: dict):
    """Background task to process AI analysis"""
    try:
        # AI analysis removed
        analysis = None
        
        # Get new database session for background task
        router = get_db_router(settings.DATA_DIR)
        auth_client = router.get_auth_db()
        if auth_client:
            db = auth_client.get_session()
            try:
                feature_request = db.query(FeatureRequest).filter(FeatureRequest.id == feature_request_id).first()
                if feature_request:
                    feature_request.ai_analysis = analysis
                    feature_request.status = "in_review"  # Move to in_review after AI analysis
                    db.commit()
            finally:
                db.close()
    except Exception as e:
        print(f"Error processing AI analysis: {e}")
        # Keep status as pending if AI analysis fails
