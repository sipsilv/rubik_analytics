import duckdb
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

from app.services.news_ai.config import AI_DB_PATH

def get_ai_enrichment_conn():
    """Get connection to AI enrichment database."""
    ai_dir = os.path.dirname(AI_DB_PATH)
    if not os.path.exists(ai_dir):
        os.makedirs(ai_dir, exist_ok=True)
    return duckdb.connect(AI_DB_PATH)

def ensure_enrichment_config_schema():
    """Ensure AI enrichment config table exists."""
    conn = get_ai_enrichment_conn()
    try:
        query = """
        CREATE SEQUENCE IF NOT EXISTS seq_ai_enrichment_config_id START 1;
        CREATE TABLE IF NOT EXISTS ai_enrichment_config (
            config_id INTEGER DEFAULT nextval('seq_ai_enrichment_config_id') PRIMARY KEY,
            connection_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn.execute(query)
    except Exception as e:
        logger.error(f"AI Enrichment Config Schema Init Error: {e}")
        raise
    finally:
        conn.close()

def get_all_enrichment_configs() -> List[Dict[str, Any]]:
    """Fetch all AI enrichment configurations."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        rows = conn.execute("SELECT * FROM ai_enrichment_config ORDER BY config_id DESC").fetchall()
        result = []
        for row in rows:
            result.append({
                "config_id": row[0],
                "connection_id": row[1],
                "model_name": row[2],
                "prompt_text": row[3],
                "is_active": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
            })
        return result
    finally:
        conn.close()

def get_enrichment_config(config_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single AI enrichment configuration."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        row = conn.execute("SELECT * FROM ai_enrichment_config WHERE config_id = ?", [config_id]).fetchone()
        if not row:
            return None
        
        return {
            "config_id": row[0],
            "connection_id": row[1],
            "model_name": row[2],
            "prompt_text": row[3],
            "is_active": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None,
        }
    finally:
        conn.close()

def get_active_enrichment_config() -> Optional[Dict[str, Any]]:
    """Get the currently active AI enrichment configuration."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        row = conn.execute("SELECT * FROM ai_enrichment_config WHERE is_active = TRUE").fetchone()
        if not row:
            return None
        
        return {
            "config_id": row[0],
            "connection_id": row[1],
            "model_name": row[2],
            "prompt_text": row[3],
            "is_active": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None,
        }
    finally:
        conn.close()

def create_enrichment_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new AI enrichment configuration."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # If this config should be active, deactivate all others
        if data.get('is_active', False):
            conn.execute("UPDATE ai_enrichment_config SET is_active = FALSE")
        
        query = """
        INSERT INTO ai_enrichment_config (
            connection_id, model_name, prompt_text, is_active
        ) VALUES (?, ?, ?, ?)
        """
        conn.execute(query, [
            data['connection_id'],
            data['model_name'],
            data['prompt_text'],
            data.get('is_active', False)
        ])
        
        # Get the newly created config
        new_config = conn.execute(
            "SELECT * FROM ai_enrichment_config ORDER BY config_id DESC LIMIT 1"
        ).fetchone()
        
        conn.execute("COMMIT")
        
        return {
            "config_id": new_config[0],
            "connection_id": new_config[1],
            "model_name": new_config[2],
            "prompt_text": new_config[3],
            "is_active": new_config[4],
            "created_at": new_config[5].isoformat() if new_config[5] else None,
            "updated_at": new_config[6].isoformat() if new_config[6] else None,
        }
    except Exception as e:
        conn.execute("ROLLBACK")
        logger.error(f"Error creating AI enrichment config: {e}")
        raise
    finally:
        conn.close()

def update_enrichment_config(config_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing AI enrichment configuration."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Build update query
        updates = []
        params = []
        
        if 'connection_id' in data:
            updates.append("connection_id = ?")
            params.append(data['connection_id'])
        
        if 'model_name' in data:
            updates.append("model_name = ?")
            params.append(data['model_name'])
        
        if 'prompt_text' in data:
            updates.append("prompt_text = ?")
            params.append(data['prompt_text'])
        
        if 'is_active' in data:
            # If activating this config, deactivate all others first
            if data['is_active']:
                conn.execute("UPDATE ai_enrichment_config SET is_active = FALSE")
            updates.append("is_active = ?")
            params.append(data['is_active'])
        
        # Always update timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        if updates:
            query = f"UPDATE ai_enrichment_config SET {', '.join(updates)} WHERE config_id = ?"
            params.append(config_id)
            conn.execute(query, params)
        
        # Get updated config
        updated_config = conn.execute(
            "SELECT * FROM ai_enrichment_config WHERE config_id = ?",
            [config_id]
        ).fetchone()
        
        conn.execute("COMMIT")
        
        if not updated_config:
            raise ValueError(f"Config {config_id} not found")
        
        return {
            "config_id": updated_config[0],
            "connection_id": updated_config[1],
            "model_name": updated_config[2],
            "prompt_text": updated_config[3],
            "is_active": updated_config[4],
            "created_at": updated_config[5].isoformat() if updated_config[5] else None,
            "updated_at": updated_config[6].isoformat() if updated_config[6] else None,
        }
    except Exception as e:
        conn.execute("ROLLBACK")
        logger.error(f"Error updating AI enrichment config {config_id}: {e}")
        raise
    finally:
        conn.close()

def delete_enrichment_config(config_id: int) -> bool:
    """Delete an AI enrichment configuration."""
    ensure_enrichment_config_schema()
    conn = get_ai_enrichment_conn()
    try:
        # Check if exists
        curr = conn.execute(
            "SELECT config_id FROM ai_enrichment_config WHERE config_id = ?",
            [config_id]
        ).fetchone()
        if not curr:
            return False
        
        conn.execute("DELETE FROM ai_enrichment_config WHERE config_id = ?", [config_id])
        return True
    except Exception as e:
        logger.error(f"Error deleting AI enrichment config {config_id}: {e}")
        return False
    finally:
        conn.close()
