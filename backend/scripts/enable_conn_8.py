
import sys
import os

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection

def enable_conn_8():
    db = SessionLocal()
    conn = db.query(Connection).filter(Connection.id == 8).first()
    if conn:
        print(f"Enabling connection {conn.id}...")
        conn.is_enabled = True
        db.commit()
        print("Done.")
    else:
        print("Connection 8 not found")
    db.close()

if __name__ == "__main__":
    enable_conn_8()
