import duckdb
import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.core.security import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

# Correct path based on implementation plan: root/data/News/ai/news_aidb.duckdb
# We need to resolve this relative to the backend or project root
# Assuming 'backend' is current working dir or similar
# Based on existing patterns:
# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")
# But let's check `backend/app/services/telegram_extractor/config.py` pattern if possible.
# Using a fixed relative path for now to match the user request "data/News/ai/news_aidb.duckdb"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(BASE_DIR, "data")
AI_DB_PATH = os.path.join(DATA_DIR, "News", "ai", "news_aidb.duckdb")

def get_ai_conn():
    ai_dir = os.path.dirname(AI_DB_PATH)
    if not os.path.exists(ai_dir):
        os.makedirs(ai_dir, exist_ok=True)
    return duckdb.connect(AI_DB_PATH)

def ensure_ai_schema():
    """Ensure AI Connections table exists."""
    conn = get_ai_conn()
    try:
        query = """
        CREATE SEQUENCE IF NOT EXISTS seq_ai_conn_id START 1;
        CREATE TABLE IF NOT EXISTS ai_connections (
            connection_id BIGINT DEFAULT nextval('seq_ai_conn_id') PRIMARY KEY,
            connection_name TEXT,
            provider_type TEXT,
            base_url TEXT,
            api_key TEXT,
            model_name TEXT,
            timeout_seconds INTEGER DEFAULT 30,
            ai_prompt_template TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            is_active BOOLEAN DEFAULT FALSE,
            status TEXT DEFAULT 'DISCONNECTED',
            last_checked_at TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn.execute(query)
    except Exception as e:
        logger.error(f"AI Schema Init Error: {e}")
        raise
    finally:
        conn.close()

def get_all_ai_connections() -> List[Dict[str, Any]]:
    """Fetch all AI connections."""
    ensure_ai_schema() 
    conn = get_ai_conn()
    try:
        # Columns: connection_id, connection_name, provider_type, base_url, api_key, model_name, timeout_seconds, ai_prompt_template, is_enabled, is_active, status, last_checked_at, last_error, created_at, updated_at
        rows = conn.execute("SELECT * FROM ai_connections ORDER BY connection_id ASC").fetchall()
        result = []
        for row in rows:
            # Mask API Key
            masked_key = "********" if row[4] else ""
            
            result.append({
                "id": -abs(row[0]), # Negative ID to distinguish from SQL DB IDs in frontend
                "db_id": row[0], # Real ID for internal use
                "name": row[1],
                "provider": row[2],
                "base_url": row[3],
                "has_api_key": bool(row[4]), # Don't return the key, just if it exists
                "model_name": row[5],
                "timeout_seconds": row[6],
                "ai_prompt_template": row[7],
                "is_enabled": row[8],
                "is_active": row[9],
                "status": row[10],
                "last_checked_at": row[11],
                "last_error": row[12],
                "created_at": row[13],
                "updated_at": row[14],
                "connection_type": "AI_ML" # Standardize for UI
            })
        return result
    finally:
        conn.close()

def get_ai_connection(db_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single AI connection."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        row = conn.execute("SELECT * FROM ai_connections WHERE connection_id = ?", [db_id]).fetchone()
        if not row:
            return None
            
        # Decrypt API Key if needed for internal usage, but for API response usually we mask it
        # This function might be used by the worker which needs the REAL key.
        # But if used by API, we should verify context. 
        # For now, return raw (encrypted key) and let caller decrypt if needed.
        
        return {
            "connection_id": row[0],
            "connection_name": row[1],
            "provider_type": row[2],
            "base_url": row[3],
            "api_key": row[4], # Encrypted
            "model_name": row[5],
            "timeout_seconds": row[6],
            "ai_prompt_template": row[7],
            "is_enabled": row[8],
            "is_active": row[9],
            "status": row[10],
            "last_checked_at": row[11],
            "last_error": row[12],
            "created_at": row[13],
            "updated_at": row[14]
        }
    finally:
        conn.close()

def update_ai_connection(
    db_id: int, 
    prompt_template: Optional[str] = None,
    model_name: Optional[str] = None,
    timeout: Optional[int] = None,
    is_active: Optional[bool] = None,
    # Other fields?
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
):
    """Update AI connection fields."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        # Build Update Query
        updates = []
        params = []
        
        if prompt_template is not None:
            updates.append("ai_prompt_template = ?")
            params.append(prompt_template)
            
        if model_name is not None:
            updates.append("model_name = ?")
            params.append(model_name)
            
        if timeout is not None:
            updates.append("timeout_seconds = ?")
            params.append(timeout)
            
        if base_url is not None:
            updates.append("base_url = ?")
            params.append(base_url)
            
        if api_key is not None:
            # Encrypt
            encrypted = encrypt_data(api_key)
            updates.append("api_key = ?")
            params.append(encrypted)
            
        if is_active is not None:
            # Transactional Active Update
            if is_active:
                conn.execute("BEGIN TRANSACTION")
                # Check eligibility: Must be ENABLED. (Status check might be too strict if we want to allow retry, but requirement says 'Disabled or Failed AI cannot be active')
                # Let's check Enabled status. Status check is tricky because 'FAILED' might be transient.
                # Requirement: "Disabled or Failed AI cannot be active"
                check = conn.execute("SELECT is_enabled, status FROM ai_connections WHERE connection_id = ?", [db_id]).fetchone()
                if not check or not check[0]: # Not enabled
                     conn.execute("ROLLBACK")
                     raise ValueError("Cannot activate a disabled AI connection.")
                if check[1] == 'ERROR': # Failed
                     conn.execute("ROLLBACK")
                     raise ValueError("Cannot activate a failed AI connection. Please fix the connection first.")

                # Deactivate all others
                conn.execute("UPDATE ai_connections SET is_active = FALSE")
                # Activate this one
                conn.execute("UPDATE ai_connections SET is_active = TRUE WHERE connection_id = ?", [db_id])
                conn.execute("COMMIT")
                # We don't add to updates list because we just did it
            else:
                # Just setting to false
                updates.append("is_active = ?")
                params.append(False)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE ai_connections SET {', '.join(updates)} WHERE connection_id = ?"
            params.append(db_id)
            conn.execute(query, params)
            
    except Exception as e:
        logger.error(f"Error updating AI connection {db_id}: {e}")
        # Rollback if transaction started? DuckDB handles auto-rollback on exception usually
        raise
    finally:
        conn.close()

def create_ai_connection(data: Dict[str, Any]):
    """Create a new AI connection (Usually via seed or API)."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        # Encrypt key
        enc_key = None
        if data.get('api_key'):
             enc_key = encrypt_data(data['api_key'])
             
        query = """
        INSERT INTO ai_connections (
            connection_name, provider_type, base_url, api_key, model_name, 
            timeout_seconds, ai_prompt_template, is_enabled, is_active, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(query, [
            data['name'], 
            data['provider'], 
            data.get('base_url'), 
            enc_key, 
            data.get('model_name'), 
            data.get('timeout', 30), 
            data.get('prompt', ''), 
            data.get('is_enabled', True), 
            False, # Default inactive
            'DISCONNECTED'
        ])
    finally:
        conn.close()

def get_active_ai_connection() -> Optional[Dict[str, Any]]:
    """Get the currently active AI connection for the worker."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        row = conn.execute("SELECT * FROM ai_connections WHERE is_active = TRUE AND is_enabled = TRUE").fetchone()
        if not row:
            return None
            
        return {
            "connection_id": row[0],
            "connection_name": row[1],
            "provider_type": row[2],
            "base_url": row[3],
            "api_key": row[4], # Encrypted
            "model_name": row[5],
            "timeout_seconds": row[6],
            "ai_prompt_template": row[7],
            "created_at": row[13]
        }
    finally:
        conn.close()

def update_ai_status(db_id: int, status: str, error: Optional[str] = None):
    """Update the status of an AI connection."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        now = datetime.now()
        if error:
            query = "UPDATE ai_connections SET status = ?, last_checked_at = ?, last_error = ? WHERE connection_id = ?"
            conn.execute(query, [status, now, error, db_id])
        else:
            query = "UPDATE ai_connections SET status = ?, last_checked_at = ?, last_error = NULL WHERE connection_id = ?"
            conn.execute(query, [status, now, db_id])
    except Exception as e:
        logger.error(f"Error updating AI status for {db_id}: {e}")
    finally:
        conn.close()

def delete_ai_connection(db_id: int) -> bool:
    """Delete an AI connection."""
    ensure_ai_schema()
    conn = get_ai_conn()
    try:
        # Check if exists
        curr = conn.execute("SELECT connection_id FROM ai_connections WHERE connection_id = ?", [db_id]).fetchone()
        if not curr:
            return False
            
        conn.execute("DELETE FROM ai_connections WHERE connection_id = ?", [db_id])
        return True
    except Exception as e:
        logger.error(f"Error deleting AI connection {db_id}: {e}")
        return False
    finally:
        conn.close()
