import duckdb
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

def clear_data():
    data_dir = os.path.join(settings.PROJECT_ROOT, "data", "News")
    
    # 1. Extraction Source & Raw
    listing_db = os.path.join(data_dir, "Raw", "telegram_listing.duckdb")
    raw_db = os.path.join(data_dir, "Raw", "telegram_raw.duckdb")
    
    # 2. Scoring
    scoring_db = os.path.join(data_dir, "Scoring", "news_scoring.duckdb")
    
    # 3. AI & Final
    ai_db = os.path.join(data_dir, "Final", "news_ai.duckdb")
    final_db = os.path.join(data_dir, "Final", "final_news.duckdb")

    print("="*50)
    print("Open Analytics - Data Clearing Utility")
    print("="*50)

    # List of tables to truncate
    db_configs = [
        (raw_db, ["telegram_raw"]),
        (scoring_db, ["news_scoring"]),
        (ai_db, ["news_ai", "ai_queue"]),
        (final_db, ["final_news"])
    ]

    for db_path, tables in db_configs:
        if not os.path.exists(db_path):
            print(f"[SKIP] DB not found: {os.path.basename(db_path)}")
            continue
            
        try:
            conn = duckdb.connect(db_path)
            for table in tables:
                try:
                    conn.execute(f"DELETE FROM {table}")
                    print(f"[OK] Cleared table '{table}' in {os.path.basename(db_path)}")
                except Exception as e:
                    print(f"[ERROR] Failed to clear table '{table}': {e}")
            conn.close()
        except Exception as e:
            print(f"[ERROR] Failed to connect to {os.path.basename(db_path)}: {e}")

    # Reset source flags
    if os.path.exists(listing_db):
        try:
            conn = duckdb.connect(listing_db)
            conn.execute("UPDATE telegram_listing SET is_extracted = FALSE, extracted_at = NULL")
            count = conn.execute("SELECT COUNT(*) FROM telegram_listing").fetchone()[0]
            print(f"[OK] Reset extraction flags for {count} rows in telegram_listing.duckdb")
            conn.close()
        except Exception as e:
            print(f"[ERROR] Failed to reset flags in listing DB: {e}")
    else:
        print("[SKIP] Listing DB not found")

    print("="*50)
    print("Data clearing complete.")
    print("="*50)

if __name__ == "__main__":
    clear_data()
