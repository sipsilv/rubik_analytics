from pydantic import BaseModel
from typing import List, Optional

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


class FetchAnnouncementsRequest(BaseModel):
    """Request model for fetching announcements"""
    connection_id: int
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    symbol: Optional[str] = None
    top_n: Optional[int] = None


class RefreshDescriptorsRequest(BaseModel):
    """Request model for refreshing descriptors"""
    connection_id: int
