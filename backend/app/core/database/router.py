"""
Database router - routes queries to active database
"""
from typing import Optional, Any
from app.core.database.connection_manager import ConnectionManager
from app.core.database.base import DatabaseClient

class DatabaseRouter:
    """Routes database operations to active connections"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager
    
    def get_auth_db(self) -> Optional[DatabaseClient]:
        """Get active authentication database"""
        return self.manager.get_client("auth")
    
    def get_analytics_db(self, db_name: str = "ohlcv") -> Optional[Any]:
        """Get active analytics database"""
        client = self.manager.get_client("analytics")
        if client and hasattr(client, 'get_session'):
            return client.get_session(db_name)
        return client
    
    def get_ai_llm_client(self) -> Optional[DatabaseClient]:
        """Get active AI/LLM client"""
        return self.manager.get_client("ai_llm")
    
    def get_broker_client(self) -> Optional[DatabaseClient]:
        """Get active broker client"""
        return self.manager.get_client("broker")
    
    def get_social_media_client(self) -> Optional[DatabaseClient]:
        """Get active social media client"""
        return self.manager.get_client("social_media")
    
    def switch_auth_db(self, connection_id: str) -> bool:
        """Switch authentication database"""
        return self.manager.switch_connection("auth", connection_id)
    
    def switch_analytics_db(self, connection_id: str) -> bool:
        """Switch analytics database"""
        return self.manager.switch_connection("analytics", connection_id)
    
    def switch_ai_llm(self, connection_id: str) -> bool:
        """Switch AI/LLM connection"""
        return self.manager.switch_connection("ai_llm", connection_id)
    
    def switch_broker(self, connection_id: str) -> bool:
        """Switch broker connection"""
        return self.manager.switch_connection("broker", connection_id)
    
    def switch_social_media(self, connection_id: str) -> bool:
        """Switch social media connection"""
        return self.manager.switch_connection("social_media", connection_id)
    
