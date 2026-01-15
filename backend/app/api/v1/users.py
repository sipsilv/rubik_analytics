from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.schemas.admin import FeedbackResponse, FeatureRequestCreate, FeatureRequestResponse
# AI service removed - feature requests no longer get AI analysis
from fastapi import BackgroundTasks
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer()

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user(credentials, db)
    # Update last active on any activity
    from datetime import datetime
    user.last_active_at = datetime.utcnow()
    db.commit()
    return user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user(credentials, db)
    
    # Check for sensitive changes requiring OTP
    sensitive_change = False
    if (user_update.email and user_update.email != user.email) or \
       (user_update.mobile and user_update.mobile != user.mobile):
        sensitive_change = True
        
    if sensitive_change and user.telegram_chat_id:
        from app.services.telegram_notification_service import TelegramNotificationService
        ns = TelegramNotificationService()
        
        if not user_update.otp:
             # Generate and send OTP
             otp = ns.generate_otp(user.mobile)
             message = (
                 f"🔐 <b>Profile Update Verification</b>\n\n"
                 f"Hello <b>{user.username}</b>,\n\n"
                 f"You are attempting to update sensitive information.\n"
                 f"Your verification OTP is: <code>{otp}</code>\n\n"
                 f"⏰ Valid for <b>5 minutes</b>\n"
                 f"⚠️ If you didn't initiate this, secure your account immediately.\n\n"
                 f"— Rubik Analytics Security Team"
             )
             await ns.bot_service.send_message(user.telegram_chat_id, message)
             raise HTTPException(
                 status_code=status.HTTP_403_FORBIDDEN,
                 detail="OTP verification required for sensitive changes. Check your Telegram."
             )
        else:
             # Verify OTP
             if not ns.verify_otp(user.mobile, user_update.otp):
                 raise HTTPException(
                     status_code=status.HTTP_400_BAD_REQUEST,
                     detail="Invalid or expired OTP"
                 )

    
    # Track changes for notification BEFORE updating
    changes_detail = []
    old_email = user.email
    old_mobile = user.mobile
    old_name = user.name
    
    # Update last active
    from datetime import datetime
    user.last_active_at = datetime.utcnow()
    
    # Update name if provided
    if user_update.name is not None:
        user.name = user_update.name
        if old_name != user_update.name:
            changes_detail.append(f"Name: {old_name or 'None'} → {user_update.name}")
    
    if user_update.email is not None:
        # Check if email is already taken (if provided)
        if user_update.email:
            existing = db.query(User).filter(User.email == user_update.email, User.id != user.id).first()
            if existing:
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
        existing = db.query(User).filter(User.mobile == user_update.mobile, User.id != user.id).first()
        if existing:
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
            from app.services.telegram_notification_service import TelegramNotificationService
            ns = TelegramNotificationService()
            
            # Build detailed change list
            changes_text = "\n".join([f"• {change}" for change in changes_detail])
            
            message = (
                f"✅ <b>Profile Updated Successfully</b>\n\n"
                f"Hello <b>{user.username}</b>,\n\n"
                f"The following changes have been made:\n\n"
                f"{changes_text}\n\n"
                f"⚠️ If you didn't make these changes, contact support immediately.\n\n"
                f"— Rubik Analytics"
            )
            await ns.send_info_notification(user, message)
        except Exception as e:
            print(f"Failed to send profile update alert: {e}")

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user

@router.post("/me/ping")
async def ping_activity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Update last active timestamp for live status tracking"""
    user = get_current_user(credentials, db)
    user.last_active_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "last_active_at": user.last_active_at}

@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Change user password"""
    user = get_current_user(credentials, db)
    
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
    db.commit()
    
    # TELEGRAM ALERT
    if user.telegram_chat_id:
        try:
            from app.services.telegram_bot_service import TelegramBotService
            from app.core.database import get_connection_manager
            from app.core.config import settings
            from datetime import datetime
            
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
                f"— Rubik Analytics Security Team"
            )
            await bot.send_message(user.telegram_chat_id, message)
        except Exception as e:
            print(f"Failed to send password alert: {e}")
    
    return {"message": "Password changed successfully"}

# Feedback (user endpoint)
class FeedbackCreate(BaseModel):
    subject: str
    message: str

@router.post("/feedback", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Create feedback (user endpoint)"""
    user = get_current_user(credentials, db)
    
    feedback = Feedback(
        user_id=user.id,
        subject=feedback_data.subject,
        message=feedback_data.message,
        status="open"
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_name=user.username,
        subject=feedback.subject,
        message=feedback.message,
        status=feedback.status,
        created_at=feedback.created_at
    )

# Feature Requests (user endpoint)
async def process_ai_analysis(feature_request_id: int, description: str, context: dict):
    """Background task to process AI analysis"""
    from app.core.database import get_db_router
    from app.core.config import settings
    
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

@router.post("/feature-requests", response_model=FeatureRequestResponse)
async def create_feature_request(
    request_data: FeatureRequestCreate,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Create a new feature request with AI analysis"""
    user = get_current_user(credentials, db)
    
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
    db.add(feature_request)
    db.commit()
    db.refresh(feature_request)
    
    # Process AI analysis in background (non-blocking)
    background_tasks.add_task(
        process_ai_analysis,
        feature_request.id,
        description,
        context_dict or {}
    )
    
    return FeatureRequestResponse(
        id=feature_request.id,
        user_id=feature_request.user_id,
        user_name=user.username,
        description=feature_request.description,
        context=feature_request.context,
        status=feature_request.status,
        ai_analysis=None,  # Will be populated by background task
        admin_note=feature_request.admin_note,
        reviewed_by=feature_request.reviewed_by,
        reviewed_at=feature_request.reviewed_at,
        created_at=feature_request.created_at,
        updated_at=feature_request.updated_at
    )

@router.get("/feature-requests", response_model=list[FeatureRequestResponse])
async def get_my_feature_requests(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user's feature requests"""
    user = get_current_user(credentials, db)
    
    requests = db.query(FeatureRequest).filter(
        FeatureRequest.user_id == user.id
    ).order_by(FeatureRequest.created_at.desc()).all()
    
    return [
        FeatureRequestResponse(
            id=req.id,
            user_id=req.user_id,
            user_name=user.username,
            description=req.description,
            context=req.context,
            status=req.status,
            ai_analysis=req.ai_analysis,
            admin_note=req.admin_note,
            reviewed_by=req.reviewed_by,
            reviewed_at=req.reviewed_at,
            created_at=req.created_at,
            updated_at=req.updated_at
        )
        for req in requests
    ]
