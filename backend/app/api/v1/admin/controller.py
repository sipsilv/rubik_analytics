from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.auth.permissions import get_admin_user, get_super_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.admin import (
    AccessRequestCreate, AccessRequestResponse, FeedbackResponse,
    FeatureRequestResponse, FeatureRequestUpdate
)
from datetime import datetime, timezone
from app.services.admin_service import AdminService, AdminMessage, ChangePasswordRequest, UserStatusUpdate

router = APIRouter()

def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)

# --- User Management ---

@router.post("/users/{user_id}/message")
async def send_user_message(
    user_id: int,
    message_data: AdminMessage,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Send a custom Telegram message to a user"""
    return await service.send_user_message(user_id, message_data, admin)

@router.get("/users/{user_id}/messages")
async def get_user_messages(
    user_id: int,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get message history for a user"""
    return service.get_user_messages(user_id, limit)

@router.get("/users", response_model=List[UserResponse])
async def get_users(
    search: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get all users, optionally filtered by search term"""
    return await service.get_users(search)

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    return service.get_user_by_id(user_id)

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    return await service.create_user(user_data, admin)

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    return await service.update_user(user_id, user_data, admin)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_super_admin),
    service: AdminService = Depends(get_admin_service)
):
    """Delete a user and handle related records"""
    return service.delete_user(user_id, admin)

@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    request: Request,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Update user account status (Activate, Suspend, Deactivate)"""
    ip_address = request.client.host if request else None
    return await service.update_user_status(user_id, status_data, admin, ip_address)

@router.patch("/users/{user_id}/change-password", response_model=UserResponse)
async def change_user_password(
    user_id: int,
    password_data: ChangePasswordRequest,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Change a user's password (admin/super_admin only)"""
    return service.change_user_password(user_id, password_data, admin)

@router.patch("/users/{user_id}/promote-to-super-admin", response_model=UserResponse)
async def promote_to_super_admin(
    user_id: int,
    super_admin: User = Depends(get_super_admin),
    service: AdminService = Depends(get_admin_service)
):
    """Promote a user to super_admin role (only super_admins can do this)"""
    return service.promote_to_super_admin(user_id, super_admin)

@router.patch("/users/{user_id}/demote-from-super-admin", response_model=UserResponse)
async def demote_from_super_admin(
    user_id: int,
    super_admin: User = Depends(get_super_admin),
    service: AdminService = Depends(get_admin_service)
):
    """Demote a super_admin to admin role (only super_admins can do this, cannot demote self)"""
    return service.demote_from_super_admin(user_id, super_admin)

# --- Access Requests ---

@router.get("/requests", response_model=List[AccessRequestResponse])
async def get_requests(
    status: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get all access requests, optionally filtered by status"""
    return service.get_access_requests(status)

@router.post("/requests", response_model=AccessRequestResponse)
async def create_request(
    request_data: AccessRequestCreate,
    service: AdminService = Depends(get_admin_service)
):
    """Create a new access request (public endpoint) - does NOT create account"""
    # Convert Pydantic model to dict for service
    return service.create_access_request(request_data.dict())

@router.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Approve an access request and CREATE USER ACCOUNT"""
    return await service.approve_access_request(request_id, admin)

@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Reject an access request"""
    return service.reject_access_request(request_id, admin)

# --- Feedback ---

@router.get("/feedback", response_model=List[FeedbackResponse])
async def get_feedback(
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get all feedback, optionally filtered by search term and status"""
    return service.get_feedback(search, status)

@router.patch("/feedback/{feedback_id}")
async def update_feedback_status(
    feedback_id: int,
    status: str,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Update feedback status"""
    return service.update_feedback_status(feedback_id, status, admin)

# --- Feature Requests ---

@router.get("/feature-requests", response_model=List[FeatureRequestResponse])
async def get_feature_requests(
    status: Optional[str] = None,
    search: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get all feature requests, optionally filtered by status and search"""
    return service.get_feature_requests(status, search)

@router.get("/feature-requests/{request_id}", response_model=FeatureRequestResponse)
async def get_feature_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Get a specific feature request"""
    return service.get_feature_request_by_id(request_id)

@router.put("/feature-requests/{request_id}", response_model=FeatureRequestResponse)
async def update_feature_request(
    request_id: int,
    update_data: FeatureRequestUpdate,
    admin: User = Depends(get_admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Update feature request status and admin note"""
    return service.update_feature_request(request_id, update_data.dict(exclude_unset=True), admin)

# --- Reference Data ---

@router.get("/reference-data/indicators")
async def get_indicators(
    admin: User = Depends(get_admin_user)
):
    # TODO: Implement Indicator model or DuckDB query
    return []

# --- AI Enrichment Configuration ---
# Keeping these as they are already using a service

from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

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
