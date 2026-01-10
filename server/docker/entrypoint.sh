#!/bin/sh
set -e

cd /app/backend

echo "==========================================="
echo "  INITIALIZING DATABASE..."
echo "==========================================="

# Get admin credentials from environment variables (if provided)
ADMIN_USERNAME=${ADMIN_USERNAME:-}
ADMIN_EMAIL=${ADMIN_EMAIL:-}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-}

# Run database initialization
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "[INFO] Creating admin user from environment variables..."
    python scripts/init/init_auth_database.py \
        --username "$ADMIN_USERNAME" \
        --email "$ADMIN_EMAIL" \
        --password "$ADMIN_PASSWORD"
else
    echo "[INFO] Initializing database (no admin credentials provided, will skip admin user creation)..."
    python scripts/init/init_auth_database.py
fi

echo "==========================================="
echo "  STARTING RUBIK ANALYTICS BACKEND"
echo "==========================================="
# Match Windows server: use --reload for development, --workers 1 for production
# --no-access-log matches Windows server behavior (HTTP access logs filtered)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
