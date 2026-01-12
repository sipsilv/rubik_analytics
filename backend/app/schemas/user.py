from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None  # Optional email
    mobile: Optional[str] = None  # Optional mobile for legacy/display
    
    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        # Convert empty string to None for optional email field
        if v == "" or v is None:
            return None
        return v

class UserCreate(BaseModel):
    username: str
    name: Optional[str] = None
    email: EmailStr  # Required email for account creation
    mobile: str  # Required mobile for account creation
    password: str
    role: str = "user"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    theme_preference: Optional[str] = None  # dark, light
    role: Optional[str] = None  # user, admin (super_admin cannot be set via this endpoint)
    otp: Optional[str] = None  # For verifying sensitive changes
    two_factor_enabled: Optional[bool] = None  # Enable/Disable 2FA

    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        # Convert empty string to None for optional email field
        if v == "" or v is None:
            return None
        return v
    
    @field_validator('role', mode='before')
    @classmethod
    def validate_role(cls, v):
        if v is None or v == "":
            return None
        v_lower = v.lower().strip()
        if v_lower not in ["user", "admin"]:
            raise ValueError("Role must be 'user' or 'admin'. Use promote/demote endpoints for super_admin changes.")
        return v_lower

class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class UserResponse(UserBase):
    id: int
    user_id: str  # Unique immutable user ID
    role: str
    is_active: bool
    account_status: str = "ACTIVE"
    theme_preference: str = "dark"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_active_at: Optional[datetime] = None  # For live status
    is_online: Optional[bool] = None  # Real-time online status from WebSocket
    telegram_chat_id: Optional[str] = None  # Telegram Chat ID for notifications
    two_factor_enabled: bool = False  # 2FA status
    
    class Config:
        from_attributes = True
