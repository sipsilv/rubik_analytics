from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
import uuid

from app.core.auth.permissions import get_admin_user
from app.models.user import User
from app.services.screener_service import ScreenerService

router = APIRouter()

# Dependency for ScreenerService (Singleton-like behavior usually desired for state, 
# but ScreenerService has class-level state, so simple instantiation is fine)
def get_screener_service() -> ScreenerService:
    return ScreenerService()

@router.post("/scrape/start")
async def start_scraping(
    connection_id: Optional[int] = None,
    triggered_by: str = "manual",
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Start a background scraping job"""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    trigger_user = f"user:{current_user.username}" if triggered_by == "manual" else triggered_by
    
    # Start the job in background (handled by Service thread management)
    service.start_scraping(job_id, trigger_user, connection_id)
    
    return {"job_id": job_id, "status": "STARTED", "message": "Scraping job started in background"}

@router.post("/scrape/stop/{connection_id}")
async def stop_scraping(
    connection_id: int,
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Stop a running scraping job for a connection"""
    service.stop_scraping(connection_id)
    return {"message": f"Stop signal sent for connection {connection_id}"}

@router.get("/scrape/status/{job_id}")
async def get_scraping_status(
    job_id: str,
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Get status of a scraping job"""
    status = service.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status

@router.get("/scrape/history")
async def get_scraping_history(
    limit: int = 20,
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Get history of scraping jobs"""
    return service.get_scraping_history(limit)

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Get Screener statistics"""
    return service.get_stats()

@router.get("/connections")
async def get_connections(
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Get all screener connections"""
    return service.get_connections()

@router.patch("/connections/{connection_id}")
async def update_connection(
    connection_id: int,
    data: dict,
    current_user: User = Depends(get_admin_user),
    service: ScreenerService = Depends(get_screener_service)
):
    """Update a screener connection"""
    service.update_connection(connection_id, data)
    return {"message": "Connection updated successfully"}
