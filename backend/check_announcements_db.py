#!/usr/bin/env python3
"""Script to check announcements database and WebSocket status"""
import os
import sys
import duckdb
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_database():
    """Check announcements database"""
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    db_path = os.path.join(data_dir, 'Company Fundamentals', 'corporate_announcements.duckdb')
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    try:
        conn = duckdb.connect(db_path)
        
        # Get total count
        count_result = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()
        total_count = count_result[0] if count_result else 0
        
        print(f"✅ Database found: {db_path}")
        print(f"📊 Total announcements in database: {total_count}")
        
        if total_count > 0:
            # Get most recent announcements
            recent = conn.execute("""
                SELECT id, news_headline, trade_date, created_at 
                FROM corporate_announcements 
                ORDER BY created_at DESC 
                LIMIT 10
            """).fetchall()
            
            print(f"\n📰 Most recent {len(recent)} announcements:")
            print("-" * 80)
            for i, (ann_id, headline, trade_date, created_at) in enumerate(recent, 1):
                headline_preview = (headline[:60] + "...") if headline and len(headline) > 60 else (headline or "N/A")
                print(f"{i}. ID: {ann_id}")
                print(f"   Headline: {headline_preview}")
                print(f"   Trade Date: {trade_date}")
                print(f"   Created: {created_at}")
                print()
            
            # Get count by date
            date_counts = conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM corporate_announcements
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 7
            """).fetchall()
            
            print("📅 Announcements by date (last 7 days):")
            for date, count in date_counts:
                print(f"   {date}: {count} announcements")
        else:
            print("\n⚠️  Database is empty - no announcements found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()

def check_websocket_service():
    """Check WebSocket service status"""
    try:
        from app.services.announcements_websocket_service import get_announcements_websocket_service
        
        ws_service = get_announcements_websocket_service()
        
        print("\n" + "=" * 80)
        print("🔌 WebSocket Service Status")
        print("=" * 80)
        
        if ws_service:
            print(f"Service exists: ✅")
            print(f"Running: {'✅ Yes' if ws_service.running else '❌ No'}")
            print(f"WebSocket: {'✅ Connected' if ws_service.websocket and hasattr(ws_service.websocket, 'open') and ws_service.websocket.open else '❌ Not connected'}")
            print(f"Connection ID: {ws_service.connection_id or 'N/A'}")
        else:
            print("Service: ❌ Not initialized")
            
    except Exception as e:
        print(f"❌ Error checking WebSocket service: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 80)
    print("🔍 Checking Announcements Database and WebSocket Status")
    print("=" * 80)
    print()
    
    check_database()
    check_websocket_service()
    
    print("\n" + "=" * 80)
    print("✅ Check complete")
    print("=" * 80)

