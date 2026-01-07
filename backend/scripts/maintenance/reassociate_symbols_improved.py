"""
Script to re-associate symbols to corporate announcements using improved matching logic.

This script:
1. Clears existing symbol associations (symbol_nse, symbol_bse, symbol)
2. Re-matches announcements with symbols database using improved matching algorithm
3. Only matches when there's high confidence (exact match, word boundary, or full name match)

Usage:
    cd backend
    python scripts/maintenance/reassociate_symbols_improved.py
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import duckdb
from app.api.v1.symbols import get_symbols_db_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_announcements_db_path():
    """Get path to corporate announcements database"""
    db_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "corporate_announcements.duckdb")
    return db_path


def improved_match_symbol(conn, headline: str, description: str, search_text: str = None) -> tuple:
    """
    Improved symbol matching with better precision
    
    Returns: (symbol_nse, symbol_bse, company_name) or (None, None, None)
    """
    try:
        symbols_db_path = get_symbols_db_path()
        if not os.path.exists(symbols_db_path):
            return (None, None, None)
        
        # Attach symbols database
        try:
            normalized_path = symbols_db_path.replace('\\', '/')
            conn.execute(f"ATTACH '{normalized_path}' AS symbols_db")
        except:
            # Already attached or error - test if accessible
            try:
                conn.execute("SELECT 1 FROM symbols_db.symbols LIMIT 1")
            except:
                return (None, None, None)
        
        # Combine headline, description, and search_text for searching
        if search_text is None:
            search_text = f"{headline or ''} {description or ''}".strip()
        else:
            search_text = f"{headline or ''} {description or ''} {search_text}".strip()
        
        if not search_text:
            return (None, None, None)
        
        search_text_upper = search_text.upper()
        
        # Improved matching with scoring
        matches = conn.execute("""
            SELECT 
                trading_symbol, 
                exchange, 
                name,
                CASE 
                    -- Exact match (highest priority)
                    WHEN UPPER(?) = UPPER(name) THEN 1
                    -- Full name appears as whole word in text (high priority)
                    WHEN ? LIKE '% ' || UPPER(name) || ' %' THEN 2
                    WHEN ? LIKE '% ' || UPPER(name) || '.' THEN 2
                    WHEN ? LIKE '% ' || UPPER(name) || ',' THEN 2
                    WHEN ? LIKE UPPER(name) || ' %' THEN 2
                    WHEN ? LIKE '% ' || UPPER(name) THEN 2
                    -- Full name appears anywhere (medium priority)
                    WHEN ? LIKE '%' || UPPER(name) || '%' THEN 3
                    -- Partial match (lower priority)
                    WHEN UPPER(name) LIKE '%' || SUBSTRING(?, 1, 50) || '%' THEN 4
                    ELSE 5
                END as match_score,
                LENGTH(name) as name_length
            FROM symbols_db.symbols
            WHERE name IS NOT NULL
              AND name != ''
              AND status = 'ACTIVE'
              AND instrument_type = 'EQ'
              AND (
                -- Exact match
                UPPER(?) = UPPER(name)
                -- Full name as word boundary
                OR ? LIKE '% ' || UPPER(name) || ' %'
                OR ? LIKE '% ' || UPPER(name) || '.'
                OR ? LIKE '% ' || UPPER(name) || ','
                OR ? LIKE UPPER(name) || ' %'
                OR ? LIKE '% ' || UPPER(name)
                -- Full name anywhere
                OR ? LIKE '%' || UPPER(name) || '%'
                -- Partial match (only if name is at least 5 chars to avoid false positives)
                OR (LENGTH(name) >= 5 AND UPPER(name) LIKE '%' || SUBSTRING(?, 1, 50) || '%')
              )
            ORDER BY 
                match_score ASC,
                name_length DESC,
                name ASC
            LIMIT 5
        """, [
            search_text_upper,  # CASE: exact match check
            search_text_upper,  # CASE: word boundary 1
            search_text_upper,  # CASE: word boundary 2
            search_text_upper,  # CASE: word boundary 3
            search_text_upper,  # CASE: word boundary 4
            search_text_upper,  # CASE: word boundary 5
            search_text_upper,  # CASE: full name anywhere
            search_text_upper,  # CASE: partial match
            search_text_upper,  # WHERE: exact match
            search_text_upper,  # WHERE: word boundary 1
            search_text_upper,  # WHERE: word boundary 2
            search_text_upper,  # WHERE: word boundary 3
            search_text_upper,  # WHERE: word boundary 4
            search_text_upper,  # WHERE: word boundary 5
            search_text_upper,  # WHERE: full name anywhere
            search_text_upper   # WHERE: partial match
        ]).fetchall()
        
        if matches:
            # Filter out poor matches - only accept score 1-3 (exact, word boundary, or full name)
            # Score 4 (partial) is only accepted if it's a very long company name (likely unique)
            good_matches = []
            for match in matches:
                trading_symbol, exchange, company_name, match_score, name_length = match
                # Accept exact matches, word boundary matches, full name matches
                # For partial matches, only accept if name is long (>= 15 chars) to reduce false positives
                if match_score <= 3 or (match_score == 4 and name_length >= 15):
                    good_matches.append(match)
            
            if good_matches:
                # Use best match (first result, already sorted by relevance)
                trading_symbol, exchange, company_name, match_score, name_length = good_matches[0]
                
                # Extract base symbol (remove -EQ suffix if present)
                base_symbol = trading_symbol.replace("-EQ", "").replace("-BE", "").replace("-FUT", "").replace("-OPT", "")
                
                if exchange.upper() == 'NSE':
                    return (base_symbol, None, company_name)
                elif exchange.upper() == 'BSE':
                    return (None, base_symbol, company_name)
                else:
                    # Default to NSE
                    return (base_symbol, None, company_name)
        
        return (None, None, None)
        
    except Exception as e:
        logger.debug(f"Error matching symbol: {e}")
        return (None, None, None)


def main():
    """Main function to re-associate symbols"""
    logger.info("Starting symbol re-association with improved matching...")
    
    announcements_db_path = get_announcements_db_path()
    if not os.path.exists(announcements_db_path):
        logger.error(f"Announcements database not found: {announcements_db_path}")
        return
    
    conn = duckdb.connect(announcements_db_path)
    
    try:
        # Get all announcements
        announcements = conn.execute("""
            SELECT announcement_id, headline, description, raw_payload
            FROM corporate_announcements
            ORDER BY received_at DESC
        """).fetchall()
        
        total = len(announcements)
        logger.info(f"Found {total} announcements to process")
        
        updated_count = 0
        cleared_count = 0
        error_count = 0
        
        for idx, (announcement_id, headline, description, raw_payload) in enumerate(announcements, 1):
            try:
                # Extract text from raw_payload if available
                search_text = None
                if raw_payload:
                    try:
                        import json
                        payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                        # Extract text from common fields
                        for key in ['company', 'companyName', 'company_name', 'name', 'symbol', 'tradingSymbol', 'trading_symbol']:
                            if key in payload_data and payload_data[key]:
                                if search_text is None:
                                    search_text = ""
                                search_text += f" {str(payload_data[key])}"
                    except:
                        if isinstance(raw_payload, str):
                            search_text = raw_payload[:500]
                
                # Try to match symbol
                matched_nse, matched_bse, matched_company = improved_match_symbol(
                    conn, headline, description, search_text
                )
                
                # Determine the best symbol
                best_symbol = matched_nse or matched_bse
                
                if matched_nse or matched_bse:
                    # Update with matched symbols
                    conn.execute("""
                        UPDATE corporate_announcements
                        SET symbol_nse = ?,
                            symbol_bse = ?,
                            symbol = ?
                        WHERE announcement_id = ?
                    """, [matched_nse, matched_bse, best_symbol, announcement_id])
                    updated_count += 1
                    
                    if idx % 100 == 0:
                        logger.info(f"Processed {idx}/{total} announcements... (Updated: {updated_count}, Cleared: {cleared_count})")
                else:
                    # Clear existing symbols if no match found (to remove incorrect matches)
                    conn.execute("""
                        UPDATE corporate_announcements
                        SET symbol_nse = NULL,
                            symbol_bse = NULL,
                            symbol = NULL
                        WHERE announcement_id = ?
                    """, [announcement_id])
                    cleared_count += 1
                    
                    if idx % 100 == 0:
                        logger.info(f"Processed {idx}/{total} announcements... (Updated: {updated_count}, Cleared: {cleared_count})")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing announcement {announcement_id}: {e}")
                if error_count > 10:
                    logger.error("Too many errors, stopping...")
                    break
        
        logger.info(f"\nRe-association complete!")
        logger.info(f"Total processed: {total}")
        logger.info(f"Updated with symbols: {updated_count}")
        logger.info(f"Cleared (no match): {cleared_count}")
        logger.info(f"Errors: {error_count}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()

