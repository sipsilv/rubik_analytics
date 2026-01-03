#!/usr/bin/env python3
"""
Core Schema Migration

Migrates core user table schema:
- Adds missing columns (user_id, name, theme_preference, last_active_at)
- Backfills missing data (UUIDs for user_id)
- Safe to run multiple times (idempotent)
"""
import sys
import os
import uuid
from sqlalchemy import text, inspect

# Add backend directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, backend_dir)

from app.core.database import get_db_router
from app.core.config import settings

def run_migration():
    print("=" * 70)
    print("CORE SCHEMA MIGRATION")
    print("=" * 70)
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client or not auth_client.connect():
        print("[ERROR] Could not connect to database")
        return False

    db = auth_client.get_session()
    
    try:
        # Inspect current schema
        inspector = inspect(db.bind)
        columns = [col['name'] for col in inspector.get_columns('users')]
        print(f"[INFO] Existing columns: {columns}")
        
        # 1. Fix 'theme_preference'
        if 'theme_preference' not in columns:
            print("[MIGRATE] Adding 'theme_preference' column...")
            try:
                try:
                    db.execute(text("ALTER TABLE users ADD COLUMN theme_preference VARCHAR DEFAULT 'dark'"))
                except Exception:
                    # Fallback for older SQLite
                    db.execute(text("ALTER TABLE users ADD COLUMN theme_preference VARCHAR"))
                db.commit()
                # Backfill
                db.execute(text("UPDATE users SET theme_preference = 'dark' WHERE theme_preference IS NULL"))
                db.commit()
                print("[OK] 'theme_preference' added")
            except Exception as e:
                print(f"[WARN] Failed to add 'theme_preference': {e}")
                db.rollback()
        else:
            print("[OK] 'theme_preference' exists")
        
        # 2. Fix 'name'
        if 'name' not in columns:
            print("[MIGRATE] Adding 'name' column...")
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR"))
                db.commit()
                print("[OK] 'name' added")
            except Exception as e:
                print(f"[WARN] Failed to add 'name': {e}")
                db.rollback()
        else:
            print("[OK] 'name' exists")
        
        # 3. Fix 'user_id' (CRITICAL)
        if 'user_id' not in columns:
            print("[MIGRATE] Adding 'user_id' column...")
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN user_id VARCHAR"))
                db.commit()
                print("[OK] 'user_id' added. Backfilling UUIDs...")
                
                # Backfill logic
                users = db.execute(text("SELECT id FROM users WHERE user_id IS NULL")).fetchall()
                for row in users:
                    uid = str(uuid.uuid4())
                    db.execute(text("UPDATE users SET user_id = :uid WHERE id = :id"), {"uid": uid, "id": row[0]})
                
                db.commit()
                print(f"[OK] Backfilled {len(users)} users with new UUIDs")
            except Exception as e:
                print(f"[ERROR] Failed to add/backfill 'user_id': {e}")
                db.rollback()
        else:
            print("[OK] 'user_id' exists")
        
        # 4. Fix 'last_active_at'
        if 'last_active_at' not in columns:
            print("[MIGRATE] Adding 'last_active_at' column...")
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN last_active_at TIMESTAMP"))
                db.commit()
                print("[OK] 'last_active_at' added")
            except Exception as e:
                print(f"[WARN] Failed to add 'last_active_at': {e}")
                db.rollback()
        else:
            print("[OK] 'last_active_at' exists")
        
        print("\n[SUCCESS] Core schema migration complete")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

