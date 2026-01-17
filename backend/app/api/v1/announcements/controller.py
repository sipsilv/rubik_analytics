"""
Corporate Announcements API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Response
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
import requests
import io

from app.core.database import get_db
from app.core.auth.permissions import get_current_user, get_admin_user
from app.models.user import User
from app.services.announcements_service import get_announcements_service
from app.providers.truedata_api import get_truedata_api_service
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


from app.schemas.announcement import (
    LinkModel,
    AnnouncementResponse,
    AnnouncementListResponse,
    FetchAnnouncementsRequest,
    RefreshDescriptorsRequest
)


@router.get("/", response_model=AnnouncementListResponse)
async def get_announcements(
    from_date: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (NSE or BSE)"),
    search: Optional[str] = Query(None, description="Search by headline or symbol (flexible match)"),
    limit: Optional[int] = Query(None, description="Maximum number of records (legacy)"),
    offset: int = Query(0, description="Offset for pagination (legacy)"),
    page: Optional[int] = Query(None, description="Page number (1-indexed)"),
    page_size: Optional[int] = Query(None, description="Number of records per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get corporate announcements from database with pagination"""
    try:
        service = get_announcements_service()
        
        # Use page/page_size if provided, otherwise use limit/offset
        announcements, total = service.get_announcements(
            from_date=from_date,
            to_date=to_date,
            symbol=symbol,
            search=search,
            limit=limit,
            offset=offset,
            page=page,
            page_size=page_size
        )
        
        logger.info(f"Retrieved {len(announcements)} announcements from DB, total: {total}")
        
        # Batch fetch descriptor metadata to avoid N+1 queries
        descriptor_ids = [ann.get("descriptor_id") for ann in announcements if ann.get("descriptor_id")]
        descriptor_metadata = {}
        if descriptor_ids:
            descriptor_metadata = service.get_descriptor_metadata_batch(descriptor_ids)
        
        # Enrich with descriptor metadata
        enriched = []
        for ann in announcements:
            try:
                enriched_ann = ann.copy()
                if ann.get("descriptor_id"):
                    desc_meta = descriptor_metadata.get(ann["descriptor_id"])
                    if desc_meta:
                        enriched_ann["descriptor_name"] = desc_meta.get("descriptor_name")
                        enriched_ann["descriptor_category"] = desc_meta.get("descriptor_category")
                
                if not enriched_ann.get("id"): continue
                
                if "links" not in enriched_ann:
                    enriched_ann["links"] = []
                
                enriched.append(AnnouncementResponse(**enriched_ann))
            except Exception as e:
                logger.warning(f"Error enriching announcement {ann.get('id', 'unknown')}: {e}")
                if ann.get("id"): enriched.append(AnnouncementResponse(**ann))
        
        # Calculate pagination info
        current_page = page if page else (offset // (page_size or limit or 25)) + 1
        current_page_size = page_size if page_size else (limit or 25)
        total_pages = (total + current_page_size - 1) // current_page_size if total > 0 else 1
        
        return AnnouncementListResponse(
            announcements=enriched,
            total=total,
            limit=current_page_size,
            offset=offset if not page else (current_page - 1) * current_page_size,
            page=current_page,
            page_size=current_page_size,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error getting announcements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/truedata-connection", response_model=dict)
async def get_truedata_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the first enabled TrueData connection ID"""
    try:
        from app.models.connection import Connection
        truedata_conn = db.query(Connection).filter(
            Connection.provider == "TrueData",
            Connection.is_enabled == True
        ).first()
        
        if not truedata_conn:
            return {"connection_id": None, "message": "No enabled TrueData connection found", "websocket_running": False, "websocket_connected": False}
        
        # Check WebSocket service status (lightweight check without import heavy logic if possible, 
        # but to keep exact logic we import)
        from app.providers.truedata_websocket import get_announcements_websocket_service
        ws_service = get_announcements_websocket_service()
        
        ws_running = ws_service.running if ws_service else False
        ws_connected = False
        if ws_service and ws_running and ws_service.websocket is not None:
            try:
                ws_connected = ws_service.websocket.open if hasattr(ws_service.websocket, 'open') else ws_running
            except:
                ws_connected = ws_running
        
        return {
            "connection_id": truedata_conn.id,
            "name": truedata_conn.name,
            "websocket_running": ws_running,
            "websocket_connected": ws_connected
        }
    except Exception as e:
        logger.error(f"Error getting TrueData connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db-status", response_model=dict)
async def get_database_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get database status and recent announcements count"""
    try:
        service = get_announcements_service()
        
        # Get total count
        _, total = service.get_announcements(limit=1, offset=0)
        
        # Get recent announcements count (last 24 hours)
        from datetime import datetime, timedelta, timezone
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_announcements, _ = service.get_announcements(from_date=yesterday.split('T')[0])
        
        # Get WebSocket status
        from app.providers.truedata_websocket import get_announcements_websocket_service
        ws_service = get_announcements_websocket_service()
        ws_running = ws_service.running if ws_service else False
        ws_connected = False
        if ws_service and ws_running and ws_service.websocket is not None:
            try:
                ws_connected = ws_service.websocket.open if hasattr(ws_service.websocket, 'open') else ws_running
            except:
                ws_connected = ws_running
        
        # Get most recent announcement timestamp
        recent_ann, _ = service.get_announcements(limit=1, offset=0)
        last_announcement_time = None
        if recent_ann and len(recent_ann) > 0:
            last_announcement_time = recent_ann[0].get('created_at') or recent_ann[0].get('trade_date')
        
        return {
            "total_announcements": total,
            "recent_24h_count": len(recent_announcements),
            "websocket_running": ws_running,
            "websocket_connected": ws_connected,
            "last_announcement_time": last_announcement_time,
            "database_accessible": True
        }
    except Exception as e:
        logger.error(f"Error getting database status: {e}", exc_info=True)
        return {
            "total_announcements": 0,
            "recent_24h_count": 0,
            "websocket_running": False,
            "websocket_connected": False,
            "last_announcement_time": None,
            "database_accessible": False,
            "error": str(e)
        }


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single announcement by ID"""
    try:
        service = get_announcements_service()
        announcement = service.get_announcement_by_id(announcement_id)
        
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        # Enrich with descriptor metadata
        if announcement.get("descriptor_id"):
            desc_meta = service.get_descriptor_metadata(announcement["descriptor_id"])
            if desc_meta:
                announcement["descriptor_name"] = desc_meta.get("descriptor_name")
                announcement["descriptor_category"] = desc_meta.get("descriptor_category")
        
        return AnnouncementResponse(**announcement)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting announcement: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/fetch", response_model=dict)
async def fetch_announcements(
    request: FetchAnnouncementsRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch announcements from TrueData REST API"""
    try:
        service = get_announcements_service()
        
        inserted_count = service.fetch_from_truedata_rest(
            connection_id=request.connection_id,
            from_date=request.from_date,
            to_date=request.to_date,
            symbol=request.symbol,
            top_n=request.top_n
        )
        
        return {
            "message": f"Fetched {inserted_count} new announcements",
            "inserted_count": inserted_count
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching announcements: {error_msg}")
        
        if "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail="TrueData announcements REST endpoint not found.")
        elif "Invalid JSON" in error_msg or "Empty response" in error_msg:
            raise HTTPException(status_code=502, detail="TrueData API returned an invalid or empty response.")
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/{announcement_id}/attachment")
async def get_announcement_attachment(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        service = get_announcements_service()
        
        # Check database first
        attachment = service.get_attachment(announcement_id)
        
        if attachment:
            logger.info(f"Returning attachment for {announcement_id} from database")
            return StreamingResponse(
                io.BytesIO(attachment['data']),
                media_type=attachment['content_type'],
                headers={
                    "Content-Disposition": f'attachment; filename="announcement-{announcement_id}.pdf"'
                }
            )
        
        # Not in database, fetch from TrueData
        logger.info(f"Attachment not in database for {announcement_id}, fetching from TrueData")
        
        from app.models.connection import Connection
        truedata_conn = db.query(Connection).filter(
            Connection.provider == "TrueData",
            Connection.is_enabled == True
        ).first()
        
        if not truedata_conn:
            raise HTTPException(status_code=404, detail="TrueData connection not found")
        
        api_service = get_truedata_api_service(truedata_conn.id, db_session=db)
        
        try:
            response = api_service.get_announcement_attachment(announcement_id)
            attachment_data = response.content
            content_type = response.headers.get('Content-Type', 'application/pdf')
            
            # Store in database
            service.store_attachment(announcement_id, attachment_data, content_type)
            
            return StreamingResponse(
                io.BytesIO(attachment_data),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="announcement-{announcement_id}.pdf"'
                }
            )
        except Exception as e:
            # Handle API errors similar to original
            error_msg = str(e)
            logger.error(f"Error fetching attachment: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Error fetching attachment: {error_msg}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attachment {announcement_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/descriptors/refresh")
async def refresh_descriptors(
    request: RefreshDescriptorsRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Refresh descriptor metadata from TrueData"""
    try:
        service = get_announcements_service()
        service.fetch_descriptors_from_truedata(request.connection_id)
        return {"message": "Descriptor metadata refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing descriptors: {e}")
        raise HTTPException(status_code=500, detail=str(e))
