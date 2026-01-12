from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db, get_connection_manager
from app.core.config import settings
from app.services.telegram_bot_service import TelegramBotService

logger = logging.getLogger(__name__)

router = APIRouter()

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
