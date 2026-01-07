"""
Diagnostic Script: Test Symbol JOIN for Corporate Announcements
This script tests the JOIN logic between announcements and symbols databases
to identify why company names are not appearing.
"""

import duckdb
import os

def test_symbol_join():
    """Test if symbols can be matched with announcements"""
    ann_db_path = 'data/Company Fundamentals/corporate_announcements.duckdb'
    symbols_db_path = 'data/symbols/symbols.duckdb'
    
    if not os.path.exists(ann_db_path):
        print(f"❌ Announcements DB not found: {ann_db_path}")
        return
    
    if not os.path.exists(symbols_db_path):
        print(f"❌ Symbols DB not found: {symbols_db_path}")
        return
    
    print("✅ Both databases exist\n")
    
    # Connect to announcements DB
    conn = duckdb.connect(ann_db_path, read_only=True)
    
    # Attach symbols DB
    try:
        normalized_path = symbols_db_path.replace('\\', '/')
        conn.execute(f"ATTACH '{normalized_path}' AS symbols_db")
        print(f"✅ Attached symbols DB: {normalized_path}\n")
    except Exception as e:
        print(f"❌ Failed to attach symbols DB: {e}")
        return
    
    # Test 1: Check announcement data quality
    print("=" * 60)
    print("TEST 1: Announcement Data Quality")
    print("=" * 60)
    
    total_announcements = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()[0]
    print(f"Total announcements: {total_announcements}")
    
    # Check how many have symbols
    nse_count = conn.execute("SELECT COUNT(*) FROM corporate_announcements WHERE symbol_nse IS NOT NULL AND symbol_nse != ''").fetchone()[0]
    bse_count = conn.execute("SELECT COUNT(*) FROM corporate_announcements WHERE symbol_bse IS NOT NULL AND symbol_bse != ''").fetchone()[0]
    symbol_count = conn.execute("SELECT COUNT(*) FROM corporate_announcements WHERE symbol IS NOT NULL AND symbol != ''").fetchone()[0]
    
    print(f"Announcements with symbol_nse: {nse_count}")
    print(f"Announcements with symbol_bse: {bse_count}")
    print(f"Announcements with symbol: {symbol_count}")
    print(f"Announcements with NO symbols: {total_announcements - max(nse_count, bse_count, symbol_count)}\n")
    
    # Test 2: Sample announcements with symbols
    print("=" * 60)
    print("TEST 2: Sample Announcements (latest 5 with symbols)")
    print("=" * 60)
    
    sample_ann = conn.execute("""
        SELECT announcement_id, symbol, symbol_nse, symbol_bse, LEFT(headline, 60) as headline
        FROM corporate_announcements
        WHERE (symbol_nse IS NOT NULL AND symbol_nse != '') 
           OR (symbol_bse IS NOT NULL AND symbol_bse != '')
        ORDER BY received_at DESC
        LIMIT 5
    """).fetchall()
    
    for i, ann in enumerate(sample_ann, 1):
        print(f"\n{i}. ID: {ann[0]}")
        print(f"   Symbol: {ann[1]}")
        print(f"   NSE: {ann[2]}")
        print(f"   BSE: {ann[3]}")
        print(f"   Headline: {ann[4]}")
    
    # Test 3: Try to JOIN with symbols DB
    print("\n" + "=" * 60)
    print("TEST 3: Symbol JOIN Test")
    print("=" * 60)
    
    join_test = conn.execute("""
        SELECT 
            a.announcement_id,
            a.symbol_nse,
            a.symbol_bse,
            COALESCE(s_nse.name, s_bse.name) as company_name,
            LEFT(a.headline, 50) as headline
        FROM corporate_announcements a
        LEFT JOIN (
            SELECT DISTINCT trading_symbol, name
            FROM symbols_db.symbols
            WHERE exchange = 'NSE' AND instrument_type = 'EQ'
        ) s_nse ON a.symbol_nse = s_nse.trading_symbol
        LEFT JOIN (
            SELECT DISTINCT trading_symbol, name
            FROM symbols_db.symbols
            WHERE exchange = 'BSE' AND instrument_type = 'EQ'
        ) s_bse ON a.symbol_bse = s_bse.trading_symbol
        WHERE (a.symbol_nse IS NOT NULL OR a.symbol_bse IS NOT NULL)
        ORDER BY a.received_at DESC
        LIMIT 5
    """).fetchall()
    
    matched_count = sum(1 for row in join_test if row[3] is not None)
    print(f"\nJOIN Results: {matched_count}/{len(join_test)} matched with company names\n")
    
    for i, row in enumerate(join_test, 1):
        print(f"{i}. NSE: {row[1]}, BSE: {row[2]}")
        print(f"   Company: {row[3] if row[3] else '❌ NO MATCH'}")
        print(f"   Headline: {row[4]}\n")
    
    # Test 4: Check symbol format in symbols DB
    print("=" * 60)
    print("TEST 4: Symbol Format Check")
    print("=" * 60)
    
    if len(join_test) > 0 and join_test[0][1]:  # If we have an NSE symbol
        test_symbol = join_test[0][1]
        print(f"Looking for symbol: '{test_symbol}' in symbols DB...")
        
        matches = conn.execute(f"""
            SELECT trading_symbol, name, exchange, instrument_type
            FROM symbols_db.symbols
            WHERE trading_symbol LIKE '%{test_symbol}%'
            LIMIT 5
        """).fetchall()
        
        if matches:
            print(f"Found {len(matches)} potential matches:")
            for match in matches:
                print(f"  {match[0]} - {match[1]} ({match[2]} {match[3]})")
        else:
            print(f"❌ No matches found for '{test_symbol}'")
    
    conn.close()
    print("\n" + "=" * 60)
    print("Diagnostic Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_symbol_join()
