import os

# Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DATA_DIR = os.path.join(BASE_DIR, "data", "News")

RAW_DB_PATH = os.path.join(DATA_DIR, "Raw", "telegram_raw.duckdb")
RAW_TABLE = "telegram_raw"

SCORING_DB_PATH = os.path.join(DATA_DIR, "Scoring", "news_scoring.duckdb")
SCORING_TABLE = "news_scoring"

# Batch Size
BATCH_SIZE = 50

# Scoring Config
SCORING_THRESHOLD = 25
TRUSTED_SOURCES = [
    "reuters", "bloomberg", "cnbc", "moneycontrol", 
    "bse", "nse", "livemint", "economic times", "business standard",
    "self", "me" # Allow user test messages
]
