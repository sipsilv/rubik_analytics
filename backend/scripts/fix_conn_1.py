
import sys
import os
import logging

# Add backend to path explicitly
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from app.core.database import SessionLocal
from app.models.connection import Connection

def fix_connection_1():
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter(Connection.id == 1).first()
        if conn:
            print(f"Found Connection 1: {conn.name}")
            if conn.credentials:
                print("Clearing broken credentials...")
                conn.credentials = None
                db.commit()
                print("✅ Credentials cleared. Decryption errors should stop.")
            else:
                print("Credentials already empty.")
        else:
            print("Connection 1 not found.")
    finally:
        db.close()

if __name__ == "__main__":
    fix_connection_1()
