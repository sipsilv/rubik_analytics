"""
Announcements Manager
Manages WebSocket workers and database writer for Corporate Announcements
"""
import logging
from typing import Dict, Optional
from queue import Queue
from app.services.announcements_websocket_worker import AnnouncementsWebSocketWorker
from app.services.announcements_db_writer import AnnouncementsDBWriter

logger = logging.getLogger(__name__)


class AnnouncementsManager:
    """
    Manager for Corporate Announcements ingestion
    
    Responsibilities:
    - Manage WebSocket workers per connection
    - Manage shared database writer
    - Start/stop workers based on connection status
    """
    
    _instance: Optional['AnnouncementsManager'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.workers: Dict[int, AnnouncementsWebSocketWorker] = {}
        self.message_queue: Queue = Queue(maxsize=10000)  # Bounded FIFO queue
        self.db_writer: Optional[AnnouncementsDBWriter] = None
        self._initialized = True
        logger.info("AnnouncementsManager initialized")
    
    def start(self):
        """Start the announcements manager (database writer)"""
        if self.db_writer is None:
            self.db_writer = AnnouncementsDBWriter(self.message_queue)
            self.db_writer.start()
            logger.info("Started announcements database writer")
    
    def stop(self):
        """Stop all workers and database writer"""
        # Stop all workers
        for connection_id, worker in list(self.workers.items()):
            try:
                worker.stop()
            except Exception as e:
                logger.error(f"Error stopping worker for connection {connection_id}: {e}")
        
        self.workers.clear()
        
        # Stop database writer
        if self.db_writer:
            try:
                self.db_writer.stop()
            except Exception as e:
                logger.error(f"Error stopping database writer: {e}")
            self.db_writer = None
        
        logger.info("AnnouncementsManager stopped")
    
    def start_worker(self, connection_id: int) -> bool:
        """
        Start WebSocket worker for a connection
        
        Args:
            connection_id: TrueData connection ID
            
        Returns:
            True if worker started, False otherwise
        """
        # If worker already exists, stop it first (for restart scenario)
        if connection_id in self.workers:
            logger.info(f"Worker for connection {connection_id} already exists, stopping it first for restart")
            self.stop_worker(connection_id)
        
        try:
            # Ensure database writer is running
            if self.db_writer is None:
                self.start()
            
            # Create and start worker
            worker = AnnouncementsWebSocketWorker(connection_id, self.message_queue)
            worker.start()
            self.workers[connection_id] = worker
            logger.info(f"Started WebSocket worker for connection {connection_id}")
            print(f"[ANNOUNCEMENTS] Started WebSocket worker for TrueData connection {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting worker for connection {connection_id}: {e}", exc_info=True)
            return False
    
    def stop_worker(self, connection_id: int) -> bool:
        """
        Stop WebSocket worker for a connection
        
        Args:
            connection_id: TrueData connection ID
            
        Returns:
            True if worker stopped, False otherwise
        """
        if connection_id not in self.workers:
            # Not an error - worker might not have been started yet
            logger.debug(f"Worker for connection {connection_id} not found (may not have been started)")
            return True  # Return True since desired state (stopped) is achieved
        
        try:
            worker = self.workers.pop(connection_id)
            worker.stop()
            logger.info(f"Stopped WebSocket worker for connection {connection_id}")
            print(f"[ANNOUNCEMENTS] Stopped WebSocket worker for TrueData connection {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping worker for connection {connection_id}: {e}", exc_info=True)
            return False
    
    def is_worker_running(self, connection_id: int) -> bool:
        """Check if worker is running for a connection"""
        worker = self.workers.get(connection_id)
        return worker is not None and worker.running
    
    def get_worker_status(self, connection_id: int) -> Dict:
        """Get status of worker for a connection"""
        worker = self.workers.get(connection_id)
        if not worker:
            return {
                "running": False,
                "connection_id": connection_id
            }
        
        return {
            "running": worker.running,
            "connection_id": connection_id,
            "queue_size": self.message_queue.qsize()
        }


def get_announcements_manager() -> AnnouncementsManager:
    """Get the global announcements manager instance"""
    return AnnouncementsManager()

