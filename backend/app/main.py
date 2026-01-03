from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.api.v1 import auth, users, admin, connections, websocket, symbols, screener, announcements
from app.core.config import settings
from app.core.database import get_connection_manager, get_db_router

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

# Initialize database connections on startup
# Initialize database connections on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup"""
    try:
        manager = get_connection_manager(settings.DATA_DIR)
        router = get_db_router(settings.DATA_DIR)
        
        # Test default connections
        auth_client = router.get_auth_db()
        if auth_client:
            print(f"[OK] Auth database connected: {auth_client.health_check()}")
        else:
            print("[ERROR] Auth database connection failed")
        
        analytics_client = router.get_analytics_db()
        if analytics_client:
            print(f"[OK] Analytics database connected")
        else:
            print("[ERROR] Analytics database connection failed")
        
        # Ensure Super User exists
        try:
            db = auth_client.get_session()
            from app.models.user import User
            from app.core.security import get_password_hash
            from sqlalchemy import inspect
            
            # Simple check for super user
            try:
                all_users = db.query(User).all()
                super_admins = [u for u in all_users if u.role and u.role.lower() == "super_admin"]
                
                if not super_admins:
                    print("[CRITICAL] No Super User found - creating default Super User")
                    import uuid
                    default_admin = User(
                        user_id=str(uuid.uuid4()),
                        username="admin",
                        email="admin@rubikview.com",
                        mobile="+10000000000",
                        hashed_password=get_password_hash("admin123"),
                        role="super_admin",
                        is_active=True,
                        theme_preference="dark"
                    )
                    db.add(default_admin)
                    db.commit()
                    print("[OK] Default Super User 'admin' created (password: admin123)")
                else:
                    print(f"[OK] {len(super_admins)} Super User(s) found.")
                    
            except Exception as e:
                print(f"[WARNING] Could not verify Super User (Database might be initializing): {e}")
                
            db.close()
        except Exception as e:
            print(f"[ERROR] Startup verification failed: {e}")
        
        # Symbols module has been removed
        pass
        
        # Start WebSocket cleanup task
        try:
            from app.core.websocket_manager import manager
            import asyncio
            # Create background task for cleanup
            loop = asyncio.get_event_loop()
            loop.create_task(manager.cleanup_stale_connections())
            print("[OK] WebSocket cleanup task started")
        except Exception as e:
            print(f"[WARNING] Could not start WebSocket cleanup task: {e}")
        
        # Start TrueData token refresh scheduler
        try:
            from app.services.token_refresh_scheduler import start_token_refresh_scheduler
            start_token_refresh_scheduler()
            print("[OK] TrueData token refresh scheduler started")
        except Exception as e:
            print(f"[WARNING] Could not start token refresh scheduler: {e}")
        
        # Initialize Screener Database and reset stale "Running" statuses
        try:
            import app.models.screener as screener_service
            screener_service.init_screener_database()
            # Ensure default connection exists
            conn = screener_service.get_db_connection()
            
            # Reset any connections that are still marked as "Running" (stale status from previous backend run)
            try:
                from datetime import datetime, timezone
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
                print(f"[WARNING] Could not reset stale screener connection statuses: {reset_error}")
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
            
            print("[OK] Screener database initialized with default connection")
        except Exception as e:
            print(f"[WARNING] Could not initialize Screener database: {e}")
        
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
            
            # Create corporate_announcements table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_announcements (
                    id VARCHAR PRIMARY KEY,
                    tradedate VARCHAR,
                    company_name VARCHAR,
                    headline VARCHAR,
                    news_sub VARCHAR,
                    news_body TEXT,
                    symbol_nse VARCHAR,
                    symbol_bse VARCHAR,
                    descriptor VARCHAR,
                    raw_payload TEXT,
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_tradedate 
                ON corporate_announcements(tradedate DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_announcements_received_at 
                ON corporate_announcements(received_at DESC)
            """)
            
            conn.close()
            print(f"[OK] Corporate announcements database initialized: {db_path}")
        except Exception as e:
            print(f"[WARNING] Could not initialize corporate announcements database: {e}")
        
        # Start Scheduler Service
        try:
            from app.services.scheduler_service import get_scheduler_service
            scheduler_service = get_scheduler_service()
            scheduler_service.start()
            print("[OK] Scheduler service started")
        except Exception as e:
            print(f"[WARNING] Could not start scheduler service: {e}")
        

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
