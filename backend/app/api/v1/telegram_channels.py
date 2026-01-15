from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.services.telegram_service import TelegramService
from pydantic import BaseModel
import duckdb
import os
from datetime import datetime, timezone
import logging

# Import config from the listener module
# Ensure path is correct relative to where app is running
from app.services.telegram_raw_listener.config import DB_PATH, TABLE_NAME

router = APIRouter()
logger = logging.getLogger(__name__)

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
    today_count: Optional[int] = 0  # New field for stats
    
    class Config:
        from_attributes = True

class ToggleChannelRequest(BaseModel):
    is_enabled: bool

# --- Helpers ---
def get_today_counts(channel_ids: List[int]) -> dict:
    """
    Queries DuckDB for message counts for the given channel IDs for the current day (UTC).
    Returns dict: { channel_id_int: count }
    """
    if not os.path.exists(DB_PATH):
        return {}

    counts = {}
    conn = None
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        # Check if table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        table_exists = any(t[0] == TABLE_NAME for t in tables)
        
        if not table_exists:
            return {}

        # Query
        # Assuming telegram_chat_id depends on how it was stored. 
        # Listener stores it as str(chat.id). 
        # NB: Telethon IDs for channels are usually -100... or just positive int depending on context.
        # But `TelegramChannel.channel_id` is BigInt (the raw ID).
        # We need to match string representation.
        
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # We fetch counts grouped by telegram_chat_id
        query = f"""
            SELECT telegram_chat_id, COUNT(*) 
            FROM {TABLE_NAME} 
            WHERE received_at >= ?
            GROUP BY telegram_chat_id
        """
        results = conn.execute(query, [today_start]).fetchall()
        
        for row in results:
            chat_id_str = row[0]
            count = row[1]
            try:
                # Listener stores chat_id. Telethon chat_id might be different?
                # Usually we just match them. 
                # If listener stored "-10012345", and DB has 12345 or -10012345?
                # We try to strict match first.
                c_id = int(chat_id_str)
                counts[c_id] = count
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error fetching stats from DuckDB: {e}")
    finally:
        if conn:
            conn.close()
            
    return counts

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
    List registered channels for a connection, with stats.
    """
    service = TelegramService(db)
    channels = service.get_registered_channels(connection_id)
    
    # 1. Collect IDs
    channel_ids = [c.channel_id for c in channels]
    
    # 2. Fetch Stats from DuckDB
    stats = get_today_counts(channel_ids)
    
    # 3. Merge and formatting
    response = []
    for c in channels:
        # Determine Status
        status_str = "IDLE"
        if c.is_enabled:
            status_str = "ACTIVE"
        
        # Get count (direct ID match, or maybe telethon handling?)
        # For now direct match.
        count = stats.get(c.channel_id, 0)
        
        # Create response object
        # We manually construct to inject 'today_count' and override 'status'
        c_resp = ChannelResponse(
            id=c.id,
            connection_id=c.connection_id,
            channel_id=c.channel_id,
            title=c.title,
            username=c.username,
            type=c.type,
            member_count=c.member_count,
            is_enabled=c.is_enabled,
            status=status_str,
            today_count=count
        )
        response.append(c_resp)
        
    return response

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
        
    # Re-wrap to include stats/status logic (basic here)
    status_str = "ACTIVE" if channel.is_enabled else "IDLE"
    
    # Fetch stats just for this one? Or return 0. 
    # Frontend will probably refresh list or use return value.
    # Let's try to fetch stats quickly
    count = 0 
    try:
        s = get_today_counts([channel.channel_id])
        count = s.get(channel.channel_id, 0)
    except:
        pass

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
        today_count=count
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
