from pydantic import BaseModel, root_validator
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.connection import ConnectionType, ConnectionStatus, ConnectionHealth, ConnectionEnvironment

class ConnectionBase(BaseModel):
    name: str
    connection_type: ConnectionType
    provider: str
    description: Optional[str] = None
    environment: ConnectionEnvironment = ConnectionEnvironment.PROD
    is_enabled: bool = False
    details: Optional[Dict[str, Any]] = None  # Flexible dictionary for form fields

    class Config:
        use_enum_values = True

class ConnectionCreate(ConnectionBase):
    pass

class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment: Optional[ConnectionEnvironment] = None
    is_enabled: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None  # To update credentials/config

class ConnectionResponse(BaseModel):
    id: int
    name: str
    connection_type: str
    provider: str
    description: Optional[str]
    environment: str
    status: str
    health: str
    is_enabled: bool
    last_checked_at: Optional[datetime]
    last_success_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # We DO NOT return full details/credentials here for security
    # We will return public configs only if needed, or masked
    
    class Config:
        from_attributes = True
