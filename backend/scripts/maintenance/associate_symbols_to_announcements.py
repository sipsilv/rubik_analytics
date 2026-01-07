"""
Associate symbols from symbols database with existing announcements
Matches by company name in headline/description
"""
import os
import sys
import duckdb
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.api.v1.symbols import get_symbols_db_path

def associate_symbols():
    """Associate symbols from symbols database with announcements"""
    data_dir = settings.DATA_DIR
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    symbols_db_path = get_symbols_db_path()
    if not os.path.exists(symbols_db_path):
        print(f"Symbols database not found: {symbols_db_path}")
        return
    
    print(f"Connecting to announcements database: {db_path}")
    print(f"Connecting to symbols database: {symbols_db_path}")
    
    conn = duckdb.connect(db_path)
    
    try:
        # Attach symbols database
        normalized_path = symbols_db_path.replace('\\', '/')
        conn.execute(f"ATTACH '{normalized_path}' AS symbols_db")
        
        # Find announcements without symbols
        announcements = conn.execute("""
            SELECT announcement_id, headline, description, symbol, symbol_nse, symbol_bse, raw_payload
            FROM corporate_announcements
            WHERE (symbol IS NULL OR symbol = '') 
              AND (symbol_nse IS NULL OR symbol_nse = '')
              AND (symbol_bse IS NULL OR symbol_bse = '')
              AND headline IS NOT NULL
            ORDER BY received_at DESC
            LIMIT 1000
        """).fetchall()
        
        print(f"\nFound {len(announcements)} announcements without symbols")
        
        if len(announcements) == 0:
            print("[OK] No announcements need symbol association!")
            return
        
        updated = 0
        for ann_id, headline, description, symbol, symbol_nse, symbol_bse, raw_payload in announcements:
            # Combine headline, description, and raw_payload for searching
            search_text = f"{headline or ''} {description or ''}".strip()
            
            # Also check raw_payload for company name or symbol
            if raw_payload:
                import json
                try:
                    payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                    # Look for company name or symbol in various fields
                    payload_text = ""
                    for key in ['company', 'companyName', 'company_name', 'name', 'symbol', 'tradingSymbol', 'trading_symbol']:
                        if key in payload_data and payload_data[key]:
                            payload_text += f" {str(payload_data[key])}"
                    # Also try to extract from nested structures
                    if isinstance(payload_data, dict):
                        for value in payload_data.values():
                            if isinstance(value, str) and len(value) > 3:
                                payload_text += f" {value}"
                    search_text += payload_text
                except:
                    # If raw_payload is not JSON, use it as-is
                    if isinstance(raw_payload, str):
                        search_text += f" {raw_payload[:500]}"  # Limit length
            
            search_text = search_text.strip()
            if not search_text:
                continue
            
            search_text_upper = search_text.upper()
            
            # Try to match with symbols database
            # Strategy 1: Exact or partial company name match
            matches = conn.execute("""
                SELECT trading_symbol, exchange, name
                FROM symbols_db.symbols
                WHERE name IS NOT NULL
                  AND name != ''
                  AND status = 'ACTIVE'
                  AND instrument_type = 'EQ'
                  AND (
                    ? LIKE '%' || UPPER(name) || '%'
                    OR UPPER(name) LIKE '%' || SUBSTRING(?, 1, 50) || '%'
                  )
                ORDER BY 
                    CASE 
                        WHEN ? LIKE '%' || UPPER(name) || '%' THEN 1
                        ELSE 2
                    END,
                    LENGTH(name) DESC
                LIMIT 1
            """, [search_text_upper, search_text_upper, search_text_upper]).fetchall()
            
            # Strategy 2: If no match, try matching by common words (company name parts)
            if not matches:
                # Extract potential company name from headline (first few words before common keywords)
                import re
                # Look for patterns like "Company Name" or "XYZ Limited" in headline
                headline_upper = (headline or "").upper()
                # Try to extract company name before keywords like "Limited", "Ltd", "Private Limited"
                company_patterns = [
                    r'^([A-Z][A-Z\s&]+?)\s+(?:LIMITED|LTD|PRIVATE LIMITED|PVT LTD|INCORPORATED|INC)',
                    r'^([A-Z][A-Z\s&]+?)\s+(?:OF|FOR|REGARDING|UNDER)',
                ]
                
                potential_company = None
                for pattern in company_patterns:
                    match = re.search(pattern, headline_upper)
                    if match:
                        potential_company = match.group(1).strip()
                        break
                
                if potential_company and len(potential_company) > 3:
                    # Try matching with this extracted company name
                    matches = conn.execute("""
                        SELECT trading_symbol, exchange, name
                        FROM symbols_db.symbols
                        WHERE name IS NOT NULL
                          AND name != ''
                          AND status = 'ACTIVE'
                          AND instrument_type = 'EQ'
                          AND (
                            UPPER(name) LIKE '%' || ? || '%'
                            OR ? LIKE '%' || UPPER(name) || '%'
                          )
                        ORDER BY LENGTH(name) DESC
                        LIMIT 1
                    """, [potential_company, potential_company]).fetchall()
            
            if matches:
                trading_symbol, exchange, company_name = matches[0]
                
                # Extract base symbol (remove -EQ suffix)
                base_symbol = trading_symbol.replace("-EQ", "").replace("-BE", "").replace("-FUT", "").replace("-OPT", "")
                
                # Update announcement
                if exchange.upper() == 'NSE':
                    conn.execute("""
                        UPDATE corporate_announcements
                        SET symbol = ?,
                            symbol_nse = ?
                        WHERE announcement_id = ?
                    """, [base_symbol, base_symbol, ann_id])
                elif exchange.upper() == 'BSE':
                    conn.execute("""
                        UPDATE corporate_announcements
                        SET symbol = ?,
                            symbol_bse = ?
                        WHERE announcement_id = ?
                    """, [base_symbol, base_symbol, ann_id])
                else:
                    # Default to NSE
                    conn.execute("""
                        UPDATE corporate_announcements
                        SET symbol = ?,
                            symbol_nse = ?
                        WHERE announcement_id = ?
                    """, [base_symbol, base_symbol, ann_id])
                
                updated += 1
                if updated <= 10:
                    print(f"  Updated {ann_id}: {base_symbol} ({exchange}) - {company_name}")
        
        print(f"\n[OK] Updated {updated} announcements with symbols")
        print(f"   {len(announcements) - updated} announcements still without symbols")
        
        # Show sample of unmatched announcements for debugging
        if len(announcements) - updated > 0:
            print(f"\nSample unmatched announcements (first 5):")
            unmatched = conn.execute("""
                SELECT announcement_id, headline
                FROM corporate_announcements
                WHERE (symbol IS NULL OR symbol = '') 
                  AND (symbol_nse IS NULL OR symbol_nse = '')
                  AND (symbol_bse IS NULL OR symbol_bse = '')
                  AND headline IS NOT NULL
                ORDER BY received_at DESC
                LIMIT 5
            """).fetchall()
            for ann_id, hline in unmatched:
                print(f"  {ann_id}: {hline[:60] if hline else 'N/A'}")
        
    except Exception as e:
        print(f"[ERROR] Error during association: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    associate_symbols()

