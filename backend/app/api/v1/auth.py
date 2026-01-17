from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.permissions import get_current_user, get_current_user_from_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse
from datetime import datetime

router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Identifier is now guaranteed to be set (either from 'identifier' or 'username' field via validator)
    identifier = login_data.identifier.strip()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identifier is required"
        )
    
    # Try to find user by multiple identifiers:
    # 1. User ID (if identifier is numeric)
    # 2. Email (case-insensitive)
    # 3. Mobile number
    # 4. Username (case-insensitive, for backward compatibility)
    
    user = None
    
    # Try User ID first (if identifier is numeric)
    if identifier.isdigit():
        try:
            user_id = int(identifier)
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                print(f"[AUTH] User found by ID: {user_id}")
        except ValueError:
            pass
    
    # Try Email (case-insensitive) - only if email is not None
    if not user:
        identifier_lower = identifier.lower()
        user = db.query(User).filter(
            User.email.isnot(None),
            func.lower(User.email) == identifier_lower
        ).first()
        if user:
            print(f"[AUTH] User found by email: {identifier}")
    
    # Try Mobile number
    if not user:
        user = db.query(User).filter(User.mobile == identifier).first()
        if user:
            print(f"[AUTH] User found by mobile: {identifier}")
    
    # Try Username (case-insensitive, for backward compatibility)
    if not user:
        identifier_lower = identifier.lower()
        user = db.query(User).filter(func.lower(User.username) == identifier_lower).first()
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
    from app.services.telegram_bot_service import TelegramBotService
    from app.core.database import get_connection_manager
    from app.core.config import settings
    
    # Only enforce if user has linked Telegram AND has enabled 2FA
    print(f"[AUTH DEBUG] Login - User: {user.username}, ChatID: {user.telegram_chat_id}, 2FA Enabled: {user.two_factor_enabled}")
    if user.telegram_chat_id and user.two_factor_enabled:
        # Check if OTP is provided
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
    # This check happens BEFORE any is_active validation
    user_role_lower = user.role.lower() if user.role else ""
    is_super_admin = user_role_lower == "super_admin"
    
    print(f"[AUTH] Login attempt - User: {user.username}, Role: '{user.role}' (normalized: '{user_role_lower}'), Is Active: {user.is_active}, Is Super Admin: {is_super_admin}")
    
    # SUPER USER BYPASS - This happens FIRST, before any other checks
    if is_super_admin:
        print(f"[AUTH] [SUPER_USER] ===== SUPER USER DETECTED =====")
        print(f"[AUTH] [SUPER_USER] User: {user.username}")
        print(f"[AUTH] [SUPER_USER] Current Status: is_active={user.is_active}")
        print(f"[AUTH] [SUPER_USER] BYPASSING ALL STATUS CHECKS - UNCONDITIONAL ACCESS GRANTED")
        
        # Force activate and normalize role (safety mechanism)
        needs_update = False
        if not user.is_active:
            print(f"[AUTH] [SUPER_USER] Auto-activating user (was inactive)")
            user.is_active = True
            needs_update = True
        
        if user.role.lower() != "super_admin":
            print(f"[AUTH] [SUPER_USER] Normalizing role from '{user.role}' to 'super_admin'")
            user.role = "super_admin"
            needs_update = True
        
        if needs_update:
            db.commit()
            print(f"[AUTH] [SUPER_USER] User updated in database")
        
        # Update last seen and last active
        user.last_seen = datetime.utcnow()
        user.last_active_at = datetime.utcnow()
        
        # Set dark theme as default if theme_preference is not set
        if not user.theme_preference:
            user.theme_preference = "dark"
        
        db.commit()
        
        print(f"[AUTH] [SUPER_USER] ===== LOGIN SUCCESSFUL - TOKEN GENERATED =====")
        
        # Generate token and return IMMEDIATELY - NO FURTHER CHECKS
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
    

    
    # For non-Super Users ONLY: Check is_active status and account_status
    print(f"[AUTH] Regular user login - checking is_active status...")
    print(f"[AUTH] User status - is_active: {user.is_active}, account_status: {user.account_status}")
    
    # Check both is_active and account_status for consistency
    if not user.is_active:
        print(f"[AUTH] [BLOCKED] Login blocked for {user.username} - Account is inactive (role: {user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Also check account_status - must be ACTIVE to login (only if account_status is set)
    # If account_status is None or empty, allow login if is_active is True (backward compatibility)
    if user.account_status:
        account_status_upper = user.account_status.upper().strip()
        if account_status_upper and account_status_upper != "ACTIVE":
            print(f"[AUTH] [BLOCKED] Login blocked for {user.username} - Account status is {user.account_status}")
            # Sync is_active with account_status for consistency
            user.is_active = False
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User account is {user.account_status.lower()}"
            )
    
    # Update last seen and last active
    user.last_seen = datetime.utcnow()
    user.last_active_at = datetime.utcnow()
    
    # Set dark theme as default if theme_preference is not set
    if not user.theme_preference:
        user.theme_preference = "dark"
    
    db.commit()
    
            
    # -------------------------------------------------------------

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

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    # In a stateless JWT system, logout is handled client-side
    # But we can update last_seen here
    try:
        user = get_current_user_from_token(credentials.credentials, db)
        user.last_seen = datetime.utcnow()
        db.commit()
    except:
        pass
    
    return {"message": "Logged out successfully"}

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    # Try to find user by email first (backward compatibility)
    user = db.query(User).filter(User.email == request.email).first()
    
    # If not found by email, try as mobile number
    if not user:
        user = db.query(User).filter(User.mobile == request.email).first()
    
    # If still not found and it's numeric, try as user ID
    if not user and request.email.isdigit():
        try:
            user_id = int(request.email)
            user = db.query(User).filter(User.id == user_id).first()
        except ValueError:
            pass
    
    if not user:
        # Don't reveal if user exists (security best practice)
        return ForgotPasswordResponse(message="If your account exists, a password reset code has been sent.")
    
    # Telegram OTP Flow (prioritize Telegram if linked)
    if user.telegram_chat_id:
        from app.services.telegram_notification_service import TelegramNotificationService
        notification_service = TelegramNotificationService()
        
        # Generate OTP (stores in memory)
        otp = notification_service.generate_otp(user.mobile)
        
        # Send OTP with professional formatting
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
    
    # TODO: Implement email sending for users without Telegram
    return ForgotPasswordResponse(message="If your account exists, a password reset code has been sent.")

@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using OTP received via Telegram"""
    
    # Find user by identifier (same logic as forgot password)
    user = db.query(User).filter(User.email == request.identifier).first()
    
    if not user:
        user = db.query(User).filter(User.mobile == request.identifier).first()
    
    if not user and request.identifier.isdigit():
        try:
            user_id = int(request.identifier)
            user = db.query(User).filter(User.id == user_id).first()
        except ValueError:
            pass
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
   # Verify OTP
    from app.services.telegram_notification_service import TelegramNotificationService
    notification_service = TelegramNotificationService()
    
    if not notification_service.verify_otp(user.mobile, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
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

@router.post("/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(credentials.credentials, db)
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
