#!/bin/bash
# Rubik Analytics - Docker Start Script
# Starts all services using Docker Compose
# Automatically detects data folder path

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==========================================="
echo "  Rubik Analytics - Docker Start"
echo "==========================================="
echo ""

# Automatically detect data folder path
# Script is in server/docker/, so data folder is at ../../data
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"

# Convert to absolute path and normalize
DATA_DIR="$(cd "$DATA_DIR" 2>/dev/null && pwd || echo "$DATA_DIR")"

# Export for docker-compose
export HOST_DATA_DIR="$DATA_DIR"

echo "[INFO] Automatically detected data folder: $HOST_DATA_DIR"

# Verify data folder exists or create it
if [ ! -d "$HOST_DATA_DIR" ]; then
    echo "[WARNING] Data folder does not exist. Creating directory structure..."
    mkdir -p "$HOST_DATA_DIR"/{auth/sqlite,analytics/duckdb,"Company Fundamentals",symbols,connection/truedata,logs/{app,db_logs,jobs},temp,backups}
    echo "[INFO] Created data folder structure at: $HOST_DATA_DIR"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "[ERROR] docker-compose is not installed. Please install Docker Compose."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "[INFO] .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "[WARNING] Please edit .env file with your configuration before starting!"
        echo "[WARNING] You MUST set JWT_SECRET_KEY, JWT_SYSTEM_SECRET_KEY, and ENCRYPTION_KEY"
        echo "[WARNING] Generate keys using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        read -p "Press Enter to continue or Ctrl+C to cancel..."
    fi
fi

# Verify required environment variables are set
if [ -f .env ]; then
    source .env
    if [ -z "$JWT_SECRET_KEY" ] || [ "$JWT_SECRET_KEY" = "your-secret-key-change-in-production" ] || [ -z "$JWT_SECRET_KEY" ]; then
        echo "[ERROR] JWT_SECRET_KEY is not set or is using default value!"
        echo "[ERROR] Please edit .env file and set a secure JWT_SECRET_KEY"
        exit 1
    fi
    if [ -z "$JWT_SYSTEM_SECRET_KEY" ] || [ "$JWT_SYSTEM_SECRET_KEY" = "your-system-secret-key-change-in-production" ]; then
        echo "[ERROR] JWT_SYSTEM_SECRET_KEY is not set or is using default value!"
        echo "[ERROR] Please edit .env file and set a secure JWT_SYSTEM_SECRET_KEY"
        exit 1
    fi
    if [ -z "$ENCRYPTION_KEY" ] || [ "$ENCRYPTION_KEY" = "jT7ACJPNHdp-IwKWVDto-vohgPGxwP_95sjBlgsr9Eg=" ]; then
        echo "[ERROR] ENCRYPTION_KEY is not set or is using default value!"
        echo "[ERROR] Please edit .env file and set a secure ENCRYPTION_KEY"
        echo "[INFO] Generate key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        exit 1
    fi
fi

echo "[INFO] Building and starting services..."
$COMPOSE_CMD up -d --build

echo ""
echo "==========================================="
echo "  Services Started"
echo "==========================================="
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop:      docker-compose down"
echo ""

