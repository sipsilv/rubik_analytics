"""
Abstract base class for database clients
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

class DatabaseClient(ABC):
    """Base interface for all database clients"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self.is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to database"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to database"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test if connection is valid"""
        pass
    
    @abstractmethod
    def get_session(self) -> Any:
        """Get database session"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a raw query"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        pass
