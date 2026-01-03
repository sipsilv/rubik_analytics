FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better Docker layer caching)
# Note: .dockerignore is automatically read from build context root (project root)
COPY backend/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install dos2unix to fix Windows CRLF issues
RUN apt-get update && apt-get install -y dos2unix && rm -rf /var/lib/apt/lists/*


# Copy application code
COPY backend/ ./backend/

# Create data directory structure (will be overwritten by volume mount if provided)
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

# Set proper permissions
RUN chmod -R 755 /app/data

# Expose port
EXPOSE 8000

# Health check with longer start period for database initialization
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run initialization and start server
WORKDIR /app/backend

# Fix line endings for all scripts and app files
RUN find . -type f -name "*.py" -exec dos2unix {} +


# Use shell form to allow for proper signal handling and initialization
CMD ["sh", "-c", "python scripts/init/init_auth_database.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
