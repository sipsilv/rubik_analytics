"""
Check raw message structure from announcements database
This will help us understand what field names TrueData uses
"""
import duckdb
import json
import os

def check_raw_messages():
    ann_db_path = 'data/Company Fundamentals/corporate_announcements.duckdb'
    
    if not os.path.exists(ann_db_path):
        print(f"❌ Database not found: {ann_db_path}")
        return
    
    print("=" * 80)
    print("CHECKING RAW MESSAGE STRUCTURE FROM DATABASE")
    print("=" * 80)
    
    conn = duckdb.connect(ann_db_path, read_only=True)
    
    # Get sample announcements with raw_payload
    result = conn.execute("""
        SELECT 
            announcement_id,
            symbol,
            symbol_nse,
            symbol_bse,
            headline,
            raw_payload
        FROM corporate_announcements
        WHERE raw_payload IS NOT NULL
        ORDER BY received_at DESC
        LIMIT 5
    """).fetchall()
    
    print(f"\nFound {len(result)} announcements with raw_payload\n")
    
    for i, row in enumerate(result, 1):
        ann_id, symbol, symbol_nse, symbol_bse, headline, raw_payload = row
        
        print("\n" + "=" * 80)
        print(f"ANNOUNCEMENT #{i}")
        print("=" * 80)
        print(f"ID: {ann_id}")
        print(f"Stored symbol: {symbol}")
        print(f"Stored symbol_nse: {symbol_nse}")
        print(f"Stored symbol_bse: {symbol_bse}")
        print(f"Headline: {headline[:80] if headline else 'None'}...")
        print("\n" + "-" * 80)
        print("RAW MESSAGE STRUCTURE:")
        print("-" * 80)
        
        try:
            if isinstance(raw_payload, str):
                parsed = json.loads(raw_payload)
            else:
                parsed = raw_payload
            
            # Print the message structure nicely
            print(json.dumps(parsed, indent=2))
            
            # Analyze field names
            print("\n" + "-" * 80)
            print("AVAILABLE FIELD NAMES:")
            print("-" * 80)
            if isinstance(parsed, dict):
                for key in parsed.keys():
                    value = parsed[key]
                    if isinstance(value, str) and len(str(value)) > 100:
                        print(f"  {key}: {type(value).__name__} (length: {len(value)})")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  Message is not a dict, type: {type(parsed)}")
            
        except Exception as e:
            print(f"❌ Error parsing raw_payload: {e}")
            print(f"Raw payload preview: {str(raw_payload)[:500]}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nLook for field names containing:")
    print("  - symbol, Symbol, SYMBOL, trading_symbol, scrip, scripcode")
    print("  - company, companyName, name")
    print("  - exchange, Exchange, NSE, BSE")
    print("  - headline, Headline, subject, title")

if __name__ == "__main__":
    check_raw_messages()
