"""
Periodic Token Refresh Scheduler for TrueData

This scheduler runs periodically (every 2-5 minutes) and checks token expiry timestamps.
It only calls TrueData API when tokens are expired or within refresh buffer.

CRITICAL: This scheduler does NOT hit TrueData API on every run.
It only checks timestamps in the database and triggers refresh when needed.
"""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from app.providers.token_manager import get_token_service

logger = logging.getLogger(__name__)

class TokenRefreshScheduler:
    """Periodic scheduler for checking and refreshing TrueData tokens"""
    
    def __init__(self):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.check_interval = 120  # Check every 2 minutes (120 seconds)
        self.lock = threading.Lock()
    
    def start(self):
        """Start the token refresh scheduler"""
        if self.running:
            logger.warning("Token refresh scheduler is already running")
            return
        
        with self.lock:
            self.running = True
            self.thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="TokenRefreshScheduler"
            )
            self.thread.start()
            logger.info(f"Token refresh scheduler started (check interval: {self.check_interval}s)")
    
    def stop(self):
        """Stop the token refresh scheduler"""
        with self.lock:
            self.running = False
        
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("Token refresh scheduler stopped")
    
    def _run_loop(self):
        """Main scheduler loop - checks tokens periodically"""
        logger.info("Token refresh scheduler loop started")
        
        while self.running:
            try:
                # Check all tokens and refresh if needed
                # This only checks timestamps, doesn't hit API unless refresh needed
                token_service = get_token_service()
                token_service.check_and_refresh_all_tokens()
                
            except Exception as e:
                logger.error(f"Error in token refresh scheduler loop: {e}", exc_info=True)
            
            # Sleep for check_interval seconds
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info("Token refresh scheduler loop stopped")

# Global scheduler instance
_token_refresh_scheduler: Optional[TokenRefreshScheduler] = None

def get_token_refresh_scheduler() -> TokenRefreshScheduler:
    """Get the global token refresh scheduler instance"""
    global _token_refresh_scheduler
    if _token_refresh_scheduler is None:
        _token_refresh_scheduler = TokenRefreshScheduler()
    return _token_refresh_scheduler

def start_token_refresh_scheduler():
    """Start the token refresh scheduler (called on app startup)"""
    scheduler = get_token_refresh_scheduler()
    scheduler.start()

def stop_token_refresh_scheduler():
    """Stop the token refresh scheduler (called on app shutdown)"""
    scheduler = get_token_refresh_scheduler()
    scheduler.stop()

