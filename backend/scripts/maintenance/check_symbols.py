"""
Check what symbol information exists in announcements database
"""
import os
import sys
import duckdb
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

def check_symbols():
    """Check symbol information in announcements"""
    data_dir = settings.DATA_DIR
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print(f"Connecting to database: {db_path}")
    conn = duckdb.connect(db_path)
    
    try:
        # Check recent announcements
        recent = conn.execute("""
            SELECT announcement_id, symbol, symbol_nse, symbol_bse, headline, raw_payload
            FROM corporate_announcements
            ORDER BY received_at DESC
            LIMIT 5
        """).fetchall()
        
        print(f"\nRecent announcements (last 5):")
        print("=" * 80)
        for ann_id, symbol, symbol_nse, symbol_bse, headline, raw_payload in recent:
            print(f"\nAnnouncement ID: {ann_id}")
            print(f"  Symbol: {symbol or 'NULL'}")
            print(f"  Symbol NSE: {symbol_nse or 'NULL'}")
            print(f"  Symbol BSE: {symbol_bse or 'NULL'}")
            print(f"  Headline: {headline[:60] if headline else 'NULL'}")
            
            # Check raw_payload for symbol info
            if raw_payload:
                try:
                    payload = json.loads(raw_payload)
                    print(f"  Raw payload keys: {list(payload.keys())[:10]}")
                    # Check for symbol fields
                    symbol_fields = ['symbol', 'Symbol', 'symbol_nse', 'SymbolNSE', 'symbol_bse', 'SymbolBSE', 
                                   'trading_symbol', 'TradingSymbol', 'scrip', 'Scrip']
                    found_symbols = {k: payload.get(k) for k in symbol_fields if payload.get(k)}
                    if found_symbols:
                        print(f"  Symbols in payload: {found_symbols}")
                    else:
                        print(f"  No symbol fields found in payload")
                except:
                    print(f"  Could not parse raw_payload")
        
        # Statistics
        total = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()[0]
        with_symbols = conn.execute("""
            SELECT COUNT(*) FROM corporate_announcements 
            WHERE symbol IS NOT NULL OR symbol_nse IS NOT NULL OR symbol_bse IS NOT NULL
        """).fetchone()[0]
        
        print(f"\n" + "=" * 80)
        print(f"Statistics:")
        print(f"  Total announcements: {total}")
        print(f"  With symbols: {with_symbols}")
        print(f"  Without symbols: {total - with_symbols}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    check_symbols()

