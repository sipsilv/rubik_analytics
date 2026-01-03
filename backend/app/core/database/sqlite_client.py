"""
SQLite database client
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, Any, Optional
from app.core.database.base import DatabaseClient

class SQLiteClient(DatabaseClient):
    """SQLite database client implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("path", "./data/auth/sqlite/auth.db")
        self.engine = None
        self.SessionLocal = None
    
    def connect(self) -> bool:
        """Connect to SQLite database"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                connect_args={"check_same_thread": False}
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"SQLite connection error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from SQLite database"""
        try:
            if self.engine:
                self.engine.dispose()
            self.is_connected = False
            return True
        except Exception as e:
            print(f"SQLite disconnect error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test SQLite connection"""
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
        """Get SQLite session"""
        if not self.is_connected:
            self.connect()
        return self.SessionLocal()
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute raw query"""
        session = self.get_session()
        try:
            from sqlalchemy import text
            # Ensure query is wrapped in text()
            stmt = text(query) if isinstance(query, str) else query
            result = session.execute(stmt, params or {})
            
            # Commit for non-SELECT statements
            # Attempt to fetch results
            try:
                rows = result.fetchall()
                session.commit()
                return rows
            except Exception:
                # No rows to fetch (e.g. INSERT/UPDATE without RETURNING)
                session.commit()
                return []
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check SQLite health"""
        return {
            "type": "sqlite",
            "connected": self.is_connected,
            "path": self.db_path,
            "status": "healthy" if self.test_connection() else "unhealthy"
        }
