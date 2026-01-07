"""
Script to fix all database paths to point to root data/ folder
"""
import os
import json
from pathlib import Path

# Get project root (parent of this script's directory)
project_root = Path(__file__).parent.absolute()
root_data = project_root / "data"
backend_data = project_root / "backend" / "data"

def fix_config_file():
    """Update config.py to use absolute path to root data folder"""
    config_file = project_root / "backend" / "app" / "core" / "config.py"
    
    if not config_file.exists():
        print(f"[ERROR] Config file not found: {config_file}")
        return False
    
    print(f"\n[1] Updating config.py...")
    
    # Read current config
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Calculate relative path from backend to root data
    # Since config is in backend/app/core/, we need to go up 3 levels to get to root
    # But we want to use absolute path or path relative to project root
    abs_data_path = str(root_data).replace('\\', '/')
    
    # Update DATA_DIR to use absolute path
    old_data_dir = 'DATA_DIR: str = "./data"'
    new_data_dir = f'DATA_DIR: str = r"{abs_data_path}"'
    
    if old_data_dir in content:
        content = content.replace(old_data_dir, new_data_dir)
        print(f"  [OK] Updated DATA_DIR to: {abs_data_path}")
    else:
        print(f"  [SKIP] DATA_DIR already updated or different format")
    
    # Update DATABASE_URL
    old_db_url = 'DATABASE_URL: str = "sqlite:///./data/auth/sqlite/auth.db"'
    new_db_url = f'DATABASE_URL: str = "sqlite:///{abs_data_path}/auth/sqlite/auth.db"'
    
    if old_db_url in content:
        content = content.replace(old_db_url, new_db_url)
        print(f"  [OK] Updated DATABASE_URL")
    else:
        print(f"  [SKIP] DATABASE_URL already updated or different format")
    
    # Update DUCKDB_PATH
    old_duckdb = 'DUCKDB_PATH: str = "./data/analytics/duckdb"'
    new_duckdb = f'DUCKDB_PATH: str = r"{abs_data_path}/analytics/duckdb"'
    
    if old_duckdb in content:
        content = content.replace(old_duckdb, new_duckdb)
        print(f"  [OK] Updated DUCKDB_PATH")
    else:
        print(f"  [SKIP] DUCKDB_PATH already updated or different format")
    
    # Write back
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def fix_connections_json():
    """Update connections.json to use relative paths from root data folder"""
    # Connections folder is now in backend/, not data/
    backend_dir = project_root / "backend"
    connections_file = backend_dir / "connections" / "connections.json"
    
    if not connections_file.exists():
        print(f"\n[2] Creating connections.json in root data folder...")
        connections_file.parent.mkdir(parents=True, exist_ok=True)
        connections = {
            "connections": [
                {
                    "id": "auth_sqlite_default",
                    "name": "Default SQLite Auth",
                    "type": "sqlite",
                    "category": "auth",
                    "config": {
                        "path": str(root_data / "auth" / "sqlite" / "auth.db")
                    },
                    "is_default": True,
                    "is_active": True,
                    "status": "active",
                    "last_tested": None,
                    "created_at": None
                },
                {
                    "id": "analytics_duckdb_default",
                    "name": "Default DuckDB Analytics",
                    "type": "duckdb",
                    "category": "analytics",
                    "config": {
                        "ohlcv": str(root_data / "analytics" / "duckdb" / "ohlcv.duckdb"),
                        "indicators": str(root_data / "analytics" / "duckdb" / "indicators.duckdb"),
                        "signals": str(root_data / "analytics" / "duckdb" / "signals.duckdb"),
                        "jobs": str(root_data / "analytics" / "duckdb" / "jobs.duckdb")
                    },
                    "is_default": True,
                    "is_active": True,
                    "status": "active",
                    "last_tested": None,
                    "created_at": None
                }
            ]
        }
        with open(connections_file, 'w', encoding='utf-8') as f:
            json.dump(connections, f, indent=2)
        print(f"  [OK] Created connections.json")
        return True
    
    print(f"\n[2] Updating connections.json...")
    
    # Read current connections
    with open(connections_file, 'r', encoding='utf-8') as f:
        connections = json.load(f)
    
    updated = False
    for conn in connections.get("connections", []):
        conn_id = conn.get("id", "")
        config = conn.get("config", {})
        
        # Fix SQLite paths
        if conn.get("type") == "sqlite" and "path" in config:
            old_path = config["path"]
            # Convert to absolute path pointing to root data
            if "backend" in old_path or not os.path.isabs(old_path):
                new_path = str(root_data / "auth" / "sqlite" / "auth.db")
                if old_path != new_path:
                    config["path"] = new_path
                    print(f"  [UPDATE] {conn_id}: path -> {new_path}")
                    updated = True
        
        # Fix DuckDB paths
        if conn.get("type") == "duckdb":
            for key in ["ohlcv", "indicators", "signals", "jobs"]:
                if key in config:
                    old_path = config[key]
                    if "backend" in old_path or (not os.path.isabs(old_path) and not old_path.startswith(str(root_data))):
                        new_path = str(root_data / "analytics" / "duckdb" / f"{key}.duckdb")
                        if old_path != new_path:
                            config[key] = new_path
                            print(f"  [UPDATE] {conn_id}: {key} -> {new_path}")
                            updated = True
        
        # Fix other DuckDB paths (symbols, etc.)
        if "path" in config and conn.get("type") in ["duckdb_direct", "duckdb_sqlalchemy"]:
            old_path = config["path"]
            if "backend" in old_path:
                # Determine the correct path based on category or path
                if "symbols" in old_path.lower():
                    new_path = str(root_data / "symbols" / "symbols.duckdb")
                elif "analytics" in old_path.lower() or "reference" in old_path.lower():
                    # Extract filename from old path
                    filename = os.path.basename(old_path)
                    new_path = str(root_data / "analytics" / "duckdb" / filename)
                else:
                    # Keep relative to root data
                    rel_path = Path(old_path).relative_to(backend_data) if backend_data in Path(old_path).parents else Path(old_path)
                    new_path = str(root_data / rel_path)
                
                if old_path != new_path:
                    config["path"] = new_path
                    print(f"  [UPDATE] {conn_id}: path -> {new_path}")
                    updated = True
    
    if updated:
        with open(connections_file, 'w', encoding='utf-8') as f:
            json.dump(connections, f, indent=2)
        print(f"  [OK] Updated connections.json")
    else:
        print(f"  [OK] connections.json already correct")
    
    return True

def main():
    print("=" * 80)
    print("FIXING DATABASE PATHS TO USE ROOT data/ FOLDER")
    print("=" * 80)
    print(f"Project root: {project_root}")
    print(f"Root data folder: {root_data}")
    print(f"Backend data folder: {backend_data}")
    
    fix_config_file()
    fix_connections_json()
    
    print("\n" + "=" * 80)
    print("PATH FIXING COMPLETE")
    print("=" * 80)
    print("\nNOTE: Some database files may still be locked.")
    print("If files were skipped, close the application and run:")
    print("  python check_and_consolidate_dbs.py")

if __name__ == "__main__":
    main()

