"""
WebSocket endpoints for real-time communication
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.websocket_manager import manager
from app.core.database import get_db
from app.core.permissions import get_current_user_from_token
from app.models.user import User

router = APIRouter()


async def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Get user from WebSocket token"""
    try:
        user = get_current_user_from_token(token, db)
        return user
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time user status updates
    
    Query parameters:
    - token: JWT authentication token
    """
    user = None
    
    # Try to get token from query parameter
    if not token:
        # Try to get from query string
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
    
    # Authenticate user
    user_id = None
    if token:
        from app.core.database import get_db_router
        from app.core.config import settings
        
        router = get_db_router(settings.DATA_DIR)
        auth_db = router.get_auth_db()
        
        if auth_db:
            db = auth_db.get_session()
            try:
                user = await get_user_from_token(token, db)
                # Extract user_id before closing the session to avoid DetachedInstanceError
                if user:
                    user_id = user.id
            except Exception as e:
                print(f"[WebSocket] Authentication error: {e}")
            finally:
                if db:
                    db.close()
    
    if not user_id:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    # Connect user
    await manager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "message": "WebSocket connection established"
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for messages (with timeout to allow periodic checks)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    if message_type == "ping":
                        # Respond to ping with pong
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    elif message_type == "status_request":
                        # Send current user status
                        await websocket.send_json({
                            "type": "status",
                            "user_id": user_id,
                            "is_online": True,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                except json.JSONDecodeError:
                    # Ignore invalid JSON
                    pass
                    
            except asyncio.TimeoutError:
                # Send periodic ping to keep connection alive
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    # Connection might be closed
                    break
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        print(f"[WebSocket] Error in connection: {e}")
    finally:
        manager.disconnect(websocket)

