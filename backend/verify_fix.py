import os
import sys

# Add backend directory to sys.path
backend_dir = r'c:\Users\jallu\OneDrive\pgp\Python\Stock predictor\rubik-analytics\backend'
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Mock settings before importing app components if necessary
# or just set environment variables
os.environ["DATA_DIR"] = r'c:\Users\jallu\OneDrive\pgp\Python\Stock predictor\rubik-analytics\data'

import duckdb
from app.models.screener import get_active_symbols, get_db_connection

def verify():
    print("Connecting to database...")
    conn = get_db_connection()
    
    print("Fetching active symbols...")
    symbols = get_active_symbols(conn)
    
    print(f"\nTotal symbols fetched: {len(symbols)}")
    print("\nFirst 20 symbols:")
    for idx, s in enumerate(symbols[:20]):
        print(f"[{idx+1}] Name: '{s['symbol']}', Exchange: '{s['exchange']}'")
        # Check if it looks like an ID
        name = s['symbol']
        if len(name) == 5 and name[:2].isdigit() and name[2:].isalnum():
             print(f"  ⚠ WARNING: '{name}' still looks like an ID!")
    
    conn.close()

if __name__ == "__main__":
    verify()
