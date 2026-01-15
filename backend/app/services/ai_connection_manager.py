import json
import logging
from typing import Dict, Any, List, Optional
from app.core.database import SessionLocal
from app.models.connection import Connection, ConnectionType
from app.core.security import decrypt_data
from .ai_adapter import get_adapter, AIAdapter

logger = logging.getLogger(__name__)

def get_ai_connection(connection_id: int) -> Optional[Dict[str, Any]]:
    """Fetch an AI connection from the database and decrypt its credentials."""
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(
            Connection.id == connection_id,
            Connection.connection_type == ConnectionType.AI_ML.value
        ).first()
        
        if not conn:
            return None
        
        details = {}
        if conn.credentials:
            try:
                decrypted_json = decrypt_data(conn.credentials)
                details = json.loads(decrypted_json)
            except Exception as e:
                logger.error(f"Failed to decrypt credentials for connection {connection_id}: {e}")
        
        return {
            "connection_id": conn.id,
            "connection_name": conn.name,
            "provider_type": conn.provider,
            "is_enabled": conn.is_enabled,
            "status": conn.status,
            "last_checked_at": conn.last_checked_at,
            "created_at": conn.created_at,
            "updated_at": conn.updated_at,
            "details": details,
            # Flattened fields for convenience
            "base_url": details.get("base_url"),
            "model_name": details.get("model_name"),
            "api_key": details.get("api_key"),
            "timeout_seconds": details.get("timeout_seconds", 120),
            "ai_prompt_template": details.get("ai_prompt_template")
        }
    finally:
        db.close()

def get_ai_adapter_for_connection(connection_id: int) -> Optional[AIAdapter]:
    """Get an initialized AIAdapter for a given connection_id."""
    conn_data = get_ai_connection(connection_id)
    if not conn_data:
        return None
    
    return get_adapter(
        provider=conn_data["provider_type"],
        api_key=conn_data["api_key"],
        base_url=conn_data["base_url"],
        model=conn_data["model_name"],
        timeout=conn_data["timeout_seconds"]
    )

def update_ai_connection(connection_id: int, **kwargs):
    """Update AI connection details (mocking what connections.py expects if needed)."""
    # This might need to interact with the main DB if we want to support updates here.
    # For now, minimal implementation to satisfy potential imports.
    logger.info(f"Update AI connection {connection_id} called with {kwargs}")
    pass
