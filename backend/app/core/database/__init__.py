"""
Database module - dynamic multi-database support
"""
from typing import Optional, Generator
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from app.core.database.connection_manager import ConnectionManager
from app.core.database.router import DatabaseRouter
from app.core.config import settings

# SQLAlchemy Base for models
Base = declarative_base()

# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None
_db_router: Optional[DatabaseRouter] = None

def get_connection_manager(data_dir: str = "./data") -> ConnectionManager:
    """Get or create connection manager singleton"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager(data_dir)
    return _connection_manager

def get_db_router(data_dir: str = "./data") -> DatabaseRouter:
    """Get or create database router singleton"""
    global _db_router
    if _db_router is None:
        manager = get_connection_manager(data_dir)
        _db_router = DatabaseRouter(manager)
    return _db_router

def get_db() -> Generator[Session, None, None]:
    """Get database session from router - FastAPI dependency"""
    from fastapi import HTTPException, status
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    if auth_client:
        session = auth_client.get_session()
        try:
            yield session
        finally:
            session.close()
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication database not initialized. Please run initialization script."
        )

def SessionLocal():
    """
    Stand-alone session factory for use in non-FastAPI contexts (e.g. scripts, background tasks).
    Returns a new SQLAlchemy Session object.
    """
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    if auth_client:
        return auth_client.get_session()
    raise Exception("Authentication database not initialized")

# get_symbols_db() function removed - symbols module has been removed

def reset_connection_manager():
    """Reset connection manager (for testing)"""
    global _connection_manager, _db_router
    if _connection_manager:
        # Disconnect all clients
        for client in _connection_manager.clients.values():
            client.disconnect()
    _connection_manager = None
    _db_router = None

# Export everything needed
__all__ = [
    "Base",
    "get_db",
    "SessionLocal",
    "get_connection_manager",
    "get_db_router",
    "reset_connection_manager",
    "ConnectionManager",
    "DatabaseRouter",
]
