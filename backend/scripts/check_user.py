
import sys
import os
# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.username == "sandeep").first()
if user:
    print(f"User: {user.username}")
    print(f"Chat ID: {user.telegram_chat_id}")
else:
    print("User not found")
db.close()
