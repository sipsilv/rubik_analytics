"""
Script to verify all databases are accessible and working correctly
"""
import os
import sys
from pathlib import Path

# Add backend to path
project_root = Path(__file__).parent.absolute()
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.core.database import get_connection_manager, get_db_router
from app.models.user import User

def verify_databases():
    """Verify all databases are accessible"""
    print("=" * 80)
    print("VERIFYING DATABASE CONNECTIONS")
    print("=" * 80)
    print(f"Data directory: {settings.DATA_DIR}")
    print()
    
    all_ok = True
    
    # Test connection manager
    print("[1] Testing Connection Manager...")
    try:
        manager = get_connection_manager(settings.DATA_DIR)
        print(f"  [OK] Connection manager initialized")
        print(f"  [INFO] Data dir: {manager.data_dir}")
    except Exception as e:
        print(f"  [ERROR] Connection manager failed: {e}")
        all_ok = False
        return all_ok
    
    # Test database router
    print("\n[2] Testing Database Router...")
    try:
        router = get_db_router(settings.DATA_DIR)
        print(f"  [OK] Database router initialized")
    except Exception as e:
        print(f"  [ERROR] Database router failed: {e}")
        all_ok = False
        return all_ok
    
    # Test auth database
    print("\n[3] Testing Auth Database (SQLite)...")
    try:
        auth_client = router.get_auth_db()
        if auth_client:
            health = auth_client.health_check()
            print(f"  [OK] Auth database connected")
            print(f"  [INFO] Type: {health.get('type')}")
            print(f"  [INFO] Path: {health.get('path')}")
            print(f"  [INFO] Status: {health.get('status')}")
            
            # Try to query users
            session = auth_client.get_session()
            try:
                user_count = session.query(User).count()
                print(f"  [OK] Can query database - {user_count} users found")
            except Exception as e:
                print(f"  [WARNING] Query test failed: {e}")
            finally:
                session.close()
        else:
            print(f"  [ERROR] Auth database client is None")
            all_ok = False
    except Exception as e:
        print(f"  [ERROR] Auth database test failed: {e}")
        all_ok = False
    
    # Test analytics database
    print("\n[4] Testing Analytics Database (DuckDB)...")
    try:
        analytics_client = router.get_analytics_db()
        if analytics_client:
            print(f"  [OK] Analytics database connected")
            print(f"  [INFO] Type: DuckDB")
        else:
            print(f"  [WARNING] Analytics database client is None (may be optional)")
    except Exception as e:
        print(f"  [WARNING] Analytics database test failed: {e}")
        # Analytics might be optional, so don't fail completely
    
    # Check database files exist
    print("\n[5] Checking Database Files...")
    db_files = [
        ("Auth DB", Path(settings.DATA_DIR) / "auth" / "sqlite" / "auth.db"),
        ("OHLCV DB", Path(settings.DATA_DIR) / "analytics" / "duckdb" / "ohlcv.duckdb"),
        ("Indicators DB", Path(settings.DATA_DIR) / "analytics" / "duckdb" / "indicators.duckdb"),
        ("Signals DB", Path(settings.DATA_DIR) / "analytics" / "duckdb" / "signals.duckdb"),
        ("Jobs DB", Path(settings.DATA_DIR) / "analytics" / "duckdb" / "jobs.duckdb"),
        ("Symbols DB", Path(settings.DATA_DIR) / "symbols" / "symbols.duckdb"),
    ]
    
    for name, path in db_files:
        if path.exists():
            size = path.stat().st_size
            print(f"  [OK] {name}: {path} ({size:,} bytes)")
        else:
            print(f"  [MISSING] {name}: {path} (file not found)")
            if name == "Auth DB":
                all_ok = False
    
    # Check for duplicate files in backend/data
    print("\n[6] Checking for Duplicate Files in backend/data...")
    backend_data = project_root / "backend" / "data"
    if backend_data.exists():
        duplicate_count = 0
        for ext in ["*.db", "*.duckdb"]:
            for file_path in backend_data.rglob(ext):
                if file_path.is_file():
                    rel_path = file_path.relative_to(backend_data)
                    root_path = project_root / "data" / rel_path
                    if root_path.exists():
                        print(f"  [DUPLICATE] {rel_path} exists in both locations")
                        duplicate_count += 1
        if duplicate_count == 0:
            print(f"  [OK] No duplicate database files found")
        else:
            print(f"  [WARNING] {duplicate_count} duplicate files found in backend/data/")
            print(f"  [NOTE] Consider removing backend/data/ folder after verifying root data/ works")
    else:
        print(f"  [OK] backend/data/ folder does not exist")
    
    print("\n" + "=" * 80)
    if all_ok:
        print("VERIFICATION COMPLETE: All critical databases are working!")
    else:
        print("VERIFICATION COMPLETE: Some issues found (see above)")
    print("=" * 80)
    
    return all_ok

if __name__ == "__main__":
    success = verify_databases()
    sys.exit(0 if success else 1)

