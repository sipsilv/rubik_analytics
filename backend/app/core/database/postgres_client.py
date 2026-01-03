"""
PostgreSQL database client
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, Any, Optional
from app.core.database.base import DatabaseClient

class PostgreSQLClient(DatabaseClient):
    """PostgreSQL database client implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "rubik")
        self.username = config.get("username", "postgres")
        self.password = config.get("password", "")
        self.engine = None
        self.SessionLocal = None
    
    def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            connection_string = (
                f"postgresql://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
            self.engine = create_engine(connection_string)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            # Test connection
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            self.is_connected = True
            return True
        except Exception as e:
            print(f"PostgreSQL connection error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from PostgreSQL database"""
        try:
            if self.engine:
                self.engine.dispose()
            self.is_connected = False
            return True
        except Exception as e:
            print(f"PostgreSQL disconnect error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test PostgreSQL connection"""
        try:
            if not self.is_connected:
                if not self.connect():
                    return False
            with self.SessionLocal() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def get_session(self) -> Session:
        """Get PostgreSQL session"""
        if not self.is_connected:
            self.connect()
        return self.SessionLocal()
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute raw query"""
        session = self.get_session()
        try:
            result = session.execute(query, params or {})
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check PostgreSQL health"""
        return {
            "type": "postgresql",
            "connected": self.is_connected,
            "host": self.host,
            "database": self.database,
            "status": "healthy" if self.test_connection() else "unhealthy"
        }
