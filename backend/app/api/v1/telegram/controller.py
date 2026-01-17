from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.core.database import get_db, get_connection_manager
from app.core.config import settings
from app.core.auth.permissions import get_current_user
from app.models.user import User
from app.services.telegram_service import TelegramService
from app.providers.telegram_bot import TelegramBotService
from app.schemas.telegram_channel import (
    ChannelDiscoveryResponse,
    ChannelRegisterRequest,
    ChannelResponse,
    ToggleChannelRequest
)

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Webhook ---

@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Telegram webhook entry point
    """
    try:
        data = await request.json()
    except Exception:
        logger.error("Invalid JSON received from Telegram")
        return {"status": "ok"}

    try:
        manager = get_connection_manager(settings.DATA_DIR)
        service = TelegramBotService(manager)
        await service.process_webhook_update(data, db)
    except Exception as e:
        logger.exception(f"Telegram webhook processing failed: {e}")

    # ALWAYS return 200 to Telegram
    return {"status": "ok"}

# --- Connection Management ---

@router.post("/connect-token")
async def generate_telegram_connect_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a short-lived token for connecting Telegram.
    Returns the deep link URL: https://t.me/<bot_username>?start=<token>
    """
    service = TelegramService(db)
    try:
        return await service.generate_connect_token(current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/disconnect")
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect Telegram account from user profile
    """
    if not current_user.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram is not connected"
        )
    
    service = TelegramService(db)
    service.disconnect_user(current_user)
    
    return {"message": "Telegram disconnected successfully"}

# --- Channel Management ---

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
        return channels
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}")
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
    List registered channels for a connection, with stats.
    """
    service = TelegramService(db)
    # Service now returns dicts with stats merged
    return service.get_registered_channels_with_stats(connection_id)

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
        
    # Re-fetch stats roughly or return 0 to fit model
    # For now returning 0 for stats on toggle, user will refresh list
    status_str = "ACTIVE" if channel.is_enabled else "IDLE"
    
    return ChannelResponse(
        id=channel.id,
        connection_id=channel.connection_id,
        channel_id=channel.channel_id,
        title=channel.title,
        username=channel.username,
        type=channel.type,
        member_count=channel.member_count,
        is_enabled=channel.is_enabled,
        status=status_str,
        today_count=0 
    )

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
