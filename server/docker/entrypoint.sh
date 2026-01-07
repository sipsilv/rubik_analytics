#!/bin/sh
set -e

cd /app/backend

echo "==========================================="
echo "  INITIALIZING DATABASE..."
echo "==========================================="
python scripts/init/init_auth_database.py

echo "==========================================="
echo "  STARTING RUBIK ANALYTICS BACKEND"
echo "==========================================="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
