from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks, Request, Query
from typing import List, Optional
import logging

from app.core.auth.permissions import get_admin_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.symbol import SymbolResponse, PaginatedSymbolResponse, PreviewResponse, ScriptResponse, ScriptCreate, ScriptUpdate, AutoUploadRequest, SchedulerCreate, SchedulerUpdate, SchedulerResponse, SchedulerSource, BulkDeleteRequest, BulkStatusRequest
from app.services.symbols_service import SymbolsService

router = APIRouter()
logger = logging.getLogger(__name__)

def get_symbols_service() -> SymbolsService:
    return SymbolsService()

# --- Upload Endpoints ---

@router.post("/upload/manual", response_model=PreviewResponse)
async def upload_manual(
    file: UploadFile = File(...),
    script_id: Optional[str] = Form(None),
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Upload symbols from CSV/Excel file - returns preview"""
    try:
        contents = await file.read()
        s_id = int(script_id) if script_id and str(script_id).strip() else None
        
        user_info = {
            "id": current_user.id,
            "name": current_user.name,
            "username": current_user.username
        }
        
        return service.process_manual_upload_preview(contents, file.filename, s_id, user_info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in manual upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/auto", response_model=PreviewResponse)
async def upload_auto(
    request_data: AutoUploadRequest,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Download file from URL/API and process same as manual upload"""
    try:
        user_info = {
            "id": current_user.id,
            "name": current_user.name,
            "username": current_user.username
        }
        return service.process_auto_upload_preview(
            request_data.url, 
            request_data.file_type, 
            request_data.headers, 
            request_data.auth_type, 
            request_data.auth_value, 
            request_data.script_id, 
            user_info
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload/confirm")
async def confirm_upload(
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Confirm and save symbols to database"""
    try:
        preview_id = data.get("preview_id")
        if not preview_id: raise HTTPException(status_code=400, detail="preview_id is required")
        return service.confirm_upload(preview_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/upload/status/{job_id}")
async def get_upload_status(
    job_id: str,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Get upload status by job ID"""
    return service.get_upload_status(job_id)

@router.get("/upload/logs")
async def get_upload_logs(
    limit: int = 50,
    page: int = 1,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Get upload logs"""
    return service.get_upload_logs(limit, page)

# --- Symbol Management Endpoints ---

@router.get("/", response_model=PaginatedSymbolResponse)
async def get_symbols(
    search: Optional[str] = None,
    exchange: Optional[str] = None,
    status: Optional[str] = None,
    expiry: Optional[str] = None,
    sort_by: Optional[str] = None,
    page_size: int = 25,
    page: int = 1,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Get symbols with pagination and filtering"""
    return service.get_symbols(search, exchange, status, expiry, sort_by, page_size, page)

@router.post("/series-lookup/reload")
async def reload_series_lookup_endpoint(
    force: bool = Query(False),
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Reload series lookup data"""
    res = service.reload_series_lookup(force)
    if not res["success"]:
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.delete("/delete_all")
async def delete_all_symbols(
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Delete all symbols"""
    return service.delete_all_symbols({"id": current_user.id})


@router.post("/delete/bulk")
async def bulk_delete_symbols(
    request: BulkDeleteRequest,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Delete multiple symbols"""
    return service.bulk_delete(request.ids)

@router.patch("/status/bulk")
async def bulk_update_status(
    request: BulkStatusRequest,
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Update status for multiple symbols"""
    if request.status.upper() not in ["ACTIVE", "INACTIVE"]:
         raise HTTPException(status_code=400, detail="Invalid status")
    return service.bulk_update_status(request.ids, request.status.upper())

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_admin_user),
    service: SymbolsService = Depends(get_symbols_service)
):
    """Get symbols statistics"""
    return service.get_stats()

@router.get("/template")
async def get_template(current_user: User = Depends(get_admin_user)):
    """Get CSV template"""
    import csv, io
    from datetime import datetime, timedelta
    
    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["exchange", "trading_symbol", "exchange_token", "name", "instrument_type", "segment", "series", "isin", "expiry_date", "strike_price", "lot_size"]
    writer.writerow(headers)
    # Add sample rows
    writer.writerow(["NSE", "RELIANCE-EQ", "2885", "Reliance Industries", "EQ", "Equity", "EQ", "INE002A01018", "", "", "1"])
    csv_content = output.getvalue()
    output.close()
    return {"content": csv_content, "filename": "symbols_template.csv", "headers": headers}

# --- Script Endpoints ---

@router.get("/scripts", response_model=List[ScriptResponse])
async def get_scripts(service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    return [
        ScriptResponse(id=r[0], name=r[1], description=r[2], content=r[3], version=r[4], created_by=r[5], created_at=r[6], updated_at=r[7], last_used_at=r[8])
        for r in service.get_scripts()
    ]

@router.get("/scripts/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: int, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    r = service.get_script(script_id)
    if not r: raise HTTPException(status_code=404, detail="Script not found")
    return ScriptResponse(id=r[0], name=r[1], description=r[2], content=r[3], version=r[4], created_by=r[5], created_at=r[6], updated_at=r[7], last_used_at=r[8])

@router.post("/scripts", response_model=ScriptResponse)
async def create_script(script_data: ScriptCreate, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    try:
        r = service.create_script(script_data.dict(), current_user.id)
        return ScriptResponse(id=r[0], name=r[1], description=r[2], content=r[3], version=r[4], created_by=r[5], created_at=r[6], updated_at=r[7], last_used_at=r[8])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/scripts/{script_id}", response_model=ScriptResponse)
async def update_script(script_id: int, script_data: ScriptUpdate, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    try:
        r = service.update_script(script_id, script_data.dict(exclude_unset=True))
        return ScriptResponse(id=r[0], name=r[1], description=r[2], content=r[3], version=r[4], created_by=r[5], created_at=r[6], updated_at=r[7], last_used_at=r[8])
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))

@router.delete("/scripts/{script_id}")
async def delete_script(script_id: int, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    service.delete_script(script_id)
    return {"message": "Script deleted"}

# --- Scheduler Endpoints ---

@router.get("/schedulers", response_model=List[SchedulerResponse])
async def get_schedulers(service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    return service.get_schedulers()

@router.post("/schedulers", response_model=SchedulerResponse)
async def create_scheduler(data: SchedulerCreate, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    r = service.create_scheduler(data.dict(), current_user.id)
    return r

@router.put("/schedulers/{scheduler_id}", response_model=SchedulerResponse)
async def update_scheduler(scheduler_id: int, data: SchedulerUpdate, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    r = service.update_scheduler(scheduler_id, data.dict(exclude_unset=True))
    if not r: raise HTTPException(status_code=404, detail="Scheduler not found")
    return r

@router.delete("/schedulers/{scheduler_id}")
async def delete_scheduler(scheduler_id: int, service: SymbolsService = Depends(get_symbols_service), current_user: User = Depends(get_admin_user)):
    service.delete_scheduler(scheduler_id)
    return {"message": "Scheduler deleted"}
