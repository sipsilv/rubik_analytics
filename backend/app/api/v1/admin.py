from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from app.core.database import get_db
from app.core.permissions import get_current_user, get_admin_user, get_super_admin
from app.core.security import get_password_hash
from app.core.websocket_manager import manager
from app.models.user import User
from app.models.access_request import AccessRequest
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.admin import (
    AccessRequestCreate, AccessRequestResponse, FeedbackResponse,
    FeatureRequestResponse, FeatureRequestUpdate
)
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import or_
import secrets
import uuid
import re
import random
import hashlib
from app.core.audit import AuditService

def generate_user_id_from_name_mobile(name: str, mobile: str, db: Session) -> str:
    """
    Generate a unique user_id based on random 4-digit ID and partial mobile number.
    Format: {4digit_random_id}{partial_mobile}
    Starts with random 4-digit number (1000-9999) and increments if collision occurs.
    Note: name parameter is kept for compatibility but not used in generation.
    """
    if not mobile:
        raise ValueError("Mobile number is required to generate user_id")
    
    # Log for debugging
    print(f"[DEBUG] Generating user_id for mobile: {mobile}")
    
    # Normalize mobile: remove all non-digit characters
    mobile_normalized = re.sub(r'[^\d]', '', mobile or '')
    
    if not mobile_normalized:
        raise ValueError("Mobile number must contain at least one digit")
    
    # Take last 4-6 digits of mobile (partial mobile number)
    if len(mobile_normalized) >= 6:
        mobile_part = mobile_normalized[-6:]  # Last 6 digits
    elif len(mobile_normalized) >= 4:
        mobile_part = mobile_normalized[-4:]  # Last 4 digits
    else:
        # If less than 4 digits, pad with zeros or use as is
        mobile_part = mobile_normalized.zfill(4)  # Pad to at least 4 digits
    
    # Start with a random 4-digit number (1000-9999)
    random_id = random.randint(1000, 9999)
    
    # Create base user_id: {4digit_id}{partial_mobile}
    user_id = f"{random_id}{mobile_part}"
    
    # Check if this user_id already exists, if so, increment the 4-digit ID
    counter = 0
    max_attempts = 9000  # Maximum attempts to find unique ID
    initial_random_id = random_id  # Track starting point to detect full cycle
    tried_ids = set()  # Track tried IDs to avoid infinite loops
    
    while True:
        # Check if user_id exists in database
        existing = db.query(User).filter(User.user_id == user_id).first()
        
        # If user_id doesn't exist in database AND we haven't tried it before, use it
        if not existing and user_id not in tried_ids:
            tried_ids.add(user_id)
            break
        
        # If we've already tried this ID, increment and try again
        # Increment the 4-digit ID
        random_id += 1
        
        # If we exceed 9999, wrap around to 1000
        if random_id > 9999:
            random_id = 1000
        
        # Check if we've cycled back to the starting point (all IDs for this mobile_part are taken)
        if counter > 0 and random_id == initial_random_id:
            # Fallback: use UUID prefix if all 4-digit combinations are exhausted
            uuid_part = str(uuid.uuid4())[:8].replace('-', '')
            user_id = f"{uuid_part}{mobile_part}"
            # Verify this UUID-based ID is also unique
            if not db.query(User).filter(User.user_id == user_id).first():
                break
            # If UUID also collides, generate a new UUID and try again
            counter += 1
            if counter > max_attempts:
                # Final fallback: use full UUID
                user_id = f"{str(uuid.uuid4()).replace('-', '')}{mobile_part}"
                break
            continue
        
        # Generate new user_id with incremented random_id
        user_id = f"{random_id}{mobile_part}"
        counter += 1
        
        # Safety: prevent infinite loop (max 9000 attempts to cycle through all 4-digit numbers)
        if counter > max_attempts:
            # Fallback: use UUID if we've exhausted all 4-digit combinations
            uuid_part = str(uuid.uuid4())[:8].replace('-', '')
            user_id = f"{uuid_part}{mobile_part}"
            # Final check
            if not db.query(User).filter(User.user_id == user_id).first():
                break
            # If even UUID collides (very unlikely), generate a completely new one
            user_id = f"{str(uuid.uuid4()).replace('-', '')}{mobile_part}"
            break
    
    # Validate user_id length (most databases have limits)
    if len(user_id) > 255:
        # If too long, truncate mobile part
        max_mobile_len = 255 - len(str(random_id))
        if max_mobile_len > 0:
            mobile_part = mobile_part[:max_mobile_len]
            user_id = f"{random_id}{mobile_part}"
        else:
            # Fallback to UUID if still too long
            user_id = str(uuid.uuid4()).replace('-', '')[:50]
    
    print(f"[DEBUG] Final user_id generated: {user_id} (length: {len(user_id)})")
    return user_id

class ChangePasswordRequest(BaseModel):
    password: str

class UserStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

class AdminMessage(BaseModel):
    message: str

router = APIRouter()

# User Management
@router.post("/users/{user_id}/message")
async def send_user_message(
    user_id: int,
    message_data: AdminMessage,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Send a custom Telegram message to a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="User has not connected Telegram")
        
    try:
        from app.services.telegram_notification_service import TelegramNotificationService
        from app.models.telegram_message import TelegramMessage
        ns = TelegramNotificationService()
        
        # Format message with Admin context
        formatted_message = (
            f"📩 <b>Message from Admin ({admin.username})</b>\n\n"
            f"{message_data.message}\n\n"
            f"— Rubik Analytics Support"
        )
        
        await ns.bot_service.send_message(user.telegram_chat_id, formatted_message)
        
        # Store message in database
        msg = TelegramMessage(
            user_id=user.id,
            chat_id=user.telegram_chat_id,
            message_text=message_data.message,
            from_user=False,
            admin_username=admin.username,
            is_read=True  # Admin messages are considered read
        )
        db.add(msg)
        db.commit()
        
        return {"message": "Message sent successfully"}
    except Exception as e:
        print(f"[ADMIN] Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@router.get("/users/{user_id}/messages")
async def get_user_messages(
    user_id: int,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get message history for a user"""
    from app.models.telegram_message import TelegramMessage
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    messages = (
        db.query(TelegramMessage)
        .filter(TelegramMessage.user_id == user_id)
        .order_by(TelegramMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    
    # Mark unread messages as read
    unread_count = (
        db.query(TelegramMessage)
        .filter(
            TelegramMessage.user_id == user_id,
            TelegramMessage.is_read == False,
            TelegramMessage.from_user == True
        )
        .update({"is_read": True})
    )
    db.commit()
    
    return {
        "messages": [
            {
                "id": msg.id,
                "message_text": msg.message_text,
                "from_user": msg.from_user,
                "admin_username": msg.admin_username,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "is_read": msg.is_read
            }
            for msg in reversed(messages)  # Show oldest first
        ],
        "unread_count": unread_count
    }


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    search: Optional[str] = None
):
    """Get all users, optionally filtered by search term"""
    query = db.query(User)
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.mobile.ilike(f"%{search}%"),
                User.user_id.ilike(f"%{search}%"),
                User.id == search if search.isdigit() else False
            )
        )
    users = query.order_by(User.created_at.desc()).all()
    
    # Calculate is_online for each user
    now = datetime.now(timezone.utc)
    online_threshold = timedelta(minutes=5)
    
    result = []
    for user in users:
        # Check if user has active WebSocket connection
        has_websocket = manager.is_user_online(user.id)
        
        # Check if user has recent activity (within 5 minutes)
        has_recent_activity = False
        if user.last_active_at:
            # Ensure both datetimes are timezone-aware for comparison
            last_active = user.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            time_diff = now - last_active
            has_recent_activity = time_diff < online_threshold
        
        # User is online if they have WebSocket connection OR recent activity (and account is active)
        is_online = (has_websocket or has_recent_activity) and user.is_active
        
        # Create response with is_online
        user_dict = {
            "id": user.id,
            "user_id": user.user_id,
            "username": user.username,
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "role": user.role,
            "is_active": user.is_active,
            "account_status": user.account_status,
            "theme_preference": user.theme_preference,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_seen": user.last_seen,
            "last_active_at": user.last_active_at,
            "is_online": is_online,
            "telegram_chat_id": user.telegram_chat_id
        }
        result.append(UserResponse(**user_dict))
    
    return result

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate is_online
    now = datetime.now(timezone.utc)
    online_threshold = timedelta(minutes=5)
    
    has_websocket = manager.is_user_online(user.id)
    has_recent_activity = False
    if user.last_active_at:
        # Ensure both datetimes are timezone-aware for comparison
        last_active = user.last_active_at
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        time_diff = now - last_active
        has_recent_activity = time_diff < online_threshold
    
    is_online = (has_websocket or has_recent_activity) and user.is_active
    
    user_dict = {
        "id": user.id,
        "user_id": user.user_id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "role": user.role,
        "is_active": user.is_active,
        "account_status": user.account_status,
        "theme_preference": user.theme_preference,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_seen": user.last_seen,
        "last_active_at": user.last_active_at,
        "is_online": is_online,
        "telegram_chat_id": user.telegram_chat_id
    }
    return UserResponse(**user_dict)

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Normalize and validate inputs
    username = str(user_data.username).strip() if user_data.username else ""
    mobile = str(user_data.mobile).strip() if user_data.mobile else ""
    email = str(user_data.email).strip() if user_data.email else ""
    
    # Validate all required fields
    missing_fields = []
    if not username:
        missing_fields.append("Username")
    if not email:
        missing_fields.append("Email")
    if not mobile:
        missing_fields.append("Mobile Number")
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Fields mandatory: {', '.join(missing_fields)}"
        )
    
    # Check if username exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Check if mobile exists
    existing = db.query(User).filter(User.mobile == mobile).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mobile number already exists")
    
    # Generate unique User ID based on mobile (immutable)
    try:
        name_for_id = str(user_data.name).strip() if user_data.name else username
        print(f"[DEBUG] Creating user - name: {name_for_id}, username: {username}, mobile: {mobile}")
        user_id = generate_user_id_from_name_mobile(name_for_id, mobile, db)
        print(f"[DEBUG] Generated user_id: {user_id}")
    except ValueError as e:
        print(f"[ERROR] ValueError in user_id generation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Unexpected error in user_id generation: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to generate user ID: {str(e)}")
    
    try:
        # Validate password is required
        if not user_data.password or not str(user_data.password).strip():
            raise HTTPException(status_code=400, detail="Password is required and cannot be empty")
        
        # Prepare user data with proper trimming and None handling
        # Note: username, email, and mobile are already validated and normalized above
        name = str(user_data.name).strip() if user_data.name and str(user_data.name).strip() else None
        # email is already normalized above and is required
        password = str(user_data.password).strip()
        role = (user_data.role or "user").strip().lower() if user_data.role else "user"
        
        # Validate role
        if role not in ["user", "admin"]:
            role = "user"
        
        print(f"[DEBUG] Creating user with: username={username}, mobile={mobile}, role={role}")
        
        user = User(
            user_id=user_id,
            username=username,
            name=name,
            email=email,
            mobile=mobile,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[DEBUG] User created successfully: {user.username}, user_id: {user.user_id}")
        return user
    except IntegrityError as e:
        db.rollback()
        # Check if it's a unique constraint violation
        error_str = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        if 'unique' in error_str or 'duplicate' in error_str:
            if 'user_id' in error_str:
                # Retry with a new user_id if there was a collision
                try:
                    print(f"[DEBUG] User ID collision detected, generating new user_id...")
                    name_for_id = str(user_data.name).strip() if user_data.name else username
                    user_id = generate_user_id_from_name_mobile(name_for_id, mobile, db)
                    print(f"[DEBUG] New user_id generated: {user_id}")
                    # Create a new User object with the new user_id
                    # IMPORTANT: Use already normalized variables from above
                    # username, email, and mobile are already normalized, just prepare other fields
                    name = str(user_data.name).strip() if user_data.name and str(user_data.name).strip() else None
                    # email is already normalized above and is required
                    password = str(user_data.password).strip()
                    role = (user_data.role or "user").strip().lower() if user_data.role else "user"
                    
                    if role not in ["user", "admin"]:
                        role = "user"
                    
                    user = User(
                        user_id=user_id,
                        username=username,
                        name=name,
                        email=email,
                        mobile=mobile,
                        hashed_password=get_password_hash(password),
                        role=role,
                        is_active=True,
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                    return user
                except Exception as retry_error:
                    db.rollback()
                    print(f"[ERROR] Failed to retry user creation: {str(retry_error)}")
                    raise HTTPException(status_code=400, detail=f"Failed to create user: {str(retry_error)}")
            elif 'username' in error_str:
                raise HTTPException(status_code=400, detail="Username already exists")
            elif 'email' in error_str:
                raise HTTPException(status_code=400, detail="Email already exists")
            elif 'mobile' in error_str:
                raise HTTPException(status_code=400, detail="Mobile number already exists")
        print(f"[ERROR] Failed to create user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Unexpected error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Track changes for notification
    changes_detail = []
    old_name = user.name
    old_email = user.email
    old_mobile = user.mobile
    old_role = user.role
    
    # CRITICAL: Cannot modify super_admin
    user_role_lower = user.role.lower() if user.role else ""
    if user_role_lower == "super_admin" and admin.id != user.id:
        # Only super_admin can modify other super_admin, but with restrictions
        if admin.role.lower() != "super_admin":
            raise HTTPException(status_code=403, detail="Cannot modify super_admin user")
    
    # Update name if provided
    if user_data.name is not None:
        if old_name != user_data.name:
            changes_detail.append(f"Name: {old_name or 'None'} → {user_data.name}")
        user.name = user_data.name
    
    # Update email if provided
    if user_data.email is not None:
        if user_data.email:  # If email is provided and not empty
            existing = db.query(User).filter(User.email == user_data.email, User.id != user_id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already exists")
        if old_email != user_data.email:
            changes_detail.append(f"Email: {old_email or 'None'} → {user_data.email}")
        user.email = user_data.email
    
    # Update mobile if provided
    if user_data.mobile is not None:
        if not user_data.mobile:
            raise HTTPException(status_code=400, detail="Mobile number is required")
        existing = db.query(User).filter(User.mobile == user_data.mobile, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Mobile number already exists")
        if old_mobile != user_data.mobile:
            changes_detail.append(f"Mobile: {old_mobile or 'None'} → {user_data.mobile}")
        user.mobile = user_data.mobile
    
    # Update updated_at timestamp
    user.updated_at = datetime.utcnow()
    
    # Update theme preference if provided
    if user_data.theme_preference:
        if user_data.theme_preference not in ["dark", "light"]:
            raise HTTPException(status_code=400, detail="Theme preference must be 'dark' or 'light'")
        user.theme_preference = user_data.theme_preference
    
    # Update role if provided (only super_admin can change roles, and cannot change super_admin role)
    if user_data.role is not None:
        # Only super_admin can change roles
        admin_role_lower = admin.role.lower() if admin.role else ""
        if admin_role_lower != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_admin can change user roles"
            )
        
        # Cannot change super_admin role via this endpoint
        user_role_lower = user.role.lower() if user.role else ""
        if user_role_lower == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change super_admin role. Use demote endpoint instead."
            )
        
        # Validate role value
        new_role_lower = user_data.role.lower().strip()
        if new_role_lower not in ["user", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'user' or 'admin'"
            )
        
        if old_role != new_role_lower:
            changes_detail.append(f"Role: {old_role} → {new_role_lower}")
        user.role = new_role_lower
        print(f"[ADMIN] Role changed for user {user.username} to {new_role_lower} by {admin.username}")
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Notify user via Telegram with detailed changes (Fail Silent)
    if user.telegram_chat_id and changes_detail:
        try:
            from app.services.telegram_notification_service import TelegramNotificationService
            ns = TelegramNotificationService()
            
            # Build detailed change list
            changes_text = "\n".join([f"• {change}" for change in changes_detail])
            
            msg = (
                f"📝 <b>Profile Updated by Admin</b>\n\n"
                f"Hello <b>{user.username}</b>,\n\n"
                f"Your profile has been updated by administrator <b>{admin.username}</b>.\n\n"
                f"<b>Changes made:</b>\n"
                f"{changes_text}\n\n"
                f"⚠️ If you have concerns about these changes, contact support.\n\n"
                f"— Rubik Analytics"
            )
            await ns.send_info_notification(user, msg)
        except Exception as e:
            print(f"[ADMIN] Failed to send Telegram notification: {e}")

    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_super_admin),
    db: Session = Depends(get_db)
):
    """Delete a user and handle related records"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    
    # Prevent deletion of super_admin (only if there's only one)
    if user.role == "super_admin":
        super_admin_count = db.query(User).filter(User.role == "super_admin").count()
        if super_admin_count <= 1:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete the last super admin. At least one super admin must exist."
            )
    
    try:
        # Delete or update related records before deleting the user
        # This prevents foreign key constraint violations
        
        # Delete feature requests created by this user
        db.query(FeatureRequest).filter(FeatureRequest.user_id == user.id).delete()
        
        # Set reviewed_by to NULL for feature requests reviewed by this user
        db.query(FeatureRequest).filter(FeatureRequest.reviewed_by == user.id).update(
            {"reviewed_by": None}
        )
        
        # Delete feedback created by this user
        db.query(Feedback).filter(Feedback.user_id == user.id).delete()
        
        # Set performer_id to NULL for audit logs (preserve audit trail but remove user reference)
        from app.models.audit_log import AuditLog
        db.query(AuditLog).filter(AuditLog.performer_id == user.id).update(
            {"performer_id": None}
        )
        
        # Set reviewed_by to NULL for access requests reviewed by this user
        db.query(AccessRequest).filter(AccessRequest.reviewed_by == user.id).update(
            {"reviewed_by": None}
        )
        
        # Now delete the user
        db.delete(user)
        db.commit()
        
        print(f"[DEBUG] User deleted successfully: {user.username} (ID: {user.id})")
        return {"message": "User deleted successfully"}
        
    except IntegrityError as e:
        db.rollback()
        error_str = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        print(f"[ERROR] IntegrityError while deleting user: {str(e)}")
        
        # Check for foreign key constraint errors
        if 'foreign key' in error_str or 'constraint' in error_str:
            raise HTTPException(
                status_code=400,
                detail="Unable to delete user: User has related records that prevent deletion. Please contact system administrator."
            )
        
        raise HTTPException(
            status_code=400,
            detail=f"Database constraint error: {str(e)}"
        )
        
    except Exception as e:
        db.rollback()
        error_str = str(e).lower()
        print(f"[ERROR] Failed to delete user: {str(e)}")
        
        # Check for foreign key constraint errors
        if 'foreign key' in error_str or 'constraint' in error_str:
            raise HTTPException(
                status_code=400,
                detail="Unable to delete user: User has related records that prevent deletion. Please contact system administrator."
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Update user account status (Activate, Suspend, Deactivate)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # CRITICAL: Super User cannot be modified
    user_role_lower = user.role.lower() if user.role else ""
    if user_role_lower == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super User status cannot be modified"
        )
    
    new_status = status_data.status.upper()
    valid_statuses = ["ACTIVE", "INACTIVE", "SUSPENDED", "DEACTIVATED"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    old_value = user.account_status
    user.account_status = new_status
    
    # Sync is_active for backward compatibility
    user.is_active = (new_status == "ACTIVE")
    
    # If deactivated/suspended, clear session tracking
    if new_status != "ACTIVE":
        user.last_active_at = None
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Audit Log
    AuditService.log_action(
        db=db,
        action="USER_STATUS_CHANGE",
        performer=admin,
        target_id=str(user.id),
        target_type="USER",
        old_value=old_value,
        new_value=new_status,
        details={"reason": status_data.reason},
        ip_address=request.client.host if request else None
    )
    
    # Notify user via Telegram (Fail Silent)
    if user.telegram_chat_id:
        try:
            from app.services.telegram_notification_service import TelegramNotificationService
            ns = TelegramNotificationService()
            status_emoji = "✅" if new_status == "ACTIVE" else "⛔"
            msg = f"{status_emoji} <b>Account Status Update</b>\n\nYour account status is now: <b>{new_status}</b>."
            if status_data.reason:
                msg += f"\nReason: {status_data.reason}"
            await ns.send_info_notification(user, msg)
        except Exception as e:
            print(f"[ADMIN] Failed to send Telegram notification: {e}")

    return user

@router.patch("/users/{user_id}/change-password", response_model=UserResponse)
async def change_user_password(
    user_id: int,
    password_data: ChangePasswordRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Change a user's password (admin/super_admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not password_data.password or len(password_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
    
    user.hashed_password = get_password_hash(password_data.password)
    user.updated_at = datetime.utcnow()
    print(f"[ADMIN] Password changed for user {user.username} (ID: {user_id}) by {admin.username} (role: {admin.role})")
    db.commit()
    db.refresh(user)
    return user

@router.patch("/users/{user_id}/promote-to-super-admin", response_model=UserResponse)
async def promote_to_super_admin(
    user_id: int,
    super_admin: User = Depends(get_super_admin),
    db: Session = Depends(get_db)
):
    """Promote a user to super_admin role (only super_admins can do this)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Case-insensitive role check
    user_role_lower = user.role.lower() if user.role else ""
    if user_role_lower == "super_admin":
        raise HTTPException(status_code=400, detail="User is already a super_admin")
    
    user.role = "super_admin"  # Normalize to lowercase
    # Super admin users must always be active
    user.is_active = True
    print(f"[ADMIN] User {user.username} promoted to super_admin and activated")
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

@router.patch("/users/{user_id}/demote-from-super-admin", response_model=UserResponse)
async def demote_from_super_admin(
    user_id: int,
    super_admin: User = Depends(get_super_admin),
    db: Session = Depends(get_db)
):
    """Demote a super_admin to admin role (only super_admins can do this, cannot demote self)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    
    # Case-insensitive role check
    user_role_lower = user.role.lower() if user.role else ""
    if user_role_lower != "super_admin":
        raise HTTPException(status_code=400, detail="User is not a super_admin")
    
    user.role = "admin"
    print(f"[ADMIN] User {user.username} demoted from super_admin to admin")
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

# Access Requests
@router.get("/requests", response_model=List[AccessRequestResponse])
async def get_requests(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None
):
    """Get all access requests, optionally filtered by status"""
    query = db.query(AccessRequest)
    if status:
        query = query.filter(AccessRequest.status == status)
    requests = query.order_by(AccessRequest.created_at.desc()).all()
    return requests

@router.post("/requests", response_model=AccessRequestResponse)
async def create_request(
    request_data: AccessRequestCreate,
    db: Session = Depends(get_db)
):
    """Create a new access request (public endpoint) - does NOT create account"""
    try:
        # Validate required fields
        if not request_data.name or not request_data.name.strip():
            raise HTTPException(status_code=422, detail="Name is required")
        
        if not request_data.mobile or not request_data.mobile.strip():
            raise HTTPException(status_code=422, detail="Mobile number is required")
        
        if not request_data.reason or not request_data.reason.strip():
            raise HTTPException(status_code=422, detail="Reason for access is required")
        
        # Normalize mobile (remove whitespace)
        mobile = request_data.mobile.strip()
        
        # Check if mobile or email already exists in users table
        try:
            if request_data.email:
                existing_user = db.query(User).filter(
                    (User.email == request_data.email) | (User.mobile == mobile)
                ).first()
            else:
                existing_user = db.query(User).filter(User.mobile == mobile).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=409, 
                    detail="An account with this email or mobile number already exists"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error checking existing users: {str(e)}"
            )
        
        # Check if request already exists (same mobile, pending status)
        try:
            existing_request = db.query(AccessRequest).filter(
                AccessRequest.mobile == mobile,
                AccessRequest.status == "pending"
            ).first()
            
            if existing_request:
                raise HTTPException(
                    status_code=409,
                    detail="A pending access request with this mobile number already exists"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error checking existing requests: {str(e)}"
            )
        
        # System auto-assigns role = "user" and request_type = "ACCESS" (non-editable, non-requestable)
        # Note: requested_role and request_type are not DB columns - they're properties that always return fixed values
        try:
            request = AccessRequest(
                name=request_data.name.strip(),
                email=request_data.email.strip() if request_data.email else None,
                mobile=mobile,
                company=request_data.company.strip() if request_data.company else None,
                reason=request_data.reason.strip(),
                # requested_role and request_type are not set - they're properties that always return "user" and "ACCESS"
                status="pending"
            )
            db.add(request)
            db.commit()
            db.refresh(request)
            return request
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error creating access request: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error creating access request: {str(e)}"
        )

@router.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Approve an access request and CREATE USER ACCOUNT"""
    request = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {request.status}")
    
    # Validate required fields - email is now mandatory
    if not request.email or not str(request.email).strip():
        raise HTTPException(
            status_code=400,
            detail="Fields mandatory: Email. Access request must include email to create account."
        )
    
    # Normalize email
    email = str(request.email).strip()
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.mobile == request.mobile)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="An account with this email or mobile number already exists"
        )
    
    # Generate unique User ID based on mobile (immutable)
    try:
        user_id = generate_user_id_from_name_mobile(request.name, request.mobile, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Generate username from email (email is now required)
    username = email.split('@')[0]
    
    # Ensure username is unique
    base_username = username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}_{counter}"
        counter += 1
    
    # Generate temporary password (should be sent via email in production)
    import secrets
    temp_password = secrets.token_urlsafe(12)
    
    # CREATE USER ACCOUNT
    # System MUST auto-assign role = "user" (non-negotiable)
    # Account MUST be created as ACTIVE (is_active = true) per master prompt
    try:
        new_user = User(
            user_id=user_id,
            username=username,
            name=request.name,
            email=email,  # Use normalized email
            mobile=request.mobile,
            hashed_password=get_password_hash(temp_password),
            role="user",  # ALWAYS "user" - system enforced, non-requestable
            is_active=True,           # ACTIVE by default per master prompt
            account_status="ACTIVE"   # Explicit ACTIVE status
        )
        db.add(new_user)
        
        # Update request status
        request.status = "approved"
        request.reviewed_by = admin.id
        request.reviewed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(new_user)
        db.refresh(request)
    except IntegrityError as e:
        db.rollback()
        # Check if it's a unique constraint violation
        error_str = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        if 'unique' in error_str or 'duplicate' in error_str:
            if 'user_id' in error_str:
                # Retry with a new user_id if there was a collision
                try:
                    print(f"[DEBUG] User ID collision detected in approve_request, generating new user_id...")
                    user_id = generate_user_id_from_name_mobile(request.name, request.mobile, db)
                    print(f"[DEBUG] New user_id generated: {user_id}")
                    # Create a new User object with the new user_id
                    new_user = User(
                        user_id=user_id,
                        username=username,
                        name=request.name,
                        email=email,  # Use normalized email
                        mobile=request.mobile,
                        hashed_password=get_password_hash(temp_password),
                        role="user",
                        is_active=True,
                        account_status="ACTIVE"
                    )
                    db.add(new_user)
                    request.status = "approved"
                    request.reviewed_by = admin.id
                    request.reviewed_at = datetime.utcnow()
                    db.commit()
                    db.refresh(new_user)
                    db.refresh(request)
                except Exception as retry_error:
                    db.rollback()
                    print(f"[ERROR] Failed to retry user creation in approve_request: {str(retry_error)}")
                    raise HTTPException(status_code=400, detail=f"Failed to create user account: {str(retry_error)}")
            elif 'username' in error_str:
                raise HTTPException(status_code=400, detail="Username already exists. Please try again.")
            elif 'email' in error_str:
                raise HTTPException(status_code=400, detail="Email already exists")
            elif 'mobile' in error_str:
                raise HTTPException(status_code=400, detail="Mobile number already exists")
        raise HTTPException(status_code=500, detail=f"Failed to create user account: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Unexpected error in approve_request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user account: {str(e)}")
    
    # Audit Log
    AuditService.log_action(
        db=db,
        action="REQUEST_APPROVED",
        performer=admin,
        target_id=str(request.id),
        target_type="REQUEST",
        details={"user_created_id": str(new_user.id)}
    )
    
    return {
        "message": "Request approved and account created (Status: ACTIVE, Role: user)",
        "request": {
            "id": request.id,
            "status": request.status,
            "reviewed_by": request.reviewed_by,
            "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None
        },
        "user": {
            "id": new_user.id,
            "user_id": new_user.user_id,
            "username": new_user.username,
            "name": new_user.name,
            "email": new_user.email,
            "mobile": new_user.mobile,
            "role": new_user.role,  # Always "user"
            "is_active": new_user.is_active,  # Always True
            "account_status": new_user.account_status,  # Always "ACTIVE"
            "temp_password": temp_password
        }
    }

@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Reject an access request"""
    request = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {request.status}")
    
    request.status = "rejected"
    request.reviewed_by = admin.id
    request.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    
    return {"message": "Request rejected", "request": request}

# Feedback
@router.get("/feedback", response_model=List[FeedbackResponse])
async def get_feedback(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[str] = None
):
    """Get all feedback, optionally filtered by search term and status"""
    query = db.query(Feedback).join(User)
    if search:
        query = query.filter(
            or_(
                Feedback.subject.ilike(f"%{search}%"),
                Feedback.message.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    if status:
        query = query.filter(Feedback.status == status)
    feedback_list = query.order_by(Feedback.created_at.desc()).all()
    
    # Convert to response format with user_name
    result = []
    for fb in feedback_list:
        result.append(FeedbackResponse(
            id=fb.id,
            user_id=fb.user_id,
            user_name=fb.user.username if fb.user else "Unknown",
            subject=fb.subject,
            message=fb.message,
            status=fb.status,
            created_at=fb.created_at
        ))
    return result

@router.patch("/feedback/{feedback_id}")
async def update_feedback_status(
    feedback_id: int,
    status: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update feedback status"""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    if status not in ["open", "in_progress", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    feedback.status = status
    feedback.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(feedback)
    
    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_name=feedback.user.username if feedback.user else "Unknown",
        subject=feedback.subject,
        message=feedback.message,
        status=feedback.status,
        created_at=feedback.created_at
    )

# Feature Requests
@router.get("/feature-requests", response_model=List[FeatureRequestResponse])
async def get_feature_requests(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """Get all feature requests, optionally filtered by status and search"""
    query = db.query(FeatureRequest).join(User, FeatureRequest.user_id == User.id)
    
    if status:
        query = query.filter(FeatureRequest.status == status)
    
    if search:
        query = query.filter(
            or_(
                FeatureRequest.description.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    requests = query.order_by(FeatureRequest.created_at.desc()).all()
    
    return [
        FeatureRequestResponse(
            id=req.id,
            user_id=req.user_id,
            user_name=req.user.username if req.user else "Unknown",
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

@router.get("/feature-requests/{request_id}", response_model=FeatureRequestResponse)
async def get_feature_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get a specific feature request"""
    request = db.query(FeatureRequest).filter(FeatureRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Feature request not found")
    
    return FeatureRequestResponse(
        id=request.id,
        user_id=request.user_id,
        user_name=request.user.username if request.user else "Unknown",
        description=request.description,
        context=request.context,
        status=request.status,
        ai_analysis=request.ai_analysis,
        admin_note=request.admin_note,
        reviewed_by=request.reviewed_by,
        reviewed_at=request.reviewed_at,
        created_at=request.created_at,
        updated_at=request.updated_at
    )

@router.put("/feature-requests/{request_id}", response_model=FeatureRequestResponse)
async def update_feature_request(
    request_id: int,
    update_data: FeatureRequestUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update feature request status and admin note"""
    request = db.query(FeatureRequest).filter(FeatureRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Feature request not found")
    
    if update_data.status:
        valid_statuses = ["pending", "in_review", "approved", "rejected", "implemented"]
        if update_data.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        request.status = update_data.status
        
        # Set reviewed_by and reviewed_at when status changes
        if update_data.status in ["approved", "rejected", "implemented"]:
            request.reviewed_by = admin.id
            request.reviewed_at = datetime.utcnow()
    
    if update_data.admin_note is not None:
        request.admin_note = update_data.admin_note
    
    request.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    
    return FeatureRequestResponse(
        id=request.id,
        user_id=request.user_id,
        user_name=request.user.username if request.user else "Unknown",
        description=request.description,
        context=request.context,
        status=request.status,
        ai_analysis=request.ai_analysis,
        admin_note=request.admin_note,
        reviewed_by=request.reviewed_by,
        reviewed_at=request.reviewed_at,
        created_at=request.created_at,
        updated_at=request.updated_at
    )

# Connections - moved to connections.py

# Reference Data - symbols endpoint removed

@router.get("/reference-data/indicators")
async def get_indicators(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # TODO: Implement Indicator model or DuckDB query
    return []

# AI Enrichment Configuration Endpoints
@router.get("/ai-enrichment-config")
async def get_ai_enrichment_configs(
    admin: User = Depends(get_admin_user)
):
    """Get all AI enrichment configurations."""
    try:
        from app.services.ai_enrichment_config_manager import get_all_enrichment_configs, get_active_enrichment_config
        
        configs = get_all_enrichment_configs()
        active_config = get_active_enrichment_config()
        
        return {
            "configs": configs,
            "active_config": active_config
        }
    except Exception as e:
        logger.error(f"Error fetching AI enrichment configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch AI enrichment configs: {str(e)}")

@router.post("/ai-enrichment-config")
async def create_ai_enrichment_config(
    data: dict,
    admin: User = Depends(get_admin_user)
):
    """Create a new AI enrichment configuration."""
    try:
        from app.services.ai_enrichment_config_manager import create_enrichment_config
        
        # Validate required fields
        if not data.get('connection_id'):
            raise HTTPException(status_code=400, detail="connection_id is required")
        if not data.get('model_name'):
            raise HTTPException(status_code=400, detail="model_name is required")
        if not data.get('prompt_text'):
            raise HTTPException(status_code=400, detail="prompt_text is required")
        
        config = create_enrichment_config(data)
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating AI enrichment config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create AI enrichment config: {str(e)}")

@router.put("/ai-enrichment-config/{config_id}")
async def update_ai_enrichment_config(
    config_id: int,
    data: dict,
    admin: User = Depends(get_admin_user)
):
    """Update an existing AI enrichment configuration."""
    try:
        from app.services.ai_enrichment_config_manager import update_enrichment_config, get_enrichment_config
        
        # Check if config exists
        existing = get_enrichment_config(config_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Config {config_id} not found")
        
        config = update_enrichment_config(config_id, data)
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating AI enrichment config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update AI enrichment config: {str(e)}")

