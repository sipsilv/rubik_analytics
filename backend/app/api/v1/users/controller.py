from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth.permissions import get_current_user
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.schemas.admin import FeedbackResponse, FeatureRequestCreate, FeatureRequestResponse
from app.services.user_service import UserService

router = APIRouter()
security = HTTPBearer()

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user(credentials, db)
    service = UserService(db)
    return service.update_last_active(user)

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = get_current_user(credentials, db)
    service = UserService(db)
    return await service.update_profile(user, user_update)

@router.post("/me/ping")
async def ping_activity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Update last active timestamp for live status tracking"""
    user = get_current_user(credentials, db)
    service = UserService(db)
    service.update_last_active(user)
    return {"status": "ok", "last_active_at": user.last_active_at}

@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Change user password"""
    user = get_current_user(credentials, db)
    service = UserService(db)
    await service.change_password(user, password_data)
    return {"message": "Password changed successfully"}

# Feedback (user endpoint)
# We can move this class to schemas/feedback.py later, but keeping usage consistent for now if it's used elsewhere
from app.schemas.feedback import FeedbackCreate

@router.post("/feedback", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Create feedback (user endpoint)"""
    user = get_current_user(credentials, db)
    service = UserService(db)
    
    feedback = service.create_feedback(user, feedback_data.subject, feedback_data.message)
    
    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_name=user.username,
        subject=feedback.subject,
        message=feedback.message,
        status=feedback.status,
        created_at=feedback.created_at
    )

@router.post("/feature-requests", response_model=FeatureRequestResponse)
async def create_feature_request(
    request_data: FeatureRequestCreate,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Create a new feature request with AI analysis"""
    user = get_current_user(credentials, db)
    service = UserService(db)
    
    feature_request = service.create_feature_request(user, request_data, background_tasks)
    
    return FeatureRequestResponse(
        id=feature_request.id,
        user_id=feature_request.user_id,
        user_name=user.username,
        description=feature_request.description,
        context=feature_request.context,
        status=feature_request.status,
        ai_analysis=feature_request.ai_analysis, 
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
    service = UserService(db)
    
    requests = service.get_user_feature_requests(user)
    
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
