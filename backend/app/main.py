from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
import logging
import logging.config
import sys

# Configure logging to suppress ONLY WebSocket access logs
# Keep all other normal logs (HTTP requests, application logs, etc.)
from app.api.v1 import auth, users, admin, connections, websocket, symbols, screener, announcements, telegram_auth, news
from app.core.config import settings
from app.core.database import get_connection_manager, get_db_router

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Configure logging to suppress ONLY WebSocket connection logs
# This filter will prevent WebSocket connection logs from appearing while keeping all other logs
class WebSocketLogFilter(logging.Filter):
    """Filter to suppress only WebSocket connection logs, keep all other logs"""
    def filter(self, record):
        # Only suppress logs that are specifically WebSocket connection messages
        message = record.getMessage()
        message_lower = message.lower()
        
        # Suppress WebSocket connection acceptance logs (e.g., "WebSocket /api/v1/ws?token=... [accepted]")
        if "websocket" in message_lower:
            if "/ws" in message_lower or "/api/v1/ws" in message_lower:
                return False
            if "[accepted]" in message_lower or "accepted" in message_lower:
                return False
        
        # Suppress standalone "connection open" and "connection closed" messages
        # These come from WebSocket protocol and don't contain "websocket" in the text
        if "connection open" in message_lower:
            return False
        if "connection closed" in message_lower:
            return False
        
        # Keep all other logs (HTTP requests, application logs, errors, etc.)
        return True

# Apply filter to uvicorn access logger (where WebSocket connection logs come from)
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(WebSocketLogFilter())

# Apply filter to uvicorn protocol loggers for WebSocket-specific messages
for ws_logger_name in ["uvicorn.protocols.websockets", "uvicorn.protocols.websockets.websockets_impl",
                       "uvicorn.protocols.websockets.impl", "uvicorn.protocols", "uvicorn.error"]:
    ws_logger = logging.getLogger(ws_logger_name)
    ws_logger.addFilter(WebSocketLogFilter())

# Apply filter to root logger to catch any WebSocket logs from other sources
logging.getLogger().addFilter(WebSocketLogFilter())

# Note: WebSocket connection logs are suppressed via WebSocketLogFilter above.
# This filter only suppresses WebSocket connection logs (keeps HTTP requests and all other logs).
# Normal application logs, HTTP request logs, errors, and startup messages are all preserved.

app = FastAPI(
    title="Open Analytics API",
    description="Enterprise Analytics Platform API (v1)",
    version="1.0.1",
)

# CORS middleware - MUST be added before other middleware
# Use settings for CORS origins to support Docker networking
app.add_middleware(
    CORSMiddleware,
    # Allow all origins for debugging "data not loading" issues
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Note: CORS middleware should handle CORS headers automatically
# Exception handlers are only needed if CORS middleware fails to add headers

# Configure logging at startup - runs before any requests
@app.on_event("startup")
async def configure_logging():
    """Configure logging to suppress only WebSocket connection logs - runs early in startup"""
    # Apply WebSocket filter to all relevant loggers (keeps HTTP and other logs)
    loggers_to_filter = [
        "uvicorn.access",
        "uvicorn.error",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.impl",
        "uvicorn.protocols",
        ""  # root logger
    ]
    for logger_name in loggers_to_filter:
        logger = logging.getLogger(logger_name)
        if not any(isinstance(f, WebSocketLogFilter) for f in logger.filters):
            logger.addFilter(WebSocketLogFilter())

# Initialize database connections on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup"""
    try:
        manager = get_connection_manager(settings.DATA_DIR)
        router = get_db_router(settings.DATA_DIR)
        
        import duckdb
        import os
        import sys
        
        # ============================================
        # SINGLE INSTANCE CHECK
        # ============================================
        # Normalize DATA_DIR to handle mixed path separators (forward/backward slashes)
        pid_file = os.path.join(os.path.normpath(settings.DATA_DIR), "backend.pid")
        try:
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        old_pid = int(f.read().strip())
                    
                    # Check if process is still running
                    # On Windows, os.kill(pid, 0) works to check existence
                    os.kill(old_pid, 0)
                    
                    print(f"\n" + "!"*70)
                    print(f" [CRITICAL] BACKEND ALREADY RUNNING (PID: {old_pid})")
                    print(f"            Please stop it before starting a new instance.")
                    print(f"            Run: server\\windows\\stop-all.bat")
                    print("!"*70 + "\n")
                    
                    # Force exit to prevent DB corruption
                    os._exit(1) 
                except (OSError, ValueError):
                    # Process dead or invalid PID, remove stale PID file
                    print(f"[INFO] Removing stale PID file from previous run (PID: {old_pid if 'old_pid' in locals() else 'unknown'})")
                    try:
                        os.remove(pid_file)
                    except:
                        pass

            # Write current PID
            current_pid = os.getpid()
            with open(pid_file, 'w') as f:
                f.write(str(current_pid))
                print(f"[INFO] PID file created: {current_pid}")
                
        except SystemExit:
            raise
        except Exception as e:
            print(f"[WARNING] Failed to manage PID file: {e}")
        
        # ============================================
        # DATABASE CONNECTION STATUS
        # ============================================
        print("\n" + "="*70)
        print(" DATABASE CONNECTION STATUS")
        print("="*70)
        
        # Test Auth database with table count
        auth_client = router.get_auth_db()
        auth_table_count = 0
        if auth_client:
            try:
                health = auth_client.health_check()
                # Try to get table count
                try:
                    db = auth_client.get_session()
                    from sqlalchemy import inspect
                    inspector = inspect(auth_client.engine)
                    auth_table_count = len(inspector.get_table_names())
                    db.close()
                except:
                    pass
                print(f"  Auth DB           : CONNECTED ({auth_table_count} tables) - {auth_client.__class__.__name__}")
            except Exception as e:
                print(f"  Auth DB           : ERROR - {str(e)}")
        else:
            print("  Auth DB           : FAILED - No connection available")
        
        # Test Analytics database
        analytics_client = router.get_analytics_db()
        if analytics_client:
            try:
                print(f"  Analytics DB      : CONNECTED - {analytics_client.__class__.__name__}")
            except Exception as e:
                print(f"  Analytics DB      : ERROR - {str(e)}")
        else:
            print("  Analytics DB      : NOT CONFIGURED")
        
        # Test Screener database with table count
        screener_table_count = 0
        try:
            import app.models.screener as screener_service
            screener_conn = screener_service.get_db_connection()
            if screener_conn:
                try:
                    tables = screener_conn.execute("SHOW TABLES").fetchall()
                    screener_table_count = len(tables)
                except:
                    pass
                screener_conn.close()
                print(f"  Screener DB       : CONNECTED ({screener_table_count} tables) - DuckDB")
            else:
                print("  Screener DB       : FAILED")
        except Exception as e:
            print(f"  Screener DB       : ERROR - {str(e)}")
        
        # Test Symbols database with table and symbol count
        symbols_table_count = 0
        symbols_record_count = 0
        try:
            from app.api.v1.symbols import get_symbols_db_path, get_db_connection
            symbols_db_path = get_symbols_db_path()
            if os.path.exists(symbols_db_path):
                symbols_conn = get_db_connection()
                if symbols_conn:
                    try:
                        tables = symbols_conn.execute("SHOW TABLES").fetchall()
                        symbols_table_count = len(tables)
                        # Try to get symbol count
                        try:
                            result = symbols_conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
                            symbols_record_count = result[0] if result else 0
                        except:
                            pass
                    except:
                        pass
                    symbols_conn.close()
                    print(f"  Symbols DB        : CONNECTED ({symbols_table_count} tables, {symbols_record_count} symbols) - DuckDB")
                else:
                    print(f"  Symbols DB        : FAILED - Connection error")
            else:
                print(f"  Symbols DB        : NOT INITIALIZED")
        except Exception as e:
            print(f"  Symbols DB        : ERROR - {str(e)}")
        
        print("="*70)
        
        # ============================================
        # USER/ADMIN STATUS
        # ============================================
        print("\n" + "="*70)
        print(" USER STATUS")
        print("="*70)
        try:
            db = auth_client.get_session()
            from app.models.user import User
            
            try:
                all_users = db.query(User).all()
                total_users = len(all_users)
                active_users_count = len([u for u in all_users if u.is_active])
                super_admins = [u for u in all_users if u.role and u.role.lower() == "super_admin"]
                admins = [u for u in all_users if u.role and u.role.lower() == "admin"]
                regular_users = [u for u in all_users if u.role and u.role.lower() == "user"]
                
                print(f"  Total Users       : {total_users}")
                print(f"  Active Users      : {active_users_count}")
                print(f"  Super Admins      : {len(super_admins)}")
                print(f"  Admins            : {len(admins)}")
                print(f"  Regular Users     : {len(regular_users)}")
                
                if not super_admins:
                    print("\n  [WARNING] No Super User found!")
                    print("            Run: python scripts/init/init_auth_database.py")
                    
            except Exception as e:
                print(f"  [WARNING] Could not verify users: {e}")
                
            db.close()
        except Exception as e:
            print(f"  [ERROR] User check failed: {e}")
        print("="*70)
        
        # ============================================
        # WEBSOCKET STATUS
        # ============================================
        print("\n" + "="*70)
        print(" WEBSOCKET STATUS")
        print("="*70)
        try:
            from app.core.websocket_manager import manager as ws_manager
            import asyncio
            # Create background task for cleanup
            loop = asyncio.get_event_loop()
            loop.create_task(ws_manager.cleanup_stale_connections())
            
            print(f"  Service Status    : READY")
            print(f"  Cleanup Task      : STARTED")
            print(f"  Listening         : /api/v1/ws")
        except Exception as e:
            print(f"  Service Status    : ERROR - {str(e)}")
        print("="*70)
        
        # ============================================
        # SCHEDULER STATUS
        # ============================================
        print("\n" + "="*70)
        print(" SCHEDULER STATUS")
        print("="*70)
        
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(IST)
        print(f"  Current Time (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*70)
        
        # Start TrueData token refresh scheduler
        try:
            from app.services.token_refresh_scheduler import start_token_refresh_scheduler, get_token_refresh_scheduler
            start_token_refresh_scheduler()
            token_scheduler = get_token_refresh_scheduler()
            status = "RUNNING" if token_scheduler.running else "STOPPED"
            
            # Calculate next check time in IST
            next_token_check = now_utc + timedelta(seconds=token_scheduler.check_interval)
            next_token_check_ist = next_token_check.astimezone(IST)
            
            print(f"  Token Refresh     : {status}")
            print(f"    Check Interval  : {token_scheduler.check_interval}s")
            print(f"    Next Check (IST): {next_token_check_ist.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"  Token Refresh     : ERROR - {str(e)}")
        
        print("-"*70)
        
        # Initialize Screener Database and reset stale "Running" statuses
        try:
            import app.models.screener as screener_service
            screener_service.init_screener_database()
            # Ensure default connection exists
            conn = screener_service.get_db_connection()
            
            # Reset any connections that are still marked as "Running" (stale status from previous backend run)
            try:
                result = conn.execute("""
                    SELECT COUNT(*) FROM screener_connections WHERE status = 'Running'
                """).fetchone()
                running_count = result[0] if result else 0
                
                if running_count > 0:
                    conn.execute("""
                        UPDATE screener_connections 
                        SET status = 'Failed', updated_at = ?
                        WHERE status = 'Running'
                    """, [datetime.now(timezone.utc)])
                    print(f"[OK] Reset {running_count} stale 'Running' screener connection(s) to 'Failed' status")
                
                conn.close()
            except Exception as reset_error:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
        except Exception as e:
            pass  # Silent - already logged in database status section
        
        # Initialize Corporate Announcements Database
        try:
            from app.services.announcements_service import init_announcements_database
            init_announcements_database()
            print(f"  Announcements DB   : INITIALIZED - DuckDB")
        except Exception as e:
            print(f"  Announcements DB   : ERROR - {str(e)}")
        
        # Start Corporate Announcements WebSocket Service
        try:
            from app.services.announcements_websocket_service import get_announcements_websocket_service
            from app.models.connection import Connection
            from app.core.database import get_db
            
            # Get active TrueData connection
            db = next(get_db())
            try:
                truedata_conn = db.query(Connection).filter(
                    Connection.provider == "TrueData",
                    Connection.is_enabled == True
                ).first()
                
                if truedata_conn:
                    ws_service = get_announcements_websocket_service()
                    connection_id = truedata_conn.id
                    
                    # Start WebSocket in background task (async)
                    async def start_ws():
                        # Get a fresh DB session for the WebSocket service
                        db_session = next(get_db())
                        try:
                            await ws_service.start_background(connection_id, db_session)
                        except Exception as e:
                            logging.error(f"Error starting announcements WebSocket: {e}")
                        # Note: Don't close db_session here - WebSocket service uses it during connection setup
                    
                    # Create background task
                    import asyncio
                    ws_service.task = asyncio.create_task(start_ws())
                    
                    print(f"  Announcements WS  : STARTING - Connection ID {connection_id}")
                else:
                    print(f"  Announcements WS  : SKIPPED - No active TrueData connection")
            finally:
                db.close()
        except Exception as e:
            print(f"  Announcements WS  : ERROR - {str(e)}")
        
        # Start Symbol Scheduler Service
        try:
            from app.services.scheduler_service import get_scheduler_service
            from app.api.v1.symbols import get_db_connection as get_symbols_db_connection
            scheduler_service = get_scheduler_service()
            scheduler_service.start()
            status = "RUNNING" if scheduler_service.running else "STOPPED"
            active_count = len(scheduler_service._active_executions) if hasattr(scheduler_service, '_active_executions') else 0
            queue_size = scheduler_service.scheduler_queue.qsize() if hasattr(scheduler_service, 'scheduler_queue') else 0
            
            # Calculate next check time in IST
            next_symbol_check = now_utc + timedelta(seconds=scheduler_service.check_interval)
            next_symbol_check_ist = next_symbol_check.astimezone(IST)
            
            # Get active scheduler count and next scheduled run from database
            active_schedulers = 0
            next_scheduled_run = None
            try:
                sched_conn = get_symbols_db_connection()
                if sched_conn:
                    result = sched_conn.execute("SELECT COUNT(*) FROM schedulers WHERE is_active = TRUE").fetchone()
                    active_schedulers = result[0] if result else 0
                    
                    # Get next scheduled run
                    next_run_result = sched_conn.execute("""
                        SELECT name, next_run_at FROM schedulers 
                        WHERE is_active = TRUE AND next_run_at IS NOT NULL 
                        ORDER BY next_run_at ASC LIMIT 1
                    """).fetchone()
                    if next_run_result:
                        next_scheduled_run = next_run_result
                    sched_conn.close()
            except:
                pass
            
            print(f"  Symbol Auto-Upload: {status}")
            print(f"    Check Interval  : {scheduler_service.check_interval}s")
            print(f"    Next Check (IST): {next_symbol_check_ist.strftime('%H:%M:%S')}")
            print(f"    Active Schedulers: {active_schedulers}")
            print(f"    Queue Size      : {queue_size}")
            
            if next_scheduled_run:
                sched_name = next_scheduled_run[0]
                next_run_at = next_scheduled_run[1]
                if next_run_at:
                    # Ensure timezone aware
                    if next_run_at.tzinfo is None:
                        next_run_at = next_run_at.replace(tzinfo=timezone.utc)
                    next_run_ist = next_run_at.astimezone(IST)
                    print(f"    Next Run        : '{sched_name}' at {next_run_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
        except Exception as e:
            print(f"  Symbol Auto-Upload: ERROR - {str(e)}")
        
        print("-"*70)
        
        # Start Telegram Bot Polling Service
        try:
            from app.services.telegram_bot_service import TelegramBotService
            from app.core.database import get_db
            import asyncio
            
            # Check if Telegram connection exists and is enabled
            db_session = next(get_db())
            try:
                from app.models.connection import Connection
                telegram_conn = db_session.query(Connection).filter(
                    Connection.connection_type == "TELEGRAM_BOT",
                    Connection.is_enabled == True
                ).first()
                
                if telegram_conn:
                    # Start polling in background
                    async def run_telegram_polling():
                        """Background task to poll Telegram for /start commands"""
                        import logging
                        logger = logging.getLogger("telegram_bot")
                        logger.setLevel(logging.INFO)
                        
                        while True:
                            try:
                                # Get fresh DB session for each iteration
                                db = next(get_db())
                                try:
                                    bot_service = TelegramBotService(manager)
                                    updates = await bot_service.get_updates()
                                    
                                    for update in updates:
                                        try:
                                            await bot_service.process_webhook_update(update, db)
                                        except Exception as e:
                                            logger.error(f"Error processing update: {e}")
                                
                                finally:
                                    db.close()
                                
                                # Wait 10 seconds between polls (as requested)
                                await asyncio.sleep(10)
                            except Exception as e:
                                logger.error(f"Telegram polling error: {e}")
                                await asyncio.sleep(30)  # Wait longer on error
                    
                    # Create background task
                    asyncio.create_task(run_telegram_polling())
                    print(f"  Telegram Bot Poll : STARTED - Connection ID {telegram_conn.id}")
                    print(f"    Poll Interval   : 10s")
                    print(f"    Listening for   : /start commands for user linking")
                else:
                    print(f"  Telegram Bot Poll : SKIPPED - No active Telegram connection")
            finally:
                db_session.close()
        except Exception as e:
            print(f"  Telegram Bot Poll : ERROR - {str(e)}")
        
        # Start Worker Manager (Listeners, Extractors, Processors)
        try:
            from app.services.worker_manager import worker_manager
            worker_manager.start_all()
        except Exception as e:
            print(f"  Worker Manager    : ERROR - {str(e)}")

        print("="*70)
        
        # Final startup message
        print("\n" + "="*70)
        print(" OPEN ANALYTICS API - READY")
        print(f" Started at: {now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
        print("="*70 + "\n")

    except Exception as e:
        print(f"[ERROR] Startup error: {e}")

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    try:
        print("[INFO] Shutting down server gracefully...")
        # Symbols module has been removed
        pass
        
        # Stop Scheduler Service
        try:
            from app.services.scheduler_service import get_scheduler_service
            scheduler_service = get_scheduler_service()
            scheduler_service.stop()
            print("[OK] Scheduler service stopped")
        except Exception as e:
            print(f"[WARNING] Error stopping scheduler service: {e}")
        
        # Stop Corporate Announcements WebSocket Service
        try:
            from app.services.announcements_websocket_service import get_announcements_websocket_service
            ws_service = get_announcements_websocket_service()
            ws_service.stop()
            print("[OK] Announcements WebSocket service stopped")
        except Exception as e:
            print(f"[WARNING] Error stopping announcements WebSocket service: {e}")
        
        # Stop Worker Manager
        try:
            from app.services.worker_manager import worker_manager
            worker_manager.stop_all()
            print("[OK] Worker Manager stopped")
        except Exception as e:
            print(f"  Worker Manager    : ERROR - {str(e)}")

        # Close database connections
        try:
            manager = get_connection_manager(settings.DATA_DIR)
            if manager:
                manager.close_all()
        except Exception as e:
            print(f"[WARNING] Error closing database connections: {e}")
        
        # Close Shared Database (DuckDB)
        try:
            from app.services.shared_db import get_shared_db
            get_shared_db().close_all()
            print("[OK] Shared Database connections closed")
        except Exception as e:
            print(f"[WARNING] Error closing Shared DB: {e}")

        # Remove PID file
        try:
            import os
            from app.core.config import settings
            # Normalize DATA_DIR to handle mixed path separators
            pid_file = os.path.join(os.path.normpath(settings.DATA_DIR), "backend.pid")
            if os.path.exists(pid_file):
                os.remove(pid_file)
                print(f"[OK] PID file removed")
        except Exception as e:
            print(f"[WARNING] Error removing PID file: {e}")

        print("[OK] Server shutdown complete")
    except Exception as e:
        print(f"[WARNING] Shutdown error: {e}")

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(connections.router, prefix="/api/v1/admin/connections", tags=["connections"])
app.include_router(symbols.router, prefix="/api/v1/admin/symbols", tags=["symbols"])
app.include_router(screener.router, prefix="/api/v1/admin/screener", tags=["screener"])
app.include_router(announcements.router, prefix="/api/v1/announcements", tags=["announcements"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
from app.api.v1 import telegram, telegram_connect, telegram_auth
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["telegram"])
app.include_router(telegram_connect.router, prefix="/api/v1/telegram", tags=["telegram_connect"])
app.include_router(telegram_auth.router, prefix="/api/v1/telegram", tags=["telegram_auth"])

from app.api.v1 import telegram_channels
app.include_router(telegram_channels.router, prefix="/api/v1/telegram-channels", tags=["telegram_channels"])

from app.api.v1 import processors
app.include_router(processors.router, prefix="/api/v1/processors", tags=["processors"])
app.include_router(news.router, prefix="/api/v1/news", tags=["news"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        router = get_db_router(settings.DATA_DIR)
        auth_client = router.get_auth_db()
        
        db_status = "connected"
        if auth_client:
            try:
                health = auth_client.health_check()
                if isinstance(health, dict) and health.get("status") != "connected":
                    db_status = "disconnected"
            except:
                db_status = "error"
        else:
            db_status = "disconnected"
        
        # Check if script endpoints are registered
        script_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and 'scripts' in route.path:
                methods = list(route.methods) if hasattr(route, 'methods') else []
                script_routes.append({
                    "path": route.path,
                    "methods": methods
                })
        
        return {
            "status": "healthy",
            "database": db_status,
            "api_version": "v1",
            "script_endpoints": script_routes,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/")
async def root():
    return {"message": "Open Analytics API"}
