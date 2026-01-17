from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from app.core.auth.permissions import get_current_user
from app.models.user import User
from app.services.news_service import get_news_service, NewsService

router = APIRouter()

@router.get("/backlog", response_model=dict)
def get_news_backlog(service: NewsService = Depends(get_news_service)):
    """
    Get counts of unprocessed news items in the pipeline.
    """
    return service.get_backlog()

@router.get("/")
def get_news(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(get_current_user),
    service: NewsService = Depends(get_news_service)
):
    """
    Get AI-enriched news from the final database with pagination and search.
    """
    return service.get_news(page=page, page_size=page_size, search=search)

@router.get("/status", response_model=dict)
def get_news_status(
    current_user: User = Depends(get_current_user),
    service: NewsService = Depends(get_news_service)
):
    """
    Get status of the news synchronization and WebSocket.
    """
    return service.get_status()

@router.post("/toggle")
def toggle_news_sync(
    enabled: bool,
    current_user: User = Depends(get_current_user),
    service: NewsService = Depends(get_news_service)
):
    """
    Enable or disable news synchronization.
    """
    return service.toggle_sync(enabled)
