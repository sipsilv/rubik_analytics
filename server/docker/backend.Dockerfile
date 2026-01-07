FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt ./requirements.txt
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
    && mkdir -p /app/data/logs/app \
    && mkdir -p /app/data/logs/db_logs \
    && mkdir -p /app/data/logs/jobs \
    && mkdir -p /app/data/temp \
    && mkdir -p /app/data/backups \
    && chmod -R 755 /app/data

# Fix line endings for Python files
RUN find ./backend -type f -name "*.py" -exec dos2unix {} +

# Copy entrypoint script
COPY server/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && dos2unix /app/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

WORKDIR /app/backend
CMD ["/app/entrypoint.sh"]
