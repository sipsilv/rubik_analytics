# Docker Configuration Updates

## Latest Update (End-to-End Improvements - Windows Server Parity)
Comprehensive updates to Docker configuration for production readiness, performance optimization, and exact Windows server compatibility.

### Improvements Made
- ✅ Added Docker Compose version specification (3.8)
- ✅ Added resource limits and reservations for both services (CPU and memory)
- ✅ Enhanced logging configuration with rotation (max-size: 10m, max-file: 3)
- ✅ Improved health check start periods (backend: 40s, frontend: 60s)
- ✅ Optimized Dockerfile layer caching for faster rebuilds
- ✅ Added pip upgrade step in backend Dockerfile
- ✅ Improved npm install with `--prefer-offline --no-audit` flags
- ✅ Better error handling for dos2unix commands
- ✅ Moved timezone setup earlier in backend Dockerfile for better caching
- ✅ **Fixed DUCKDB_PATH to use absolute path** (`/app/data/analytics/duckdb`) to match Windows server
- ✅ **Verified all environment variables match Windows server configuration exactly**
- ✅ **Entrypoint script verified to match Windows server uvicorn command pattern**

## Previous Updates

## Summary
Updated Docker configuration to match Windows server setup end-to-end, ensuring all services, dependencies, and configurations are properly configured.

## Changes Made

### 1. docker-compose.yml
- ✅ Fixed frontend `NEXT_PUBLIC_API_URL` to use service name (`http://backend:8000`) instead of `localhost`
- ✅ Added admin user creation environment variables (`ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`)
- ✅ All environment variables match Windows server configuration

### 2. backend.Dockerfile
- ✅ All required directories created (matches Windows structure)
- ✅ Line ending fixes for Windows compatibility
- ✅ Entrypoint script properly configured
- ✅ Health check configured

### 3. frontend.Dockerfile
- ✅ Added `wget` for health checks (in both deps and runner stages)
- ✅ Standalone output properly configured
- ✅ Health check configured
- ✅ All Next.js build optimizations in place

### 4. entrypoint.sh
- ✅ Enhanced to support admin user creation via environment variables
- ✅ Proper error handling
- ✅ Database initialization before server start

### 5. Documentation
- ✅ Created comprehensive `README.md` with setup instructions
- ✅ Created `.env.example` template (blocked by gitignore, but documented)
- ✅ Created helper scripts:
  - `docker-start.sh` / `docker-start.bat` (Linux/Windows)
  - `docker-stop.sh` / `docker-stop.bat` (Linux/Windows)

## Directory Structure

All required directories are created in the Docker container:
```
/app/data/
├── auth/
│   ├── sqlite/
│   └── postgres/
├── analytics/
│   ├── duckdb/
│   └── postgres/
├── Company Fundamentals/
├── symbols/
├── connection/
│   └── truedata/
├── logs/
│   ├── app/
│   ├── db_logs/
│   └── jobs/
├── temp/
└── backups/
```

## Environment Variables

All environment variables from Windows server are supported:
- Data directory configuration
- Database URLs
- JWT configuration
- CORS settings
- TrueData configuration
- Admin user creation (optional)

## First-Time Setup

Admin user can be created via:
1. Environment variables in docker-compose.yml or .env file
2. Manual command after container starts

## Data Persistence

All data is persisted via volume mount:
- `../../data:/app/data` (mounted from host)

## Networking

- Services communicate via `rubik-network` bridge network
- Frontend → Backend: `http://backend:8000`
- External access: `http://localhost:3000` (frontend), `http://localhost:8000` (backend)

## Health Checks

- Backend: `curl -f http://localhost:8000/health`
- Frontend: `wget --spider http://localhost:3000/`

## Compatibility

✅ Fully compatible with Windows server setup
✅ Same environment variables
✅ Same directory structure
✅ Same initialization scripts
✅ Same port mappings

## Next Steps

1. Create `.env` file from `.env.example` (if needed)
2. Update secrets (JWT keys, encryption key) for production
3. Run `docker-compose up -d --build` to start services
4. Access application at `http://localhost:3000`

