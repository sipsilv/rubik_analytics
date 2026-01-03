FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
# Note: .dockerignore is automatically read from build context root (project root)
# Source ignore patterns are in server/docker/backend.dockerignore
COPY backend/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/

# Create data directory structure
RUN mkdir -p /app/data/auth/sqlite \
    && mkdir -p /app/data/auth/postgres/migrations \
    && mkdir -p /app/data/analytics/duckdb \
    && mkdir -p /app/data/analytics/postgres/analytics_schema \
    && mkdir -p /app/data/Company\ Fundamentals \
    && mkdir -p /app/data/symbols \
    && mkdir -p /app/data/connection/truedata \
    && mkdir -p /app/data/connections \
    && mkdir -p /app/data/logs/app \
    && mkdir -p /app/data/logs/db_logs \
    && mkdir -p /app/data/logs/jobs \
    && mkdir -p /app/data/temp \
    && mkdir -p /app/data/backups

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run initialization and start server
WORKDIR /app/backend
CMD python scripts/init/init_auth_database.py && uvicorn app.main:app --host 0.0.0.0 --port 8000
