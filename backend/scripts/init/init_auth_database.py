#!/usr/bin/env python3
"""
Initialize the authentication database with tables and default admin user.

This script creates all database tables and ensures a super_admin user exists.
Safe to run multiple times (idempotent).
"""
import sys
import os
import uuid

# Add backend directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, backend_dir)

from app.core.database import Base, get_db_router, get_connection_manager
from app.models.user import User
from app.models.access_request import AccessRequest
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest
from app.models.connection import Connection
from app.models.audit_log import AuditLog
# Note: Symbol, SymbolUploadLog, ScheduledIngestion models have been removed.
# TransformationScript may be used for other purposes, but is not imported here.
# Import only auth-related models.
from app.core.security import get_password_hash
from app.core.config import settings

def init_auth_database():
    """Initialize authentication database with tables and default admin user"""
    print("Initializing authentication database...")
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client:
        print("[ERROR] Failed to connect to authentication database")
        return False
    
    # Ensure client is connected
    if not auth_client.is_connected:
        if not auth_client.connect():
            print("[ERROR] Failed to connect to authentication database")
            return False
    
    # Create all tables using the client's engine
    if hasattr(auth_client, 'engine') and auth_client.engine:
        engine = auth_client.engine
    else:
        # Fallback: create engine from connection config
        from sqlalchemy import create_engine
        manager = get_connection_manager(settings.DATA_DIR)
        conn_id = manager.active_connections.get("auth")
        if conn_id:
            conn_config = manager.connections.get(conn_id, {}).get("config", {})
            db_path = conn_config.get("path", os.path.join(settings.DATA_DIR, "auth", "sqlite", "auth.db"))
        else:
            db_path = os.path.join(settings.DATA_DIR, "auth", "sqlite", "auth.db")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")
    
    db = auth_client.get_session()
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            # Create default admin user
            admin = User(
                user_id=str(uuid.uuid4()),
                username="admin",
                email="admin@rubikview.com",
                mobile="+10000000000",
                hashed_password=get_password_hash("admin123"),
                role="super_admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("[OK] Default admin user created")
            print(f"  User ID: {admin.user_id}")
            print("  Username: admin")
            print("  Password: admin123")
            print("  Role: super_admin")
            print("  Status: ACTIVE")
            print("  [WARNING] Please change the password after first login!")
        else:
            # Ensure admin has user_id if missing
            if not admin.user_id or admin.user_id == '':
                admin.user_id = str(uuid.uuid4())
                db.commit()
                print(f"[OK] Generated user_id for existing admin: {admin.user_id}")
            
            # Ensure admin has mobile if missing
            if not admin.mobile or admin.mobile == '':
                admin.mobile = "+10000000000"
                db.commit()
                print("[OK] Set mobile number for existing admin")
            
            # Ensure existing admin user is active and has super_admin role
            was_updated = False
            if not admin.is_active:
                admin.is_active = True
                was_updated = True
                print("[OK] Admin user activated")
            
            # Case-insensitive role check
            if admin.role and admin.role.lower() != "super_admin":
                admin.role = "super_admin"
                was_updated = True
                print("[OK] Admin user promoted to super_admin")
            
            if was_updated:
                db.commit()
                print("[OK] Admin user updated")
            else:
                print("[OK] Admin user already exists and is active")
            
            print(f"  Username: {admin.username}")
            print(f"  Email: {admin.email}")
            print(f"  Role: {admin.role}")
            print(f"  Status: {'ACTIVE' if admin.is_active else 'INACTIVE'}")
        
        # Ensure ALL super_admin users are active (critical) - case-insensitive
        all_users = db.query(User).all()
        super_admins = [u for u in all_users if u.role and u.role.lower() == "super_admin"]
        super_admin_updated = False
        for super_user in super_admins:
            # Normalize role
            if super_user.role.lower() != "super_admin":
                super_user.role = "super_admin"
                super_admin_updated = True
                print(f"[OK] Normalized role for {super_user.username} to super_admin")
            if not super_user.is_active:
                super_user.is_active = True
                super_admin_updated = True
                print(f"[OK] Activated super_admin user: {super_user.username}")
        
        if super_admin_updated:
            db.commit()
            print("[OK] All super_admin users are now active and protected")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = init_auth_database()
    if success:
        print("[OK] Authentication database initialization complete")
    else:
        print("[ERROR] Authentication database initialization failed")
        sys.exit(1)

