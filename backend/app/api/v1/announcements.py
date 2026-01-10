"""
Corporate Announcements API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
import requests

from app.core.database import get_db
from app.core.permissions import get_current_user, get_admin_user
from app.models.user import User
from app.services.announcements_service import get_announcements_service
from app.services.truedata_api_service import get_truedata_api_service
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class LinkModel(BaseModel):
    """Link model"""
    title: Optional[str] = None
    url: str

class AnnouncementResponse(BaseModel):
    """Announcement response model"""
    id: str
    trade_date: Optional[str] = None
    script_code: Optional[int] = None
    symbol_nse: Optional[str] = None
    symbol_bse: Optional[str] = None
    company_name: Optional[str] = None
    file_status: Optional[str] = None
    news_headline: Optional[str] = None
    news_subhead: Optional[str] = None
    news_body: Optional[str] = None
    descriptor_id: Optional[int] = None
    descriptor_name: Optional[str] = None
    descriptor_category: Optional[str] = None
    announcement_type: Optional[str] = None
    meeting_type: Optional[str] = None
    date_of_meeting: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    links: Optional[List[LinkModel]] = []
    # Note: attachments field removed - attachments are NOT in payload
    # They must be fetched separately via /{announcement_id}/attachment endpoint

    class Config:
        from_attributes = True


class AnnouncementListResponse(BaseModel):
    """Paginated announcement list response"""
    announcements: List[AnnouncementResponse]
    total: int
    limit: Optional[int] = None
    offset: int = 0
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None


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
            logger.debug(f"Batch loaded {len(descriptor_metadata)} descriptor metadata entries")
        
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
                
                # Ensure all required fields are present
                if not enriched_ann.get("id"):
                    logger.warning(f"Skipping announcement without ID: {enriched_ann}")
                    continue
                
                # Add links (empty for now, can be populated from TrueData later)
                # Note: Attachments are NOT in announcement payload - they must be fetched separately via /attachment endpoint
                if "links" not in enriched_ann:
                    enriched_ann["links"] = []
                # Do NOT add attachments - they don't exist in payload
                # Attachments must be fetched on-demand via /{announcement_id}/attachment endpoint
                
                enriched.append(AnnouncementResponse(**enriched_ann))
            except Exception as e:
                logger.warning(f"Error enriching announcement {ann.get('id', 'unknown')}: {e}", exc_info=True)
                # Still add the announcement without enrichment
                try:
                    if ann.get("id"):
                        enriched.append(AnnouncementResponse(**ann))
                except Exception as e2:
                    logger.error(f"Failed to create response for announcement {ann.get('id', 'unknown')}: {e2}")
                    continue
        
        logger.info(f"Successfully enriched {len(enriched)} announcements for response")
        
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
        
        # Check WebSocket service status
        from app.services.announcements_websocket_service import get_announcements_websocket_service
        ws_service = get_announcements_websocket_service()
        
        # Check if WebSocket is running and connected
        ws_running = ws_service.running if ws_service else False
        # Check if websocket exists and is open (websockets library uses open property)
        ws_connected = False
        if ws_service and ws_running and ws_service.websocket is not None:
            try:
                # Check if websocket is open (websockets library)
                ws_connected = ws_service.websocket.open if hasattr(ws_service.websocket, 'open') else ws_running
            except:
                ws_connected = ws_running  # Fallback to running status
        
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
        announcements, total = service.get_announcements(limit=1, offset=0)
        
        # Get recent announcements count (last 24 hours)
        from datetime import datetime, timedelta, timezone
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_announcements, _ = service.get_announcements(from_date=yesterday.split('T')[0])
        
        # Get WebSocket status
        from app.services.announcements_websocket_service import get_announcements_websocket_service
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


class FetchAnnouncementsRequest(BaseModel):
    """Request model for fetching announcements"""
    connection_id: int
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    symbol: Optional[str] = None
    top_n: Optional[int] = None


@router.post("/fetch", response_model=dict)
async def fetch_announcements(
    request: FetchAnnouncementsRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),  # Changed to allow all users
    db: Session = Depends(get_db)
):
    """Fetch announcements from TrueData REST API"""
    try:
        service = get_announcements_service()
        
        # Fetch from TrueData
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
        
        # Provide helpful error messages based on error type
        if "404" in error_msg or "not found" in error_msg.lower():
            detail = (
                "TrueData announcements REST endpoint not found. "
                "This may mean: 1) The endpoint name is incorrect, "
                "2) Your TrueData plan doesn't include this API, "
                "3) The endpoint requires different authentication. "
                "Please check TrueData documentation or contact TrueData support. "
                "Alternatively, use WebSocket for real-time announcements."
            )
            raise HTTPException(status_code=404, detail=detail)
        elif "Invalid JSON" in error_msg or "Empty response" in error_msg:
            detail = (
                "TrueData API returned an invalid or empty response. "
                "This may indicate: 1) The endpoint exists but returned an error page, "
                "2) Authentication issues, 3) API rate limiting. "
                "Please check your TrueData connection and token status."
            )
            raise HTTPException(status_code=502, detail=detail)
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/{announcement_id}/attachment")
async def get_announcement_attachment(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get announcement attachment file (DB-first, then TrueData if needed)
    
    This endpoint:
    1. Checks database first for cached attachment
    2. If not found, fetches from TrueData API
    3. Stores in database for future use
    4. Returns the file
    
    Note: Attachments are NOT included in announcement payloads.
    They must be fetched separately using this endpoint.
    """
    try:
        service = get_announcements_service()
        
        # Check database first
        attachment = service.get_attachment(announcement_id)
        
        if attachment:
            # Found in database, return it
            logger.info(f"Returning attachment for {announcement_id} from database")
            from fastapi.responses import StreamingResponse
            import io
            
            return StreamingResponse(
                io.BytesIO(attachment['data']),
                media_type=attachment['content_type'],
                headers={
                    "Content-Disposition": f'attachment; filename="announcement-{announcement_id}.pdf"'
                }
            )
        
        # Not in database, fetch from TrueData
        logger.info(f"Attachment not in database for {announcement_id}, fetching from TrueData")
        
        # Get connection ID from TrueData connection
        from app.models.connection import Connection
        truedata_conn = db.query(Connection).filter(
            Connection.provider == "TrueData",
            Connection.is_enabled == True
        ).first()
        
        if not truedata_conn:
            raise HTTPException(status_code=404, detail="TrueData connection not found")
        
        api_service = get_truedata_api_service(truedata_conn.id, db_session=db)
        
        # Fetch binary file from TrueData
        response = api_service.get_announcement_attachment(announcement_id)
        
        # Get content
        attachment_data = response.content
        content_type = response.headers.get('Content-Type', 'application/pdf')
        
        # Store in database for future use
        try:
            service.store_attachment(announcement_id, attachment_data, content_type)
            logger.info(f"Stored attachment for {announcement_id} in database")
        except Exception as store_error:
            logger.warning(f"Failed to store attachment in database: {store_error}")
            # Continue anyway - we can still return the file
        
        # Return binary file stream
        from fastapi.responses import StreamingResponse
        import io
        
        return StreamingResponse(
            io.BytesIO(attachment_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="announcement-{announcement_id}.pdf"'
            }
        )
    except HTTPException:
        raise
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error getting attachment {announcement_id}: {e}")
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out. The attachment may be large or the server is experiencing high load. Please try again later."
        )
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error getting attachment {announcement_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Unable to connect to the server. Please check your internet connection and try again."
        )
    except requests.exceptions.HTTPError as e:
        # Check if this is a "file not found" error
        # TrueData API sometimes returns 500 with "File does not exist" instead of 404
        is_not_found = False
        if e.response:
            if e.response.status_code == 404:
                is_not_found = True
            elif e.response.status_code == 500:
                # Check if marked as file not found or if error message indicates file not found
                if hasattr(e, 'is_file_not_found') and e.is_file_not_found:
                    is_not_found = True
                else:
                    error_text = e.response.text if hasattr(e.response, 'text') else str(e.response)
                    if "File does not exist" in error_text or "file does not exist" in error_text.lower():
                        is_not_found = True
        
        if is_not_found:
            logger.info(f"Attachment not found for announcement {announcement_id}")
            raise HTTPException(status_code=404, detail=f"Attachment not found for announcement {announcement_id}. The file may not be available.")
        
        # For other HTTP errors, provide more context
        status_code = e.response.status_code if e.response else 500
        error_detail = f"Error fetching attachment"
        if e.response:
            error_text = e.response.text[:200] if hasattr(e.response, 'text') else str(e.response)
            if error_text:
                error_detail += f": {error_text}"
        
        logger.error(f"HTTP error getting attachment {announcement_id}: {status_code} - {error_detail}")
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting attachment {announcement_id}: {error_msg}", exc_info=True)
        
        # Provide user-friendly error messages
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise HTTPException(
                status_code=504,
                detail="Request timed out. Please try again later."
            )
        elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to the server. Please check your connection and try again."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching attachment: {error_msg}"
            )


class RefreshDescriptorsRequest(BaseModel):
    """Request model for refreshing descriptors"""
    connection_id: int


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

