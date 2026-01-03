from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False, index=True)  # e.g., "USER_APPROVAL", "STATUS_CHANGE"
    performer_id = Column(Integer, ForeignKey("users.id"), nullable=True) # User who performed the action
    target_id = Column(String, nullable=True) # ID of the object being acted upon (e.g., User ID, Request ID)
    target_type = Column(String, nullable=True) # "USER", "REQUEST", "SYSTEM"
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(Text, nullable=True) # JSON or text description
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    performer = relationship("User", foreign_keys=[performer_id])
