"""
Script to check Corporate Announcements database status
"""
import os
import sys
import duckdb
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

def check_announcements_db():
    """Check announcements database and show status"""
    data_dir = os.path.abspath(settings.DATA_DIR)
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    
    print(f"\n{'='*70}")
    print(" CORPORATE ANNOUNCEMENTS DATABASE STATUS")
    print(f"{'='*70}\n")
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file does not exist: {db_path}")
        print("\nThe database will be created automatically when the first announcement is received.")
        return
    
    print(f"[OK] Database file exists: {db_path}")
    
    try:
        conn = duckdb.connect(db_path)
        
        # Check table exists
        try:
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]
            
            if "corporate_announcements" not in table_names:
                print("[ERROR] Table 'corporate_announcements' does not exist")
                print("Available tables:", table_names)
                conn.close()
                return
            
            print("[OK] Table 'corporate_announcements' exists")
            
            # Get schema
            try:
                schema = conn.execute("PRAGMA table_info(corporate_announcements)").fetchall()
                print(f"\n📋 Table Schema ({len(schema)} columns):")
                for col in schema:
                    print(f"   - {col[1]} ({col[2]})")
            except Exception as e:
                print(f"[WARNING] Could not read schema: {e}")
            
            # Get count
            try:
                count_result = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()
                count = count_result[0] if count_result else 0
                print(f"\n[INFO] Total Announcements: {count}")
                
                if count > 0:
                    # Get latest announcements
                    print(f"\n[INFO] Latest 5 Announcements:")
                    latest = conn.execute("""
                        SELECT 
                            announcement_id,
                            headline,
                            symbol_nse,
                            symbol_bse,
                            received_at
                        FROM corporate_announcements
                        ORDER BY received_at DESC
                        LIMIT 5
                    """).fetchall()
                    
                    for i, ann in enumerate(latest, 1):
                        print(f"\n   {i}. ID: {ann[0]}")
                        print(f"      Headline: {ann[1][:60] if ann[1] else 'N/A'}...")
                        print(f"      Symbol: NSE={ann[2] or 'N/A'}, BSE={ann[3] or 'N/A'}")
                        print(f"      Received: {ann[4]}")
                else:
                    print("\n[WARNING] No announcements in database yet.")
                    print("   This could mean:")
                    print("   - WebSocket worker is not running")
                    print("   - WebSocket is not connected")
                    print("   - No announcements have been received from TrueData")
                    print("   - Connection is disabled")
                    
            except Exception as e:
                print(f"[ERROR] Error counting announcements: {e}")
            
            conn.close()
            
        except Exception as e:
            print(f"[ERROR] Error checking table: {e}")
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Error connecting to database: {e}")

if __name__ == "__main__":
    check_announcements_db()

