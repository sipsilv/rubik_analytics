"""
Script to check database files in both locations and consolidate them to root data/ folder
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

# Paths
root_data = Path("data")
backend_data = Path("backend/data")

def get_file_info(file_path):
    """Get file size and modification time"""
    if file_path.exists():
        return {
            "size": os.path.getsize(file_path),
            "mtime": os.path.getmtime(file_path),
            "mtime_str": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        }
    return None

def compare_and_copy_files():
    """Compare files and copy from backend/data to root data if needed"""
    print("=" * 80)
    print("DATABASE CONSOLIDATION CHECK")
    print("=" * 80)
    
    # Check root data folder
    print("\n[1] Checking ROOT data/ folder...")
    root_files = {}
    for ext in ["*.db", "*.duckdb"]:
        for file_path in root_data.rglob(ext):
            if file_path.is_file():
                rel_path = file_path.relative_to(root_data)
                root_files[str(rel_path)] = get_file_info(file_path)
                print(f"  [OK] {rel_path}: {root_files[str(rel_path)]['size']} bytes, modified {root_files[str(rel_path)]['mtime_str']}")
    
    # Check backend data folder
    print("\n[2] Checking BACKEND data/ folder...")
    backend_files = {}
    for ext in ["*.db", "*.duckdb"]:
        for file_path in backend_data.rglob(ext):
            if file_path.is_file():
                rel_path = file_path.relative_to(backend_data)
                backend_files[str(rel_path)] = {
                    "info": get_file_info(file_path),
                    "full_path": file_path
                }
                info = backend_files[str(rel_path)]["info"]
                print(f"  [OK] {rel_path}: {info['size']} bytes, modified {info['mtime_str']}")
    
    # Compare and copy
    print("\n[3] Comparing and copying files...")
    copied_count = 0
    updated_count = 0
    
    for rel_path, backend_file_info in backend_files.items():
        backend_info = backend_file_info["info"]
        backend_full_path = backend_file_info["full_path"]
        
        target_path = root_data / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if rel_path not in root_files:
            # File doesn't exist in root, copy it
            print(f"  [COPY] Copying NEW file: {rel_path}")
            try:
                shutil.copy2(backend_full_path, target_path)
                copied_count += 1
            except PermissionError:
                print(f"    [SKIP] File is locked (in use): {rel_path}")
                print(f"    [NOTE] Please close the application and run this script again")
        else:
            # File exists, compare
            root_info = root_files[rel_path]
            if backend_info["mtime"] > root_info["mtime"] or backend_info["size"] != root_info["size"]:
                # Backend file is newer or different size, copy it
                print(f"  [UPDATE] Updating file (backend is newer/different): {rel_path}")
                print(f"    Root: {root_info['size']} bytes, {root_info['mtime_str']}")
                print(f"    Backend: {backend_info['size']} bytes, {backend_info['mtime_str']}")
                try:
                    shutil.copy2(backend_full_path, target_path)
                    updated_count += 1
                except PermissionError:
                    print(f"    [SKIP] File is locked (in use): {rel_path}")
                    print(f"    [NOTE] Please close the application and run this script again")
            else:
                print(f"  [OK] File up to date: {rel_path}")
    
    # Copy temp folder if it exists
    print("\n[4] Checking temp folder...")
    backend_temp = backend_data / "temp"
    root_temp = root_data / "temp"
    if backend_temp.exists() and backend_temp.is_dir():
        if not root_temp.exists():
            print(f"  [COPY] Copying temp folder...")
            shutil.copytree(backend_temp, root_temp)
        else:
            print(f"  [OK] Temp folder already exists in root")
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {copied_count} new files copied, {updated_count} files updated")
    print("=" * 80)
    
    # Final check
    print("\n[5] Final database files in root data/ folder:")
    for ext in ["*.db", "*.duckdb"]:
        for file_path in sorted(root_data.rglob(ext)):
            if file_path.is_file():
                rel_path = file_path.relative_to(root_data)
                info = get_file_info(file_path)
                print(f"  [OK] {rel_path}: {info['size']} bytes")

if __name__ == "__main__":
    compare_and_copy_files()

