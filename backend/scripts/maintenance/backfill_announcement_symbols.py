"""
Backfill symbols for announcements that have NULL symbols
Extracts symbols from headlines using regex patterns
"""
import os
import sys
import duckdb
import re
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

def extract_symbol_from_text(text):
    """Extract potential symbol from text using regex"""
    if not text:
        return None
    
    # Common false positives to exclude
    false_positives = {
        'THE', 'AND', 'FOR', 'ARE', 'NOT', 'ALL', 'ANY', 'SEE', 'REG', 'SEBI', 'DP', 'RBI', 'NSE', 'BSE',
        'COMPLIANCES', 'COMPLIANCE', 'ANNOUNCEMENT', 'ANNOUNCEMENTS', 'CLOSURE', 'TRADING', 'WINDOW',
        'CERTIFICATE', 'REGULATION', 'REGULATIONS', 'LODR', 'CORPORATE', 'GOVERNANCE', 'REPORT',
        'RUMOUR', 'VERIFICATION', 'ALLOTMENT', 'EQUITY', 'SHARES', 'SECURITIES', 'EXCHANGE', 'BOARD',
        'MEETING', 'RESULTS', 'QUARTER', 'ANNUAL', 'AUDIT', 'AUDITOR', 'DIRECTOR', 'MANAGEMENT'
    }
    
    # Pattern 1: Look for common stock symbol patterns (3-15 uppercase letters, possibly with numbers)
    # Exclude common words and require at least 3 consecutive uppercase letters
    symbol_pattern = r'\b([A-Z]{3,15}(?:[0-9]{0,3})?)\b'
    matches = re.findall(symbol_pattern, str(text).upper())
    
    for match in matches:
        # Filter out false positives
        if match not in false_positives and len(match) >= 3:
            # Check if it looks like a stock symbol (not all common words)
            # Stock symbols are usually 3-10 chars, mostly letters
            if 3 <= len(match) <= 10 and match.isalpha():
                return match
    
    return None

def backfill_symbols():
    """Backfill symbols for announcements with NULL symbols"""
    data_dir = settings.DATA_DIR
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print(f"Connecting to database: {db_path}")
    conn = duckdb.connect(db_path)
    
    try:
        # Find announcements with NULL symbols
        # Also check raw_payload for symbol information
        null_symbols = conn.execute("""
            SELECT announcement_id, headline, description, symbol, symbol_nse, symbol_bse, raw_payload
            FROM corporate_announcements
            WHERE (symbol IS NULL OR symbol = '') 
              AND (symbol_nse IS NULL OR symbol_nse = '')
              AND (symbol_bse IS NULL OR symbol_bse = '')
              AND headline IS NOT NULL
            ORDER BY received_at DESC
            LIMIT 1000
        """).fetchall()
        
        print(f"\nFound {len(null_symbols)} announcements with NULL symbols")
        
        if len(null_symbols) == 0:
            print("✅ No announcements need symbol backfilling!")
            return
        
        updated = 0
        import json
        for ann_id, headline, description, symbol, symbol_nse, symbol_bse, raw_payload in null_symbols:
            extracted_symbol = None
            
            # First, try to extract from raw_payload JSON if available
            if raw_payload:
                try:
                    payload_data = json.loads(raw_payload)
                    # Try common symbol fields
                    extracted_symbol = (
                        payload_data.get("symbol") or
                        payload_data.get("Symbol") or
                        payload_data.get("symbol_nse") or
                        payload_data.get("SymbolNSE") or
                        payload_data.get("symbol_bse") or
                        payload_data.get("SymbolBSE") or
                        payload_data.get("trading_symbol") or
                        payload_data.get("TradingSymbol") or
                        payload_data.get("scrip") or
                        payload_data.get("Scrip")
                    )
                except:
                    pass
            
            # If not found in payload, try extracting from headline/description
            if not extracted_symbol:
                if headline:
                    extracted_symbol = extract_symbol_from_text(headline)
                if not extracted_symbol and description:
                    extracted_symbol = extract_symbol_from_text(description)
            
            if extracted_symbol and len(extracted_symbol) >= 3:
                # Update the announcement with extracted symbol
                conn.execute("""
                    UPDATE corporate_announcements
                    SET symbol = ?,
                        symbol_nse = ?
                    WHERE announcement_id = ?
                """, [extracted_symbol, extracted_symbol, ann_id])
                updated += 1
                if updated <= 10:  # Show first 10 updates
                    print(f"  Updated {ann_id}: {extracted_symbol} (from: {headline[:50] if headline else 'N/A'})")
        
        print(f"\n[OK] Updated {updated} announcements with extracted symbols")
        print(f"   {len(null_symbols) - updated} announcements still have NULL symbols")
        
    except Exception as e:
        print(f"[ERROR] Error during backfill: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    backfill_symbols()

