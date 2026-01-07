"""
Connection manager for dynamic database switching
"""
import json
import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.database.base import DatabaseClient
from app.core.database.sqlite_client import SQLiteClient
from app.core.database.duckdb_client import DuckDBClient
from app.core.database.duckdb_sqlalchemy_client import DuckDBSQLAlchemyClient
from app.core.database.postgres_client import PostgreSQLClient
from app.core.database.api_client import APIClient

class ConnectionManager:
    """Manages database connections and dynamic switching"""
    
    def __init__(self, data_dir: str = "./data"):
        # Validate data_dir is not empty
        if not data_dir or not data_dir.strip():
            raise ValueError(f"ConnectionManager data_dir cannot be empty. Received: '{data_dir}'")
        self.data_dir = os.path.abspath(data_dir)
        # Validate that abspath didn't result in empty string (shouldn't happen, but safety check)
        if not self.data_dir or not self.data_dir.strip():
            raise ValueError(f"ConnectionManager data_dir resolved to empty path. Original: '{data_dir}'")
        # Connections folder is now in backend directory, not data directory
        # Get backend directory: backend/app/core/database/connection_manager.py -> backend/
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        connections_dir = os.path.join(backend_dir, "connections")
        self.connections_file = os.path.join(connections_dir, "connections.json")
        self.active_file = os.path.join(connections_dir, "active_connection.json")
        self.clients: Dict[str, DatabaseClient] = {}
        self.active_connections: Dict[str, str] = {}
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.load_connections()
        self.load_active_connections()
        self.initialize_defaults()
    
    def load_connections(self) -> None:
        """Load connection configurations from file"""
        try:
            if os.path.exists(self.connections_file):
                with open(self.connections_file, 'r') as f:
                    data = json.load(f)
                    connections_list = data.get("connections", [])
                    # Fix any connections with empty or invalid paths
                    for conn in connections_list:
                        if conn.get("type") == "sqlite":
                            config = conn.get("config", {})
                            path = config.get("path", "")
                            if not path or not path.strip():
                                # Fix empty path
                                config["path"] = os.path.abspath(os.path.join(self.data_dir, "auth", "sqlite", "auth.db"))
                                print(f"[INFO] Fixed empty path for connection {conn.get('id')}: {config['path']}")
                    self.connections = {conn["id"]: conn for conn in connections_list}
            else:
                self.connections = {}
        except Exception as e:
            print(f"Error loading connections: {e}")
            self.connections = {}
    
    def save_connections(self) -> None:
        """Save connection configurations to file"""
        try:
            os.makedirs(os.path.dirname(self.connections_file), exist_ok=True)
            data = {
                "connections": list(self.connections.values())
            }
            with open(self.connections_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving connections: {e}")
    
    def load_active_connections(self) -> None:
        """Load active connection mappings"""
        try:
            if os.path.exists(self.active_file):
                with open(self.active_file, 'r') as f:
                    self.active_connections = json.load(f)
            else:
                self.active_connections = {}
        except Exception as e:
            print(f"Error loading active connections: {e}")
            self.active_connections = {}
    
    def save_active_connections(self) -> None:
        """Save active connection mappings"""
        try:
            os.makedirs(os.path.dirname(self.active_file), exist_ok=True)
            with open(self.active_file, 'w') as f:
                json.dump(self.active_connections, f, indent=2)
        except Exception as e:
            print(f"Error saving active connections: {e}")
    
    def initialize_defaults(self) -> None:
        """Initialize default connections"""
        # Validate data_dir is set
        if not self.data_dir or not self.data_dir.strip():
            raise ValueError(f"ConnectionManager data_dir cannot be empty. Current value: '{self.data_dir}'")
        
        # Ensure default SQLite auth connection exists
        if "auth_sqlite_default" not in self.connections:
            db_path = os.path.abspath(os.path.join(self.data_dir, "auth", "sqlite", "auth.db"))
            # Validate path is not empty
            if not db_path or not db_path.strip():
                raise ValueError(f"Cannot create database path. data_dir: '{self.data_dir}', resulting path: '{db_path}'")
            self.connections["auth_sqlite_default"] = {
                "id": "auth_sqlite_default",
                "name": "Default SQLite Auth",
                "type": "sqlite",
                "category": "auth",
                "config": {
                    "path": db_path
                },
                "is_default": True,
                "is_active": True,
                "status": "active",
                "last_tested": None,
                "created_at": datetime.utcnow().isoformat()
            }
            # Don't save during initialization to avoid file I/O during import
            # Will be saved on first actual use
        
        # Ensure default DuckDB analytics connection exists
        if "analytics_duckdb_default" not in self.connections:
            self.connections["analytics_duckdb_default"] = {
                "id": "analytics_duckdb_default",
                "name": "Default DuckDB Analytics",
                "type": "duckdb",
                "category": "analytics",
                "config": {
                    "ohlcv": os.path.abspath(os.path.join(self.data_dir, "analytics", "duckdb", "ohlcv.duckdb")),
                    "indicators": os.path.abspath(os.path.join(self.data_dir, "analytics", "duckdb", "indicators.duckdb")),
                    "signals": os.path.abspath(os.path.join(self.data_dir, "analytics", "duckdb", "signals.duckdb")),
                    "jobs": os.path.abspath(os.path.join(self.data_dir, "analytics", "duckdb", "jobs.duckdb"))
                },
                "is_default": True,
                "is_active": True,
                "status": "active",
                "last_tested": None,
                "created_at": datetime.utcnow().isoformat()
            }
            # Don't save during initialization to avoid file I/O during import
        
        # Set active connections if not set
        if "auth" not in self.active_connections:
            self.active_connections["auth"] = "auth_sqlite_default"
        if "analytics" not in self.active_connections:
            self.active_connections["analytics"] = "analytics_duckdb_default"
        # Don't save during initialization to avoid file I/O during import
    
    def get_client(self, category: str) -> Optional[DatabaseClient]:
        """Get active client for category"""
        connection_id = self.active_connections.get(category)
        if not connection_id:
            return None
        
        # Return cached client if exists and connected
        if connection_id in self.clients:
            client = self.clients[connection_id]
            if client.is_connected:
                return client
        
        # Create new client
        connection = self.connections.get(connection_id)
        if not connection:
            return None
        
        client = self._create_client(connection)
        if client and client.connect():
            self.clients[connection_id] = client
            # Save defaults if they were just created (lazy save)
            if connection.get("is_default"):
                try:
                    self.save_connections()
                    self.save_active_connections()
                except Exception as e:
                    # Non-critical - just log and continue
                    print(f"[WARNING] Could not save connection defaults: {e}")
            return client
        
        return None
    
    def _create_client(self, connection: Dict[str, Any]) -> Optional[DatabaseClient]:
        """Create client instance based on connection type"""
        conn_type = connection.get("type")
        config = connection.get("config", {})
        
        # Helper to fix paths when running in Docker (Linux) but reading Windows config
        def fix_path_if_needed(path_str):
            if not path_str or not isinstance(path_str, str):
                return path_str
            
            # If path exists, it's fine
            if os.path.exists(path_str):
                return path_str
            
            # Docker -> Windows Fix
            # If we are on Windows and the path starts with /app/ or looks like a unix path
            if (sys.platform == "win32") and (path_str.startswith("/app/") or path_str.startswith("/")):
                 # Try to rebase relative to data_dir
                parts = path_str.strip("/").split("/")
                
                # Markers to identify where the relative path starts
                markers = ["auth", "analytics", "Company Fundamentals", "symbols", "connections", "logs"]
                
                for marker in markers:
                    if marker in parts:
                        try:
                            idx = parts.index(marker)
                            # Reconstruct path from marker onwards relative to our data_dir
                            rel_path = os.path.join(*parts[idx:])
                            new_path = os.path.join(self.data_dir, rel_path)
                            # Verify if this corrected path exists (optional, but good for confirmation)
                            if os.path.exists(new_path) or os.path.exists(os.path.dirname(new_path)):
                                print(f"[INFO] Path correction (Docker->Win): '{path_str}' -> '{new_path}'")
                                return new_path
                        except Exception as e:
                            print(f"[WARNING] Path correction failed for '{path_str}': {e}")

            # Windows -> Docker Fix (existing logic)
            # If we are in Docker (implied by /app/data existing or path starting with /app)
            # and the path looks like a Windows path (drive letter or backslashes)
            if (sys.platform != "win32") and (":" in path_str or "\\" in path_str):
                # Try to rebase relative to data_dir
                # Strategy: find known markers like 'auth', 'analytics', 'data'
                parts = path_str.replace("\\", "/").split("/")
                
                # Common subdirectories in our structure
                markers = ["auth", "analytics", "Company Fundamentals", "symbols", "connections", "logs"]
                
                for marker in markers:
                    if marker in parts:
                        try:
                            idx = parts.index(marker)
                            # Reconstruct path from marker onwards relative to our data_dir
                            rel_path = os.path.join(*parts[idx:])
                            new_path = os.path.join(self.data_dir, rel_path)
                            print(f"[INFO] Path correction (Win->Docker): '{path_str}' -> '{new_path}'")
                            return new_path
                        except Exception as e:
                            print(f"[WARNING] Path correction failed for '{path_str}': {e}")
            
            return path_str

        # Apply path fix to config
        if "path" in config:
            config["path"] = fix_path_if_needed(config["path"])
        if "ohlcv" in config:
            config["ohlcv"] = fix_path_if_needed(config["ohlcv"])
        if "indicators" in config:
            config["indicators"] = fix_path_if_needed(config["indicators"])
        if "signals" in config:
            config["signals"] = fix_path_if_needed(config["signals"])
        if "jobs" in config:
            config["jobs"] = fix_path_if_needed(config["jobs"])
        
        if conn_type == "sqlite":
            # Validate path exists in config
            db_path = config.get("path", "")
            if not db_path or not db_path.strip():
                # Try to construct path from data_dir
                db_path = os.path.abspath(os.path.join(self.data_dir, "auth", "sqlite", "auth.db"))
                config["path"] = db_path
                print(f"[WARNING] SQLite connection missing path, using default: {db_path}")
            return SQLiteClient(config)
        elif conn_type == "duckdb":
            return DuckDBClient(config)
        elif conn_type == "duckdb_sqlalchemy":
            return DuckDBSQLAlchemyClient(config)
        elif conn_type == "postgresql":
            return PostgreSQLClient(config)
        elif conn_type == "api":
            return APIClient(config)
        else:
            print(f"Unknown connection type: {conn_type}")
            return None
    
    def switch_connection(self, category: str, connection_id: str) -> bool:
        """Switch active connection for a category"""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        if connection.get("category") != category:
            return False
        
        # Disconnect old client
        old_id = self.active_connections.get(category)
        if old_id and old_id in self.clients:
            self.clients[old_id].disconnect()
            del self.clients[old_id]
        
        # Set new active connection
        self.active_connections[category] = connection_id
        self.save_active_connections()
        
        # Connect new client
        client = self.get_client(category)
        return client is not None and client.is_connected
    
    def test_connection(self, connection_id: str) -> bool:
        """Test a connection"""
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        client = self._create_client(connection)
        if not client:
            return False
        
        result = client.test_connection()
        client.disconnect()
        
        # Update last tested time
        connection["last_tested"] = datetime.utcnow().isoformat()
        connection["status"] = "active" if result else "error"
        self.save_connections()
        
        return result
    
    def add_connection(self, connection: Dict[str, Any]) -> str:
        """Add a new connection"""
        connection_id = connection.get("id") or f"{connection.get('type')}_{connection.get('category')}_{len(self.connections)}"
        connection["id"] = connection_id
        connection["created_at"] = datetime.utcnow().isoformat()
        connection["status"] = "inactive"
        self.connections[connection_id] = connection
        self.save_connections()
        return connection_id
    
    def update_connection(self, connection_id: str, updates: Dict[str, Any]) -> bool:
        """Update a connection"""
        if connection_id not in self.connections:
            return False
        
        self.connections[connection_id].update(updates)
        self.connections[connection_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # If this is the active connection, reconnect
        for category, active_id in self.active_connections.items():
            if active_id == connection_id:
                self.switch_connection(category, connection_id)
                break
        
        self.save_connections()
        return True
    
    def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection"""
        if connection_id not in self.connections:
            return False
        
        # Don't delete if it's active
        if connection_id in self.active_connections.values():
            return False
        
        # Disconnect if connected
        if connection_id in self.clients:
            self.clients[connection_id].disconnect()
            del self.clients[connection_id]
        
        del self.connections[connection_id]
        self.save_connections()
        return True
    
    def get_all_connections(self) -> List[Dict[str, Any]]:
        """Get all connections"""
        return list(self.connections.values())
    
    def get_connections_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get connections by category"""
        return [conn for conn in self.connections.values() if conn.get("category") == category]
    
    def close_all(self) -> None:
        """Close all database connections"""
        try:
            for connection_id, client in list(self.clients.items()):
                try:
                    client.disconnect()
                except Exception as e:
                    print(f"Error closing connection {connection_id}: {e}")
            self.clients.clear()
        except Exception as e:
            print(f"Error closing all connections: {e}")
