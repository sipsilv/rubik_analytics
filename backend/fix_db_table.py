import sys
import os

# Add the current directory to python path so we can import app modules
sys.path.append(os.getcwd())

from app.core.database import get_db_router
from app.core.config import settings
from app.models.telegram_message import TelegramMessage
from sqlalchemy import inspect

print("Checking database connection...")

# Initialize Router
# Force DATA_DIR if needed, but settings should have it
router = get_db_router(settings.DATA_DIR)
auth_client = router.get_auth_db()

if not auth_client:
    print("ERROR: Could not get Auth DB client")
    sys.exit(1)

# Get Engine
session = auth_client.get_session()
engine = session.bind
session.close()

# Create the table
print(f"Creating telegram_messages table using engine: {engine}...")
TelegramMessage.__table__.create(bind=engine, checkfirst=True)

# Verify
inspector = inspect(engine)
tables = inspector.get_table_names()

if "telegram_messages" in tables:
    print("SUCCESS: 'telegram_messages' table exists!")
else:
    print("FAILURE: Table still does not exist.")
