"""
WebSocket Manager for real-time user status tracking
"""
from typing import Dict, Set
from datetime import datetime, timedelta
import asyncio
from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections for real-time user status updates"""
    
    def __init__(self):
        # Map of user_id -> Set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Map of WebSocket -> user_id
        self.connection_users: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Register a new WebSocket connection for a user"""
        await websocket.accept()
        
        # Check if this is the user's first connection
        is_first_connection = user_id not in self.active_connections or len(self.active_connections[user_id]) == 0
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        # Only log on first connection for this user to reduce log spam
        if is_first_connection:
            print(f"[WebSocket] User {user_id} connected (first connection). Total active users: {len(self.active_connections)}, Total connections: {len(self.connection_users)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        user_id = self.connection_users.pop(websocket, None)
        
        if user_id and user_id in self.active_connections:
            # Check if this is the user's last connection
            was_last_connection = len(self.active_connections[user_id]) == 1
            
            self.active_connections[user_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # Only log when user has no more connections (fully disconnected)
                print(f"[WebSocket] User {user_id} disconnected (all connections closed). Total active users: {len(self.active_connections)}, Total connections: {len(self.connection_users)}")
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if a user has any active WebSocket connections"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to all connections of a specific user"""
        if user_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error sending message to user {user_id}: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_user_status(self, user_id: int, is_online: bool, last_active_at: datetime = None):
        """Broadcast user status update to all connected clients"""
        message = {
            "type": "user_status_update",
            "event": "user_status_update",
            "user_id": user_id,
            "is_online": is_online,
            "last_active_at": last_active_at.isoformat() if last_active_at else None
        }
        
        # Broadcast to all connected clients (not just the user themselves)
        disconnected = set()
        for user_connections in self.active_connections.values():
            for connection in user_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting status update: {e}")
                    disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def cleanup_stale_connections(self):
        """Periodically clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                # Connections are cleaned up automatically on disconnect
                # This is a placeholder for future cleanup logic
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WebSocket] Error in cleanup task: {e}")


# Global manager instance
manager = WebSocketManager()

