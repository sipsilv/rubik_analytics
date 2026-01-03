from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.permissions import get_current_user, get_current_user_from_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, ForgotPasswordRequest, ForgotPasswordResponse
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
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        # Don't reveal if email exists
        return ForgotPasswordResponse(message="If the email exists, a reset link has been sent")
    
    # TODO: Implement email sending
    return ForgotPasswordResponse(message="If the email exists, a reset link has been sent")

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
