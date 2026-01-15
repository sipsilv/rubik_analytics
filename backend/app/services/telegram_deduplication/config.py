import os

# Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DATA_DIR = os.path.join(BASE_DIR, "data", "News")
RAW_DB_PATH = os.path.join(DATA_DIR, "Raw", "telegram_raw.duckdb")
RAW_TABLE = "telegram_raw"

# Batch processing size
BATCH_SIZE = 50

# Deduplication Thresholds
JACCARD_THRESHOLD = 0.90
SIMILARITY_LOOKBACK_LIMIT = 200  # Number of recent non-duplicates to check against
SIMILARITY_LOOKBACK_HOURS = 24  # Time window for checking duplicates
