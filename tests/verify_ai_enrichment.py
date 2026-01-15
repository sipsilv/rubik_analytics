import os
import sys
import duckdb
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Set environment variables to use test paths
TEST_DIR = os.path.join(os.getcwd(), "data_test")
os.makedirs(TEST_DIR, exist_ok=True)

# Important: Patch the paths in config modules
import app.services.news_ai.config as ai_config
ai_config.DATA_DIR = os.path.join(TEST_DIR, "News")
ai_config.SCORING_DB_PATH = os.path.join(ai_config.DATA_DIR, "Scoring", "news_scoring.duckdb")
ai_config.AI_DB_PATH = os.path.join(ai_config.DATA_DIR, "Final", "news_ai.duckdb")

import app.services.news_scoring.config as scoring_config
scoring_config.DATA_DIR = os.path.join(TEST_DIR, "News")
scoring_config.SCORING_DB_PATH = ai_config.SCORING_DB_PATH
scoring_config.RAW_DB_PATH = os.path.join(ai_config.DATA_DIR, "Raw", "telegram_raw.duckdb")

# Force SharedDatabase to reload paths or just manually set them if possible
from app.services.shared_db import get_shared_db
import app.services.shared_db as shared_db_mod

# Inject paths into the shared_db module's imports so it uses our test paths
shared_db_mod.RAW_DB_PATH = scoring_config.RAW_DB_PATH
shared_db_mod.LISTING_DB_PATH = os.path.join(TEST_DIR, "telegram_listing.duckdb")
shared_db_mod.AI_DB_PATH = ai_config.AI_DB_PATH
shared_db_mod.SCORING_DB_PATH = ai_config.SCORING_DB_PATH

from app.services.news_ai.db import ensure_schema, get_eligible_news, insert_enriched_news
from app.services.news_ai.processor import AIEnrichmentProcessor
from app.services.ai_adapter import AIAdapter

def setup_test_data():
    """Create mock data for testing."""
    print(f"Setting up test data in {TEST_DIR}...")
    
    # Ensure directories exist
    os.makedirs(os.path.dirname(shared_db_mod.RAW_DB_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(shared_db_mod.SCORING_DB_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(shared_db_mod.AI_DB_PATH), exist_ok=True)
    
    db = get_shared_db()
    
    # 1. Setup Raw DB and Table
    raw_query = """
        CREATE TABLE IF NOT EXISTS telegram_raw (
            raw_id BIGINT PRIMARY KEY,
            combined_text TEXT,
            received_at TIMESTAMP,
            is_scored BOOLEAN DEFAULT FALSE,
            is_duplicate BOOLEAN DEFAULT FALSE,
            deduped_at TIMESTAMP
        );
    """
    db.run_raw_query(raw_query)
    
    raw_id = 999
    db.run_raw_query("DELETE FROM telegram_raw WHERE raw_id = ?", [raw_id])
    db.run_raw_query("INSERT INTO telegram_raw (raw_id, combined_text, received_at, is_scored, is_duplicate, deduped_at) VALUES (?, ?, ?, ?, ?, ?)",
                     [raw_id, "Reliance Industries reports 20% growth in quarterly profit.", datetime.now(), False, False, datetime.now()])
    
    # 2. Setup Scoring DB and Table
    from app.services.news_scoring.db import ensure_schema as ensure_scoring_schema
    ensure_scoring_schema()
    
    db.run_scoring_query("DELETE FROM news_scoring WHERE raw_id = ?", [raw_id])
    db.run_scoring_query("INSERT INTO news_scoring (raw_id, final_score, decision, scored_at) VALUES (?, ?, ?, ?)",
                       [raw_id, 80, "Bullish", datetime.now()])
    
    # 3. Ensure AI DB Table
    ensure_schema()
    db.run_ai_query("DELETE FROM news_ai")
    
    print("Test data setup complete.")

class MockAdapter(AIAdapter):
    def process(self, prompt: str):
        return {
            "category_code": "RESULTS",
            "sub_type_code": "QUARTERLY_RESULTS",
            "company_name": "Reliance Industries",
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "country_code": "IN",
            "headline": "Reliance Profit Up 20%",
            "summary": "Reliance Industries reported a significant growth in its quarterly results.",
            "sentiment": "Positive",
            "language_code": "en",
            "url": ""
        }

def verify_flow():
    print("Verifying AI Enrichment Flow...")
    
    # Set up test data
    setup_test_data()
    
    # Initialize processor
    processor = AIEnrichmentProcessor()
    
    # Mock refresh_config to avoid loading from real DB
    processor.active_config = {
        "config_id": 1,
        "connection_id": 1,
        "prompt_text": "Analyze: {{COMBINED_TEXT}}",
        "model_name": "mock-model"
    }
    processor.adapter = MockAdapter(api_key="mock", model="mock-model")
    processor.refresh_config = MagicMock(return_value=True)
    
    # Run process_batch
    print("Processing batch...")
    count = processor.process_batch(limit=1)
    
    if count > 0:
        print(f"SUCCESS: Enriched {count} news items.")
        
        # Verify result in DB
        db = get_shared_db()
        # We need to ATTACH scoring_db to ai_db for this query just for verification
        conn = db.get_ai_connection()
        conn.execute(f"ATTACH IF NOT EXISTS '{ai_config.SCORING_DB_PATH}' AS scoring_db")
        
        result = conn.execute("SELECT * FROM news_ai WHERE news_id = (SELECT score_id FROM scoring_db.news_scoring WHERE raw_id = 999)").fetchone()
        if result:
            print("DB Verification: Row found in news_ai table!")
            print(f"Headline: {result[8]}") # index 8 is headline
            print(f"Company: {result[4]}")  # index 4 is company_name
        else:
            print("FAILED: Result not found in news_ai table.")
    else:
        print("FAILED: No news items were enriched.")
        # Debug: Check eligible news count
        eligible = get_eligible_news(limit=10)
        print(f"Eligible news count: {len(eligible)}")

if __name__ == "__main__":
    try:
        verify_flow()
    finally:
        # Close all connections
        get_shared_db().close_all()
