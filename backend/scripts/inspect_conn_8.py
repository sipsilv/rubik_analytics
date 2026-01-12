
import sys
import os

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection

def check_conn_8():
    db = SessionLocal()
    conn = db.query(Connection).filter(Connection.id == 8).first()
    if conn:
        print(f"ID: {conn.id}")
        print(f"Name: {conn.name}")
        print(f"Type: {conn.connection_type}")
        print(f"Enabled: {conn.is_enabled}")
        print(f"Status: {conn.status}")
    else:
        print("Connection 8 not found")
    db.close()

if __name__ == "__main__":
    check_conn_8()
