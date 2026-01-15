from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.services.telegram_service import TelegramService
from pydantic import BaseModel

router = APIRouter()

# --- Schemas ---
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
    
    class Config:
        from_attributes = True

class ToggleChannelRequest(BaseModel):
    is_enabled: bool

# --- Endpoints ---

@router.get("/discover/{connection_id}", response_model=List[ChannelDiscoveryResponse])
async def discover_channels(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger Telegram channel discovery for a specific connection.
    """
    service = TelegramService(db)
    try:
        channels = await service.discover_channels(connection_id)
        return channels
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")

@router.get("/search/{connection_id}", response_model=List[ChannelDiscoveryResponse])
async def search_channels(
    connection_id: int,
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for public Telegram channels globally.
    """
    service = TelegramService(db)
    try:
        channels = await service.search_channels(connection_id, q)
        # print(f"DEBUG: Service returned {len(channels)} channels")
        return channels
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"ROUTER ERROR: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
@router.post("/{connection_id}/register")
async def register_channels(
    connection_id: int,
    request: ChannelRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register selected channels to the connection.
    """
    service = TelegramService(db)
    # Convert Pydantic models to dicts for the service
    channels_data = [ch.dict() for ch in request.channels]
    count = service.register_channels(connection_id, channels_data)
    return {"message": f"Successfully registered {count} channels."}

@router.get("/list/{connection_id}", response_model=List[ChannelResponse])
def list_channels(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List registered channels for a connection.
    """
    service = TelegramService(db)
    return service.get_registered_channels(connection_id)

@router.patch("/{channel_id}/toggle", response_model=ChannelResponse)
def toggle_channel(
    channel_id: int,
    request: ToggleChannelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable or disable a channel.
    """
    service = TelegramService(db)
    channel = service.toggle_channel(channel_id, request.is_enabled)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel

@router.delete("/{channel_id}")
def delete_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a registered channel.
    """
    service = TelegramService(db)
    success = service.delete_channel(channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel deleted successfully"}
