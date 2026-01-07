"""
Corporate Announcements API
Serves announcements from database to UI.

UI reads ONLY from database - never calls TrueData directly.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import Optional, List
import os
import duckdb
import json
import logging
import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.connection import Connection
from app.core.permissions import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def get_announcements_db_path() -> str:
    """Get path to corporate announcements database."""
    db_dir = os.path.join(settings.DATA_DIR, "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "corporate_announcements.duckdb")


@router.get("/announcements")
async def get_announcements(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get corporate announcements with pagination and search.
    
    Returns:
        - unique_hash (unique identifier)
        - announcement_datetime (source datetime, UTC)
        - company_info (Company Name | NSE: SYMBOL | BSE: SYMBOL | ISIN: CODE)
        - headline
        - category
        - attachments (JSON array: [{file_name, file_url, mime_type}, ...])
        - source_link
        - created_at (system timestamp)
    
    Ordered by announcement_datetime DESC.
    """
    db_path = get_announcements_db_path()
    
    if not os.path.exists(db_path):
        return {
            "announcements": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }
    
    conn = duckdb.connect(db_path, read_only=True)
    
    try:
        # Build search condition
        search_condition = ""
        search_params = []
        
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            search_condition = """
                WHERE (
                    headline ILIKE ? OR
                    company_info ILIKE ? OR
                    category ILIKE ?
                )
            """
            search_params = [search_term, search_term, search_term]
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) FROM corporate_announcements
            {search_condition}
        """
        total_result = conn.execute(count_query, search_params).fetchone()
        total = total_result[0] if total_result else 0
        
        # Get announcements - ordered by announcement_datetime DESC
        query = f"""
            SELECT 
                unique_hash,
                announcement_datetime,
                company_info,
                headline,
                category,
                attachments,
                source_link,
                created_at
            FROM corporate_announcements
            {search_condition}
            ORDER BY announcement_datetime DESC NULLS LAST, created_at DESC
            LIMIT ? OFFSET ?
        """
        
        rows = conn.execute(query, search_params + [limit, offset]).fetchall()
        
        # Convert to list of dicts
        announcements = []
        for row in rows:
            # Parse company_info to extract components
            company_info = row[2] or ""
            company_name, nse_symbol, bse_symbol, isin = _parse_company_info(company_info)
            
            # Parse attachments JSON
            attachments = []
            try:
                if row[5]:
                    attachments = json.loads(row[5]) if isinstance(row[5], str) else row[5]
            except (json.JSONDecodeError, TypeError):
                pass
            
            announcements.append({
                "unique_hash": row[0],
                "announcement_datetime": row[1].isoformat() if row[1] else None,
                "company_info": company_info,
                "company_name": company_name,
                "symbol_nse": nse_symbol,
                "symbol_bse": bse_symbol,
                "isin": isin,
                "headline": row[3],
                "category": row[4],
                "attachments": attachments,
                "source_link": row[6],
                "created_at": row[7].isoformat() if row[7] else None
            })
        
        logger.info(f"Returning {len(announcements)} announcements (total: {total})")
        
        return {
            "announcements": announcements,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error fetching announcements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching announcements: {str(e)}")
    finally:
        conn.close()


def _parse_company_info(company_info: str) -> tuple:
    """
    Parse company_info string to extract components.
    
    Format: "Company Name | NSE: SYMBOL | BSE: SYMBOL | ISIN: CODE"
    
    Returns: (company_name, nse_symbol, bse_symbol, isin)
    """
    company_name = None
    nse_symbol = None
    bse_symbol = None
    isin = None
    
    if not company_info:
        return (company_name, nse_symbol, bse_symbol, isin)
    
    parts = [p.strip() for p in company_info.split("|")]
    
    for part in parts:
        if part.startswith("NSE:"):
            nse_symbol = part[4:].strip()
        elif part.startswith("BSE:"):
            bse_symbol = part[4:].strip()
        elif part.startswith("ISIN:"):
            isin = part[5:].strip()
        elif not company_name:
            # First non-prefixed part is company name
            company_name = part
    
    return (company_name, nse_symbol, bse_symbol, isin)


@router.get("/announcements/status")
async def get_announcements_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get status of announcements ingestion system.
    """
    from app.services.announcements_service import get_announcements_service
    
    service = get_announcements_service()
    
    # Get TrueData connections
    truedata_conns = db.query(Connection).filter(
        Connection.provider == "TrueData",
        Connection.connection_type == "DATA_FEED"
    ).all()
    
    workers_status = []
    for conn in truedata_conns:
        status = service.get_status(conn.id)
        workers_status.append({
            "connection_id": conn.id,
            "connection_name": conn.name,
            "is_enabled": conn.is_enabled,
            "worker_running": service.is_worker_running(conn.id),
            **status.get("stats", {})
        })
    
    # Get database stats
    db_path = get_announcements_db_path()
    total_announcements = 0
    latest_announcement = None
    
    if os.path.exists(db_path):
        ddb_conn = duckdb.connect(db_path, read_only=True)
        try:
            result = ddb_conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()
            total_announcements = result[0] if result else 0
            
            if total_announcements > 0:
                latest = ddb_conn.execute("""
                    SELECT unique_hash, headline, announcement_datetime, created_at
                    FROM corporate_announcements
                    ORDER BY announcement_datetime DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """).fetchone()
                
                if latest:
                    latest_announcement = {
                        "unique_hash": latest[0],
                        "headline": latest[1],
                        "announcement_datetime": latest[2].isoformat() if latest[2] else None,
                        "created_at": latest[3].isoformat() if latest[3] else None
                    }
        finally:
            ddb_conn.close()
    
    return {
        "workers": workers_status,
        "total_announcements": total_announcements,
        "latest_announcement": latest_announcement
    }


@router.get("/announcements/{unique_hash}/attachment/{attachment_index}")
async def get_announcement_attachment(
    unique_hash: str,
    attachment_index: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download attachment file for an announcement.
    
    Backend fetches and streams the file - never exposes TrueData URL to UI.
    """
    db_path = get_announcements_db_path()
    
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    ddb_conn = duckdb.connect(db_path, read_only=True)
    try:
        result = ddb_conn.execute("""
            SELECT attachments FROM corporate_announcements
            WHERE unique_hash = ?
        """, [unique_hash]).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        # Parse attachments
        attachments = []
        try:
            if result[0]:
                attachments = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=404, detail="No attachments available")
        
        if not attachments or attachment_index >= len(attachments):
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        attachment = attachments[attachment_index]
        file_url = attachment.get("file_url")
        file_name = attachment.get("file_name", "attachment.pdf")
        mime_type = attachment.get("mime_type", "application/octet-stream")
        
        if not file_url:
            raise HTTPException(status_code=404, detail="Attachment URL not available")
        
    finally:
        ddb_conn.close()
    
    # Fetch the file
    try:
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Determine content type
        content_type = response.headers.get("Content-Type", mime_type)
        if content_type == "application/octet-stream" and file_name.endswith(".pdf"):
            content_type = "application/pdf"
        
        return Response(
            content=response.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"'
            }
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching attachment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download attachment: {str(e)}")


# Legacy endpoint for backward compatibility
@router.get("/announcements/{announcement_id}/attachment")
async def get_announcement_attachment_legacy(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Legacy attachment endpoint - redirects to new format.
    """
    # Try to find by unique_hash (new format) or by searching
    db_path = get_announcements_db_path()
    
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    ddb_conn = duckdb.connect(db_path, read_only=True)
    try:
        result = ddb_conn.execute("""
            SELECT unique_hash, attachments FROM corporate_announcements
            WHERE unique_hash = ?
            LIMIT 1
        """, [announcement_id]).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        # Parse attachments
        attachments = []
        try:
            if result[1]:
                attachments = json.loads(result[1]) if isinstance(result[1], str) else result[1]
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=404, detail="No attachments available")
        
        if not attachments:
            raise HTTPException(status_code=404, detail="No attachments available")
        
        attachment = attachments[0]
        file_url = attachment.get("file_url")
        file_name = attachment.get("file_name", "attachment.pdf")
        mime_type = attachment.get("mime_type", "application/octet-stream")
        
        if not file_url:
            raise HTTPException(status_code=404, detail="Attachment URL not available")
        
    finally:
        ddb_conn.close()
    
    # Fetch the file
    try:
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", mime_type)
        if content_type == "application/octet-stream" and file_name.endswith(".pdf"):
            content_type = "application/pdf"
        
        return Response(
            content=response.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"'
            }
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching attachment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download attachment: {str(e)}")
