from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.core.permissions import get_current_user
from app.models.user import User
from app.services.telegram_bot_service import TelegramBotService

from app.models.connection import Connection, ConnectionType
from app.core.security import decrypt_data
import json

router = APIRouter()

def get_bot_username(db: Session) -> str:
    """Helper to get bot username from connection settings"""
    conn = (
        db.query(Connection)
        .filter(
            Connection.connection_type == ConnectionType.TELEGRAM_BOT,
            Connection.is_enabled == True
        )
        .first()
    )
    
    if not conn or not conn.credentials:
        return None

    try:
        decrypted = decrypt_data(conn.credentials)
        if decrypted.strip().startswith("{"):
            creds = json.loads(decrypted)
            # TrueData connection format or standard JSON format
            return creds.get("bot_username")
        return None
    except:
        return None

@router.post("/connect-token")
async def generate_telegram_connect_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a short-lived token for connecting Telegram.
    Returns the deep link URL: https://t.me/<bot_username>?start=<token>
    """
    service = TelegramBotService(None) # Manager not needed for token gen
    token = service.generate_connect_token(current_user.id)
    
    # Get Bot Username
    # 1. Try to get from Settings (if stored in JSON)
    bot_username = get_bot_username(db)
    
    # 2. Fallback: Fetch from Telegram API using the token
    if not bot_username:
        bot_username = await service.get_bot_username()

    if not bot_username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Telegram Bot Connection not configured or unable to fetch bot info."
        )

    return {
        "token": token,
        "bot_username": bot_username,
        "deep_link": f"https://t.me/{bot_username}?start={token}"
    }

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
    
    current_user.telegram_chat_id = None
    db.commit()
    
    return {"message": "Telegram disconnected successfully"}
