# Keep the existing imports and router setup at the top
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import os
import duckdb
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.core.permissions import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

def get_announcements_db_path():
    """Get path to corporate announcements database"""
    from app.core.config import settings
    db_dir = os.path.join(settings.DATA_DIR, "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    return db_path

@router.get("/announcements")
async def get_announcements(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get corporate announcements with pagination and search
    
    Returns:
        - announcement_id
        - Symbol (symbol_nse, symbol_bse)
        - Company name (from symbols DB join)
        - Headline
        - Description
        - Category
        - Announcement datetime
        - Attachment ID
    """
    db_path = get_announcements_db_path()
    
    if not os.path.exists(db_path):
        return {
            "announcements": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }
    
    conn = duckdb.connect(db_path)
    
    try:
        # Try to attach symbols database for company name lookup
        symbols_db_attached = False
        try:
            from app.api.v1.symbols import get_symbols_db_path
            symbols_db_path = get_symbols_db_path()
            if os.path.exists(symbols_db_path):
                normalized_path = symbols_db_path.replace('\\', '/')
                conn.execute(f"ATTACH '{normalized_path}' AS symbols_db")
                # Test if accessible
                conn.execute("SELECT 1 FROM symbols_db.symbols LIMIT 1")
                symbols_db_attached = True
                logger.debug("Symbols database attached successfully")
        except Exception as attach_error:
            logger.debug(f"Could not attach symbols database: {attach_error}")
            symbols_db_attached = False
        
        # Build search condition
        search_condition = ""
        search_params = []
        if search and search.strip():
            search_term = f"%{search.strip().upper()}%"
            search_condition = """
                AND (
                    UPPER(a.headline) LIKE ? OR
                    UPPER(a.description) LIKE ? OR
                    UPPER(COALESCE(a.symbol_nse, a.symbol_bse, a.symbol, '')) LIKE ? OR
                    UPPER(a.symbol_nse) LIKE ? OR
                    UPPER(a.symbol_bse) LIKE ? OR
                    UPPER(COALESCE(s_nse.name, s_bse.name, '')) LIKE ?
                )
            """
            # Note: search_condition will be inserted after WHERE a.rn = 1
            search_params = [search_term, search_term, search_term, search_term, search_term, search_term]
        
        # Get total count with search - use same deduplication as main query
        try:
            if search and search.strip():
                # For search, count after deduplication
                count_query = f"""
                    SELECT COUNT(DISTINCT a.announcement_id)
                    FROM corporate_announcements a
                    INNER JOIN (
                        SELECT announcement_id, MAX(received_at) as max_received_at
                        FROM corporate_announcements
                        WHERE announcement_id IS NOT NULL AND announcement_id != ''
                        GROUP BY announcement_id
                    ) latest ON a.announcement_id = latest.announcement_id 
                        AND a.received_at = latest.max_received_at
                    WHERE (
                          UPPER(a.headline) LIKE ? OR
                          UPPER(a.description) LIKE ? OR
                          UPPER(COALESCE(a.symbol_nse, a.symbol_bse, a.symbol, '')) LIKE ? OR
                          UPPER(a.symbol_nse) LIKE ? OR
                          UPPER(a.symbol_bse) LIKE ?
                      )
                """
                count_params = search_params[:5]  # Remove company name param for count
                total_result = conn.execute(count_query, count_params).fetchone()
                total = total_result[0] if total_result else 0
            else:
                # No search - simple count of unique announcement_ids
                total_result = conn.execute("""
                    SELECT COUNT(DISTINCT announcement_id) 
                    FROM corporate_announcements 
                    WHERE announcement_id IS NOT NULL AND announcement_id != ''
                """).fetchone()
                total = total_result[0] if total_result else 0
        except Exception as count_error:
            logger.error(f"Error counting announcements: {count_error}")
            conn.close()
            return {
                "announcements": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        # Get announcements with symbol join
        announcements = []
        try:
            if symbols_db_attached:
                try:
                    query = f"""
                        SELECT DISTINCT
                            a.announcement_id,
                            COALESCE(a.symbol_nse, a.symbol_bse, a.symbol) as symbol,
                            a.symbol_nse,
                            a.symbol_bse,
                            a.exchange,
                            a.headline,
                            a.description,
                            a.category,
                            a.announcement_datetime,
                            a.received_at,
                            a.attachment_id,
                            COALESCE(s_nse.name, s_bse.name) as company_name
                        FROM corporate_announcements a
                        INNER JOIN (
                            SELECT announcement_id, MAX(received_at) as max_received_at
                            FROM corporate_announcements
                            WHERE announcement_id IS NOT NULL AND announcement_id != ''
                            GROUP BY announcement_id
                        ) latest ON a.announcement_id = latest.announcement_id 
                            AND a.received_at = latest.max_received_at
                        LEFT JOIN (
                            SELECT DISTINCT trading_symbol, name, exchange
                            FROM symbols_db.symbols
                            WHERE exchange = 'NSE' AND instrument_type = 'EQ'
                        ) s_nse ON 
                            a.symbol_nse IS NOT NULL 
                            AND (
                                a.symbol_nse = s_nse.trading_symbol 
                                OR a.symbol_nse || '-EQ' = s_nse.trading_symbol
                                OR REPLACE(REPLACE(REPLACE(REPLACE(s_nse.trading_symbol, '-EQ', ''), '-BE', ''), '-FUT', ''), '-OPT', '') = a.symbol_nse
                            )
                        LEFT JOIN (
                            SELECT DISTINCT trading_symbol, name, exchange
                            FROM symbols_db.symbols
                            WHERE exchange = 'BSE' AND instrument_type = 'EQ'
                        ) s_bse ON 
                            a.symbol_bse IS NOT NULL 
                            AND (
                                a.symbol_bse = s_bse.trading_symbol 
                                OR a.symbol_bse || '-EQ' = s_bse.trading_symbol
                                OR REPLACE(REPLACE(REPLACE(REPLACE(s_bse.trading_symbol, '-EQ', ''), '-BE', ''), '-FUT', ''), '-OPT', '') = a.symbol_bse
                            )
                        WHERE 1=1 {search_condition}
                        ORDER BY a.received_at DESC, a.announcement_datetime DESC
                        LIMIT ? OFFSET ?
                    """
                    announcements = conn.execute(query, search_params + [limit, offset]).fetchall()
                except Exception as join_error:
                    logger.warning(f"Symbols DB join failed, using fallback: {join_error}")
                    symbols_db_attached = False
            
            if not symbols_db_attached:
                # Fallback: query without join
                fallback_search = ""
                fallback_params = []
                if search and search.strip():
                    search_term = f"%{search.strip().upper()}%"
                    fallback_search = """
                        AND (
                            UPPER(COALESCE(a.symbol_nse, a.symbol_bse, a.symbol, '')) LIKE ? OR
                            UPPER(a.symbol_nse) LIKE ? OR
                            UPPER(a.symbol_bse) LIKE ? OR
                            UPPER(a.headline) LIKE ? OR
                            UPPER(a.description) LIKE ?
                        )
                    """
                    # Note: fallback_search will be inserted after WHERE a.rn = 1
                    fallback_params = [search_term, search_term, search_term, search_term, search_term]
                
                query = f"""
                    SELECT DISTINCT
                        a.announcement_id,
                        COALESCE(a.symbol_nse, a.symbol_bse, a.symbol) as symbol,
                        a.symbol_nse,
                        a.symbol_bse,
                        a.exchange,
                        a.headline,
                        a.description,
                        a.category,
                        a.announcement_datetime,
                        a.received_at,
                        a.attachment_id,
                        NULL as company_name
                    FROM corporate_announcements a
                    INNER JOIN (
                        SELECT announcement_id, MAX(received_at) as max_received_at
                        FROM corporate_announcements
                        WHERE announcement_id IS NOT NULL AND announcement_id != ''
                        GROUP BY announcement_id
                    ) latest ON a.announcement_id = latest.announcement_id 
                        AND a.received_at = latest.max_received_at
                    WHERE 1=1 {fallback_search}
                    ORDER BY a.received_at DESC, a.announcement_datetime DESC
                    LIMIT ? OFFSET ?
                """
                announcements = conn.execute(query, fallback_params + [limit, offset]).fetchall()
        except Exception as query_error:
            logger.error(f"Error querying announcements: {query_error}", exc_info=True)
            conn.close()
            return {
                "announcements": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        conn.close()
        
        # Convert to list of dicts - FIXED: Properly handle None values
        # Additional deduplication: Use a set to track seen announcement_ids
        seen_ids = set()
        result = []
        for ann in announcements:
            try:
                # Helper function to safely extract and clean values
                def clean_value(val, index):
                    if val is None:
                        return None
                    val_str = str(val).strip()
                    if not val_str or val_str.lower() in ['null', 'none', '']:
                        return None
                    return val_str
                
                # Extract values with proper None handling
                # Query order: announcement_id, symbol, symbol_nse, symbol_bse, exchange, headline, description, category, announcement_datetime, received_at, attachment_id, company_name
                announcement_id = str(ann[0]) if ann[0] else None
                
                # Skip if we've already seen this announcement_id (extra safety check)
                if announcement_id and announcement_id in seen_ids:
                    logger.debug(f"Skipping duplicate announcement_id in result set: {announcement_id}")
                    continue
                
                if announcement_id:
                    seen_ids.add(announcement_id)
                symbol = clean_value(ann[1], 1)
                symbol_nse = clean_value(ann[2], 2)
                symbol_bse = clean_value(ann[3], 3)
                exchange = clean_value(ann[4], 4)
                headline = clean_value(ann[5], 5)
                description = clean_value(ann[6], 6)
                category = clean_value(ann[7], 7)
                announcement_datetime = ann[8].isoformat() if ann[8] else None
                received_at = ann[9].isoformat() if ann[9] else None
                attachment_id = clean_value(ann[10], 10)
                company_name = clean_value(ann[11], 11)
                
                result.append({
                    "announcement_id": announcement_id,
                    "symbol": symbol,
                    "symbol_nse": symbol_nse,
                    "symbol_bse": symbol_bse,
                    "exchange": exchange,
                    "headline": headline,
                    "description": description,
                    "category": category,
                    "announcement_datetime": announcement_datetime,
                    "received_at": received_at,
                    "attachment_id": attachment_id,
                    "company_name": company_name
                })
            except Exception as e:
                logger.error(f"Error formatting announcement: {e}, data: {ann}", exc_info=True)
                continue
        
        logger.info(f"Returning {len(result)} announcements (total: {total})")
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
        logger.error(f"Error fetching announcements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching announcements: {str(e)}")

@router.get("/announcements/status")
async def get_announcements_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get status of announcements ingestion system
    """
    from app.services.announcements_manager import get_announcements_manager
    from app.models.connection import Connection
    
    manager = get_announcements_manager()
    
    # Get TrueData connections
    truedata_conns = db.query(Connection).filter(
        Connection.provider == "TrueData",
        Connection.connection_type == "DATA_FEED"
    ).all()
    
    status_info = {
        "worker_running": False,
        "queue_size": 0,
        "total_processed": 0,
        "last_message_at": None,
        "connection_status": "disconnected"
    }
    
    if truedata_conns:
        conn = truedata_conns[0]
        worker_status = manager.get_worker_status(conn.id)
        if worker_status:
            status_info.update(worker_status)
    
    # Get database stats
    db_path = get_announcements_db_path()
    if os.path.exists(db_path):
        conn = duckdb.connect(db_path)
        try:
            result = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()
            total_announcements = result[0] if result else 0
            
            # Get latest announcement timestamp
            if total_announcements > 0:
                latest = conn.execute("""
                    SELECT announcement_id, headline, received_at 
                    FROM corporate_announcements 
                    ORDER BY received_at DESC 
                    LIMIT 1
                """).fetchone()
                if latest:
                    status_info["latest_announcement"] = {
                        "id": str(latest[0]) if latest[0] else None,
                        "headline": str(latest[1]) if latest[1] else None,
                        "received_at": latest[2].isoformat() if latest[2] else None
                    }
            
            status_info["total_announcements"] = total_announcements
        finally:
            conn.close()
    
    return status_info


@router.get("/announcements/{announcement_id}/attachment")
async def get_announcement_attachment(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch and stream attachment file from TrueData REST API
    
    Never exposes TrueData URL to UI - backend fetches and streams
    """
    from fastapi.responses import Response
    from app.services.truedata_api_service import get_truedata_api_service
    from app.models.connection import Connection
    
    try:
        # Get announcement from DB to find attachment_id
        db_path = get_announcements_db_path()
        if not os.path.exists(db_path):
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        conn = duckdb.connect(db_path)
        try:
            result = conn.execute("""
                SELECT attachment_id, symbol_nse, symbol_bse
                FROM corporate_announcements
                WHERE announcement_id = ?
            """, [announcement_id]).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Announcement not found")
            
            attachment_id = result[0]
            if not attachment_id:
                raise HTTPException(status_code=404, detail="No attachment available")
            
            symbol_nse = result[1]
            symbol_bse = result[2]
            symbol = symbol_nse or symbol_bse
        finally:
            conn.close()
        
        # Get TrueData connection
        truedata_conn = db.query(Connection).filter(
            Connection.provider == "TrueData",
            Connection.connection_type == "DATA_FEED"
        ).first()
        
        if not truedata_conn:
            raise HTTPException(status_code=404, detail="TrueData connection not found")
        
        # Get token and fetch attachment
        api_service = get_truedata_api_service(truedata_conn.id, db)
        
        # Try to fetch attachment
        try:
            file_data = api_service.get_announcement_attachment(
                params={"announcementid": attachment_id, "symbol": symbol}
            )
        except:
            try:
                file_data = api_service.get_announcement_attachment2(
                    params={"announcementid": attachment_id, "symbol": symbol}
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to fetch attachment: {str(e)}")
        
        # If file_data is a URL, fetch it
        if isinstance(file_data, dict) and "url" in file_data:
            import requests
            response = requests.get(file_data["url"], stream=True)
            response.raise_for_status()
            
            filename = file_data.get("filename", attachment_id)
            
            return Response(
                content=response.content,
                media_type=response.headers.get("Content-Type", "application/pdf"),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        else:
            # Return file data directly
            return Response(
                content=file_data,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{attachment_id}"'
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching attachment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching attachment: {str(e)}")


async def _fetch_from_truedata_rest(
    symbol: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = None
):
    """
    Fallback: Fetch announcements from TrueData REST API if not in DB
    """
    from app.services.truedata_api_service import get_truedata_api_service
    from app.models.connection import Connection
    import json
    
    try:
        truedata_conn = db.query(Connection).filter(
            Connection.provider == "TrueData",
            Connection.connection_type == "DATA_FEED"
        ).first()
        
        if not truedata_conn:
            return []
        
        api_service = get_truedata_api_service(truedata_conn.id, db)
        
        # Fetch from TrueData REST API
        ann_data_list = api_service.get_announcements_for_companies2(
            params={"symbol": symbol, "limit": limit, "offset": offset}
        )
        
        # Store in DB and return
        db_path = get_announcements_db_path()
        conn = duckdb.connect(db_path)
        try:
            for ann_data in ann_data_list:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO corporate_announcements (
                            announcement_id, symbol, symbol_nse, symbol_bse, exchange,
                            headline, description, category, announcement_datetime,
                            received_at, attachment_id, raw_payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        ann_data.get("announcement_id") or ann_data.get("id"),
                        symbol,
                        ann_data.get("symbol_nse") or (symbol if "NSE" in str(ann_data.get("exchange", "")).upper() else None),
                        ann_data.get("symbol_bse") or (symbol if "BSE" in str(ann_data.get("exchange", "")).upper() else None),
                        ann_data.get("exchange"),
                        ann_data.get("headline") or ann_data.get("subject") or ann_data.get("title"),
                        ann_data.get("description") or ann_data.get("body"),
                        ann_data.get("category"),
                        ann_data.get("announcement_datetime") or ann_data.get("datetime"),
                        datetime.now(timezone.utc).isoformat(),
                        ann_data.get("attachment_id") or ann_data.get("attachment"),
                        json.dumps(ann_data)
                    ])
                except Exception as e:
                    logger.error(f"Error storing announcement from REST API: {e}")
                    continue
            conn.commit()
        finally:
            conn.close()
        
        # Return stored announcements
        return _fetch_from_db(symbol, limit, offset)
    except Exception as e:
        logger.error(f"Error fetching from TrueData REST API: {e}")
        return []


def _fetch_from_db(symbol: str, limit: int, offset: int):
    """Helper to fetch from DB"""
    db_path = get_announcements_db_path()
    if not os.path.exists(db_path):
        return []
    
    conn = duckdb.connect(db_path)
    try:
        result = conn.execute("""
            SELECT 
                announcement_id, symbol, symbol_nse, symbol_bse, exchange,
                headline, description, category, announcement_datetime,
                received_at, attachment_id, NULL as company_name
            FROM corporate_announcements
            WHERE symbol = ? OR symbol_nse = ? OR symbol_bse = ?
            ORDER BY received_at DESC, announcement_datetime DESC
            LIMIT ? OFFSET ?
        """, [symbol, symbol, symbol, limit, offset]).fetchall()
        
        total = conn.execute("""
            SELECT COUNT(*) FROM corporate_announcements
            WHERE symbol = ? OR symbol_nse = ? OR symbol_bse = ?
        """, [symbol, symbol, symbol]).fetchone()[0]
        
        announcements = []
        for ann in result:
            announcements.append({
                "announcement_id": str(ann[0]) if ann[0] else None,
                "symbol": str(ann[1]) if ann[1] else None,
                "symbol_nse": str(ann[2]) if ann[2] else None,
                "symbol_bse": str(ann[3]) if ann[3] else None,
                "exchange": str(ann[4]) if ann[4] else None,
                "headline": str(ann[5]) if ann[5] else None,
                "description": str(ann[6]) if ann[6] else None,
                "category": str(ann[7]) if ann[7] else None,
                "announcement_datetime": ann[8].isoformat() if ann[8] else None,
                "received_at": ann[9].isoformat() if ann[9] else None,
                "attachment_id": str(ann[10]) if ann[10] else None,
                "company_name": None
            })
        
        return {
            "announcements": announcements,
            "total": total
        }
    finally:
        conn.close()
