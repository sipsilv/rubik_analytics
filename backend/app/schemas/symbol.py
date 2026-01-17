from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime

class SymbolBase(BaseModel):
    exchange: str
    trading_symbol: str
    exchange_token: Optional[str] = None
    name: Optional[str] = None
    instrument_type: Optional[str] = None
    segment: Optional[str] = None
    series: Optional[str] = None
    series_description: Optional[str] = None
    isin: Optional[str] = None
    expiry_date: Optional[date] = None
    strike_price: Optional[float] = None
    lot_size: Optional[int] = None
    status: str = "ACTIVE"
    source: Optional[str] = "MANUAL"

class SymbolCreate(SymbolBase):
    pass

class SymbolResponse(SymbolBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaginatedSymbolResponse(BaseModel):
    items: List[SymbolResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class PreviewResponse(BaseModel):
    headers: List[str]
    rows: List[dict]
    total_rows: int
    preview_id: str

class ScriptBase(BaseModel):
    name: str
    description: Optional[str] = None
    content: str

class ScriptCreate(ScriptBase):
    pass

class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None

class ScriptResponse(ScriptBase):
    id: int
    version: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AutoUploadRequest(BaseModel):
    url: str
    headers: Optional[Dict[str, Any]] = None
    auth_type: Optional[str] = None
    auth_value: Optional[str] = None
    file_type: Optional[str] = "AUTO"
    script_id: Optional[int] = None

class SchedulerSource(BaseModel):
    url: str
    headers: Optional[Dict[str, Any]] = None
    auth_type: Optional[str] = None
    auth_value: Optional[str] = None
    file_type: Optional[str] = "AUTO"

class SchedulerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    mode: str  # RUN_ONCE, INTERVAL, or CRON
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None  # minutes, hours, days, etc.
    cron_expression: Optional[str] = None
    script_id: Optional[int] = None
    is_active: bool = True
    sources: List[SchedulerSource]

class SchedulerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[str] = None
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    cron_expression: Optional[str] = None
    script_id: Optional[int] = None
    is_active: Optional[bool] = None
    sources: Optional[List[SchedulerSource]] = None

class SchedulerResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    mode: str
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    cron_expression: Optional[str] = None
    script_id: Optional[int] = None
    is_active: bool
    sources: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[int] = None
    last_run_status: Optional[str] = None  # Status from upload logs (SUCCESS, FAILED, etc.)

    class Config:
        from_attributes = True


class BulkDeleteRequest(BaseModel):
    ids: List[int]
    hard_delete: bool = False

class BulkStatusRequest(BaseModel):
    ids: List[int]
    status: str
