import os

# Base directory paths
# Current file is in backend/app/services/telegram_raw_listener/
current_dir = os.path.dirname(os.path.abspath(__file__))

# Go up 4 levels to get to rubik-analytics/ (project root)
# 1. services
# 2. app
# 3. backend
# 4. rubik-analytics
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

# Data Directory: rubik-analytics/data/News/Raw
DATA_DIR = os.path.join(project_root, "data", "News", "Raw")
DB_PATH = os.path.join(DATA_DIR, "telegram_listing.duckdb")

# Table Name
TABLE_NAME = "telegram_listing"

# Retention Policy
RETENTION_HOURS = 24
