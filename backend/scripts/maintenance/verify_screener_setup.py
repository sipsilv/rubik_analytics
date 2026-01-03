"""
Verification script for Screener implementation
Checks database, imports, and API routes
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def verify_database():
    """Verify database exists and is accessible"""
    print("=" * 60)
    print("1. Verifying Database")
    print("=" * 60)
    try:
        import app.models.screener as screener_service
        db_path = screener_service.get_screener_db_path()
        print(f"[OK] Database path: {db_path}")
        
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            print(f"[OK] Database file exists ({size} bytes)")
        else:
            print("[WARN] Database file NOT found - initializing...")
            screener_service.init_screener_database()
            print("[OK] Database initialized")
        
        # Test connection
        conn = screener_service.get_db_connection()
        result = conn.execute("SELECT COUNT(*) FROM screener_data").fetchone()
        print(f"[OK] Database connection successful (records: {result[0]})")
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Database verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_imports():
    """Verify all imports work"""
    print("\n" + "=" * 60)
    print("2. Verifying Imports")
    print("=" * 60)
    try:
        import app.models.screener as screener_service
        print("[OK] screener_service imported")
        
        from app.api.v1 import screener
        print("[OK] screener API imported")
        
        from app.main import app
        print("[OK] FastAPI app imported")
        return True
    except Exception as e:
        print(f"[ERROR] Import verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_routes():
    """Verify API routes are registered"""
    print("\n" + "=" * 60)
    print("3. Verifying API Routes")
    print("=" * 60)
    try:
        from app.main import app
        routes = [r.path for r in app.routes if 'screener' in r.path]
        expected_routes = [
            '/api/v1/admin/screener/scrape',
            '/api/v1/admin/screener/scrape/status/{job_id}',
            '/api/v1/admin/screener/stats',
            '/api/v1/admin/screener/data'
        ]
        
        print(f"Found {len(routes)} screener routes:")
        for route in routes:
            print(f"  [OK] {route}")
        
        for expected in expected_routes:
            if expected not in routes:
                print(f"[ERROR] Missing route: {expected}")
                return False
        
        print("[OK] All expected routes found")
        return True
    except Exception as e:
        print(f"[ERROR] Route verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_database_schema():
    """Verify database schema is correct"""
    print("\n" + "=" * 60)
    print("4. Verifying Database Schema")
    print("=" * 60)
    try:
        import app.models.screener as screener_service
        conn = screener_service.get_db_connection()
        
        # Check tables exist
        tables = conn.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'main'
        """).fetchall()
        
        table_names = [t[0] for t in tables]
        print(f"[OK] Found tables: {', '.join(table_names)}")
        
        required_tables = ['screener_data', 'screener_scraping_logs']
        for table in required_tables:
            if table in table_names:
                print(f"  [OK] Table '{table}' exists")
            else:
                print(f"  [ERROR] Table '{table}' missing")
                return False
        
        # Check screener_data columns
        columns = conn.execute("PRAGMA table_info(screener_data)").fetchall()
        column_names = [c[1] for c in columns]
        required_columns = [
            'id', 'entity_type', 'symbol', 'exchange', 'period_type', 
            'period_key', 'statement_group', 'metric_name', 'metric_value'
        ]
        
        print(f"\n[OK] screener_data columns: {len(column_names)}")
        for col in required_columns:
            if col in column_names:
                print(f"  [OK] Column '{col}' exists")
            else:
                print(f"  [ERROR] Column '{col}' missing")
                return False
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Schema verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SCREENER IMPLEMENTATION VERIFICATION")
    print("=" * 60 + "\n")
    
    results = []
    results.append(verify_database())
    results.append(verify_imports())
    results.append(verify_routes())
    results.append(verify_database_schema())
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if all(results):
        print("[OK] All checks passed! Screener implementation is ready.")
        sys.exit(0)
    else:
        print("[ERROR] Some checks failed. Please review the errors above.")
        sys.exit(1)

