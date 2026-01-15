import os

# Base directory paths
# Current file is in backend/app/services/telegram_extractor/
current_dir = os.path.dirname(os.path.abspath(__file__))
# rubik-analytics/
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

# Data Directories
DATA_DIR = os.path.join(project_root, "data", "News")
RAW_DIR = os.path.join(DATA_DIR, "Raw")
CACHE_DIR = os.path.join(DATA_DIR, "Cache")

# Database Paths
INPUT_DB_PATH = os.path.join(RAW_DIR, "telegram_listing.duckdb")
OUTPUT_DB_PATH = os.path.join(RAW_DIR, "telegram_raw.duckdb")

# Cache Paths
LINK_CACHE_DIR = os.path.join(CACHE_DIR, "link_text_cache")
OCR_CACHE_DIR = os.path.join(CACHE_DIR, "ocr_cache")

# Table Names
INPUT_TABLE = "telegram_listing"
OUTPUT_TABLE = "telegram_raw"

# Settings
BATCH_SIZE = 10
REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
