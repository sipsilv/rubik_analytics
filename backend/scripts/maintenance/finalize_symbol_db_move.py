"""
Script to finalize the move of symbols database and check for duplicates
"""

import os
import shutil
from pathlib import Path
import duckdb

ROOT_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data")
BACKEND_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/backend/data")

# Locations
CORRECT_LOCATION = ROOT_DATA / "symbols" / "symbols.duckdb"
OLD_LOCATION = ROOT_DATA / "analytics" / "duckdb" / "symbols.duckdb"

def check_database_info(db_path: Path):
    """Get information about a database"""
    if not db_path.exists():
        return None
    
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        symbol_count = 0
        if "symbols" in tables:
            result = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
            symbol_count = result[0] if result else 0
        conn.close()
        
        size = db_path.stat().st_size
        return {
            "exists": True,
            "size": size,
            "tables": tables,
            "symbol_count": symbol_count
        }
    except Exception as e:
        return {"exists": True, "error": str(e), "size": db_path.stat().st_size if db_path.exists() else 0}

def check_all_databases():
    """Check all database locations for duplicates"""
    print("=" * 80)
    print("CHECKING ALL DATABASES FOR DUPLICATES")
    print("=" * 80)
    print()
    
    # Analytics databases
    print("Analytics Databases:")
    analytics_dbs = [
        ("ohlcv.duckdb", ROOT_DATA / "analytics" / "duckdb" / "ohlcv.duckdb"),
        ("indicators.duckdb", ROOT_DATA / "analytics" / "duckdb" / "indicators.duckdb"),
        ("signals.duckdb", ROOT_DATA / "analytics" / "duckdb" / "signals.duckdb"),
        ("jobs.duckdb", ROOT_DATA / "analytics" / "duckdb" / "jobs.duckdb"),
    ]
    
    duplicates = []
    
    for name, primary_path in analytics_dbs:
        backend_path = BACKEND_DATA / "analytics" / "duckdb" / name
        
        primary_exists = primary_path.exists()
        backend_exists = backend_path.exists()
        
        print(f"  {name}:")
        print(f"    Primary: {primary_path} {'[EXISTS]' if primary_exists else '[MISSING]'}")
        if primary_exists:
            size = primary_path.stat().st_size
            print(f"      Size: {size:,} bytes")
        
        if backend_exists:
            size = backend_path.stat().st_size
            print(f"    Duplicate: {backend_path} [EXISTS]")
            print(f"      Size: {size:,} bytes")
            duplicates.append(backend_path)
        print()
    
    # Auth database
    print("Auth Database:")
    auth_primary = ROOT_DATA / "auth" / "sqlite" / "auth.db"
    auth_backend = BACKEND_DATA / "auth" / "sqlite" / "auth.db"
    
    print(f"  Primary: {auth_primary} {'[EXISTS]' if auth_primary.exists() else '[MISSING]'}")
    if auth_primary.exists():
        size = auth_primary.stat().st_size
        print(f"    Size: {size:,} bytes")
    
    if auth_backend.exists():
        size = auth_backend.stat().st_size
        print(f"  Duplicate: {auth_backend} [EXISTS]")
        print(f"    Size: {size:,} bytes")
        duplicates.append(auth_backend)
    print()
    
    # Symbols database
    print("Symbols Database:")
    print(f"  Correct Location: {CORRECT_LOCATION}")
    correct_info = check_database_info(CORRECT_LOCATION)
    if correct_info:
        print(f"    [OK] Exists - {correct_info['size']:,} bytes")
        if "symbol_count" in correct_info:
            print(f"    Symbols: {correct_info['symbol_count']:,}")
    else:
        print(f"    [MISSING]")
    
    print(f"  Old Location: {OLD_LOCATION}")
    old_info = check_database_info(OLD_LOCATION)
    if old_info:
        print(f"    [FOUND] Still exists - {old_info['size']:,} bytes")
        if "symbol_count" in old_info:
            print(f"    Symbols: {old_info['symbol_count']:,}")
        duplicates.append(OLD_LOCATION)
    else:
        print(f"    [OK] Not found")
    print()
    
    return duplicates

def remove_duplicates(duplicates):
    """Remove duplicate databases"""
    print("=" * 80)
    print("REMOVING DUPLICATES")
    print("=" * 80)
    print()
    
    removed = []
    failed = []
    
    for dup_path in duplicates:
        try:
            print(f"Removing: {dup_path}")
            dup_path.unlink()
            removed.append(dup_path)
            print(f"  [OK] Removed")
        except PermissionError:
            print(f"  [SKIP] File is locked (may be in use)")
            failed.append(dup_path)
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            failed.append(dup_path)
        print()
    
    return removed, failed

def main():
    print("=" * 80)
    print("FINALIZING SYMBOLS DATABASE MOVE")
    print("=" * 80)
    print()
    
    # Check all databases
    duplicates = check_all_databases()
    
    # Remove duplicates
    if duplicates:
        print(f"Found {len(duplicates)} duplicate database(s) to remove")
        removed, failed = remove_duplicates(duplicates)
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Successfully removed: {len(removed)} duplicate(s)")
        if failed:
            print(f"Could not remove: {len(failed)} file(s) (may be in use)")
            print("\nLocked files (close applications and remove manually):")
            for f in failed:
                print(f"  - {f}")
    else:
        print("[OK] No duplicates found!")

if __name__ == "__main__":
    main()

