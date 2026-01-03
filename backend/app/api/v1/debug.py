"""Debug endpoints for troubleshooting database connectivity"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import os
import logging

from app.core.database import get_db
from app.core.config import settings
from app.models.connection import Connection
from app.core.security import decrypt_data
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/db-diagnostic")
async def db_diagnostic(db: Session = Depends(get_db)):
    """Diagnostic endpoint to check database configuration and connectivity"""
    try:
        # Check user connections
        user_conns = db.query(Connection).filter(
            Connection.is_enabled == True,
            Connection.provider.in_(["sqlite", "duckdb", "duckdb_sqlalchemy", "duckdb_direct"]),
        ).all()
        
        result = {
            "data_dir": settings.DATA_DIR,
            "user_connections": []
        }
        
        for conn in user_conns:
            conn_info = {
                "id": conn.id,
                "name": conn.name,
                "provider": conn.provider,
                "connection_type": conn.connection_type,
                "is_enabled": conn.is_enabled
            }
            
            # Try to extract path
            try:
                if conn.credentials:
                    config = json.loads(decrypt_data(conn.credentials))
                    path = config.get("path") or config.get("database") or config.get("filename")
                    
                    if not path and (conn.name.endswith(".db") or conn.name.endswith(".duckdb")):
                        path = conn.name
                    
                    if path and not os.path.isabs(path):
                        data_path = os.path.join(settings.DATA_DIR, path)
                        if os.path.exists(data_path):
                            path = data_path
                        else:
                            path = os.path.abspath(path)
                    
                    conn_info["resolved_path"] = path
                    conn_info["file_exists"] = os.path.exists(path) if path else False
                    
                    # Try to query the database
                    if conn.provider.lower() in ["duckdb", "duckdb_direct"]:
                        try:
                            import duckdb
                            test_conn = duckdb.connect(path, read_only=True)
                            
                            # Get table list
                            tables = test_conn.execute("SHOW TABLES").fetchall()
                            conn_info["tables"] = [t[0] for t in tables]
                            
                            test_conn.close()
                        except Exception as e:
                            conn_info["query_error"] = str(e)
            except Exception as e:
                conn_info["config_error"] = str(e)
            
            result["user_connections"].append(conn_info)
        
        return result
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}", exc_info=True)
        return {"error": str(e)}
