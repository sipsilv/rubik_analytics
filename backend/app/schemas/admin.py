from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class AccessRequestCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None  # Optional email
    mobile: str  # Required mobile
    company: Optional[str] = None
    reason: str
    # requested_role removed - system auto-assigns "user" only

class AccessRequestResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    mobile: str
    company: Optional[str] = None
    reason: str
    requested_role: str = "user"  # Always "user" - provided by model property, not DB column
    request_type: str = "ACCESS"  # Always "ACCESS" - provided by model property, not DB column
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    subject: str
    message: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Feature Request Schemas
class FeatureRequestContext(BaseModel):
    page: Optional[str] = None
    module: Optional[str] = None
    issue_type: Optional[str] = None

class FeatureRequestCreate(BaseModel):
    description: str
    context: Optional[FeatureRequestContext] = None

class AIAnalysis(BaseModel):
    summary: str
    category: str  # UI, Backend, Performance, Analytics, Security
    complexity: str  # Low, Medium, High
    impacted_modules: list[str]
    suggested_steps: list[str]

class FeatureRequestResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    description: str
    context: Optional[dict] = None
    status: str
    ai_analysis: Optional[AIAnalysis] = None
    admin_note: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FeatureRequestUpdate(BaseModel):
    status: Optional[str] = None  # in_review, approved, rejected, implemented
    admin_note: Optional[str] = None
