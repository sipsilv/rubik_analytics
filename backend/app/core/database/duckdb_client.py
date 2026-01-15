"""
DuckDB database client
"""
import os
import duckdb
from typing import Dict, Any, Optional
from app.core.database.base import DatabaseClient

class DuckDBClient(DatabaseClient):
    """DuckDB database client implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if "path" in config:
            self.databases = {"default": config["path"]}
        else:
            self.databases = {
                "ohlcv": config.get("ohlcv", "./data/analytics/duckdb/ohlcv.duckdb"),
                "indicators": config.get("indicators", "./data/analytics/duckdb/indicators.duckdb"),
                "signals": config.get("signals", "./data/analytics/duckdb/signals.duckdb"),
                "jobs": config.get("jobs", "./data/analytics/duckdb/jobs.duckdb"),
            }
        self.connections = {}
    
    def connect(self) -> bool:
        """Connect to DuckDB databases"""
        try:
            for name, path in self.databases.items():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                self.connections[name] = duckdb.connect(path, config={'allow_unsigned_extensions': True})
            self.is_connected = True
            return True
        except Exception as e:
            print(f"DuckDB connection error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from DuckDB databases"""
        try:
            for conn in self.connections.values():
                conn.close()
            self.connections.clear()
            self.is_connected = False
            return True
        except Exception as e:
            print(f"DuckDB disconnect error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test DuckDB connection"""
        try:
            if not self.is_connected:
                if not self.connect():
                    return False
            # Test first database
            first_db = list(self.connections.values())[0] if self.connections else None
            if first_db:
                first_db.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def get_session(self, db_name: str = "ohlcv") -> duckdb.DuckDBPyConnection:
        """Get DuckDB connection for specific database"""
        if not self.is_connected:
            self.connect()
        return self.connections.get(db_name)
    
    def execute_query(self, query: str, params: Optional[Dict] = None, db_name: str = "ohlcv") -> Any:
        """Execute raw query on specified database"""
        conn = self.get_session(db_name)
        try:
            if params:
                return conn.execute(query, params).fetchall()
            return conn.execute(query).fetchall()
        except Exception as e:
            raise e
    
    def health_check(self) -> Dict[str, Any]:
        """Check DuckDB health"""
        return {
            "type": "duckdb",
            "connected": self.is_connected,
            "databases": list(self.databases.keys()),
            "status": "healthy" if self.test_connection() else "unhealthy"
        }
