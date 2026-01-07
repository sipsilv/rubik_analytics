from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
import logging
import logging.config
import sys

# Configure logging to suppress ONLY WebSocket access logs
# Keep all other normal logs (HTTP requests, application logs, etc.)
from app.api.v1 import auth, users, admin, connections, websocket, symbols, screener, announcements
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
    title="Rubik Analytics API",
    description="Enterprise Analytics Platform API (v1)",
    version="1.0.1",
)

# CORS middleware - MUST be added before other middleware
# Use settings for CORS origins to support Docker networking
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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
        
        # Test Corporate Announcements database with record count
        announcements_count = 0
        try:
            data_dir = os.path.abspath(settings.DATA_DIR)
            db_dir = os.path.join(data_dir, "Company Fundamentals")
            db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
            if os.path.exists(db_path):
                test_conn = duckdb.connect(db_path)
                try:
                    result = test_conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()
                    announcements_count = result[0] if result else 0
                except:
                    pass
                test_conn.close()
                print(f"  Announcements DB  : CONNECTED ({announcements_count} records) - DuckDB")
            else:
                print(f"  Announcements DB  : NOT INITIALIZED")
        except Exception as e:
            print(f"  Announcements DB  : ERROR - {str(e)}")
        
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
            import duckdb
            import os
            data_dir = os.path.abspath(settings.DATA_DIR)
            db_dir = os.path.join(data_dir, "Company Fundamentals")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
            
            # Create database and table if it doesn't exist
            conn = duckdb.connect(db_path)
            
            # Check if old schema exists (with 'id' column)
            old_schema_exists = False
            try:
                result = conn.execute("PRAGMA table_info(corporate_announcements)").fetchall()
                columns = [col[1] for col in result]
                if 'id' in columns and 'announcement_id' not in columns:
                    old_schema_exists = True
            except:
                pass
            
            # Migrate from old schema if needed
            if old_schema_exists:
                print("[INFO] Migrating corporate_announcements table to new schema...")
                try:
                    # Create new table with correct schema
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS corporate_announcements_new (
                            announcement_id VARCHAR PRIMARY KEY,
                            symbol VARCHAR,
                            exchange VARCHAR,
                            headline VARCHAR,
                            description TEXT,
                            category VARCHAR,
                            announcement_datetime TIMESTAMP,
                            received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            attachment_id VARCHAR,
                            symbol_nse VARCHAR,
                            symbol_bse VARCHAR,
                            raw_payload TEXT
                        )
                    """)
                    
                    # Migrate data from old schema
                    conn.execute("""
                        INSERT INTO corporate_announcements_new (
                            announcement_id, symbol, exchange, headline, description, category,
                            announcement_datetime, received_at, attachment_id, symbol_nse, symbol_bse, raw_payload
                        )
                        SELECT 
                            COALESCE(id, '') as announcement_id,
                            COALESCE(symbol_nse, symbol_bse) as symbol,
                            CASE 
                                WHEN symbol_nse IS NOT NULL THEN 'NSE'
                                WHEN symbol_bse IS NOT NULL THEN 'BSE'
                                ELSE NULL
                            END as exchange,
                            headline,
                            COALESCE(news_body, news_sub) as description,
                            descriptor as category,
                            CAST(tradedate AS TIMESTAMP) as announcement_datetime,
                            received_at,
                            NULL as attachment_id,
                            symbol_nse,
                            symbol_bse,
                            raw_payload
                        FROM corporate_announcements
                        WHERE id IS NOT NULL
                    """)
                    
                    # Drop old table and rename new one
                    conn.execute("DROP TABLE corporate_announcements")
                    conn.execute("ALTER TABLE corporate_announcements_new RENAME TO corporate_announcements")
                    conn.commit()
                    print("[OK] Migration completed successfully")
                except Exception as e:
                    print(f"[WARNING] Migration error: {e}, keeping old schema")
                    conn.rollback()
            
            # Create corporate_announcements table with new schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_announcements (
                    announcement_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    exchange VARCHAR,
                    headline VARCHAR,
                    description TEXT,
                    category VARCHAR,
                    announcement_datetime TIMESTAMP,
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    attachment_id VARCHAR,
                    symbol_nse VARCHAR,
                    symbol_bse VARCHAR,
                    raw_payload TEXT
                )
            """)
            
            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_datetime 
                ON corporate_announcements(announcement_datetime DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_received_at 
                ON corporate_announcements(received_at DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_symbol 
                ON corporate_announcements(symbol)
            """)
            
            conn.commit()
            conn.close()
            
            # Start announcements manager
            from app.services.announcements_manager import get_announcements_manager
            manager = get_announcements_manager()
            manager.start()
            print("[OK] Corporate Announcements service started")
            
            # Start WebSocket workers for enabled TrueData connections
            try:
                from app.core.database import get_db
                from app.models.connection import Connection
                db_gen = get_db()
                db = next(db_gen)
                try:
                    enabled_truedata_conns = db.query(Connection).filter(
                        Connection.provider == "TrueData",
                        Connection.is_enabled == True
                    ).all()
                    
                    for conn in enabled_truedata_conns:
                        try:
                            manager.start_worker(conn.id)
                            print(f"[OK] Started WebSocket worker for TrueData connection {conn.id} ({conn.name})")
                        except Exception as e:
                            print(f"[WARNING] Failed to start WebSocket worker for connection {conn.id}: {e}")
                finally:
                    db.close()
            except Exception as e:
                print(f"[WARNING] Could not start WebSocket workers: {e}")
            
        except Exception as e:
            print(f"[WARNING] Could not initialize corporate announcements database: {e}")
        
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
        
        print("="*70)
        
        # Final startup message
        print("\n" + "="*70)
        print(" RUBIK ANALYTICS API - READY")
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
        
        
        # Close database connections
        try:
            manager = get_connection_manager(settings.DATA_DIR)
            if manager:
                manager.close_all()
        except Exception as e:
            print(f"[WARNING] Error closing database connections: {e}")
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
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(announcements.router, prefix="/api/v1", tags=["announcements"])

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
    return {"message": "Rubik Analytics API"}
