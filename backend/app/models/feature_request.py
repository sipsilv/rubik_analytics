from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class FeatureRequest(Base):
    __tablename__ = "feature_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)  # Optional context: page, module, issue_type
    status = Column(String, default="pending", nullable=False)  # pending, in_review, approved, rejected, implemented
    
    # AI-generated analysis
    ai_analysis = Column(JSON, nullable=True)  # Stores: summary, category, complexity, modules, steps
    
    # Admin fields
    admin_note = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="feature_requests")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
