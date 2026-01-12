from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class TelegramMessage(Base):
    __tablename__ = "telegram_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_id = Column(String, nullable=False)  # Telegram Chat ID
    message_text = Column(Text, nullable=False)
    from_user = Column(Boolean, nullable=False, default=True)  # True if from user, False if from admin
    admin_username = Column(String, nullable=True)  # Who sent if from admin
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    
    # Relationship
    user = relationship("User", backref="telegram_messages")
