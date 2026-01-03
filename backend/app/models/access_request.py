from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base

class AccessRequest(Base):
    __tablename__ = "access_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)  # Optional email
    mobile = Column(String, nullable=False, index=True)  # Required mobile
    company = Column(String, nullable=True)
    reason = Column(Text, nullable=False)
    # requested_role and request_type are NOT database columns - the actual table doesn't have them
    # Use @property below to provide them as read-only attributes
    status = Column(String, default="pending", nullable=False)  # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    reviewed_by = Column(Integer, nullable=True)  # User ID who reviewed
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    @property
    def requested_role(self):
        """Always returns 'user' - system enforced, not stored in DB"""
        return "user"
    
    @property
    def request_type(self):
        """Always returns 'ACCESS' - system enforced, not stored in DB"""
        return "ACCESS"
