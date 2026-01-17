"""
Scheduler Service for Auto Upload
Handles scheduled downloads from URL/API, processing, preview, and upload
"""
import asyncio
import logging
import threading
import time
import queue
import requests
import tempfile
import os
import pandas as pd
import io
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from croniter import croniter

from app.core.config import settings
from app.api.v1.symbols import (
    get_db_connection,
    apply_transformation_script,
    process_upload_async,
    _preview_cache,
    _upload_status_cache
)

logger = logging.getLogger(__name__)

class SchedulerService:
    """Background service that executes scheduled auto uploads"""
    
    def __init__(self):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.check_interval = 60  # Check every 60 seconds
        self.lock = threading.Lock()
        self._active_executions: set = set()  # Track active executions to prevent duplicates
        self._execution_lock = threading.Lock()  # Lock for active_executions set
        
        # Queue system for serial execution
        self.scheduler_queue = queue.Queue()  # Queue to hold schedulers waiting to run
        self.queue_worker_thread: Optional[threading.Thread] = None
        self.queue_running = False
    
    def start(self):
        """Start the scheduler service"""
        if self.running:
            logger.warning("Scheduler service is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="SchedulerService")
        self.thread.start()
        
        # Start queue worker thread for serial execution
        self.queue_running = True
        self.queue_worker_thread = threading.Thread(target=self._queue_worker_loop, daemon=True, name="SchedulerQueueWorker")
        self.queue_worker_thread.start()
        logger.info("Scheduler queue worker thread started")
        logger.info("Scheduler service started")
    
    def stop(self):
        """Stop the scheduler service"""
        self.running = False
        self.queue_running = False
        
        # Signal queue worker to stop
        try:
            self.scheduler_queue.put(None)  # Sentinel value to stop worker
        except:
            pass
        
        if self.queue_worker_thread:
            self.queue_worker_thread.join(timeout=5)
        
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("Scheduler service stopped")
    
    def _run_loop(self):
        """Main scheduler loop - checks for schedulers that need to run and adds them to queue"""
        logger.info("Scheduler service loop started")
        while self.running:
            try:
                self._check_and_queue_schedulers()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            
            # Sleep for check_interval seconds
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _queue_worker_loop(self):
        """Worker thread that processes scheduler queue serially (one at a time)"""
        logger.info("Scheduler queue worker started")
        while self.queue_running:
            try:
                # Get next scheduler from queue (blocks until available or timeout)
                scheduler_task = self.scheduler_queue.get(timeout=1)
                
                # Check for sentinel value (shutdown signal)
                if scheduler_task is None:
                    logger.info("Queue worker received shutdown signal")
                    break
                
                # Execute the scheduler
                scheduler_id, name, sources_json, script_id, mode, interval_value, interval_unit, cron_expression = scheduler_task
                
                print(f"[QUEUE] Processing scheduler {name} (ID: {scheduler_id}) from queue")
                logger.info(f"[QUEUE] Processing scheduler {name} (ID: {scheduler_id}) from queue")
                
                # Execute scheduler (no manual trigger lock for auto-scheduled runs)
                self._execute_scheduler(
                    scheduler_id, name, sources_json, script_id, mode,
                    interval_value, interval_unit, cron_expression,
                    triggered_by_user=None, manual_trigger_lock=None
                )
                
                print(f"[QUEUE] Completed scheduler {name} (ID: {scheduler_id})")
                logger.info(f"[QUEUE] Completed scheduler {name} (ID: {scheduler_id})")
                
                # Mark task as done
                self.scheduler_queue.task_done()
                
            except queue.Empty:
                # Timeout - continue loop to check if still running
                continue
            except Exception as e:
                logger.error(f"Error in queue worker: {e}", exc_info=True)
                # Mark task as done even on error to prevent queue blocking
                try:
                    self.scheduler_queue.task_done()
                except:
                    pass
        
        logger.info("Scheduler queue worker stopped")
    
    def _check_and_refresh_tokens(self):
        """Check and refresh TrueData tokens if needed (only if expired)"""
        # Token refresh is now handled by scheduled timer at expiry time
        # This method is kept for backward compatibility but does minimal checking
        try:
            from app.providers.token_manager import get_token_service
            token_service = get_token_service()
            
            # Only check if token exists and is expired (no periodic refresh)
            token_info = token_service.get_token_info()
            if not token_info:
                return
            
            # Only refresh if actually expired (timer should handle this, but this is a safety check)
            if token_info.get("is_expired"):
                from app.core.database import get_db
                from app.models.connection import Connection
                from app.core.auth.security import decrypt_data
                import json
                
                db_gen = get_db()
                db = next(db_gen)
                try:
                    truedata_conn = db.query(Connection).filter(
                        Connection.provider.ilike('TRUEDATA'),
                        Connection.is_enabled == True
                    ).first()
                    
                    if not truedata_conn:
                        return
                    
                    config = {}
                    if truedata_conn.credentials:
                        try:
                            decrypted_json = decrypt_data(truedata_conn.credentials)
                            config = json.loads(decrypted_json)
                        except Exception as e:
                            logger.warning(f"Failed to decrypt TrueData credentials: {e}")
                            return
                    
                    username = config.get("username")
                    password = config.get("password")
                    auth_url = config.get("auth_url", "https://auth.truedata.in/token")
                    
                    if username and password:
                        # Refresh only if expired (timer should have handled this, but safety check)
                        refreshed = token_service.refresh_token_if_needed(
                            connection_id=truedata_conn.id,
                            username=username,
                            password=password,
                            auth_url=auth_url
                        )
                        if refreshed:
                            logger.info("TrueData token refreshed (expired token detected)")
                finally:
                    db.close()
        except Exception as e:
            logger.error(f"Error checking/refreshing tokens: {e}", exc_info=True)
    
    def _check_and_queue_schedulers(self):
        """Check for schedulers that need to run and add them to the execution queue"""
        # Use lock to prevent race conditions
        if not self.lock.acquire(blocking=False):
            # Another check is already running, skip this iteration
            return
        
        # Token refresh is now handled by scheduled timer at expiry time
        # No need to check every 60 seconds
        
        conn = None
        try:
            conn = get_db_connection()
            
            # Get all active schedulers
            schedulers = conn.execute("""
                SELECT id, name, mode, interval_value, interval_unit, cron_expression,
                       script_id, sources, is_active, next_run_at, last_run_at
                FROM schedulers
                WHERE is_active = TRUE
            """).fetchall()
            
            now = datetime.now(timezone.utc)
            logger.debug(f"Checking {len(schedulers)} active schedulers at {now}")
            
            for sched in schedulers:
                scheduler_id = sched[0]
                name = sched[1]
                mode = sched[2]
                interval_value = sched[3]
                interval_unit = sched[4]
                cron_expression = sched[5]
                script_id = sched[6]
                sources_json = sched[7]
                is_active = bool(sched[8])
                next_run_at = sched[9]
                last_run_at = sched[10]
                
                if not is_active:
                    continue
                
                # Check if it's time to run
                should_run = False
                
                if mode == 'RUN_ONCE':
                    # Run once schedulers run immediately if they haven't run yet
                    if last_run_at is None:
                        should_run = True
                elif mode == 'INTERVAL':
                    # Check if next_run_at has passed
                    if next_run_at is None:
                        # Calculate first next_run_at (run immediately for first time)
                        next_run_at = self._calculate_next_run_interval(now, interval_value, interval_unit)
                        self._update_next_run_at(conn, scheduler_id, next_run_at)
                        # For first run, execute immediately
                        should_run = True
                    else:
                        # Ensure next_run_at is timezone-aware before comparison
                        next_run_aware = next_run_at.replace(tzinfo=timezone.utc) if next_run_at.tzinfo is None else next_run_at
                        if next_run_aware <= now:
                            # Safety check: Prevent duplicate execution if scheduler just ran (within last 5 seconds)
                            # This prevents race conditions when check loop runs multiple times quickly
                            if last_run_at:
                                # Ensure both datetimes are timezone-aware before comparison
                                last_run_aware = last_run_at.replace(tzinfo=timezone.utc) if last_run_at.tzinfo is None else last_run_at
                                time_since_last = now - last_run_aware
                                if time_since_last < timedelta(seconds=5):
                                    logger.debug(f"Scheduler {name} (ID: {scheduler_id}) just ran {time_since_last.total_seconds():.1f} seconds ago, skipping to prevent duplicate execution")
                                    # Still update next_run_at to prevent it from being stuck
                                    new_next_run_at = self._calculate_next_run_interval(now, interval_value, interval_unit)
                                    self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                                    continue
                            
                            should_run = True
                            # CRITICAL: Update last_run_at IMMEDIATELY before starting thread
                            # This prevents the check loop from triggering the scheduler again
                            # while it's still executing
                            conn.execute("""
                                UPDATE schedulers SET last_run_at = ? WHERE id = ?
                            """, [now, scheduler_id])
                            # Update next_run_at immediately to prevent duplicate runs
                            new_next_run_at = self._calculate_next_run_interval(now, interval_value, interval_unit)
                            self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                            conn.commit()  # Commit both updates together
                elif mode == 'CRON':
                    # Check if cron expression matches current time
                    if cron_expression:
                        if next_run_at is None:
                            # Calculate first next_run_at from cron
                            next_run_at = self._calculate_next_run_cron(now, cron_expression)
                            if next_run_at:
                                self._update_next_run_at(conn, scheduler_id, next_run_at)
                                # If first run time is now or in the past, run immediately
                                next_run_aware = next_run_at.replace(tzinfo=timezone.utc) if next_run_at.tzinfo is None else next_run_at
                                if next_run_aware <= now:
                                    should_run = True
                        else:
                            # Ensure next_run_at is timezone-aware before comparison
                            next_run_aware = next_run_at.replace(tzinfo=timezone.utc) if next_run_at.tzinfo is None else next_run_at
                            if next_run_aware <= now:
                                # Safety check: Prevent duplicate execution if scheduler just ran (within last 5 seconds)
                                if last_run_at:
                                    # Ensure both datetimes are timezone-aware before comparison
                                    last_run_aware = last_run_at.replace(tzinfo=timezone.utc) if last_run_at.tzinfo is None else last_run_at
                                    time_since_last = now - last_run_aware
                                    if time_since_last < timedelta(seconds=5):
                                        logger.debug(f"Scheduler {name} (ID: {scheduler_id}) just ran {time_since_last.total_seconds():.1f} seconds ago, skipping to prevent duplicate execution")
                                        # Still update next_run_at to prevent it from being stuck
                                        new_next_run_at = self._calculate_next_run_cron(now, cron_expression)
                                        if new_next_run_at:
                                            self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                                        continue
                                
                                should_run = True
                                # CRITICAL: Update last_run_at IMMEDIATELY before starting thread
                                conn.execute("""
                                    UPDATE schedulers SET last_run_at = ? WHERE id = ?
                                """, [now, scheduler_id])
                                # Calculate next run time immediately to prevent duplicate runs
                                new_next_run_at = self._calculate_next_run_cron(now, cron_expression)
                                if new_next_run_at:
                                    self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                                conn.commit()  # Commit both updates together
                
                if should_run:
                    # Check if scheduler is already executing (prevent auto + manual trigger conflict)
                    execution_key = f"scheduler_{scheduler_id}_execution"
                    
                    # Also check if manual trigger lock is held
                    manual_lock_held = False
                    try:
                        from app.api.v1.symbols import _scheduler_manual_locks, _scheduler_locks_lock
                        with _scheduler_locks_lock:
                            if scheduler_id in _scheduler_manual_locks:
                                manual_lock = _scheduler_manual_locks[scheduler_id]
                                manual_lock_held = manual_lock.locked()
                    except Exception:
                        pass  # If import fails, continue anyway
                    
                    with self._execution_lock:
                        if execution_key in self._active_executions or manual_lock_held:
                            reason = "already executing" if execution_key in self._active_executions else "manual trigger in progress"
                            print(f"[AUTO-SCHEDULER] BLOCKED: Scheduler {name} (ID: {scheduler_id}) {reason}, skipping auto-trigger")
                            logger.warning(f"[AUTO-SCHEDULER] Scheduler {name} (ID: {scheduler_id}) {reason}, skipping auto-trigger")
                            # Still update next_run_at to prevent it from being stuck
                            if mode == 'INTERVAL':
                                new_next_run_at = self._calculate_next_run_interval(now, interval_value, interval_unit)
                                self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                            elif mode == 'CRON':
                                new_next_run_at = self._calculate_next_run_cron(now, cron_expression)
                                if new_next_run_at:
                                    self._update_next_run_at(conn, scheduler_id, new_next_run_at)
                            conn.commit()
                            continue
                    
                    print(f"[AUTO-SCHEDULER] Queueing scheduler: {name} (ID: {scheduler_id}, Mode: {mode})")
                    logger.info(f"[AUTO-SCHEDULER] Queueing scheduler: {name} (ID: {scheduler_id}, Mode: {mode}, Next run was: {next_run_at})")
                    
                    # Add to queue for serial execution instead of starting immediately
                    scheduler_task = (
                        scheduler_id, name, sources_json, script_id, mode,
                        interval_value, interval_unit, cron_expression
                    )
                    try:
                        self.scheduler_queue.put(scheduler_task, block=False)
                        print(f"[AUTO-SCHEDULER] Scheduler {name} (ID: {scheduler_id}) added to queue (queue size: {self.scheduler_queue.qsize()})")
                        logger.info(f"[AUTO-SCHEDULER] Scheduler {name} (ID: {scheduler_id}) added to queue (queue size: {self.scheduler_queue.qsize()})")
                    except queue.Full:
                        logger.error(f"[AUTO-SCHEDULER] Queue is full! Cannot queue scheduler {name} (ID: {scheduler_id})")
                        print(f"[AUTO-SCHEDULER] ERROR: Queue is full! Cannot queue scheduler {name} (ID: {scheduler_id})")
                else:
                    # Log why scheduler is not running (for debugging)
                    if mode == 'INTERVAL':
                        if next_run_at:
                            logger.debug(f"Scheduler {name} (ID: {scheduler_id}) waiting. Next run: {next_run_at} (in {(next_run_at - now).total_seconds():.0f} seconds)")
                        else:
                            logger.warning(f"Scheduler {name} (ID: {scheduler_id}) has no next_run_at set")
                    elif mode == 'CRON':
                        if next_run_at:
                            logger.debug(f"Scheduler {name} (ID: {scheduler_id}) waiting. Next run: {next_run_at} (in {(next_run_at - now).total_seconds():.0f} seconds)")
                        else:
                            logger.warning(f"Scheduler {name} (ID: {scheduler_id}) has no next_run_at set for CRON")
                    elif mode == 'RUN_ONCE':
                        if last_run_at:
                            logger.debug(f"Scheduler {name} (ID: {scheduler_id}) already ran (RUN_ONCE mode)")
        
        except Exception as e:
            logger.error(f"Error checking schedulers: {e}", exc_info=True)
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            # Always release the lock
            try:
                self.lock.release()
            except:
                pass
    
    def _calculate_next_run_interval(self, now: datetime, interval_value: int, interval_unit: str) -> datetime:
        """Calculate next run time for INTERVAL mode"""
        # Normalize interval_unit to lowercase for case-insensitive matching
        unit_lower = interval_unit.lower() if interval_unit else 'hours'
        
        if unit_lower == 'seconds' or unit_lower == 'second':
            delta = timedelta(seconds=interval_value)
        elif unit_lower == 'minutes' or unit_lower == 'minute':
            delta = timedelta(minutes=interval_value)
        elif unit_lower == 'hours' or unit_lower == 'hour':
            delta = timedelta(hours=interval_value)
        elif unit_lower == 'days' or unit_lower == 'day':
            delta = timedelta(days=interval_value)
        else:
            logger.warning(f"Unknown interval_unit '{interval_unit}', defaulting to 1 hour")
            delta = timedelta(hours=1)  # Default to 1 hour
        
        next_run = now + delta
        logger.debug(f"Calculated next run: {next_run} (interval: {interval_value} {interval_unit})")
        return next_run
    
    def _calculate_next_run_cron(self, now: datetime, cron_expression: str) -> Optional[datetime]:
        """Calculate next run time for CRON mode"""
        try:
            cron = croniter(cron_expression, now)
            next_run = cron.get_next(datetime)
            # Convert to timezone-aware if needed
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            return next_run
        except Exception as e:
            logger.error(f"Error parsing cron expression '{cron_expression}': {e}")
            return None
    
    def _update_next_run_at(self, conn, scheduler_id: int, next_run_at: datetime):
        """Update next_run_at for a scheduler"""
        try:
            conn.execute("""
                UPDATE schedulers SET next_run_at = ? WHERE id = ?
            """, [next_run_at, scheduler_id])
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating next_run_at for scheduler {scheduler_id}: {e}")
    
    def _execute_scheduler(self, scheduler_id: int, name: str, sources_json: str, 
                          script_id: Optional[int], mode: str, interval_value: Optional[int],
                          interval_unit: Optional[str], cron_expression: Optional[str],
                          triggered_by_user: Optional[Dict[str, Any]] = None,
                          manual_trigger_lock: Optional[threading.Lock] = None):
        """Execute a scheduler: download, process, preview, upload
        
        Args:
            triggered_by_user: Optional dict with user info (name, username, email, id) when manually triggered
            manual_trigger_lock: Optional threading.Lock that will be released after execution completes
        """
        conn = None
        temp_file_path = None
        
        try:
            # Parse sources
            sources = json.loads(sources_json) if sources_json else []
            if not sources:
                logger.warning(f"Scheduler {name} has no sources")
                return
            
            trigger_type = "MANUAL" if manual_trigger_lock else "AUTO"
            print(f"[SCHEDULER] Starting {trigger_type} execution for scheduler {name} (ID: {scheduler_id}), processing {len(sources)} source(s)")
            logger.info(f"[SCHEDULER] Starting {trigger_type} execution for scheduler {name} (ID: {scheduler_id}), processing {len(sources)} source(s)")
            
            # Check if this execution was already started (prevent duplicate executions)
            # This is a safety check in case multiple threads somehow get through
            execution_key = f"scheduler_{scheduler_id}_execution"
            
            with self._execution_lock:
                if execution_key in self._active_executions:
                    print(f"[SCHEDULER] BLOCKED: Execution for scheduler {name} (ID: {scheduler_id}) is already in progress, skipping duplicate {trigger_type} trigger")
                    logger.warning(f"[SCHEDULER] Execution for scheduler {name} (ID: {scheduler_id}) is already in progress, skipping duplicate {trigger_type} trigger")
                    # Release lock if this was a manual trigger
                    if manual_trigger_lock and manual_trigger_lock.locked():
                        try:
                            manual_trigger_lock.release()
                            print(f"[SCHEDULER] Released lock after blocking duplicate execution")
                        except:
                            pass
                    return
                self._active_executions.add(execution_key)
                print(f"[SCHEDULER] Marked scheduler {scheduler_id} as executing ({trigger_type} trigger, lock held: {manual_trigger_lock.locked() if manual_trigger_lock else 'N/A'})")
                logger.info(f"[SCHEDULER] Marked scheduler {scheduler_id} as executing ({trigger_type} trigger)")
            
            try:
                # Deduplicate sources by URL - only process unique URLs
                # This prevents processing the same file multiple times if duplicate sources exist
                seen_urls = set()
                unique_sources = []
                for source in sources:
                    source_url = source.get('url', '').strip()
                    if source_url and source_url not in seen_urls:
                        seen_urls.add(source_url)
                        unique_sources.append(source)
                    else:
                        if source_url:
                            print(f"[SCHEDULER] Skipping duplicate source with URL: {source_url}")
                            logger.info(f"[SCHEDULER] Skipping duplicate source with URL: {source_url}")
                
                if len(unique_sources) < len(sources):
                    print(f"[SCHEDULER] Deduplicated sources: {len(sources)} -> {len(unique_sources)} unique source(s)")
                    logger.info(f"[SCHEDULER] Deduplicated sources: {len(sources)} -> {len(unique_sources)} unique source(s)")
                
                if not unique_sources:
                    print(f"[SCHEDULER] No unique sources to process after deduplication")
                    logger.warning(f"[SCHEDULER] No unique sources to process after deduplication")
                    return
                
                # Process each unique source
                print(f"[SCHEDULER] ===== STARTING EXECUTION: Scheduler {name} (ID: {scheduler_id}) will process {len(unique_sources)} unique source(s) (from {len(sources)} total) ===== ")
                logger.info(f"[SCHEDULER] Starting execution: Scheduler {name} (ID: {scheduler_id}) will process {len(unique_sources)} unique source(s) (from {len(sources)} total)")
                for idx, source in enumerate(unique_sources):
                    source_name = source.get('name', f'Source {idx + 1}')
                    print(f"[SCHEDULER] >>> Processing source {idx + 1}/{len(unique_sources)}: {source_name} for scheduler {name}")
                    logger.info(f"[SCHEDULER] Processing source {idx + 1}/{len(unique_sources)}: {source_name} for scheduler {name}")
                    try:
                        # Download file from URL/API (temporary)
                        print(f"[SCHEDULER] Downloading file for source {idx + 1} from {source.get('url', 'N/A')}")
                        logger.info(f"Downloading file for scheduler {name} from {source.get('url', 'N/A')}")
                        temp_file_path = self._download_file(source)
                        
                        if not temp_file_path or not os.path.exists(temp_file_path):
                            logger.error(f"Failed to download file for scheduler {name}")
                            continue
                        
                        # Load file to script (same as manual)
                        df = self._load_file(temp_file_path, source.get('file_type', 'AUTO'))
                        
                        # Apply transformation script if provided
                        script_name = None
                        script_loaded = False
                        transformed = False
                        original_rows = len(df)
                        original_cols = len(df.columns)
                        
                        if script_id:
                            df, script_name = self._apply_script(df, script_id)
                            script_loaded = True
                            transformed = True
                        
                        new_rows = len(df)
                        new_cols = len(df.columns)
                        
                        # Preview (same as manual) - cache for upload
                        preview_id = f"preview_{uuid.uuid4().hex[:16]}"
                        filename = os.path.basename(urlparse(source.get('url', '')).path) or f"scheduled_{scheduler_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        
                        # Determine user_name: if manually triggered, use user's name; otherwise use scheduler name
                        if triggered_by_user:
                            # Manually triggered - use the user who clicked the play button
                            user_name = (triggered_by_user.get('name') or 
                                       triggered_by_user.get('username') or 
                                       triggered_by_user.get('email') or 
                                       f"User-{triggered_by_user.get('id', 'unknown')}")
                            user_id = triggered_by_user.get('id')
                        else:
                            # Auto-triggered by scheduler - use scheduler name
                            user_name = name
                            user_id = None
                        
                        _preview_cache[preview_id] = {
                            'df': df,
                            'filename': filename,
                            'script_id': script_id,
                            'script_name': script_name,
                            'script_loaded': script_loaded,
                            'transformed': transformed,
                            'original_rows': original_rows,
                            'original_cols': original_cols,
                            'new_rows': new_rows,
                            'new_cols': new_cols,
                            'user_id': user_id,
                            'user_name': user_name,  # User name if manually triggered, scheduler name if auto
                            'upload_type': 'AUTO',  # Always AUTO for scheduler runs
                            'scheduler_id': scheduler_id,  # Store scheduler ID for linking
                            'scheduler_mode': mode,  # Store scheduler timing info
                            'scheduler_interval_value': interval_value,
                            'scheduler_interval_unit': interval_unit,
                            'scheduler_cron_expression': cron_expression,
                            'manually_triggered': triggered_by_user is not None  # Flag to indicate manual trigger
                        }
                        
                        # Upload (same as manual) - use the same process_upload_async function
                        job_id = f"job_{uuid.uuid4().hex[:16]}"
                        print(f"[SCHEDULER] >>> Starting upload for source {idx + 1}/{len(unique_sources)} (job_id: {job_id})")
                        logger.info(f"Starting upload for scheduler {name}, source {idx + 1}/{len(unique_sources)}, job_id: {job_id}")
                        
                        # Process upload in background thread
                        upload_thread = threading.Thread(
                            target=process_upload_async,
                            args=(preview_id, job_id),
                            daemon=True,
                            name=f"Upload-{job_id}"
                        )
                        upload_thread.start()
                        
                        print(f"[SCHEDULER] >>> Upload thread started for source {idx + 1}/{len(unique_sources)} (job_id: {job_id})")
                        logger.info(f"Scheduler {name} execution started for source {idx + 1}/{len(unique_sources)}, job_id: {job_id}")
                        
                    except Exception as e:
                        logger.error(f"Error processing source for scheduler {name}: {e}", exc_info=True)
                    finally:
                        # Clean up temporary file
                        if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                            try:
                                os.remove(temp_file_path)
                            except Exception as e:
                                logger.warning(f"Failed to remove temp file {temp_file_path}: {e}")
                
                # Update last_run_at and calculate next_run_at
                # Note: next_run_at is already updated in _check_and_queue_schedulers to prevent race conditions
                # But we'll update it here as well to ensure it's correct after execution
                conn = get_db_connection()
                now = datetime.now(timezone.utc)
                
                # Update last_run_at
                conn.execute("""
                    UPDATE schedulers SET last_run_at = ? WHERE id = ?
                """, [now, scheduler_id])
                
                # Calculate and update next_run_at (only if not already updated)
                # This ensures next_run_at is correct even if the check loop missed it
                if mode == 'INTERVAL' and interval_value and interval_unit:
                    # Check current next_run_at
                    current_next = conn.execute("""
                        SELECT next_run_at FROM schedulers WHERE id = ?
                    """, [scheduler_id]).fetchone()
                    
                    # Only update if next_run_at is in the past or None
                    if not current_next or not current_next[0] or current_next[0] <= now:
                        next_run_at = self._calculate_next_run_interval(now, interval_value, interval_unit)
                        self._update_next_run_at(conn, scheduler_id, next_run_at)
                elif mode == 'CRON' and cron_expression:
                    # Check current next_run_at
                    current_next = conn.execute("""
                        SELECT next_run_at FROM schedulers WHERE id = ?
                    """, [scheduler_id]).fetchone()
                    
                    # Only update if next_run_at is in the past or None
                    if not current_next or not current_next[0] or current_next[0] <= now:
                        next_run_at = self._calculate_next_run_cron(now, cron_expression)
                        if next_run_at:
                            self._update_next_run_at(conn, scheduler_id, next_run_at)
                # For RUN_ONCE, don't update next_run_at (it won't run again)
                
                conn.commit()
                logger.info(f"Scheduler {name} execution completed")
                
                # Remove from active executions
                with self._execution_lock:
                    self._active_executions.discard(execution_key)
                    logger.info(f"[SCHEDULER] Removed scheduler {scheduler_id} from active executions")
                
                # Release the manual trigger lock if this was manually triggered
                # (Lock will be released in finally block)
                print(f"[SCHEDULER] ===== EXECUTION COMPLETE: Scheduler {name} (ID: {scheduler_id}) finished processing {len(unique_sources)} unique source(s) ===== ")
                logger.info(f"[SCHEDULER] Scheduler {name} (ID: {scheduler_id}) execution completed successfully - processed {len(unique_sources)} unique source(s) (from {len(sources)} total)")
            
            except Exception as e:
                logger.error(f"Error in scheduler execution loop for {name}: {e}", exc_info=True)
                # Remove from active executions on error
                with self._execution_lock:
                    self._active_executions.discard(execution_key)
                    logger.info(f"[SCHEDULER] Removed scheduler {scheduler_id} from active executions (after error)")
                
                # Release the manual trigger lock on error
                if manual_trigger_lock and manual_trigger_lock.locked():
                    try:
                        manual_trigger_lock.release()
                        print(f"[SCHEDULER] Released manual trigger lock for scheduler {scheduler_id} (after inner error)")
                        logger.info(f"[SCHEDULER] Released manual trigger lock for scheduler {scheduler_id} (after inner error)")
                    except Exception as e:
                        print(f"[SCHEDULER] ERROR releasing lock: {e}")
                        logger.warning(f"[SCHEDULER] Could not release manual trigger lock on error: {e}")
                
                raise
        
        except Exception as e:
            logger.error(f"Error executing scheduler {name}: {e}", exc_info=True)
            # Remove from active executions on error (if execution_key was set)
            if 'execution_key' in locals():
                with self._execution_lock:
                    if execution_key in self._active_executions:
                        self._active_executions.discard(execution_key)
                        logger.info(f"[SCHEDULER] Removed scheduler {scheduler_id} from active executions (after outer error)")
            
            # Release the manual trigger lock on error
            try:
                from app.api.v1.symbols import _scheduler_manual_locks, _scheduler_locks_lock
                with _scheduler_locks_lock:
                    if scheduler_id in _scheduler_manual_locks:
                        manual_lock = _scheduler_manual_locks[scheduler_id]
                        if manual_lock.locked():
                            manual_lock.release()
                            logger.info(f"[SCHEDULER] Released manual trigger lock for scheduler {scheduler_id} (after outer error)")
            except Exception as lock_error:
                logger.warning(f"[SCHEDULER] Could not release manual trigger lock on outer error: {lock_error}")
        finally:
            # Remove from active executions
            if 'execution_key' in locals():
                with self._execution_lock:
                    if execution_key in self._active_executions:
                        self._active_executions.discard(execution_key)
                        print(f"[SCHEDULER] Removed scheduler {scheduler_id} from active executions (finally)")
                        logger.info(f"[SCHEDULER] Removed scheduler {scheduler_id} from active executions (finally)")
            
            # Release the manual trigger lock if it was passed
            if manual_trigger_lock and manual_trigger_lock.locked():
                try:
                    manual_trigger_lock.release()
                    print(f"[SCHEDULER] Released manual trigger lock for scheduler {scheduler_id} (finally)")
                    logger.info(f"[SCHEDULER] Released manual trigger lock for scheduler {scheduler_id} (finally)")
                except Exception as e:
                    print(f"[SCHEDULER] ERROR releasing lock in finally: {e}")
                    logger.warning(f"[SCHEDULER] Could not release manual trigger lock in finally: {e}")
            
            if conn:
                try:
                    conn.close()
                except:
                    pass
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
    
    def _download_file(self, source: Dict[str, Any]) -> Optional[str]:
        """Download file from URL/API to temporary location"""
        url = source.get('url')
        if not url:
            raise ValueError("Source URL is required")
        
        # Prepare headers
        headers = source.get('headers') or {}
        
        # Add authentication if provided
        auth_type = source.get('auth_type')
        auth_value = source.get('auth_value')
        if auth_type and auth_value:
            if auth_type.lower() == 'bearer':
                headers['Authorization'] = f"Bearer {auth_value}"
            elif auth_type.lower() == 'basic':
                headers['Authorization'] = f"Basic {auth_value}"
            elif auth_type.lower() == 'api_key':
                # For API key, we need to know the header name
                # Default to X-API-Key if not specified
                api_key_header = source.get('api_key_header', 'X-API-Key')
                headers[api_key_header] = auth_value
        
        # Download file
        response = requests.get(url, headers=headers, timeout=300, stream=True)
        response.raise_for_status()
        
        # Create temporary file
        temp_dir = os.path.join(os.path.abspath(settings.DATA_DIR), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Determine file extension
        parsed_url = urlparse(url)
        url_path = parsed_url.path
        file_ext = os.path.splitext(url_path)[1].lower()
        
        if not file_ext:
            content_type = response.headers.get('Content-Type', '')
            if 'csv' in content_type.lower():
                file_ext = '.csv'
            elif 'excel' in content_type.lower() or 'spreadsheet' in content_type.lower():
                file_ext = '.xlsx'
            else:
                file_ext = '.csv'  # Default
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            delete=False,
            suffix=file_ext,
            dir=temp_dir
        )
        temp_file_path = temp_file.name
        
        # Write downloaded content
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        return temp_file_path
    
    def _load_file(self, file_path: str, file_type: str) -> pd.DataFrame:
        """Load file into DataFrame (same as manual upload)"""
        # Determine file type
        if file_type == 'AUTO':
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.csv':
                file_type = 'CSV'
            elif file_ext in ['.xlsx', '.xls']:
                file_type = 'XLSX'
            else:
                file_type = 'CSV'  # Default
        
        # Read file
        with open(file_path, 'rb') as f:
            contents = f.read()
        
        if file_type == 'CSV':
            df = pd.read_csv(io.BytesIO(contents), low_memory=False)
        elif file_type == 'XLSX':
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return df
    
    def _apply_script(self, df: pd.DataFrame, script_id: int):
        # Returns: (pd.DataFrame, Optional[str])
        """Apply transformation script to dataframe. Returns (df, script_name)"""
        conn = None
        script_name = None
        try:
            conn = get_db_connection()
            script = conn.execute("""
                SELECT name, content FROM transformation_scripts WHERE id = ?
            """, [script_id]).fetchone()
            
            if script:
                script_name = script[0]
                script_content = script[1]
                df = apply_transformation_script(df, script_content)
                logger.info(f"Applied transformation script {script_name} (ID: {script_id})")
            else:
                logger.warning(f"Transformation script {script_id} not found")
                raise ValueError(f"Transformation script {script_id} not found")
        except Exception as e:
            logger.error(f"Error applying transformation script {script_id}: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
        
        return df, script_name

# Global scheduler service instance
_scheduler_service: Optional[SchedulerService] = None

def get_scheduler_service() -> SchedulerService:
    """Get the global scheduler service instance"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service

