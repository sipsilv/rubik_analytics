"""
DuckDB database client with SQLAlchemy support
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, Any, Optional
from app.core.database.base import DatabaseClient

class DuckDBSQLAlchemyClient(DatabaseClient):
    """DuckDB database client with SQLAlchemy ORM support"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Default path for DuckDB database
        self.db_path = config.get("path", "./data/analytics/duckdb/database.duckdb")
        self.engine = None
        self.SessionLocal = None
        self._tables_created = False  # Track if we've attempted table creation
    
    def connect(self) -> bool:
        """Connect to DuckDB database using SQLAlchemy and auto-create if missing"""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            # Log if database file is being created
            db_exists = os.path.exists(self.db_path)
            if not db_exists:
                print(f"[INFO] DuckDB database not found, creating: {self.db_path}")
            
            # Try duckdb-engine (required for SQLAlchemy integration)
            try:
                # SQLAlchemy DuckDB connection string
                # Format: duckdb:///path/to/database.duckdb
                # Requires duckdb-engine package for SQLAlchemy integration
                connection_string = f"duckdb:///{self.db_path}"
                # Pass config params via connect_args
                connect_args = {
                    'config': {
                        'allow_unsigned_extensions': True
                    }
                }
                self.engine = create_engine(connection_string, pool_pre_ping=True, connect_args=connect_args)
                
                # Test the connection by creating a session
                test_sessionmaker = sessionmaker(bind=self.engine)
                test_session = test_sessionmaker()
                from sqlalchemy import text
                test_session.execute(text("SELECT 1"))
                test_session.close()
                
                if not db_exists:
                    print(f"[OK] DuckDB database created: {self.db_path}")
                
            except ImportError as import_err:
                # Missing duckdb-engine package
                error_msg = (
                    f"DuckDB SQLAlchemy connection failed: duckdb-engine package not installed. "
                    f"Please install it with: pip install duckdb-engine\n"
                    f"Error: {import_err}"
                )
                print(f"[ERROR] {error_msg}")
                self.is_connected = False
                return False
            except Exception as conn_err:
                # Connection failed for other reasons (including missing dialect)
                error_str = str(conn_err)
                if "Can't load plugin" in error_str and "duckdb" in error_str.lower():
                    # SQLAlchemy dialect loading error - duckdb-engine missing
                    error_msg = (
                        f"DuckDB SQLAlchemy connection failed: duckdb-engine package not installed or not properly loaded. "
                        f"Please install it with: pip install duckdb-engine\n"
                        f"Original error: {error_str}"
                    )
                else:
                    error_msg = f"DuckDB SQLAlchemy connection failed: {conn_err}"
                print(f"[ERROR] {error_msg}")
                self.is_connected = False
                return False
            
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.is_connected = True
            
            # Auto-create tables if they don't exist (idempotent)
            if not self._tables_created:
                self._ensure_tables_exist()
                self._tables_created = True
            
            return True
        except Exception as e:
            error_msg = f"DuckDB SQLAlchemy connection error: {e}"
            print(f"[ERROR] {error_msg}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from DuckDB database"""
        try:
            if self.engine:
                self.engine.dispose()
            self.is_connected = False
            return True
        except Exception as e:
            print(f"DuckDB SQLAlchemy disconnect error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test DuckDB connection"""
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
        """Get DuckDB SQLAlchemy session, auto-connect and create tables if needed"""
        if not self.is_connected:
            if not self.connect():
                raise RuntimeError(
                    f"DuckDB database is not available at {self.db_path}. "
                    "Please ensure duckdb-engine is installed: pip install duckdb-engine"
                )
        return self.SessionLocal()
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute raw query and return fetched results as list of rows"""
        session = self.get_session()
        try:
            from sqlalchemy import text
            result = session.execute(text(query), params or {})
            session.commit()
            # Fetch all results and return as list of tuples (consistent with other clients)
            return result.fetchall()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def _ensure_tables_exist(self) -> None:
        """Ensure tables exist - symbols module removed, method is now a no-op"""
        # Symbols module has been removed, so this method no longer creates any tables
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """Check DuckDB health"""
        return {
            "type": "duckdb_sqlalchemy",
            "connected": self.is_connected,
            "path": self.db_path,
            "status": "healthy" if self.test_connection() else "unhealthy"
        }

