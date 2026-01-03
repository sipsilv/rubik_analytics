"""
REST API client for external services
"""
import requests
from typing import Dict, Any, Optional
from app.core.database.base import DatabaseClient

class APIClient(DatabaseClient):
    """REST API client for external services (AI, Broker, Social Media)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)
    
    def connect(self) -> bool:
        """Connect to API (validate endpoint)"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                headers=self.headers,
                timeout=self.timeout
            )
            self.is_connected = response.status_code == 200
            return self.is_connected
        except Exception as e:
            print(f"API connection error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from API"""
        self.is_connected = False
        return True
    
    def test_connection(self) -> bool:
        """Test API connection"""
        return self.connect()
    
    def get_session(self) -> Any:
        """Get API session (returns requests session)"""
        session = requests.Session()
        session.headers.update(self.headers)
        if self.api_key:
            session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        return session
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute API request"""
        session = self.get_session()
        try:
            response = session.get(
                self.base_url + query,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise e
        finally:
            session.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return {
            "type": "api",
            "connected": self.is_connected,
            "base_url": self.base_url,
            "status": "healthy" if self.test_connection() else "unhealthy"
        }
