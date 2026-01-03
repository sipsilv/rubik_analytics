#!/usr/bin/env python3
"""
Accounts Schema Migration

Creates audit_logs table and adds account_status to users table.
Safe to run multiple times (idempotent).
"""
import sys
import os
from sqlalchemy import text, inspect

# Add backend directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, backend_dir)

from app.core.database import get_db_router
from app.core.config import settings

def run_migration():
    print("=" * 70)
    print("ACCOUNTS SCHEMA MIGRATION")
    print("=" * 70)
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client or not auth_client.connect():
        print("[ERROR] Database connection failed")
        return False

    db = auth_client.get_session()
    
    try:
        inspector = inspect(db.bind)
        
        # 1. Create audit_logs table
        if not inspector.has_table("audit_logs"):
            print("[MIGRATE] Creating 'audit_logs' table...")
            db.execute(text("""
                CREATE TABLE audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action VARCHAR NOT NULL,
                    performer_id INTEGER,
                    target_id VARCHAR,
                    target_type VARCHAR,
                    old_value TEXT,
                    new_value TEXT,
                    details TEXT,
                    ip_address VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(performer_id) REFERENCES users(id)
                )
            """))
            # Index on action
            db.execute(text("CREATE INDEX ix_audit_logs_action ON audit_logs (action)"))
            db.commit()
            print("[OK] 'audit_logs' created")
        else:
            print("[OK] 'audit_logs' table already exists")
        
        # 2. Add account_status to users
        user_columns = [col['name'] for col in inspector.get_columns('users')]
        if 'account_status' not in user_columns:
            print("[MIGRATE] Adding 'account_status' to users...")
            # Default to ACTIVE to preserve existing access
            db.execute(text("ALTER TABLE users ADD COLUMN account_status VARCHAR DEFAULT 'ACTIVE'"))
            # Sync is_active logic: if is_active=0, set status=DEACTIVATED
            db.execute(text("UPDATE users SET account_status = 'DEACTIVATED' WHERE is_active = 0 OR is_active = FALSE"))
            db.commit()
            print("[OK] 'account_status' added and synced")
        else:
            print("[OK] 'account_status' already exists")
        
        print("\n[SUCCESS] Accounts schema migration complete")
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

