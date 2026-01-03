from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ConnectionType(str, enum.Enum):
    MARKET_DATA = "MARKET_DATA"
    BROKER = "BROKER"
    AI_ML = "AI_ML"
    NEWS = "NEWS"
    SOCIAL = "SOCIAL"
    INTERNAL = "INTERNAL"

class ConnectionStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"

class ConnectionHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"

class ConnectionEnvironment(str, enum.Enum):
    PROD = "PROD"
    SANDBOX = "SANDBOX"

class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    connection_type = Column(String, nullable=False) # Store Enum as string for simplicity with SQLite
    provider = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Encrypted credentials (stored as a JSON string)
    credentials = Column(Text, nullable=True)
    
    environment = Column(String, default="PROD")
    status = Column(String, default="DISCONNECTED")
    health = Column(String, default="HEALTHY")
    
    is_enabled = Column(Boolean, default=False)
    
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    
    error_logs = Column(Text, nullable=True) # JSON or text logs
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
