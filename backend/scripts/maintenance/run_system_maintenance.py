#!/usr/bin/env python3
"""
System maintenance utilities for Rubik Analytics backend.

Provides diagnostic and maintenance functions that are safe to run repeatedly.
All operations are idempotent.
"""
import sys
import os
from pathlib import Path
import datetime

# Add backend directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import get_db_router
from app.core.config import settings
from app.models.user import User

def diagnose_users():
    """Diagnose all users and their status"""
    print("=" * 60)
    print("User Diagnostic Report")
    print("=" * 60)
    print()
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client:
        print("[ERROR] Could not connect to database")
        return False
    
    if not auth_client.is_connected:
        if not auth_client.connect():
            print("[ERROR] Failed to connect to database")
            return False
    
    db = auth_client.get_session()
    try:
        users = db.query(User).all()
        print(f"Total users: {len(users)}")
        print()
        
        for user in users:
            print(f"User: {user.username}")
            print(f"  ID: {user.id}")
            print(f"  User ID: {user.user_id if hasattr(user, 'user_id') else 'N/A'}")
            print(f"  Email: {user.email}")
            print(f"  Mobile: {user.mobile}")
            print(f"  Role: {user.role}")
            print(f"  Status: {'ACTIVE' if user.is_active else 'INACTIVE'}")
            print()
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def diagnose_super_users():
    """Diagnose super admin users specifically"""
    print("=" * 60)
    print("Super User Diagnostic Report")
    print("=" * 60)
    print()
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client:
        print("[ERROR] Could not connect to database")
        return False
    
    if not auth_client.is_connected:
        if not auth_client.connect():
            print("[ERROR] Failed to connect to database")
            return False
    
    db = auth_client.get_session()
    try:
        all_users = db.query(User).all()
        super_users = [u for u in all_users if u.role and u.role.lower() == "super_admin"]
        
        print(f"Total super admin users: {len(super_users)}")
        print()
        
        if not super_users:
            print("[WARNING] No super admin users found!")
            return False
        
        for user in super_users:
            print(f"Super Admin: {user.username}")
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Role: {user.role}")
            print(f"  Status: {'ACTIVE' if user.is_active else 'INACTIVE'}")
            print(f"  Can Login: {'YES' if user.is_active else 'NO (should be fixed)'}")
            print()
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def check_database():
    """Check database status"""
    print("=" * 60)
    print("Database Status Check")
    print("=" * 60)
    print()
    
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    
    if not auth_client:
        print("[ERROR] Could not connect to database")
        return False
    
    db = auth_client.get_session()
    try:
        user_count = db.query(User).count()
        print(f"Users in database: {user_count}")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def fix_stuck_uploads():
    """
    Fix stuck uploads - placeholder (symbols module removed)
    """
    print("=" * 60)
    print("Fixing Stuck Uploads")
    print("=" * 60)
    print()
    print("[INFO] Symbols module has been removed. This function is no longer available.")
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="System maintenance utilities for Rubik Analytics")
    parser.add_argument("command", choices=["users", "super-users", "db", "fix-uploads"], 
                       help="Command to run: users, super-users, db, or fix-uploads (fix-uploads is deprecated)")
    
    args = parser.parse_args()
    
    if args.command == "users":
        success = diagnose_users()
    elif args.command == "super-users":
        success = diagnose_super_users()
    elif args.command == "db":
        success = check_database()
    elif args.command == "fix-uploads":
        success = fix_stuck_uploads()
    
    sys.exit(0 if success else 1)

