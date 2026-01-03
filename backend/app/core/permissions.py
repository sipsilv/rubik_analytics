from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.core.security import decode_access_token
from datetime import datetime, timedelta

security = HTTPBearer()

# Throttle permission logs to avoid spam
_last_permission_log = {}
PERMISSION_LOG_THROTTLE_SECONDS = 60  # Only log once per minute per user

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # CRITICAL: Check for Super User FIRST - bypass ALL status checks
    user_role_lower = user.role.lower() if user.role else ""
    is_super_admin = user_role_lower == "super_admin"
    
    if is_super_admin:
        # Throttle permission logs to avoid spam on every API call
        now = datetime.utcnow()
        should_log = True
        if user.username in _last_permission_log:
            time_since_log = now - _last_permission_log[user.username]
            if time_since_log < timedelta(seconds=PERMISSION_LOG_THROTTLE_SECONDS):
                should_log = False
        
        if should_log:
            _last_permission_log[user.username] = now
            print(f"[PERMISSIONS] [SUPER_USER] Access granted for: {user.username}")
        
        # Force activate and normalize role (safety mechanism)
        if not user.is_active:
            print(f"[PERMISSIONS] [SUPER_USER] WARNING: User was inactive - auto-activating")
            user.is_active = True
        
        if user.role.lower() != "super_admin":
            print(f"[PERMISSIONS] [SUPER_USER] WARNING: Role mismatch - normalizing to super_admin")
            user.role = "super_admin"
        
        # Update last_active_at (throttled: only if last update was > 1 minute ago)
        now = datetime.utcnow()
        should_update = True
        if user.last_active_at:
            time_since_update = now - user.last_active_at
            if time_since_update < timedelta(minutes=1):
                should_update = False
        
        if should_update:
            user.last_active_at = now
            db.commit()
        else:
            db.commit()  # Still commit role/is_active changes
        
        return user
    
    # For non-Super Users: Check is_active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    # Update last_active_at for authenticated API calls (throttled: only if last update was > 1 minute ago)
    now = datetime.utcnow()
    should_update = True
    if user.last_active_at:
        time_since_update = now - user.last_active_at
        if time_since_update < timedelta(minutes=1):
            should_update = False
    
    if should_update:
        user.last_active_at = now
        db.commit()
    
    return user

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # Normalize roles for case-insensitive comparison
        user_role_lower = current_user.role.lower() if current_user.role else ""
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        
        if user_role_lower not in allowed_roles_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def get_admin_user(current_user: User = Depends(require_roles(["admin", "super_admin"]))) -> User:
    return current_user

def get_super_admin(current_user: User = Depends(require_roles(["super_admin"]))) -> User:
    return current_user

# Helper function for token-based auth (used in auth endpoints)
def get_current_user_from_token(token: str, db: Session) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # CRITICAL: Check for Super User FIRST - bypass ALL status checks
    user_role_lower = user.role.lower() if user.role else ""
    is_super_admin = user_role_lower == "super_admin"
    
    if is_super_admin:
        # Throttle permission logs to avoid spam
        now = datetime.utcnow()
        should_log = True
        if user.username in _last_permission_log:
            time_since_log = now - _last_permission_log[user.username]
            if time_since_log < timedelta(seconds=PERMISSION_LOG_THROTTLE_SECONDS):
                should_log = False
        
        if should_log:
            _last_permission_log[user.username] = now
            print(f"[PERMISSIONS] [SUPER_USER] Token access granted for: {user.username}")
        
        # Force activate and normalize role (safety mechanism)
        if not user.is_active:
            print(f"[PERMISSIONS] [SUPER_USER] WARNING: User was inactive - auto-activating")
            user.is_active = True
        
        if user.role.lower() != "super_admin":
            print(f"[PERMISSIONS] [SUPER_USER] WARNING: Role mismatch - normalizing to super_admin")
            user.role = "super_admin"
        
        # Update last_active_at (throttled: only if last update was > 1 minute ago)
        now = datetime.utcnow()
        should_update = True
        if user.last_active_at:
            time_since_update = now - user.last_active_at
            if time_since_update < timedelta(minutes=1):
                should_update = False
        
        if should_update:
            user.last_active_at = now
            db.commit()
        else:
            db.commit()  # Still commit role/is_active changes
        
        return user
    
    # For non-Super Users: Check is_active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    # Update last_active_at for authenticated API calls (throttled: only if last update was > 1 minute ago)
    now = datetime.utcnow()
    should_update = True
    if user.last_active_at:
        time_since_update = now - user.last_active_at
        if time_since_update < timedelta(minutes=1):
            should_update = False
    
    if should_update:
        user.last_active_at = now
        db.commit()
    
    return user
