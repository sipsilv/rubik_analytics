"""
Screener API endpoints for Company Fundamentals, News, and Corporate Actions
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import Dict, Optional
import uuid
import threading
import time
import logging
import traceback
import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.permissions import get_admin_user
from app.core.database import get_db
from app.models.user import User
import app.models.screener as screener_service

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory cache for scraping status
_scraping_status_cache: Dict[str, Dict] = {}

# Track stop flags for running jobs by connection_id
_stop_flags: Dict[int, bool] = {}
_stop_flags_lock = threading.Lock()

# Track active threads by job_id to check if scraper is still running
_active_threads: Dict[str, threading.Thread] = {}
_threads_lock = threading.Lock()

# Track connection_id to job_id mapping for proper job management
_connection_jobs: Dict[int, str] = {}  # connection_id -> job_id
_connection_jobs_lock = threading.Lock()

def process_scraping_async(job_id: str, triggered_by: str, connection_id: Optional[int] = None):
    """Process Screener scraping in background and update status cache"""
    started_at = datetime.now(timezone.utc)
    start_time = time.time()
    
    conn = None
    try:
        # Initialize status
        _scraping_status_cache[job_id] = {
            "status": "PROCESSING",
            "total_symbols": 0,
            "symbols_processed": 0,
            "symbols_succeeded": 0,
            "symbols_failed": 0,
            "total_records_inserted": 0,
            "percentage": 0,
            "triggered_by": triggered_by,
            "connection_id": connection_id,  # Store connection_id for job tracking
            "current_symbol": None,
            "current_exchange": None,
            "errors": []
        }
        
        # Track connection_id to job_id mapping
        if connection_id:
            with _connection_jobs_lock:
                _connection_jobs[connection_id] = job_id
                logger.info(f"[JOB {job_id}] Mapped to connection {connection_id}")
        
        # Get active symbols first (uses separate connection internally)
        try:
            # Get a temporary connection just for fetching symbols
            temp_conn = None
            try:
                temp_conn = screener_service.get_db_connection()
                symbols = screener_service.get_active_symbols(temp_conn)
            finally:
                if temp_conn:
                    try:
                        temp_conn.close()
                        logger.debug(f"[JOB {job_id}] Closed temporary connection after fetching symbols")
                    except:
                        pass
            total_symbols = len(symbols)
            logger.info(f"[JOB {job_id}] Found {total_symbols} unique active symbols (EQ/CASH only) to process")
            
            # Log sample of symbols being processed
            if total_symbols > 0:
                sample_symbols = symbols[:10] if len(symbols) > 10 else symbols
                logger.info(f"[JOB {job_id}] Sample symbols to scrape: {[s['symbol'] for s in sample_symbols]}")
                if total_symbols > 10:
                    logger.info(f"[JOB {job_id}] ... and {total_symbols - 10} more symbols")
        except Exception as symbols_error:
            logger.error(f"[JOB {job_id}] Failed to get active symbols: {symbols_error}", exc_info=True)
            raise
        
        _scraping_status_cache[job_id]["total_symbols"] = total_symbols
        
        if total_symbols == 0:
            error_msg = "No active symbols found (EQ/CASH only)"
            _scraping_status_cache[job_id]["status"] = "FAILED"
            _scraping_status_cache[job_id]["errors"] = [error_msg]
            logger.warning(f"[JOB {job_id}] Failed: {error_msg}")
            
            # Update connection status to Failed
            if connection_id:
                try:
                    status_conn = screener_service.get_db_connection()
                    status_conn.execute("""
                        UPDATE screener_connections 
                        SET status = 'Failed', updated_at = ?
                        WHERE id = ?
                    """, [datetime.now(timezone.utc), connection_id])
                    status_conn.close()
                    logger.info(f"Updated connection {connection_id} status to Failed (no symbols)")
                except Exception as status_error:
                    logger.error(f"Failed to update connection status: {status_error}", exc_info=True)
            
            try:
                log_conn = screener_service.get_db_connection()
                _save_scraping_log(
                    log_conn, job_id, triggered_by, started_at,
                    datetime.now(timezone.utc), "FAILED",
                    0, 0, 0, 0, 0, [error_msg]
                )
                log_conn.close()
            except Exception as log_error:
                logger.error(f"Failed to save scraping log: {log_error}")
            
            # Remove from active threads and connection mapping
            with _threads_lock:
                if job_id in _active_threads:
                    del _active_threads[job_id]
            if connection_id:
                with _connection_jobs_lock:
                    if connection_id in _connection_jobs and _connection_jobs[connection_id] == job_id:
                        del _connection_jobs[connection_id]
            
            return
        
        # Process each symbol
        symbols_succeeded = 0
        symbols_failed = 0
        total_records = 0
        errors = []
        
        # Get connection details if connection_id provided (use separate connection)
        connection_type = None
        base_url = None
        connection_name = None
        if connection_id:
            config_conn = None
            try:
                config_conn = screener_service.get_db_connection()
                conn_result = config_conn.execute("""
                    SELECT connection_name, connection_type, base_url FROM screener_connections WHERE id = ?
                """, [connection_id]).fetchone()
                if conn_result:
                    connection_name = conn_result[0]
                    connection_type = conn_result[1]
                    base_url = conn_result[2]
                
                # Log START action with total symbols count
                screener_service.write_detailed_log(
                    config_conn, job_id, connection_id, connection_name,
                    None, None, "START",
                    f"Scraping started for connection {connection_name or connection_id}. Total symbols to process: {total_symbols}",
                    company_name=None,
                    symbol_index=None,
                    total_symbols=total_symbols
                )
            finally:
                if config_conn:
                    try:
                        config_conn.close()
                    except:
                        pass
            
            # Initialize stop flag for this connection
            with _stop_flags_lock:
                _stop_flags[connection_id] = False
        
        for idx, symbol_info in enumerate(symbols):
            # Check stop flag before processing each symbol
            if connection_id:
                with _stop_flags_lock:
                    if _stop_flags.get(connection_id, False):
                        logger.info(f"[JOB {job_id}] Stop flag detected for connection {connection_id}, stopping scraping at symbol {idx + 1}/{total_symbols}")
                        _scraping_status_cache[job_id]["status"] = "STOPPED"
                        _scraping_status_cache[job_id]["errors"] = [f"Scraping stopped by user at symbol {idx + 1}/{total_symbols}"]
                        
                        # Update connection status to Stopped
                        try:
                            status_conn = screener_service.get_db_connection()
                            status_conn.execute("""
                                UPDATE screener_connections 
                                SET status = 'Stopped', updated_at = ?
                                WHERE id = ?
                            """, [datetime.now(timezone.utc), connection_id])
                            status_conn.close()
                            logger.info(f"Updated connection {connection_id} status to Stopped (stopped by user)")
                        except Exception as status_error:
                            logger.error(f"Failed to update connection status to Stopped: {status_error}", exc_info=True)
                        
                        # Log STOP action with progress format
                        progress_format = f"({idx + 1}/{total_symbols})"
                        stop_company_name = display_name if 'display_name' in locals() else "Unknown"
                        log_conn = None
                        try:
                            log_conn = screener_service.get_db_connection()
                            screener_service.write_detailed_log(
                                log_conn, job_id, connection_id, connection_name,
                                symbol_for_url if 'symbol_for_url' in locals() else None,
                                exchange or "Unknown", "STOP",
                                f"{stop_company_name} {progress_format}: Scraping stopped by user",
                                company_name=stop_company_name,
                                symbol_index=idx + 1,
                                total_symbols=total_symbols
                            )
                        finally:
                            if log_conn:
                                try:
                                    log_conn.close()
                                except:
                                    pass
                        break
            
            # Get symbol info - symbol is for URL, display_name is for logging
            symbol_for_url = symbol_info.get("symbol", "").strip() if symbol_info.get("symbol") else ""
            display_name = symbol_info.get("display_name", symbol_for_url).strip() if symbol_info.get("display_name") else symbol_for_url
            exchange = symbol_info.get("exchange", "").strip().upper() if symbol_info.get("exchange") else ""
            
            # Validate symbol
            if not symbol_for_url:
                error_msg = f"Index {idx + 1}: Invalid symbol (empty or None)"
                logger.error(f"[{exchange}] {display_name} - Failed: Invalid symbol")
                symbols_failed += 1
                errors.append(error_msg)
                continue
            
            # Update current symbol in status cache for real-time progress
            _scraping_status_cache[job_id]["current_symbol"] = display_name
            _scraping_status_cache[job_id]["current_exchange"] = exchange
            
            try:
                # Get a fresh connection for each symbol to avoid long-held locks
                # This prevents database file locking issues
                symbol_conn = None
                try:
                    symbol_conn = screener_service.get_db_connection()
                    
                    # Log FETCH action with progress format
                    progress_format = f"({idx + 1}/{total_symbols})"
                    screener_service.write_detailed_log(
                        symbol_conn, job_id, connection_id, connection_name,
                        symbol_for_url, exchange, "FETCH",
                        f"Fetching data for {display_name} {progress_format}",
                        company_name=display_name,
                        symbol_index=idx + 1,
                        total_symbols=total_symbols
                    )
                    
                    # Pass symbol_for_url to scrape_symbol (company name for NSE, ID for BSE)
                    result = screener_service.scrape_symbol(symbol_for_url, exchange, symbol_conn, connection_type, base_url)
                finally:
                    # Close connection immediately after scraping each symbol
                    if symbol_conn:
                        try:
                            symbol_conn.close()
                        except Exception as close_err:
                            logger.debug(f"[JOB {job_id}] Error closing symbol connection: {close_err}")
                
                # Always use display_name from symbols database (not extracted from page)
                # This ensures consistency and uses the same source as the symbol query
                company_name_from_db = display_name
                
                # Add 1 second delay between symbols for visibility
                time.sleep(1)
                
                if result["success"]:
                    symbols_succeeded += 1
                    records_count = result["records_inserted"]
                    total_records += records_count
                    progress_format = f"({idx + 1}/{total_symbols})"
                    # Log format: "[Exchange] Company Name (count/total) - X records scraped"
                    logger.info(f"[{exchange}] {company_name_from_db} {progress_format} - {records_count} records scraped")
                    
                    # Build enhanced description of scraped data
                    # Data categories: Header Fundamentals (MARKET), Peer Comparison (PEER), 
                    # Financial Statements (Profit & Loss, Balance Sheet, Cash Flows, Ratios)
                    data_description = (
                        f"{company_name_from_db} {progress_format}: Successfully scraped data from consolidated page. "
                        f"Categories: Header Fundamentals (Market data), Peer Comparison, "
                        f"Financial Statements (Profit & Loss, Balance Sheet, Cash Flows, Ratios). "
                        f"Total {records_count} records inserted."
                    )
                    
                    # Log INSERT action with enhanced description of scraped data
                    log_conn = None
                    try:
                        log_conn = screener_service.get_db_connection()
                        screener_service.write_detailed_log(
                            log_conn, job_id, connection_id, connection_name,
                            symbol_for_url, exchange, "INSERT",
                            data_description,
                            company_name=company_name_from_db,  # Use name from symbols database
                            symbol_index=idx + 1,
                            total_symbols=total_symbols,
                            records_count=records_count
                        )
                    finally:
                        if log_conn:
                            try:
                                log_conn.close()
                            except:
                                pass
                else:
                    symbols_failed += 1
                    progress_format = f"({idx + 1}/{total_symbols})"
                    # Extract and format error message for user readability
                    error_full = result.get('error', 'Unknown error')
                    error_str = str(error_full)
                    
                    # Determine failure reason and URL type for user-friendly description
                    failure_reason = "Unknown error"
                    url_type_attempted = "consolidated"
                    
                    if "404" in error_str or "Not Found" in error_str:
                        failure_reason = "Page not found (404 error)"
                        url_type_attempted = "consolidated"
                    elif "Timeout" in error_str or "timeout" in error_str:
                        failure_reason = "Network timeout"
                        url_type_attempted = "consolidated"
                    elif "Connection" in error_str or "connection" in error_str:
                        failure_reason = "Network connection error"
                        url_type_attempted = "consolidated"
                    elif "Invalid" in error_str or "invalid" in error_str:
                        failure_reason = "Invalid page structure or data format"
                        url_type_attempted = "consolidated"
                    else:
                        # Extract first line of error message, limit to 100 chars
                        error_short = error_str.split('\n')[0][:100] if error_str else "Unknown error"
                        failure_reason = error_short.strip()
                        url_type_attempted = "consolidated"
                    
                    # Build enhanced failure description
                    failure_description = (
                        f"{display_name} {progress_format}: Failed to scrape data. "
                        f"Reason: {failure_reason}. "
                        f"URL type attempted: {url_type_attempted}."
                    )
                    
                    error_msg = f"{display_name}: {failure_reason}"
                    errors.append(error_msg)
                    # Log format: "[Exchange] Company Name (count/total) - Failed: reason"
                    logger.error(f"[{exchange}] {display_name} {progress_format} - Failed: {failure_reason}")
                    
                    # Log ERROR action with enhanced failure description
                    log_conn = None
                    try:
                        log_conn = screener_service.get_db_connection()
                        screener_service.write_detailed_log(
                            log_conn, job_id, connection_id, connection_name,
                            symbol_for_url, exchange, "ERROR",
                            failure_description,
                            company_name=display_name,
                            symbol_index=idx + 1,
                            total_symbols=total_symbols
                        )
                    finally:
                        if log_conn:
                            try:
                                log_conn.close()
                            except:
                                pass
                
                # Update progress
                _scraping_status_cache[job_id]["symbols_processed"] = idx + 1
                _scraping_status_cache[job_id]["symbols_succeeded"] = symbols_succeeded
                _scraping_status_cache[job_id]["symbols_failed"] = symbols_failed
                _scraping_status_cache[job_id]["total_records_inserted"] = total_records
                _scraping_status_cache[job_id]["percentage"] = int(
                    ((idx + 1) / total_symbols) * 100
                )
                
            except Exception as e:
                symbols_failed += 1
                progress_format = f"({idx + 1}/{total_symbols})"
                # Extract and format error message for user readability
                error_str = str(e)
                
                # Determine failure reason for user-friendly description
                failure_reason = "Unknown error"
                url_type_attempted = "consolidated"
                
                if "404" in error_str or "Not Found" in error_str:
                    failure_reason = "Page not found (404 error)"
                    url_type_attempted = "consolidated"
                elif "Timeout" in error_str or "timeout" in error_str:
                    failure_reason = "Network timeout"
                    url_type_attempted = "consolidated"
                elif "Connection" in error_str or "connection" in error_str:
                    failure_reason = "Network connection error"
                    url_type_attempted = "consolidated"
                elif "Invalid" in error_str or "invalid" in error_str:
                    failure_reason = "Invalid page structure or data format"
                    url_type_attempted = "consolidated"
                else:
                    # Extract first line of error message, limit to 100 chars
                    error_short = error_str.split('\n')[0][:100] if error_str else "Unknown error"
                    failure_reason = error_short.strip()
                    url_type_attempted = "consolidated"
                
                # Build enhanced failure description
                failure_description = (
                    f"{display_name} {progress_format}: Failed to scrape data. "
                    f"Reason: {failure_reason}. "
                    f"URL type attempted: {url_type_attempted}."
                )
                
                error_msg = f"{display_name}: {failure_reason}"
                errors.append(error_msg)
                # Log format: "[Exchange] Company Name (count/total) - Failed: reason"
                logger.error(f"[{exchange}] {display_name} {progress_format} - Failed: {failure_reason}")
                logger.debug(f"[JOB {job_id}] Full traceback for {display_name}:\n{traceback.format_exc()}")
                
                # Log ERROR action with enhanced failure description (use display_name since page wasn't fetched)
                log_conn = None
                try:
                    log_conn = screener_service.get_db_connection()
                    screener_service.write_detailed_log(
                        log_conn, job_id, connection_id, connection_name,
                        symbol_for_url, exchange, "ERROR",
                        failure_description,
                        company_name=display_name,  # Use database name since page fetch failed
                        symbol_index=idx + 1,
                        total_symbols=total_symbols
                    )
                finally:
                    if log_conn:
                        try:
                            log_conn.close()
                        except:
                            pass
            
            # Note: Stop flag check happens at the start of each loop iteration above
            # No need to check again here to avoid duplicate logic
        
        # Finalize status
        ended_at = datetime.now(timezone.utc)
        duration = int(time.time() - start_time)
        
        # Check if stopped (check cache status first, then flag)
        was_stopped = _scraping_status_cache.get(job_id, {}).get("status") == "STOPPED"
        if not was_stopped and connection_id:
            with _stop_flags_lock:
                was_stopped = _stop_flags.get(connection_id, False)
        
        # Map status to connection status values
        # Check cache status first (may have been set to STOPPED in loop)
        cache_status = _scraping_status_cache.get(job_id, {}).get("status")
        if cache_status == "STOPPED" or was_stopped:
            # When stopped, show as Stopped status
            connection_status = "Stopped"
            job_status = "STOPPED"
        elif symbols_succeeded == 0 and total_symbols > 0:
            # All symbols failed - mark as Failed
            connection_status = "Failed"
            job_status = "FAILED"
        elif symbols_failed == 0:
            # All symbols succeeded
            connection_status = "Completed"
            job_status = "COMPLETED"
        else:
            # Some succeeded, some failed - partial success is still Completed
            connection_status = "Completed"
            job_status = "COMPLETED (Partial)"
        
        _scraping_status_cache[job_id]["status"] = job_status
        _scraping_status_cache[job_id]["symbols_processed"] = total_symbols
        _scraping_status_cache[job_id]["symbols_succeeded"] = symbols_succeeded
        _scraping_status_cache[job_id]["symbols_failed"] = symbols_failed
        _scraping_status_cache[job_id]["total_records_inserted"] = total_records
        _scraping_status_cache[job_id]["percentage"] = 100
        _scraping_status_cache[job_id]["errors"] = errors[:10]  # Limit to 10 errors
        _scraping_status_cache[job_id]["current_symbol"] = None  # Clear current symbol when done
        _scraping_status_cache[job_id]["current_exchange"] = None
        
        # Remove thread from active threads when job completes
        with _threads_lock:
            if job_id in _active_threads:
                del _active_threads[job_id]
        
        # Update connection status and stats - CRITICAL: Must always update to avoid stuck in "Running"
        if connection_id:
            status_update_success = False
            max_retries = 3
            for retry in range(max_retries):
                try:
                    temp_conn = screener_service.get_db_connection()
                    # Always update status, last_run, records_loaded, and updated_at
                    # If status was already set to Stopped during loop break, this ensures consistency
                    temp_conn.execute("""
                        UPDATE screener_connections 
                        SET status = ?, last_run = ?, records_loaded = ?, updated_at = ?
                        WHERE id = ?
                    """, [connection_status, ended_at, total_records, ended_at, connection_id])
                    temp_conn.close()
                    status_update_success = True
                    logger.info(f"Updated connection {connection_id} status to {connection_status} with stats (attempt {retry + 1})")
                    break
                except Exception as update_error:
                    logger.error(f"Failed to update connection status to {connection_status} (attempt {retry + 1}/{max_retries}): {update_error}", exc_info=True)
                    if retry < max_retries - 1:
                        time.sleep(0.5)  # Brief delay before retry
            
            # Final fallback: If all retries failed, try to set status to Failed to avoid stuck in Running
            if not status_update_success:
                try:
                    temp_conn2 = screener_service.get_db_connection()
                    temp_conn2.execute("""
                        UPDATE screener_connections 
                        SET status = 'Failed', updated_at = ?
                        WHERE id = ?
                    """, [datetime.now(timezone.utc), connection_id])
                    temp_conn2.close()
                    logger.warning(f"Fallback: Set connection {connection_id} status to Failed due to repeated update failures")
                except Exception as fallback_error:
                    logger.error(f"CRITICAL: Failed to update connection {connection_id} status even in fallback: {fallback_error}", exc_info=True)
        
        # Save log
        try:
            log_conn = screener_service.get_db_connection()
            try:
                _save_scraping_log(
                    log_conn, job_id, triggered_by, started_at, ended_at, job_status,
                    total_symbols, total_symbols, symbols_succeeded, symbols_failed,
                    total_records, errors[:10]
                )
            finally:
                log_conn.close()
            
            # Final summary log
            logger.info(f"[JOB {job_id}] =========================================")
            logger.info(f"[JOB {job_id}] SCRAPING JOB COMPLETE")
            logger.info(f"[JOB {job_id}] =========================================")
            logger.info(f"[JOB {job_id}] Status: {job_status}")
            logger.info(f"[JOB {job_id}] Total Companies Processed: {total_symbols}")
            logger.info(f"[JOB {job_id}] Companies Succeeded: {symbols_succeeded}")
            logger.info(f"[JOB {job_id}] Companies Failed: {symbols_failed}")
            logger.info(f"[JOB {job_id}] Total Records Scraped: {total_records}")
            logger.info(f"[JOB {job_id}] Duration: {duration} seconds")
            logger.info(f"[JOB {job_id}] =========================================")
        except Exception as log_error:
            logger.error(f"Failed to save scraping log for job {job_id}: {log_error}", exc_info=True)
        
    except Exception as e:
        error_msg = str(e)
        full_traceback = traceback.format_exc()
        logger.error(f"Scraping job {job_id} failed: {error_msg}", exc_info=True)
        logger.error(f"Full traceback for job {job_id}:\n{full_traceback}")
        _scraping_status_cache[job_id]["status"] = "FAILED"
        _scraping_status_cache[job_id]["errors"] = [error_msg]
        _scraping_status_cache[job_id]["current_symbol"] = None  # Clear current symbol on failure
        _scraping_status_cache[job_id]["current_exchange"] = None
        
        # Remove thread from active threads when job fails
        with _threads_lock:
            if job_id in _active_threads:
                del _active_threads[job_id]
        
        # Remove connection_id to job_id mapping
        if connection_id:
            with _connection_jobs_lock:
                if connection_id in _connection_jobs and _connection_jobs[connection_id] == job_id:
                    del _connection_jobs[connection_id]
        
        # Update connection status on failure - CRITICAL: Must always update to avoid stuck in "Running"
        if connection_id:
            status_update_success = False
            max_retries = 3
            for retry in range(max_retries):
                try:
                    temp_conn = screener_service.get_db_connection()
                    temp_conn.execute("""
                        UPDATE screener_connections 
                        SET status = 'Failed', updated_at = ?
                        WHERE id = ?
                    """, [datetime.now(timezone.utc), connection_id])
                    temp_conn.close()
                    status_update_success = True
                    logger.info(f"Updated connection {connection_id} status to Failed after exception (attempt {retry + 1})")
                    break
                except Exception as update_error:
                    logger.error(f"Failed to update connection status to Failed (attempt {retry + 1}/{max_retries}): {update_error}", exc_info=True)
                    if retry < max_retries - 1:
                        time.sleep(0.5)  # Brief delay before retry
            
            # Final fallback: If all retries failed, log critical error
            if not status_update_success:
                logger.error(f"CRITICAL: Failed to update connection {connection_id} status to Failed after {max_retries} attempts. Connection may be stuck in 'Running' state.")
        
        # Save log with a separate connection
        try:
            log_conn = screener_service.get_db_connection()
            _save_scraping_log(
                log_conn, job_id, triggered_by, started_at,
                datetime.now(timezone.utc), "FAILED",
                0, 0, 0, 0, 0, [error_msg]
            )
            log_conn.close()
            logger.info(f"Saved scraping log for failed job {job_id}")
        except Exception as log_error:
            logger.error(f"Failed to save scraping log: {log_error}", exc_info=True)
    finally:
        # Clear stop flag when job completes
        if connection_id:
            with _stop_flags_lock:
                if connection_id in _stop_flags:
                    _stop_flags[connection_id] = False
                    logger.debug(f"Cleared stop flag for connection {connection_id}")
        
        # No main connection to close - we use per-symbol connections that are closed immediately
        
        # Always remove thread from active threads when job ends
        with _threads_lock:
            if job_id in _active_threads:
                del _active_threads[job_id]
                logger.debug(f"Removed thread tracking for job {job_id}")
        
        # Always remove connection_id to job_id mapping when job ends
        if connection_id:
            with _connection_jobs_lock:
                if connection_id in _connection_jobs and _connection_jobs[connection_id] == job_id:
                    del _connection_jobs[connection_id]
                    logger.debug(f"Removed connection {connection_id} to job {job_id} mapping")

def _save_scraping_log(
    conn,
    job_id: str,
    triggered_by: str,
    started_at: datetime,
    ended_at: datetime,
    status: str,
    total_symbols: int,
    symbols_processed: int,
    symbols_succeeded: int,
    symbols_failed: int,
    total_records: int,
    errors: list
):
    """Save scraping log to database"""
    if not conn:
        return
    
    try:
        duration = int((ended_at - started_at).total_seconds())
        error_summary = "; ".join(errors) if errors else None
        
        # Check if log already exists
        existing = conn.execute("SELECT id FROM screener_scraping_logs WHERE job_id = ?", [job_id]).fetchone()
        
        if existing:
            # Update existing log
            conn.execute("""
                UPDATE screener_scraping_logs SET
                    triggered_by = ?, started_at = ?, ended_at = ?, duration_seconds = ?,
                    total_symbols = ?, symbols_processed = ?, symbols_succeeded = ?, symbols_failed = ?,
                    total_records_inserted = ?, status = ?, error_summary = ?
                WHERE job_id = ?
            """, [
                triggered_by, started_at, ended_at, duration,
                total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                total_records, status, error_summary, job_id
            ])
        else:
            # Insert new log with explicit ID (DuckDB doesn't auto-increment)
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM screener_scraping_logs").fetchone()
            next_id = (max_id_result[0] if max_id_result else 0) + 1
            
            conn.execute("""
                INSERT INTO screener_scraping_logs (
                    id, job_id, triggered_by, started_at, ended_at, duration_seconds,
                    total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                    total_records_inserted, status, error_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                next_id, job_id, triggered_by, started_at, ended_at, duration,
                total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                total_records, status, error_summary
            ])
        # DuckDB auto-commits, no need for explicit commit
    except Exception as e:
        logger.error(f"Failed to save scraping log: {e}")


@router.get("/scrape/status/{job_id}")
async def get_scraping_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get scraping status by job ID with real-time progress"""
    # Check in-memory cache first
    if job_id in _scraping_status_cache:
        status = _scraping_status_cache[job_id]
        current_symbol = status.get("current_symbol", None)
        current_exchange = status.get("current_exchange", None)
        current_symbol_display = None
        if current_symbol and current_exchange:
            current_symbol_display = f"[{current_exchange}] {current_symbol}"
        
        # Check if thread is still alive
        is_running = False
        with _threads_lock:
            if job_id in _active_threads:
                thread = _active_threads[job_id]
                is_running = thread.is_alive()
                # If thread is dead but status says PROCESSING, update status
                if not is_running and status["status"] == "PROCESSING":
                    status["status"] = "FAILED"
                    status["errors"] = ["Scraper thread stopped unexpectedly"]
                    # Remove from active threads
                    del _active_threads[job_id]
        
        return {
            "job_id": job_id,
            "status": status["status"],
            "is_running": is_running,
            "total_symbols": status["total_symbols"],
            "symbols_processed": status["symbols_processed"],
            "symbols_succeeded": status["symbols_succeeded"],
            "symbols_failed": status["symbols_failed"],
            "total_records_inserted": status["total_records_inserted"],
            "percentage": status["percentage"],
            "triggered_by": status.get("triggered_by", "system"),
            "current_symbol": current_symbol,
            "current_exchange": current_exchange,
            "current_symbol_display": current_symbol_display,
            "errors": status.get("errors", [])
        }
    
    # If not in cache, check database
    conn = None
    try:
        conn = screener_service.get_db_connection()
        result = conn.execute("""
            SELECT job_id, triggered_by, started_at, ended_at, duration_seconds,
                   total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                   total_records_inserted, status, error_summary
            FROM screener_scraping_logs
            WHERE job_id = ?
            ORDER BY started_at DESC
            LIMIT 1
        """, [job_id]).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        errors = []
        if result[11]:  # error_summary
            errors = result[11].split("; ") if result[11] else []
        
        # Check if job is still running (from database, it's completed)
        db_status = result[10] if result[10] else "UNKNOWN"
        is_running = db_status in ["PROCESSING", "PENDING"]
        
        return {
            "job_id": result[0],
            "status": db_status,
            "is_running": is_running,
            "total_symbols": result[5] if result[5] is not None else 0,
            "symbols_processed": result[6] if result[6] is not None else 0,
            "symbols_succeeded": result[7] if result[7] is not None else 0,
            "symbols_failed": result[8] if result[8] is not None else 0,
            "total_records_inserted": result[9] if result[9] is not None else 0,
            "percentage": 100 if db_status in ["COMPLETED", "COMPLETED (Partial)", "FAILED", "STOPPED"] else 0,
            "triggered_by": result[1] if result[1] else "system",
            "errors": errors,
            "started_at": result[2].isoformat() if result[2] else None,
            "ended_at": result[3].isoformat() if result[3] else None,
            "duration_seconds": result[4] if result[4] is not None else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching scraping status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch scraping status: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.get("/stats")
async def get_screener_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get Screener statistics"""
    conn = None
    try:
        conn = screener_service.get_db_connection()
        
        # Get latest scraping log
        latest_log = conn.execute("""
            SELECT job_id, triggered_by, started_at, ended_at, duration_seconds,
                   total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                   total_records_inserted, status, error_summary
            FROM screener_scraping_logs
            ORDER BY started_at DESC
            LIMIT 1
        """).fetchone()
        
        # Get total records count
        total_records = conn.execute("""
            SELECT COUNT(*) FROM screener_data
        """).fetchone()[0] or 0
        
        # Get unique symbols count
        unique_symbols = conn.execute("""
            SELECT COUNT(DISTINCT symbol) FROM screener_data
        """).fetchone()[0] or 0
        
        stats = {
            "total_records": total_records,
            "unique_symbols": unique_symbols,
            "last_status": None,
            "last_run_datetime": None,
            "last_triggered_by": None,
            "last_total_symbols": 0,
            "last_symbols_processed": 0,
            "last_symbols_succeeded": 0,
            "last_symbols_failed": 0,
            "last_records_inserted": 0
        }
        
        if latest_log:
            stats["last_status"] = latest_log[10] if latest_log[10] else None
            stats["last_run_datetime"] = latest_log[2].isoformat() if latest_log[2] else None
            stats["last_triggered_by"] = latest_log[1] if latest_log[1] else None
            stats["last_total_symbols"] = latest_log[5] if latest_log[5] is not None else 0
            stats["last_symbols_processed"] = latest_log[6] if latest_log[6] is not None else 0
            stats["last_symbols_succeeded"] = latest_log[7] if latest_log[7] is not None else 0
            stats["last_symbols_failed"] = latest_log[8] if latest_log[8] is not None else 0
            stats["last_records_inserted"] = latest_log[9] if latest_log[9] is not None else 0
        
        return stats
    except Exception as e:
        logger.error(f"Error fetching Screener stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.get("/data")
async def get_screener_data(
    symbol: Optional[str] = None,
    period_type: Optional[str] = None,
    statement_group: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get Screener data with filters"""
    conn = None
    try:
        conn = screener_service.get_db_connection()
        
        # Build query
        query = "SELECT * FROM screener_data WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if period_type:
            query += " AND period_type = ?"
            params.append(period_type)
        
        if statement_group:
            query += " AND statement_group = ?"
            params.append(statement_group)
        
        query += " ORDER BY symbol, period_key DESC, metric_name LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Get column names by executing query with LIMIT 0 (replace LIMIT ? OFFSET ? at the end)
        column_query = query.replace(" LIMIT ? OFFSET ?", " LIMIT 0")
        column_params = params[:-2]  # Remove limit and offset params
        columns = [desc[0] for desc in conn.execute(column_query, column_params).description]
        
        # Execute the actual query with limit and offset
        result = conn.execute(query, params).fetchall()
        
        # Convert to list of dicts
        data = []
        for row in result:
            data.append(dict(zip(columns, row)))
        
        return {
            "items": data,
            "total": len(data),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error fetching Screener data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.post("/scrape")
async def trigger_scraping(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Trigger scraping using default connection (legacy endpoint for config page)"""
    conn = None
    try:
        logger.info(f"[TRIGGER] User {current_user.username} triggering scraping via legacy endpoint")
        
        # Find default connection (connection_id = 1 or first available)
        conn = screener_service.get_db_connection()
        default_conn = conn.execute("""
            SELECT id, connection_name, status FROM screener_connections 
            WHERE id = 1 OR connection_name LIKE '%Screener.in%' OR connection_name LIKE '%default%'
            ORDER BY id ASC
            LIMIT 1
        """).fetchone()
        
        if not default_conn:
            # Create default connection if none exists
            logger.info(f"[TRIGGER] No default connection found, creating one...")
            now = datetime.now(timezone.utc)
            conn.execute("""
                INSERT INTO screener_connections 
                (connection_name, connection_type, base_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                "Screener.in (Default)",
                "WEBSITE_SCRAPING",
                "https://www.screener.in/company/{symbol}/",
                "Idle",
                now,
                now
            ])
            connection_id = 1
            connection_name = "Screener.in (Default)"
        else:
            connection_id = default_conn[0]
            connection_name = default_conn[1] if len(default_conn) > 1 else f"Connection {connection_id}"
        
        logger.info(f"[TRIGGER] Using connection {connection_id} ({connection_name})")
        
        # Check if already running
        if default_conn and len(default_conn) > 2 and default_conn[2] == 'Running':
            logger.warning(f"[TRIGGER] Connection {connection_id} is already running")
            raise HTTPException(status_code=409, detail="Scraping is already in progress. Please wait for it to complete.")
        
        # Update status to Running
        conn.execute("""
            UPDATE screener_connections SET status = 'Running', updated_at = ? WHERE id = ?
        """, [datetime.now(timezone.utc), connection_id])
        
        # Generate job ID
        job_id = f"screener_{uuid.uuid4().hex[:16]}"
        triggered_by = current_user.username
        
        logger.info(f"[TRIGGER] Starting scraping job {job_id} for connection {connection_id} ({connection_name}) by user {triggered_by}")
        
        # Start background processing
        thread = threading.Thread(
            target=process_scraping_async,
            args=(job_id, triggered_by, connection_id),
            name=f"Screener-{job_id}"
        )
        thread.daemon = True
        thread.start()
        
        # Track the thread and connection mapping
        with _threads_lock:
            _active_threads[job_id] = thread
        with _connection_jobs_lock:
            _connection_jobs[connection_id] = job_id
        
        logger.info(f"[TRIGGER] Successfully started scraping job {job_id} - thread is alive: {thread.is_alive()}")
        
        return {
            "job_id": job_id,
            "status": "PROCESSING",
            "message": f"Scraping started for {connection_name}. Processing in background..."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TRIGGER] Error triggering scraping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger scraping: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
                logger.debug(f"[TRIGGER] Closed database connection")
            except Exception as close_error:
                logger.error(f"[TRIGGER] Error closing database connection: {close_error}")

@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get Screener configuration"""
    conn = None
    try:
        conn = screener_service.get_db_connection()
        result = conn.execute("""
            SELECT source_type, config_json
            FROM screener_config
            WHERE is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 1
        """).fetchone()
        
        if result:
            import json
            config = json.loads(result[1])
            config['source_type'] = result[0]
            return config
        
        # Return default config if none exists
        return {
            "source_type": "WEBSITE_SCRAPING",
            "website_scraping": {
                "base_url": "https://www.screener.in/company/{symbol}/consolidated/",
                "consolidated": True
            }
        }
    except Exception as e:
        logger.error(f"Error fetching Screener config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {close_error}")

@router.post("/config")
async def save_config(
    config: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Save Screener configuration"""
    conn = None
    try:
        logger.info(f"[CONFIG] User {current_user.username} saving screener configuration")
        conn = screener_service.get_db_connection()
        
        import json
        config_json = json.dumps(config)
        source_type = config.get("source_type", "WEBSITE_SCRAPING")
        now = datetime.now(timezone.utc)
        
        # Insert or update config
        conn.execute("""
            INSERT INTO screener_config (source_type, config_json, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (source_type) DO UPDATE SET
                config_json = EXCLUDED.config_json,
                is_active = EXCLUDED.is_active,
                updated_at = EXCLUDED.updated_at
        """, [source_type, config_json, True, now, now])
        
        logger.info(f"[CONFIG] Configuration saved successfully for source_type: {source_type}")
        return {"message": "Configuration saved successfully"}
    except Exception as e:
        logger.error(f"[CONFIG] Error saving Screener config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
                logger.debug(f"[CONFIG] Closed database connection")
            except Exception as close_error:
                logger.error(f"[CONFIG] Error closing database connection: {close_error}")

@router.get("/connections")
async def get_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get all Screener connections"""
    conn = None
    try:
        conn = screener_service.get_db_connection()
        result = conn.execute("""
            SELECT id, connection_name, connection_type, website_name, base_url, api_provider_name,
                   auth_type, status, last_run, records_loaded
            FROM screener_connections
            ORDER BY created_at DESC
        """).fetchall()
        
        connections = []
        for row in result:
            connections.append({
                "id": row[0],
                "connection_name": row[1],
                "connection_type": row[2],
                "website_name": row[3],
                "base_url": row[4],
                "api_provider_name": row[5],
                "auth_type": row[6],
                "status": row[7] or "Idle",
                "last_run": row[8].isoformat() if row[8] else None,
                "records_loaded": row[9] or 0
            })
        
        return connections
    except Exception as e:
        logger.error(f"Error fetching connections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch connections: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.post("/connections")
async def create_connection(
    connection_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new Screener connection"""
    conn = None
    try:
        from datetime import datetime, timezone
        
        conn = screener_service.get_db_connection()
        
        connection_name = connection_data.get('connection_name')
        connection_type = connection_data.get('connection_type')
        
        if not connection_name or not connection_type:
            raise HTTPException(status_code=400, detail="connection_name and connection_type are required")
        
        now = datetime.now(timezone.utc)
        
        if connection_type == 'WEBSITE_SCRAPING':
            base_url = connection_data.get('base_url', 'https://www.screener.in/company/{symbol}/consolidated/')
            if not base_url or not base_url.strip():
                base_url = 'https://www.screener.in/company/{symbol}/consolidated/'
            try:
                # Use INSERT with explicit column list, omitting id to let it auto-increment
                result = conn.execute("""
                    INSERT INTO screener_connections 
                    (connection_name, connection_type, base_url, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    RETURNING id
                """, [connection_name, connection_type, base_url.strip(), 'Idle', now, now])
                new_id = result.fetchone()
                logger.info(f"Created WEBSITE_SCRAPING connection with ID: {new_id[0] if new_id else 'unknown'}")
            except Exception as db_error:
                logger.error(f"Database error creating WEBSITE_SCRAPING connection: {db_error}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        elif connection_type == 'API_CONNECTION':
            api_provider_name = connection_data.get('api_provider_name', '')
            auth_type = connection_data.get('auth_type', 'NONE')
            try:
                # Get next ID manually if auto-increment doesn't work
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_connections").fetchone()
                next_id = max_id_result[0] if max_id_result else 1
                
                # Insert with explicit ID
                conn.execute("""
                    INSERT INTO screener_connections 
                    (id, connection_name, connection_type, api_provider_name, auth_type, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [next_id, connection_name, connection_type, api_provider_name or '', auth_type or 'NONE', 'Idle', now, now])
                logger.info(f"Created API_CONNECTION with ID: {next_id}")
            except Exception as db_error:
                logger.error(f"Database error creating API_CONNECTION: {db_error}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        else:
            raise HTTPException(status_code=400, detail="Invalid connection_type")
        
        return {"message": "Connection created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating connection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create connection: {str(e)}")
    finally:
        if conn:
            conn.close()

@router.post("/connections/{connection_id}/start")
async def start_scraping(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Start scraping for a specific connection with validation"""
    conn = None
    try:
        logger.info(f"[START] User {current_user.username} attempting to start scraping for connection {connection_id}")
        conn = screener_service.get_db_connection()
        
        # Validate: Check if connection exists and is active
        conn_result = conn.execute("""
            SELECT id, connection_name, connection_type, status FROM screener_connections WHERE id = ?
        """, [connection_id]).fetchone()
        
        if not conn_result:
            logger.error(f"[START] Connection {connection_id} not found")
            raise HTTPException(status_code=404, detail="Connection not found")
        
        connection_name = conn_result[1] if len(conn_result) > 1 else f"Connection {connection_id}"
        connection_type = conn_result[2] if len(conn_result) > 2 else None
        current_status = conn_result[3] if len(conn_result) > 3 else "Unknown"
        
        logger.info(f"[START] Connection {connection_id} ({connection_name}) current status: {current_status}")
        
        # Validate: Cannot start if already running
        if current_status == 'Running':
            logger.warning(f"[START] Connection {connection_id} is already running")
            raise HTTPException(status_code=409, detail="Scraping is already running for this connection")
        
        # Validate: Verify Screener DuckDB is accessible
        try:
            test_conn = screener_service.get_db_connection()
            test_conn.execute("SELECT 1")
            test_conn.close()
        except Exception as db_error:
            logger.error(f"[START] Screener database not accessible: {db_error}")
            raise HTTPException(status_code=500, detail="Screener database is not accessible")
        
        # Validate: Verify symbol filter = CASH only (done in get_active_symbols)
        # This is enforced in the scraping function itself
        
        # Update status to Running - ensure it's committed
        try:
            conn.execute("""
                UPDATE screener_connections SET status = 'Running', updated_at = ? WHERE id = ?
            """, [datetime.now(timezone.utc), connection_id])
            logger.info(f"[START] Updated connection {connection_id} status to 'Running'")
        except Exception as update_error:
            logger.error(f"[START] Failed to update connection {connection_id} status to Running: {update_error}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update connection status. Please try again.")
        
        # Generate job ID
        job_id = f"screener_{uuid.uuid4().hex[:16]}"
        triggered_by = current_user.username
        
        logger.info(f"[START] Starting scraping job {job_id} for connection {connection_id} ({connection_name}) by user {triggered_by}")
        
        # Start background processing
        thread = threading.Thread(
            target=process_scraping_async,
            args=(job_id, triggered_by, connection_id),
            name=f"Screener-{job_id}"
        )
        thread.daemon = True
        thread.start()
        
        # Track the thread and connection mapping
        with _threads_lock:
            _active_threads[job_id] = thread
        with _connection_jobs_lock:
            _connection_jobs[connection_id] = job_id
            logger.info(f"[START] Mapped connection {connection_id} to job {job_id}")
        
        logger.info(f"[START] Successfully started scraping job {job_id} - thread is alive: {thread.is_alive()}")
        
        return {
            "job_id": job_id,
            "status": "PROCESSING",
            "message": f"Scraping started for {connection_name}. Processing in background..."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[START] Error starting scraping for connection {connection_id}: {e}", exc_info=True)
        # Rollback status: If we set it to Running, set it back to Failed/Idle
        if conn:
            try:
                # Check current status - if it's Running (we just set it), rollback to Failed
                current_status_result = conn.execute("""
                    SELECT status FROM screener_connections WHERE id = ?
                """, [connection_id]).fetchone()
                current_status = current_status_result[0] if current_status_result else None
                
                if current_status == 'Running':
                    conn.execute("""
                        UPDATE screener_connections SET status = 'Failed', updated_at = ? WHERE id = ?
                    """, [datetime.now(timezone.utc), connection_id])
                    logger.info(f"[START] Rolled back connection {connection_id} status from Running to Failed due to error")
            except Exception as rollback_error:
                logger.error(f"[START] Failed to rollback connection status: {rollback_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
                logger.debug(f"[START] Closed database connection")
            except Exception as close_error:
                logger.error(f"[START] Error closing database connection: {close_error}")

@router.post("/connections/{connection_id}/stop")
async def stop_scraping(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Stop scraping for a specific connection with validation"""
    conn = None
    try:
        logger.info(f"[STOP] User {current_user.username} attempting to stop scraping for connection {connection_id}")
        
        # Get connection info first - validate connection exists
        conn = screener_service.get_db_connection()
        conn_result = conn.execute("""
            SELECT id, connection_name, status FROM screener_connections WHERE id = ?
        """, [connection_id]).fetchone()
        
        if not conn_result:
            logger.error(f"[STOP] Connection {connection_id} not found")
            raise HTTPException(status_code=404, detail="Connection not found")
        
        connection_name = conn_result[1] if len(conn_result) > 1 else f"Connection {connection_id}"
        current_status = conn_result[2] if len(conn_result) > 2 else "Unknown"
        
        logger.info(f"[STOP] Connection {connection_id} ({connection_name}) current status: {current_status}")
        
        # Validate: Can only stop if status is Running
        if current_status != 'Running':
            logger.warning(f"[STOP] Connection {connection_id} is not running (status: {current_status})")
            raise HTTPException(status_code=400, detail=f"Cannot stop scraping: connection is not running (status: {current_status})")
        
        # Set stop flag for this connection
        with _stop_flags_lock:
            _stop_flags[connection_id] = True
            logger.info(f"[STOP] Stop flag set for connection {connection_id} by user {current_user.username}")
        
        # Find and stop any running jobs for this connection
        stopped_jobs = []
        with _connection_jobs_lock:
            job_id = _connection_jobs.get(connection_id)
            if job_id:
                logger.info(f"[STOP] Found job {job_id} for connection {connection_id}")
                with _threads_lock:
                    if job_id in _active_threads:
                        thread = _active_threads[job_id]
                        if thread.is_alive():
                            _scraping_status_cache[job_id]["status"] = "STOPPED"
                            stopped_jobs.append(job_id)
                            logger.info(f"[STOP] Marked job {job_id} for stopping (thread is alive)")
                        else:
                            logger.warning(f"[STOP] Job {job_id} thread is not alive")
                    else:
                        logger.warning(f"[STOP] Job {job_id} not found in active threads")
                if job_id in _scraping_status_cache:
                    _scraping_status_cache[job_id]["status"] = "STOPPED"
                    if job_id not in stopped_jobs:
                        stopped_jobs.append(job_id)
        
        # Update status to Stopped - ensure it's committed
        try:
            conn.execute("""
                UPDATE screener_connections SET status = 'Stopped', updated_at = ? WHERE id = ?
            """, [datetime.now(timezone.utc), connection_id])
            logger.info(f"[STOP] Updated connection {connection_id} status to 'Stopped' (stopped by user)")
        except Exception as update_error:
            logger.error(f"[STOP] Failed to update connection {connection_id} status to Stopped: {update_error}", exc_info=True)
            # Don't fail the request, but log the error
        
        if stopped_jobs:
            logger.info(f"[STOP] Successfully sent stop signal for {len(stopped_jobs)} job(s): {stopped_jobs}")
            return {
                "message": f"Stop signal sent. Scraping will stop after current symbol.",
                "stopped_jobs": stopped_jobs
            }
        else:
            logger.warning(f"[STOP] No active jobs found for connection {connection_id}")
            return {"message": "No active scraping jobs found for this connection."}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[STOP] Error stopping scraping for connection {connection_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop scraping: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
                logger.debug(f"[STOP] Closed database connection")
            except Exception as close_error:
                logger.error(f"[STOP] Error closing database connection: {close_error}")
                pass

@router.get("/logs")
async def get_detailed_logs(
    job_id: Optional[str] = None,
    connection_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get detailed Screener scraping logs (Admin only)"""
    conn = None
    try:
        conn = screener_service.get_db_connection()
        
        # Build query with filters - include all new fields
        query = """SELECT id, job_id, connection_id, connection_name, symbol, exchange, 
                   company_name, symbol_index, total_symbols, action, message, records_count, timestamp 
                   FROM screener_detailed_logs WHERE 1=1"""
        params = []
        
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        
        if connection_id:
            query += " AND connection_id = ?"
            params.append(connection_id)
        
        if action:
            query += " AND action = ?"
            params.append(action.upper())
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Execute query
        result = conn.execute(query, params).fetchall()
        
        # Convert to list of dicts with all fields
        logs = []
        for row in result:
            # Handle both old schema (9 columns) and new schema (13 columns)
            if len(row) >= 13:
                # New schema with all fields
                id_val = row[0]
                job_id_val = row[1]
                connection_id_val = row[2]
                connection_name_val = row[3]
                symbol_val = row[4]
                exchange_val = row[5]
                company_name = row[6]
                symbol_index = row[7]
                total_symbols = row[8]
                action_val = row[9]
                message_val = row[10]
                records_count = row[11]
                timestamp_val = row[12]
            else:
                # Old schema (backward compatibility)
                id_val = row[0]
                job_id_val = row[1]
                connection_id_val = row[2]
                connection_name_val = row[3]
                symbol_val = row[4]
                exchange_val = row[5]
                action_val = row[6]
                message_val = row[7]
                timestamp_val = row[8]
                company_name = None
                symbol_index = None
                total_symbols = None
                records_count = None
            
            # Format count display (e.g., "1/100" or just count if total not available)
            count_display = None
            if symbol_index is not None and total_symbols is not None:
                count_display = f"{symbol_index}/{total_symbols}"
            elif symbol_index is not None:
                count_display = str(symbol_index)
            
            # Use company_name if available, otherwise fallback to symbol_val
            # This ensures we always have a display value even for old logs or failed fetches
            company_display = company_name if company_name and company_name.strip() else symbol_val
            
            logs.append({
                # Primary fields as requested: company_name, id, symbol, exchange, count
                "company_name": company_display,  # Company name (extracted from page, or symbol as fallback)
                "id": id_val,  # Log ID
                "symbol": symbol_val,  # URL symbol
                "exchange": exchange_val,  # Exchange (NSE/BSE)
                "count": count_display,  # Count format: "1/100" or "1" or None
                # Additional fields for completeness
                "job_id": job_id_val,
                "connection_id": connection_id_val,
                "connection_name": connection_name_val,
                "symbol_display": f"{company_display} ({count_display})" if count_display else company_display,
                "symbol_index": symbol_index,
                "total_symbols": total_symbols,
                "action": action_val,
                "message": message_val,  # Description of scraped data (INSERT) or failed description (ERROR)
                "records_count": records_count,
                "timestamp": timestamp_val.isoformat() if timestamp_val else None
            })
        
        return {
            "items": logs,
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error fetching detailed logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")
    finally:
        if conn:
            conn.close()

