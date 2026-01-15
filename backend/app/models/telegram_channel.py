from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ChannelStatus(str, enum.Enum):
    IDLE = "IDLE"
    DISCOVERED = "DISCOVERED"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"

class TelegramChannel(Base):
    __tablename__ = "telegram_channels"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("connections.id"), nullable=False)
    
    # Telegram specific fields
    channel_id = Column(BigInteger, nullable=False)  # The Telegram ID
    title = Column(String, nullable=False)
    username = Column(String, nullable=True)
    type = Column(String, nullable=False) # 'channel' or 'supergroup'
    member_count = Column(Integer, nullable=True)
    
    # Management fields
    is_enabled = Column(Boolean, default=True)
    status = Column(String, default=ChannelStatus.IDLE)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    connection = relationship("Connection", backref="channels")
