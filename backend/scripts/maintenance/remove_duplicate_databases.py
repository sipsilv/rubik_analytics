"""
Script to remove duplicate databases from backend/data/ folder.
All databases have been consolidated into the root data/ folder.
"""

import os
import shutil
from pathlib import Path

ROOT_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data")
BACKEND_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/backend/data")

# Duplicate databases to remove
DUPLICATES = [
    BACKEND_DATA / "analytics" / "duckdb" / "ohlcv.duckdb",
    BACKEND_DATA / "analytics" / "duckdb" / "indicators.duckdb",
    BACKEND_DATA / "analytics" / "duckdb" / "signals.duckdb",
    BACKEND_DATA / "analytics" / "duckdb" / "jobs.duckdb",
    BACKEND_DATA / "auth" / "sqlite" / "auth.db",
    # Also remove the entire backend/data folder structure if empty
]

# Locked files that need manual removal
LOCKED_FILES = [
    ROOT_DATA / "symbols" / "symbols.db",
    BACKEND_DATA / "symbols" / "symbols.db",
]

def remove_duplicates():
    """Remove duplicate databases"""
    print("=" * 80)
    print("REMOVING DUPLICATE DATABASES")
    print("=" * 80)
    print()
    
    removed = []
    failed = []
    
    for db_path in DUPLICATES:
        if db_path.exists():
            try:
                print(f"Removing: {db_path}")
                db_path.unlink()
                removed.append(str(db_path))
                print(f"  [OK] Removed")
            except PermissionError:
                print(f"  [SKIP] File is locked (may be in use)")
                failed.append(str(db_path))
            except Exception as e:
                print(f"  [ERROR] {str(e)}")
                failed.append(str(db_path))
        else:
            print(f"Skipping (not found): {db_path}")
    
    print()
    print(f"Removed: {len(removed)} file(s)")
    if failed:
        print(f"Failed/Skipped: {len(failed)} file(s)")
        print("\nLocked files (close applications and remove manually):")
        for f in failed:
            print(f"  - {f}")
    
    # Check for locked symbol.db files
    print()
    print("=" * 80)
    print("LOCKED FILES (Invalid databases - safe to remove manually)")
    print("=" * 80)
    print()
    for locked_file in LOCKED_FILES:
        if locked_file.exists():
            print(f"  {locked_file}")
            print(f"    -> This file is not a valid database and can be safely deleted")
            print(f"    -> Close any applications using it, then delete manually")
            print()
    
    return removed, failed

def main():
    print("=" * 80)
    print("DUPLICATE DATABASE REMOVAL SCRIPT")
    print("=" * 80)
    print()
    print("This script will remove duplicate databases from backend/data/")
    print("All data has been consolidated into the root data/ folder.")
    print()
    
    removed, failed = remove_duplicates()
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Successfully removed: {len(removed)} duplicate database(s)")
    if failed:
        print(f"Could not remove: {len(failed)} file(s) (may be in use)")
        print("\nPlease close any applications using these files and run again,")
        print("or delete them manually.")

if __name__ == "__main__":
    main()

