"""
WebSocket service for real-time corporate announcements ingestion from TrueData
"""
import asyncio
import websockets
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.services.announcements_service import get_announcements_service
from app.services.truedata_api_service import get_truedata_api_service
from app.models.connection import Connection
from app.core.websocket_manager import manager
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AnnouncementsWebSocketService:
    """Service for managing WebSocket connection to TrueData for real-time announcements"""
    
    def __init__(self):
        self.running = False
        self.websocket = None
        self.connection_id = None
        self.task = None
    
    async def connect(self, connection_id: int, db_session: Session):
        """
        Connect to TrueData WebSocket for corporate announcements
        
        Args:
            connection_id: TrueData connection ID
            db_session: Database session for getting connection details
        """
        username = None
        password = None
        try:
            # Get connection details
            conn = db_session.query(Connection).filter(
                Connection.id == connection_id,
                Connection.provider == "TrueData",
                Connection.is_enabled == True
            ).first()
            
            if not conn:
                raise ValueError(f"TrueData connection {connection_id} not found or not enabled")
            
            # Get credentials
            from app.core.security import decrypt_data
            import json as json_lib
            
            decrypted_json = decrypt_data(conn.credentials)
            credentials = json_lib.loads(decrypted_json)
            username = credentials.get("username")
            password = credentials.get("password")
            
            if not username or not password:
                raise ValueError("Username and password required for WebSocket connection")
            
        finally:
            # Close the database session - we don't need it anymore
            try:
                db_session.close()
            except:
                pass
        
        # Build WebSocket URL (port 9092 for Corporate Announcements)
        ws_url = f"wss://corp.truedata.in:9092?user={username}&password={password}"
        
        logger.info(f"Connecting to TrueData WebSocket for announcements: {ws_url}")
        
        try:
            # Connect to WebSocket
            self.websocket = await websockets.connect(ws_url)
            self.connection_id = connection_id
            self.running = True
            
            logger.info(f"Connected to TrueData WebSocket for connection {connection_id}")
            
            # Start listening for messages
            await self._listen()
            
        except Exception as e:
            logger.error(f"Error connecting to TrueData WebSocket: {e}")
            self.running = False
            raise
    
    async def _listen(self):
        """Listen for incoming announcement messages"""
        service = get_announcements_service()
        
        try:
            while self.running and self.websocket:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=30.0
                    )
                    
                    # Parse message
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON message: {message[:100]}")
                        continue
                    
                    # Check if this is an announcement message (must have 'id' field)
                    if not isinstance(data, dict):
                        logger.debug(f"Received non-dict message: {type(data)}")
                        continue
                    
                    # Skip non-announcement messages (heartbeats, errors, etc.)
                    if 'id' not in data:
                        logger.debug(f"Skipping non-announcement message (missing 'id'): {list(data.keys())[:5] if data else 'empty'}")
                        continue
                    
                    # Process announcement
                    await self._process_announcement(data, service)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    if self.websocket:
                        try:
                            await self.websocket.ping()
                        except:
                            pass
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
        finally:
            self.running = False
    
    async def _process_announcement(self, data: Dict[str, Any], service):
        """Process a single announcement message"""
        announcement = None
        try:
            # Validate data
            if not data or not isinstance(data, dict):
                logger.warning(f"Invalid announcement data received: {type(data)}")
                return
            
            # Map TrueData WebSocket payload to our schema
            try:
                announcement = service._map_truedata_to_schema(data)
            except ValueError as ve:
                logger.warning(f"Failed to map announcement data: {ve}")
                return
            
            # Validate announcement was created successfully
            if not announcement or not isinstance(announcement, dict):
                logger.warning(f"Invalid announcement object after mapping: {type(announcement)}")
                return
            
            announcement_id = announcement.get('id')
            if not announcement_id:
                logger.warning("Announcement missing ID after mapping")
                return
            
            # Insert into database (id-based de-duplication)
            inserted = service.insert_announcement(announcement)
            
            if inserted:
                headline = announcement.get('news_headline', '') or ''
                headline_preview = headline[:50] if headline else 'N/A'
                logger.info(f"Inserted new announcement: {announcement_id} - {headline_preview}")
                
                # Broadcast to all connected frontend clients
                try:
                    # Enrich announcement with descriptor metadata if available
                    enriched_announcement = announcement.copy()
                    if announcement.get("descriptor_id"):
                        desc_meta = service.get_descriptor_metadata(announcement["descriptor_id"])
                        if desc_meta:
                            enriched_announcement["descriptor_name"] = desc_meta.get("descriptor_name")
                            enriched_announcement["descriptor_category"] = desc_meta.get("descriptor_category")
                    
                    # Broadcast to all connected clients
                    await manager.broadcast_announcement(enriched_announcement)
                    logger.debug(f"Broadcast announcement {announcement_id} to connected clients")
                except Exception as broadcast_error:
                    logger.warning(f"Failed to broadcast announcement {announcement_id}: {broadcast_error}")
                    # Don't fail the whole process if broadcast fails
            else:
                logger.debug(f"Announcement already exists: {announcement_id}")
                
        except Exception as e:
            # Safe logging - don't access announcement if it might be None
            announcement_id = announcement.get('id') if announcement and isinstance(announcement, dict) else 'unknown'
            logger.error(f"Error processing announcement {announcement_id}: {e}", exc_info=True)
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        logger.info("Disconnected from TrueData WebSocket")
    
    async def start_background(self, connection_id: int, db_session: Session):
        """Start WebSocket connection in background task"""
        if self.running:
            logger.warning("WebSocket service already running")
            return
        
        try:
            await self.connect(connection_id, db_session)
        except Exception as e:
            logger.error(f"Background WebSocket service error: {e}")
            # Try to reconnect after a delay
            await asyncio.sleep(30)
            if not self.running:
                try:
                    await self.start_background(connection_id, db_session)
                except:
                    pass
    
    def stop(self):
        """Stop WebSocket service"""
        self.running = False
        if self.task:
            self.task.cancel()
        # Disconnect synchronously
        if self.websocket:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.disconnect())
                else:
                    loop.run_until_complete(self.disconnect())
            except:
                pass


# Global service instance
_websocket_service: Optional[AnnouncementsWebSocketService] = None


def get_announcements_websocket_service() -> AnnouncementsWebSocketService:
    """Get global WebSocket service instance"""
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = AnnouncementsWebSocketService()
    return _websocket_service

