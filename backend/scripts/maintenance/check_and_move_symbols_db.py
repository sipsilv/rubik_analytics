"""
Script to verify symbols database is in the correct location and check for duplicates
"""

import os
import shutil
from pathlib import Path
import duckdb

ROOT_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data")

# Correct location
CORRECT_LOCATION = ROOT_DATA / "symbols" / "symbols.duckdb"
OLD_LOCATION = ROOT_DATA / "analytics" / "duckdb" / "symbols.duckdb"

# Other possible locations to check
OTHER_LOCATIONS = [
    ROOT_DATA / "analytics" / "symbols" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "symbols" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "analytics" / "duckdb" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "analytics" / "symbols" / "symbols.duckdb",
]

def check_database_info(db_path: Path):
    """Get information about a database"""
    if not db_path.exists():
        return None
    
    try:
        conn = duckdb.connect(str(db_path))
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
        return {"exists": True, "error": str(e), "size": db_path.stat().st_size}

def main():
    print("=" * 80)
    print("CHECKING SYMBOLS DATABASE LOCATIONS")
    print("=" * 80)
    print()
    
    # Check correct location
    print(f"Correct Location: {CORRECT_LOCATION}")
    correct_info = check_database_info(CORRECT_LOCATION)
    if correct_info:
        print(f"  [OK] Exists")
        print(f"  Size: {correct_info['size']:,} bytes ({correct_info['size'] / 1024 / 1024:.2f} MB)")
        if "symbol_count" in correct_info:
            print(f"  Symbols: {correct_info['symbol_count']:,}")
        if "error" in correct_info:
            print(f"  [ERROR] {correct_info['error']}")
    else:
        print(f"  [MISSING] Database not found!")
    print()
    
    # Check old location
    print(f"Old Location (analytics/duckdb): {OLD_LOCATION}")
    old_info = check_database_info(OLD_LOCATION)
    if old_info:
        print(f"  [FOUND] Still exists!")
        print(f"  Size: {old_info['size']:,} bytes")
        if "symbol_count" in old_info:
            print(f"  Symbols: {old_info['symbol_count']:,}")
        print(f"  [ACTION] Should be removed")
    else:
        print(f"  [OK] Not found (already moved/removed)")
    print()
    
    # Check other locations
    print("Other Possible Locations:")
    duplicates_found = []
    for loc in OTHER_LOCATIONS:
        info = check_database_info(loc)
        if info:
            print(f"  {loc}")
            print(f"    [FOUND] Size: {info['size']:,} bytes")
            if "symbol_count" in info:
                print(f"    Symbols: {info['symbol_count']:,}")
            duplicates_found.append(loc)
        else:
            print(f"  {loc}")
            print(f"    [OK] Not found")
    print()
    
    # Summary and actions
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if correct_info and not correct_info.get("error"):
        print("[OK] Symbols database is in correct location")
    else:
        print("[ERROR] Symbols database not found in correct location!")
    
    if old_info:
        print(f"[ACTION NEEDED] Remove old database: {OLD_LOCATION}")
        response = input("Remove old database from analytics/duckdb? (y/n): ")
        if response.lower() == 'y':
            try:
                OLD_LOCATION.unlink()
                print(f"[OK] Removed {OLD_LOCATION}")
            except Exception as e:
                print(f"[ERROR] Could not remove: {e}")
    
    if duplicates_found:
        print(f"[ACTION NEEDED] Found {len(duplicates_found)} duplicate(s) in other locations")
        for dup in duplicates_found:
            print(f"  - {dup}")
        response = input("Remove duplicates? (y/n): ")
        if response.lower() == 'y':
            for dup in duplicates_found:
                try:
                    dup.unlink()
                    print(f"[OK] Removed {dup}")
                except Exception as e:
                    print(f"[ERROR] Could not remove {dup}: {e}")
    else:
        print("[OK] No duplicates found in other locations")

if __name__ == "__main__":
    main()

