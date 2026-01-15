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
# Note: scripts/init/init_auth_database.py seems to be missing
# Windows start-all.bat says: "Database initialization is handled automatically by the backend on startup"
echo "[INFO] Starting backend (skipping explicit init script)..."

echo "==========================================="
echo "  STARTING RUBIK ANALYTICS BACKEND"
echo "==========================================="
# Match Windows server behavior: use --reload for development parity
# Note: We don't force --env-file here because Docker Compose injects environment variables directly,
# but we add --reload to see detailed logs and enable hot-reloading as requested ("same as Windows")
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --no-access-log
