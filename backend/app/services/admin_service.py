from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import random
import re
import uuid
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User
from app.models.access_request import AccessRequest
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest
from app.models.telegram_message import TelegramMessage
from app.repositories.user_repository import UserRepository
from app.repositories.access_request_repository import AccessRequestRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.feature_request_repository import FeatureRequestRepository
from app.schemas.user import UserCreate, UserUpdate, UserStatusUpdate
from app.schemas.admin import AccessRequestResponse, AdminMessage, ChangePasswordRequest
from app.core.auth.security import get_password_hash
from app.core.websocket.manager import manager
from app.core.logging.audit import AuditService
from app.services.telegram_notification_service import TelegramNotificationService

class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository()
        self.access_request_repo = AccessRequestRepository()
        self.feedback_repo = FeedbackRepository()
        self.feature_request_repo = FeatureRequestRepository()

    # --- User Management ---

    def _generate_user_id(self, mobile: str) -> str:
        """
        Generate a unique user_id based on random 4-digit ID and partial mobile number.
        """
        if not mobile:
            raise ValueError("Mobile number is required to generate user_id")
        
        mobile_normalized = re.sub(r'[^\d]', '', mobile or '')
        if not mobile_normalized:
            raise ValueError("Mobile number must contain at least one digit")
        
        if len(mobile_normalized) >= 6:
            mobile_part = mobile_normalized[-6:]
        elif len(mobile_normalized) >= 4:
            mobile_part = mobile_normalized[-4:]
        else:
            mobile_part = mobile_normalized.zfill(4)
        
        random_id = random.randint(1000, 9999)
        user_id = f"{random_id}{mobile_part}"
        
        counter = 0
        max_attempts = 9000
        initial_random_id = random_id
        tried_ids = set()
        
        while True:
            existing = self.db.query(User).filter(User.user_id == user_id).first()
            if not existing and user_id not in tried_ids:
                tried_ids.add(user_id)
                break
            
            random_id += 1
            if random_id > 9999:
                random_id = 1000
            
            if counter > 0 and random_id == initial_random_id:
                uuid_part = str(uuid.uuid4())[:8].replace('-', '')
                user_id = f"{uuid_part}{mobile_part}"
                if not self.db.query(User).filter(User.user_id == user_id).first():
                    break
                counter += 1
                if counter > max_attempts:
                     user_id = f"{str(uuid.uuid4()).replace('-', '')}{mobile_part}"
                     break
                continue
            
            user_id = f"{random_id}{mobile_part}"
            counter += 1
            
            if counter > max_attempts:
                uuid_part = str(uuid.uuid4())[:8].replace('-', '')
                user_id = f"{uuid_part}{mobile_part}"
                if not self.db.query(User).filter(User.user_id == user_id).first():
                    break
                user_id = f"{str(uuid.uuid4()).replace('-', '')}{mobile_part}"
                break
        
        if len(user_id) > 255:
             max_mobile_len = 255 - len(str(random_id))
             if max_mobile_len > 0:
                 mobile_part = mobile_part[:max_mobile_len]
                 user_id = f"{random_id}{mobile_part}"
             else:
                 user_id = str(uuid.uuid4()).replace('-', '')[:50]
        
        return user_id

    async def get_users(self, search: Optional[str] = None) -> List[dict]:
        query = self.db.query(User)
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
        
        now = datetime.now(timezone.utc)
        online_threshold = timedelta(minutes=5)
        
        result = []
        for user in users:
            has_websocket = manager.is_user_online(user.id)
            has_recent_activity = False
            if user.last_active_at:
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
            result.append(user_dict)
        return result

    def get_user_by_id(self, user_id: int) -> dict:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        now = datetime.now(timezone.utc)
        online_threshold = timedelta(minutes=5)
        
        has_websocket = manager.is_user_online(user.id)
        has_recent_activity = False
        if user.last_active_at:
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
        return user_dict

    async def create_user(self, user_data: UserCreate, admin: User) -> User:
        username = str(user_data.username).strip() if user_data.username else ""
        mobile = str(user_data.mobile).strip() if user_data.mobile else ""
        email = str(user_data.email).strip() if user_data.email else ""
        
        if not username or not email or not mobile:
            raise HTTPException(status_code=400, detail="Username, Email and Mobile are mandatory")
            
        if self.user_repo.get_by_username(self.db, username):
             raise HTTPException(status_code=400, detail="Username already exists")
        if self.user_repo.get_by_email(self.db, email):
             raise HTTPException(status_code=400, detail="Email already exists")
        if self.user_repo.get_by_mobile(self.db, mobile):
             raise HTTPException(status_code=400, detail="Mobile number already exists")
             
        if not user_data.password or not str(user_data.password).strip():
            raise HTTPException(status_code=400, detail="Password is required")
            
        try:
            user_id = self._generate_user_id(mobile)
            
            name = str(user_data.name).strip() if user_data.name and str(user_data.name).strip() else None
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
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
             self.db.rollback()
             # Retry logic could be implemented here as in original code, simplifying for now
             raise HTTPException(status_code=400, detail="User creation failed due to database constraint violation")
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def update_user(self, user_id: int, user_data: UserUpdate, admin: User) -> User:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        changes_detail = []
        old_name = user.name
        old_email = user.email
        old_mobile = user.mobile
        old_role = user.role
        
        # Super admin check
        user_role_lower = user.role.lower() if user.role else ""
        if user_role_lower == "super_admin" and admin.id != user.id:
            if admin.role.lower() != "super_admin":
                raise HTTPException(status_code=403, detail="Cannot modify super_admin user")

        if user_data.name is not None:
             if old_name != user_data.name:
                 changes_detail.append(f"Name: {old_name or 'None'} → {user_data.name}")
             user.name = user_data.name
        
        if user_data.email is not None:
            if user_data.email and user_data.email != old_email:
                if self.user_repo.get_by_email(self.db, user_data.email):
                     raise HTTPException(status_code=400, detail="Email already exists")
                changes_detail.append(f"Email: {old_email or 'None'} → {user_data.email}")
            user.email = user_data.email
            
        if user_data.mobile is not None:
            if not user_data.mobile:
                 raise HTTPException(status_code=400, detail="Mobile number is required")
            if user_data.mobile != old_mobile:
                if self.user_repo.get_by_mobile(self.db, user_data.mobile):
                     raise HTTPException(status_code=400, detail="Mobile number already exists")
                changes_detail.append(f"Mobile: {old_mobile or 'None'} → {user_data.mobile}")
            user.mobile = user_data.mobile
            
        user.updated_at = datetime.utcnow()
        
        if user_data.theme_preference:
            if user_data.theme_preference not in ["dark", "light"]:
                 raise HTTPException(status_code=400, detail="Theme preference must be 'dark' or 'light'")
            user.theme_preference = user_data.theme_preference
        
        if user_data.role is not None:
            admin_role_lower = admin.role.lower() if admin.role else ""
            if admin_role_lower != "super_admin":
                raise HTTPException(status_code=403, detail="Only super_admin can change user roles")
            
            if user_role_lower == "super_admin":
                raise HTTPException(status_code=403, detail="Cannot change super_admin role")
                
            new_role_lower = user_data.role.lower().strip()
            if new_role_lower not in ["user", "admin"]:
                 raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
            
            if old_role != new_role_lower:
                changes_detail.append(f"Role: {old_role} → {new_role_lower}")
            user.role = new_role_lower
            
        self.db.commit()
        self.db.refresh(user)
        
        if user.telegram_chat_id and changes_detail:
             try:
                ns = TelegramNotificationService()
                changes_text = "\n".join([f"• {change}" for change in changes_detail])
                msg = (
                    f"📝 <b>Profile Updated by Admin</b>\n\n"
                    f"Hello <b>{user.username}</b>,\n\n"
                    f"Your profile has been updated by administrator <b>{admin.username}</b>.\n\n"
                    f"<b>Changes made:</b>\n{changes_text}\n\n"
                    f"— Open Analytics"
                )
                await ns.send_info_notification(user, msg)
             except:
                 pass
        
        return user

    def delete_user(self, user_id: int, admin: User):
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        if user.id == admin.id:
             raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        if user.role == "super_admin":
            count = self.db.query(User).filter(User.role == "super_admin").count()
            if count <= 1:
                 raise HTTPException(status_code=400, detail="Cannot delete the last super admin")
        
        try:
            # Cascade deletes/updates
            self.db.query(FeatureRequest).filter(FeatureRequest.user_id == user.id).delete()
            self.db.query(FeatureRequest).filter(FeatureRequest.reviewed_by == user.id).update({"reviewed_by": None})
            self.db.query(Feedback).filter(Feedback.user_id == user.id).delete()
            from app.models.audit_log import AuditLog
            self.db.query(AuditLog).filter(AuditLog.performer_id == user.id).update({"performer_id": None})
            self.db.query(AccessRequest).filter(AccessRequest.reviewed_by == user.id).update({"reviewed_by": None})
            
            self.db.delete(user)
            self.db.commit()
            return {"message": "User deleted successfully"}
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=400, detail="Unable to delete user due to related records")
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def update_user_status(self, user_id: int, status_data: UserStatusUpdate, admin: User, ip_address: str = None) -> User:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if user.role.lower() == "super_admin":
             raise HTTPException(status_code=403, detail="Super User status cannot be modified")
        
        new_status = status_data.status.upper()
        if new_status not in ["ACTIVE", "INACTIVE", "SUSPENDED", "DEACTIVATED"]:
             raise HTTPException(status_code=400, detail="Invalid status")
             
        old_value = user.account_status
        user.account_status = new_status
        user.is_active = (new_status == "ACTIVE")
        if new_status != "ACTIVE":
             user.last_active_at = None
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        AuditService.log_action(
            db=self.db,
            action="USER_STATUS_CHANGE",
            performer=admin,
            target_id=str(user.id),
            target_type="USER",
            old_value=old_value,
            new_value=new_status,
            details={"reason": status_data.reason},
            ip_address=ip_address
        )
        
        if user.telegram_chat_id:
             try:
                 ns = TelegramNotificationService()
                 emoji = "✅" if new_status == "ACTIVE" else "⛔"
                 msg = f"{emoji} <b>Account Status Update</b>\n\nYour account status is now: <b>{new_status}</b>."
                 if status_data.reason:
                     msg += f"\nReason: {status_data.reason}"
                 await ns.send_info_notification(user, msg)
             except:
                 pass
        
        return user

    def change_user_password(self, user_id: int, password_data: ChangePasswordRequest, admin: User) -> User:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        if len(password_data.password) < 6:
             raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        user.hashed_password = get_password_hash(password_data.password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    async def send_user_message(self, user_id: int, message_data: AdminMessage, admin: User):
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        if not user.telegram_chat_id:
             raise HTTPException(status_code=400, detail="User has not connected Telegram")
             
        try:
            ns = TelegramNotificationService()
            formatted_message = (
                f"📩 <b>Message from Admin ({admin.username})</b>\n\n"
                f"{message_data.message}\n\n"
                f"— Open Analytics Support"
            )
            await ns.bot_service.send_message(user.telegram_chat_id, formatted_message)
            
            msg = TelegramMessage(
                user_id=user.id,
                chat_id=user.telegram_chat_id,
                message_text=message_data.message,
                from_user=False,
                admin_username=admin.username,
                is_read=True
            )
            self.db.add(msg)
            self.db.commit()
            return {"message": "Message sent successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

    def get_user_messages(self, user_id: int, limit: int = 50) -> dict:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        messages = (
            self.db.query(TelegramMessage)
            .filter(TelegramMessage.user_id == user_id)
            .order_by(TelegramMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        
        unread_count = (
            self.db.query(TelegramMessage)
            .filter(
                TelegramMessage.user_id == user_id,
                TelegramMessage.is_read == False,
                TelegramMessage.from_user == True
            )
            .update({"is_read": True})
        )
        self.db.commit()
        
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
                for msg in reversed(messages)
            ],
            "unread_count": unread_count
        }

    # --- Super Admin Management ---

    def promote_to_super_admin(self, user_id: int, super_admin: User) -> User:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        user_role_lower = user.role.lower() if user.role else ""
        if user_role_lower == "super_admin":
             raise HTTPException(status_code=400, detail="User is already a super_admin")
             
        user.role = "super_admin"
        user.is_active = True
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def demote_from_super_admin(self, user_id: int, super_admin: User) -> User:
        user = self.user_repo.get_by_id(self.db, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        if user.id == super_admin.id:
             raise HTTPException(status_code=400, detail="Cannot demote yourself")
             
        user_role_lower = user.role.lower() if user.role else ""
        if user_role_lower != "super_admin":
             raise HTTPException(status_code=400, detail="User is not a super_admin")
             
        user.role = "admin"
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    # --- Access Requests ---

    def get_access_requests(self, status: Optional[str] = None) -> List[AccessRequest]:
        query = self.db.query(AccessRequest)
        if status:
            query = query.filter(AccessRequest.status == status)
        return query.order_by(AccessRequest.created_at.desc()).all()

    def create_access_request(self, request_data: dict) -> AccessRequest:
        try:
             name = request_data.get("name")
             mobile = request_data.get("mobile")
             email = request_data.get("email")
             reason = request_data.get("reason")
             company = request_data.get("company")
             
             if not name or not name.strip():
                 raise HTTPException(status_code=422, detail="Name is required")
             if not mobile or not mobile.strip():
                 raise HTTPException(status_code=422, detail="Mobile number is required")
             if not reason or not reason.strip():
                 raise HTTPException(status_code=422, detail="Reason for access is required")
                 
             mobile = mobile.strip()
             email = email.strip() if email else None
             name = name.strip()
             reason = reason.strip()
             company = company.strip() if company else None
             
             # Check for existing user
             query = self.db.query(User).filter(User.mobile == mobile)
             if email:
                 query = self.db.query(User).filter(or_(User.email == email, User.mobile == mobile))
             
             if query.first():
                  raise HTTPException(status_code=409, detail="An account with this email or mobile number already exists")
             
             # Check for pending request
             existing_request = self.db.query(AccessRequest).filter(
                 AccessRequest.mobile == mobile,
                 AccessRequest.status == "pending"
             ).first()
             
             if existing_request:
                  raise HTTPException(status_code=409, detail="A pending access request with this mobile number already exists")
             
             request = AccessRequest(
                 name=name,
                 email=email,
                 mobile=mobile,
                 company=company,
                 reason=reason,
                 status="pending"
             )
             self.db.add(request)
             self.db.commit()
             self.db.refresh(request)
             return request
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def approve_access_request(self, request_id: int, admin: User) -> dict:
        request = self.access_request_repo.get_by_id(self.db, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if request.status != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {request.status}")
            
        if not request.email or not str(request.email).strip():
             raise HTTPException(status_code=400, detail="Access request must include email to create account")
             
        email = str(request.email).strip()
        
        existing_user = self.db.query(User).filter(
            or_(User.email == email, User.mobile == request.mobile)
        ).first()
        
        if existing_user:
             raise HTTPException(status_code=400, detail="An account with this email or mobile number already exists")
             
        try:
             user_id = self._generate_user_id(request.mobile)
             username = email.split('@')[0]
             base_username = username
             counter = 1
             while self.user_repo.get_by_username(self.db, username):
                 username = f"{base_username}_{counter}"
                 counter += 1
                 
             import secrets
             temp_password = secrets.token_urlsafe(12)
             
             new_user = User(
                 user_id=user_id,
                 username=username,
                 name=request.name,
                 email=email,
                 mobile=request.mobile,
                 hashed_password=get_password_hash(temp_password),
                 role="user",
                 is_active=True,
                 account_status="ACTIVE"
             )
             self.db.add(new_user)
             
             request.status = "approved"
             request.reviewed_by = admin.id
             request.reviewed_at = datetime.utcnow()
             
             self.db.commit()
             self.db.refresh(new_user)
             self.db.refresh(request)
             
             AuditService.log_action(
                db=self.db,
                action="REQUEST_APPROVED",
                performer=admin,
                target_id=str(request.id),
                target_type="REQUEST",
                details={"user_created_id": str(new_user.id)}
             )
             
             return {
                 "message": "Request approved and account created",
                 "request": request,
                 "user": new_user,
                 "temp_password": temp_password
             }
             
        except Exception as e:
             self.db.rollback()
             raise HTTPException(status_code=500, detail=f"Failed to create user account: {str(e)}")

    def reject_access_request(self, request_id: int, admin: User) -> dict:
        request = self.access_request_repo.get_by_id(self.db, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
            
        if request.status != "pending":
             raise HTTPException(status_code=400, detail=f"Request is already {request.status}")
             
        request.status = "rejected"
        request.reviewed_by = admin.id
        request.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(request)
        return {"message": "Request rejected", "request": request}

    # --- Feedback ---

    def get_feedback(self, search: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
        query = self.db.query(Feedback).join(User)
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
        
        result = []
        for fb in feedback_list:
            result.append({
                "id": fb.id,
                "user_id": fb.user_id,
                "user_name": fb.user.username if fb.user else "Unknown",
                "subject": fb.subject,
                "message": fb.message,
                "status": fb.status,
                "created_at": fb.created_at
            })
        return result

    def update_feedback_status(self, feedback_id: int, status_str: str, admin: User) -> dict:
        feedback = self.feedback_repo.get_by_id(self.db, feedback_id)
        if not feedback:
             raise HTTPException(status_code=404, detail="Feedback not found")
        
        if status_str not in ["open", "in_progress", "resolved"]:
             raise HTTPException(status_code=400, detail="Invalid status")
             
        feedback.status = status_str
        feedback.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(feedback)
        
        return {
            "id": feedback.id,
            "user_id": feedback.user_id,
            "user_name": feedback.user.username if feedback.user else "Unknown",
            "subject": feedback.subject,
            "message": feedback.message,
            "status": feedback.status,
            "created_at": feedback.created_at
        }
    
    # --- Feature Requests ---

    def get_feature_requests(self, status: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
        query = self.db.query(FeatureRequest).join(User, FeatureRequest.user_id == User.id)
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
            {
                "id": req.id,
                "user_id": req.user_id,
                "user_name": req.user.username if req.user else "Unknown",
                "description": req.description,
                "context": req.context,
                "status": req.status,
                "ai_analysis": req.ai_analysis,
                "admin_note": req.admin_note,
                "reviewed_by": req.reviewed_by,
                "reviewed_at": req.reviewed_at,
                "created_at": req.created_at,
                "updated_at": req.updated_at
            }
            for req in requests
        ]

    def get_feature_request_by_id(self, request_id: int) -> dict:
        request = self.feature_request_repo.get_by_id(self.db, request_id)
        if not request:
             raise HTTPException(status_code=404, detail="Feature request not found")
        
        return {
            "id": request.id,
            "user_id": request.user_id,
            "user_name": request.user.username if request.user else "Unknown",
            "description": request.description,
            "context": request.context,
            "status": request.status,
            "ai_analysis": request.ai_analysis,
            "admin_note": request.admin_note,
            "reviewed_by": request.reviewed_by,
            "reviewed_at": request.reviewed_at,
            "created_at": request.created_at,
            "updated_at": request.updated_at
        }

    def update_feature_request(self, request_id: int, update_data: dict, admin: User) -> dict:
        request = self.feature_request_repo.get_by_id(self.db, request_id)
        if not request:
             raise HTTPException(status_code=404, detail="Feature request not found")
             
        status_val = update_data.get("status")
        if status_val:
            valid_statuses = ["pending", "in_review", "approved", "rejected", "implemented"]
            if status_val not in valid_statuses:
                 raise HTTPException(status_code=400, detail=f"Invalid status")
            request.status = status_val
            if status_val in ["approved", "rejected", "implemented"]:
                request.reviewed_by = admin.id
                request.reviewed_at = datetime.utcnow()
        
        admin_note = update_data.get("admin_note")
        if admin_note is not None:
             request.admin_note = admin_note
             
        request.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(request)
        
        return {
            "id": request.id,
            "user_id": request.user_id,
            "user_name": request.user.username if request.user else "Unknown",
            "description": request.description,
            "context": request.context,
            "status": request.status,
            "ai_analysis": request.ai_analysis,
            "admin_note": request.admin_note,
            "reviewed_by": request.reviewed_by,
            "reviewed_at": request.reviewed_at,
            "created_at": request.created_at,
            "updated_at": request.updated_at
        }
