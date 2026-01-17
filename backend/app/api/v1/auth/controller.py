from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth.permissions import get_current_user_from_token
from app.schemas.auth import LoginRequest, TokenResponse, ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return await service.login(login_data)

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        user = get_current_user_from_token(credentials.credentials, db)
        service = AuthService(db)
        service.logout(user)
    except:
        pass
    
    return {"message": "Logged out successfully"}

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return await service.forgot_password(request)

@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using OTP received via Telegram"""
    service = AuthService(db)
    return await service.reset_password(request)

@router.post("/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(credentials.credentials, db)
    service = AuthService(db)
    return service.refresh_token(user)
