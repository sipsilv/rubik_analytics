"""
API endpoints for Corporate Announcements
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
import duckdb
import os
from app.core.config import settings
from datetime import datetime

router = APIRouter()


def get_announcements_db_path() -> str:
    """Get path to announcements DuckDB database"""
    data_dir = os.path.abspath(settings.DATA_DIR)
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    return db_path


@router.get("/announcements")
async def get_announcements(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get corporate announcements from DuckDB
    
    REST GET FLOW (per master prompt):
    1. Query DuckDB first (single source of truth)
    2. IF data exists → return
    3. IF data missing → call TrueData REST API (future enhancement)
    4. Save fetched data into DuckDB
    5. Return updated response
    
    This endpoint MUST NEVER:
    - Open WebSocket
    - Restart WebSocket
    - Poll repeatedly
    
    WebSocket is the primary source for real-time announcements.
    REST API is only for filling gaps when data is missing.
    
    Returns announcements in reverse chronological order (latest first)
    """
    try:
        db_path = get_announcements_db_path()
        
        if not os.path.exists(db_path):
            return {
                "announcements": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        conn = duckdb.connect(db_path)
        
        # Check if table exists by trying to query it
        # If table doesn't exist, DuckDB will raise an exception
        try:
            # Try to get total count - this will fail if table doesn't exist
            total_result = conn.execute(
                "SELECT COUNT(*) FROM corporate_announcements"
            ).fetchone()
            total = total_result[0] if total_result else 0
        except Exception as count_error:
            # Table doesn't exist yet (no announcements received)
            conn.close()
            return {
                "announcements": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        # Get announcements (reverse chronological order)
        try:
            announcements = conn.execute("""
                SELECT 
                    id,
                    tradedate,
                    company_name,
                    headline,
                    news_sub,
                    news_body,
                    symbol_nse,
                    symbol_bse,
                    descriptor,
                    received_at,
                    created_at
                FROM corporate_announcements
                ORDER BY received_at DESC, created_at DESC
                LIMIT ? OFFSET ?
            """, [limit, offset]).fetchall()
        except Exception as query_error:
            conn.close()
            return {
                "announcements": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        conn.close()
        
        # Convert to list of dicts
        result = []
        for ann in announcements:
            result.append({
                "id": ann[0],
                "tradedate": ann[1],
                "company_name": ann[2],
                "headline": ann[3],
                "news_sub": ann[4],
                "news_body": ann[5],
                "symbol_nse": ann[6],
                "symbol_bse": ann[7],
                "descriptor": ann[8],
                "received_at": ann[9].isoformat() if ann[9] else None,
                "created_at": ann[10].isoformat() if ann[10] else None
            })
        
        return {
            "announcements": result,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching announcements: {str(e)}")



