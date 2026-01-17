from typing import List, Optional
from pydantic import BaseModel

class ChannelDiscoveryResponse(BaseModel):
    id: int # Telegram ID
    db_id: Optional[int] = None # Database ID (if registered)
    title: str
    username: Optional[str]
    type: str
    participants_count: Optional[int]
    status: str

class ChannelRegisterRequest(BaseModel):
    channels: List[ChannelDiscoveryResponse]

class ChannelResponse(BaseModel):
    id: int
    connection_id: int
    channel_id: int
    title: str
    username: Optional[str]
    type: str
    member_count: Optional[int]
    is_enabled: bool
    status: str
    today_count: Optional[int] = 0  # New field for stats
    
    class Config:
        from_attributes = True

class ToggleChannelRequest(BaseModel):
    is_enabled: bool
