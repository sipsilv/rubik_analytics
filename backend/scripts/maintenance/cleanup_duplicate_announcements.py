"""
Cleanup script to remove duplicate announcements from the database.

This script identifies and removes duplicate announcements based on:
1. Same headline + same date + same company_name (if available)
2. Same headline + same date + same symbol (for announcements without company_name)
3. Same ID (true duplicates)
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

import duckdb
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_path():
    """Get the path to the corporate announcements database"""
    db_dir = os.path.join(os.path.dirname(backend_dir), "data", "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "corporate_announcements.duckdb")

def find_and_remove_duplicates(dry_run=True):
    """
    Find and remove duplicate announcements from the database.
    
    Args:
        dry_run: If True, only report duplicates without deleting them
    
    Returns:
        Tuple of (duplicates_found, duplicates_removed)
    """
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at: {db_path}")
        return 0, 0
    
    conn = duckdb.connect(db_path)
    
    try:
        # Strategy 1: Remove exact ID duplicates (keep the first one)
        logger.info("Checking for duplicate IDs...")
        id_duplicates = conn.execute("""
            SELECT id, COUNT(*) as cnt
            FROM corporate_announcements
            GROUP BY id
            HAVING COUNT(*) > 1
        """).fetchall()
        
        id_dup_count = 0
        if id_duplicates:
            logger.info(f"Found {len(id_duplicates)} IDs with duplicates")
            for dup_id, cnt in id_duplicates:
                logger.info(f"  ID {dup_id}: {cnt} copies")
                if not dry_run:
                    # Keep the first one (lowest rowid), delete others
                    conn.execute("""
                        DELETE FROM corporate_announcements
                        WHERE id = ?
                        AND rowid NOT IN (
                            SELECT MIN(rowid) FROM corporate_announcements WHERE id = ?
                        )
                    """, [dup_id, dup_id])
                    id_dup_count += cnt - 1
            if not dry_run:
                conn.commit()
                logger.info(f"Removed {id_dup_count} duplicate ID records")
        
        # Strategy 2: Remove duplicates with company_name (same headline + date + company)
        logger.info("\nChecking for duplicates with company_name...")
        company_duplicates = conn.execute("""
            SELECT 
                LOWER(TRIM(company_name)) as company,
                LOWER(TRIM(news_headline)) as headline,
                DATE(trade_date) as date_part,
                COUNT(*) as cnt,
                GROUP_CONCAT(id ORDER BY trade_date DESC, rowid) as ids
            FROM corporate_announcements
            WHERE company_name IS NOT NULL AND TRIM(company_name) != ''
            GROUP BY company, headline, date_part
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """).fetchall()
        
        company_dup_count = 0
        if company_duplicates:
            logger.info(f"Found {len(company_duplicates)} duplicate groups with company_name")
            for company, headline, date_part, cnt, ids_str in company_duplicates:
                if ids_str:
                    ids = [id.strip() for id in ids_str.split(',') if id.strip()]
                else:
                    # Fallback: query IDs directly
                    ids_result = conn.execute("""
                        SELECT id FROM corporate_announcements
                        WHERE LOWER(TRIM(company_name)) = ?
                        AND LOWER(TRIM(news_headline)) = ?
                        AND DATE(trade_date) = DATE(?)
                        ORDER BY trade_date DESC, rowid
                    """, [company, headline, date_part]).fetchall()
                    ids = [str(row[0]) for row in ids_result]
                
                duplicates_to_remove = cnt - 1  # Keep 1, remove rest
                company_dup_count += duplicates_to_remove
                
                logger.info(f"  Company: {company}, Date: {date_part}, Count: {cnt} (will remove {duplicates_to_remove})")
                logger.info(f"    Headline: {headline[:60]}...")
                
                if not dry_run and len(ids) > 1:
                    # Keep the first ID (most recent), delete others
                    ids_to_delete = ids[1:]  # Keep first, delete rest
                    for dup_id in ids_to_delete:
                        conn.execute("DELETE FROM corporate_announcements WHERE id = ?", [dup_id])
            
            if not dry_run:
                conn.commit()
                logger.info(f"Removed {company_dup_count} duplicate records with company_name")
        
        # Strategy 3: Remove duplicates without company_name (same headline + date + symbol)
        # This is important for mutual fund announcements where different funds have same headline
        logger.info("\nChecking for duplicates without company_name (using symbol)...")
        # DuckDB doesn't have GROUP_CONCAT, so we'll query differently
        no_company_duplicates = conn.execute("""
            SELECT 
                LOWER(TRIM(news_headline)) as headline,
                DATE(trade_date) as date_part,
                COALESCE(symbol_nse, symbol_bse, CAST(script_code AS VARCHAR)) as symbol,
                COUNT(*) as cnt
            FROM corporate_announcements
            WHERE (company_name IS NULL OR TRIM(company_name) = '')
            AND news_headline IS NOT NULL
            AND TRIM(news_headline) != ''
            GROUP BY headline, date_part, symbol
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """).fetchall()
        
        symbol_dup_count = 0
        if no_company_duplicates:
            logger.info(f"Found {len(no_company_duplicates)} duplicate groups without company_name")
            for headline, date_part, symbol, cnt in no_company_duplicates[:10]:  # Show first 10
                # Get IDs for this duplicate group
                ids_result = conn.execute("""
                    SELECT id FROM corporate_announcements
                    WHERE (company_name IS NULL OR TRIM(company_name) = '')
                    AND LOWER(TRIM(news_headline)) = ?
                    AND DATE(trade_date) = DATE(?)
                    AND COALESCE(symbol_nse, symbol_bse, CAST(script_code AS VARCHAR)) = ?
                    ORDER BY trade_date DESC, rowid
                """, [headline, date_part, symbol]).fetchall()
                ids = [str(row[0]) for row in ids_result]
                
                duplicates_to_remove = cnt - 1  # Keep 1, remove rest
                symbol_dup_count += duplicates_to_remove
                
                logger.info(f"  Symbol: {symbol}, Date: {date_part}, Count: {cnt} (will remove {duplicates_to_remove})")
                logger.info(f"    Headline: {headline[:60]}...")
                
                if not dry_run and len(ids) > 1:
                    # Keep the first ID (most recent), delete others
                    ids_to_delete = ids[1:]  # Keep first, delete rest
                    for dup_id in ids_to_delete:
                        conn.execute("DELETE FROM corporate_announcements WHERE id = ?", [dup_id])
            
            # Process remaining duplicates
            if not dry_run and len(no_company_duplicates) > 10:
                for headline, date_part, symbol, cnt in no_company_duplicates[10:]:
                    ids_result = conn.execute("""
                        SELECT id FROM corporate_announcements
                        WHERE (company_name IS NULL OR TRIM(company_name) = '')
                        AND LOWER(TRIM(news_headline)) = ?
                        AND DATE(trade_date) = DATE(?)
                        AND COALESCE(symbol_nse, symbol_bse, CAST(script_code AS VARCHAR)) = ?
                        ORDER BY trade_date DESC, rowid
                    """, [headline, date_part, symbol]).fetchall()
                    ids = [str(row[0]) for row in ids_result]
                    
                    if len(ids) > 1:
                        ids_to_delete = ids[1:]
                        for dup_id in ids_to_delete:
                            conn.execute("DELETE FROM corporate_announcements WHERE id = ?", [dup_id])
                        symbol_dup_count += len(ids_to_delete)
            
            if not dry_run:
                conn.commit()
                logger.info(f"Removed {symbol_dup_count} duplicate records without company_name")
        
        total_duplicates_found = len(id_duplicates) + len(company_duplicates) + len(no_company_duplicates)
        total_duplicates_removed = id_dup_count + company_dup_count + symbol_dup_count
        
        # Get final count
        initial_count = conn.execute("SELECT COUNT(*) FROM corporate_announcements").fetchone()[0]
        final_count = initial_count - total_duplicates_removed if not dry_run else initial_count
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Summary:")
        logger.info(f"  Initial record count: {initial_count}")
        logger.info(f"  Duplicate groups found: {total_duplicates_found}")
        logger.info(f"  Duplicate records {'would be ' if dry_run else ''}removed: {total_duplicates_removed}")
        logger.info(f"  Final record count: {final_count}")
        logger.info(f"{'='*60}")
        
        return total_duplicates_found, total_duplicates_removed
        
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup duplicate announcements from database")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove duplicates (default is dry-run mode)"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Running in {'EXECUTE' if args.execute else 'DRY-RUN'} mode")
    logger.info("="*60)
    
    find_and_remove_duplicates(dry_run=not args.execute)
    
    if not args.execute:
        logger.info("\nTo actually remove duplicates, run with --execute flag")

