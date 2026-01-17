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
        self._loop = None
        try:
            import asyncio
            # In Python 3.7+ we should ideally use get_running_loop but 
            # this is called during global module initialization, so we use get_event_loop
            self._loop = asyncio.get_event_loop()
        except Exception:
            pass
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Register a new WebSocket connection for a user"""
        # Capture the running loop if we don't have it yet
        if not self._loop:
            try:
                self._loop = asyncio.get_running_loop()
            except:
                pass

        await websocket.accept()
        
        # Ensure this physical connection is not already registered elsewhere
        # This prevents duplicate broadcasts if the connection is re-associated
        self.disconnect(websocket)
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        # Log active connections for debugging
        print(f"[WebSocket] User {user_id} connected. Total active users: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        user_id = self.connection_users.pop(websocket, None)
        
        if user_id and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
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
    
    async def broadcast_announcement(self, announcement: dict):
        """Broadcast a new announcement to all connected clients"""
        message = {
            "type": "announcement",
            "event": "new_announcement",
            "data": announcement
        }
        
        # Broadcast to all connected clients
        disconnected = set()
        for user_connections in self.active_connections.values():
            for connection in user_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting announcement: {e}")
                    disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_news(self, news_item: dict):
        """Broadcast a new AI-enriched news item to all connected clients"""
        # Determine message type (new vs update)
        msg_type = news_item.get("type", "news_update") if "type" in news_item else "news_update"
        
        message = {
            "type": "news_update", # Keep top-level type consistent for frontend handler
            "event": msg_type,     # Use event field for specific type (new_news vs update_news)
            "data": news_item
        }
        
        # Broadcast to all connected clients
        count = 0
        disconnected = set()
        sent_to = set() # Track connections within this broadcast to avoid duplicates
        news_id = news_item.get('news_id')
        
        # Use list() to avoid "dictionary changed size during iteration"
        for user_connections in list(self.active_connections.values()):
            for connection in list(user_connections):
                if connection in sent_to:
                    continue
                    
                try:
                    # Duplicate Prevention: Check if already sent recently to this connection
                    # We store recent broadcasts in a temporary attribute on the websocket object
                    if not hasattr(connection, 'recent_broadcasts'):
                        connection.recent_broadcasts = set()
                        
                    # Clean up old entries (simple approach: clear if too big)
                    if len(connection.recent_broadcasts) > 100:
                        connection.recent_broadcasts.clear()
                        
                    # Skip if already sent (only for new_news, allowed for update_news)
                    if msg_type == "new_news" and news_id in connection.recent_broadcasts:
                        sent_to.add(connection)
                        continue
                        
                    await connection.send_json(message)
                    sent_to.add(connection)
                    
                    # Track this broadcast
                    if news_id:
                        connection.recent_broadcasts.add(news_id)
                        
                    count += 1
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting news: {e}")
                    disconnected.add(connection)
        
        if count > 0:
            print(f"[WebSocket] Broadcasted news {news_id} ({msg_type}) to {count} connections")
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect_all(connection)

    def broadcast_news_sync(self, news_item: dict):
        """Sync wrapper to broadcast news from sync context"""
        try:
            import asyncio
            # Use the stored loop if available
            loop = self._loop
            
            # Fallback to event loop if we can get it
            if not loop:
                try:
                    loop = asyncio.get_event_loop()
                except:
                    pass
            
            if loop and loop.is_running():
                # Correctly schedule the coroutine in the running loop
                asyncio.run_coroutine_threadsafe(self.broadcast_news(news_item), loop)
            else:
                # If no loop is running (rare in FastAPI context), try to run it directly
                # This might fail if we are not in an async context
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self.broadcast_news(news_item))
                except Exception as e:
                    print(f"[WebSocket] Failed to broadcast sync (no loop): {e}")
                    
        except Exception as e:
            print(f"[WebSocket] Error in broadcast_news_sync: {e}")
            pass

    def disconnect_all(self, websocket: WebSocket):
        """Helper to disconnect a websocket from all users (fallback cleanup)"""
        try:
            self.disconnect(websocket)
        except:
            pass
    
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

