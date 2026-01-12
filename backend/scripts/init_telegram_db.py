import sqlite3
import duckdb
import os

# ---------------- PATHS ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
DATA_DIR = os.path.join(BASE_DIR, "data")

AUTH_DB_PATH = os.path.join(DATA_DIR, "auth", "sqlite", "auth.db")

NEWS_DB_DIR = os.path.join(DATA_DIR, "news")
NEWS_DB_PATH = os.path.join(NEWS_DB_DIR, "telegram_news.duckdb")


# ---------------- SQLITE MIGRATION ----------------
def migrate_sqlite():
    print(f"Checking SQLite at {AUTH_DB_PATH}...")

    if not os.path.exists(AUTH_DB_PATH):
        print("ERROR: Auth DB not found.")
        return

    conn = sqlite3.connect(AUTH_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if "telegram_chat_id" not in columns:
        print("Adding telegram_chat_id column to users table...")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN telegram_chat_id TEXT"
        )
        conn.commit()
        print("✓ Column added.")
    else:
        print("✓ Column telegram_chat_id already exists.")

    conn.close()


# ---------------- DUCKDB INIT ----------------
def init_duckdb():
    print(f"Initializing Telegram DuckDB at {NEWS_DB_PATH}...")

    os.makedirs(NEWS_DB_DIR, exist_ok=True)

    conn = duckdb.connect(NEWS_DB_PATH)

    # ---- SOURCE CHANNELS ----
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_source_channels (
            channel_username VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT TRUE,
            ocr_enabled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("✓ Table telegram_source_channels ready.")

    # ---- TELEGRAM NEWS ----
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_news (
            message_id BIGINT PRIMARY KEY,
            source VARCHAR DEFAULT 'TELEGRAM',
            channel_name VARCHAR,
            headline_text TEXT,
            image_path VARCHAR,
            posted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("✓ Table telegram_news ready.")

    conn.close()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    migrate_sqlite()
    init_duckdb()
    print("Telegram DB initialization completed successfully.")
