# Open Analytics - Docker Environment

This directory contains Docker configuration files for running Open Analytics in a containerized environment.

## Prerequisites

- Docker Engine 20.10+ or Docker Desktop
- Docker Compose 2.0+

## Quick Start

### Automatic Setup (Recommended)

The Docker setup **automatically detects** the data folder path - no manual configuration needed!

1. **Configure environment variables** (REQUIRED):
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and set REQUIRED security keys (no default passwords allowed):
   # - JWT_SECRET_KEY (generate: openssl rand -base64 32)
   # - JWT_SYSTEM_SECRET_KEY (generate: openssl rand -base64 32)
   # - ENCRYPTION_KEY (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   ```

2. **Start services** using the start scripts (automatic data folder detection):
   ```bash
   # Linux/Mac
   ./docker-start.sh
   
   # Windows
   docker-start.bat
   ```
   
   The start scripts will:
   - ✅ Automatically detect the `data/` folder from the project root
   - ✅ Create the directory structure if it doesn't exist
   - ✅ Verify security keys are set (prevents startup with default passwords)
   - ✅ Start all services with proper configuration

3. **Alternative: Manual start** (not recommended - requires manual path configuration):
   ```bash
   # Only if you need to override the automatic detection
   HOST_DATA_DIR=/absolute/path/to/data docker-compose up -d --build
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Stop all services**:
   ```bash
   docker-compose down
   ```

## Environment Variables

### Backend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATA_DIR` | Auto | Directory for all data files (databases, logs, etc.) - set to `/app/data` in container |
| `DATABASE_URL` | Auto | SQLite database URL for authentication - auto-configured |
| `DUCKDB_PATH` | Auto | Path for DuckDB analytics databases - auto-configured |
| `JWT_SECRET_KEY` | **YES** | Secret key for JWT tokens - **MUST BE SET** (generate: `openssl rand -base64 32`) |
| `JWT_SYSTEM_SECRET_KEY` | **YES** | System secret key - **MUST BE SET** (generate: `openssl rand -base64 32`) |
| `JWT_ALGORITHM` | No | JWT algorithm (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token expiration (default: `480` = 8 hours) |
| `IDLE_TIMEOUT_MINUTES` | No | Idle session timeout (default: `30`) |
| `ENCRYPTION_KEY` | **YES** | Fernet encryption key - **MUST BE SET** (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins (default: `http://localhost:3000,...`) |
| `TRUEDATA_DEFAULT_AUTH_URL` | No | TrueData authentication URL (default: `https://auth.truedata.in/token`) |
| `TRUEDATA_DEFAULT_WEBSOCKET_PORT` | No | TrueData WebSocket port (default: `8086`) |
| `HOST_DATA_DIR` | No | Host path to data folder - **automatically detected** (override if needed) |
| `ADMIN_USERNAME` | No | Admin username for initial setup (optional) |
| `ADMIN_EMAIL` | No | Admin email for initial setup (optional) |
| `ADMIN_PASSWORD` | No | Admin password for initial setup (optional) |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://backend:8000` | Backend API URL (use service name in Docker) |
| `NODE_ENV` | `production` | Node.js environment |

## First-Time Setup

### Creating Admin User

On first startup, you can create an admin user by setting environment variables:

```bash
# In docker-compose.yml or .env file
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=SecurePassword123!
```

Or create manually after startup:
```bash
docker-compose exec backend python scripts/init/init_auth_database.py \
  --username admin \
  --email admin@example.com \
  --password SecurePassword123!
```

## Data Persistence & Automatic Folder Detection

### 🎯 Automatic Data Folder Detection (Default Behavior)

**The data folder is automatically detected and configured - no manual setup required!**

When you use `docker-start.sh` or `docker-start.bat`, the scripts automatically:

1. **Detect project root**: Finds the project root directory (parent of `server/docker/`)
2. **Locate data folder**: Locates the `data/` folder relative to the project root
3. **Convert to absolute path**: Converts the path to an absolute path for Docker volume mounting
4. **Create structure**: Creates the complete directory structure if it doesn't exist:
   - `data/auth/sqlite/`
   - `data/analytics/duckdb/`
   - `data/Company Fundamentals/`
   - `data/symbols/`
   - `data/connection/truedata/`
   - `data/logs/app/`, `data/logs/db_logs/`, `data/logs/jobs/`
   - `data/temp/`
   - `data/backups/`

**Example Output:**
```
[INFO] Automatically detected data folder: /home/user/rubik-analytics/data
```

**Benefits:**
- ✅ Works when transferring Docker to another machine (maintains project structure)
- ✅ No manual path configuration needed
- ✅ Consistent behavior across different operating systems
- ✅ Automatically creates missing directories

**Just run:**
```bash
./docker-start.sh      # Linux/Mac
docker-start.bat       # Windows
```

### Manual Override (Optional)

If you need to use a custom data folder location, set `HOST_DATA_DIR` in your `.env` file:
```bash
# .env
HOST_DATA_DIR=/custom/path/to/data
```

### Data Directory Contents

The mounted data directory includes:
- Authentication database (`auth/sqlite/auth.db`)
- Analytics databases (`analytics/duckdb/`)
- Corporate announcements (`Company Fundamentals/corporate_announcements.duckdb`)
- Symbols database (`symbols/symbols.duckdb`)
- Logs (`logs/`)
- Connection configurations (`connection/`)

**Important Notes:**
- The data directory is mounted from the host, so data persists across container restarts.
- The data folder path **inside the container** is always `/app/data` (don't change this).
- The data folder path **on the host** is automatically detected (or can be set via `HOST_DATA_DIR`).
- When transferring Docker to another machine, **the automatic detection will work** as long as the project structure is maintained (`data/` folder is in the project root).
- The start scripts ensure the data folder exists and has proper permissions.

## Services

### Backend (rubik-backend)
- **Port**: 8000
- **Health Check**: `http://localhost:8000/health`
- **API Docs**: `http://localhost:8000/docs`
- **Base Image**: `python:3.11-slim`

### Frontend (rubik-frontend)
- **Port**: 3000
- **Health Check**: `http://localhost:3000/`
- **Base Image**: `node:20-alpine`

## Networking

Services communicate via the `rubik-network` bridge network:
- Frontend → Backend: `http://backend:8000`
- External → Frontend: `http://localhost:3000`
- External → Backend: `http://localhost:8000`

## Security Configuration

### Required Environment Variables (NO DEFAULT PASSWORDS)

**⚠️ IMPORTANT: Default passwords are NOT allowed and will be rejected!**

Before starting Docker, you **MUST** set these security keys in your `.env` file. **All three keys are required and must be unique, secure values.**

1. **JWT_SECRET_KEY** - Used for signing JWT tokens
   ```bash
   # Generate a secure key:
   openssl rand -base64 32
   
   # Then add to .env:
   JWT_SECRET_KEY=<your-generated-key>
   ```

2. **JWT_SYSTEM_SECRET_KEY** - Used for system-level JWT operations
   ```bash
   # Generate a secure key:
   openssl rand -base64 32
   
   # Then add to .env:
   JWT_SYSTEM_SECRET_KEY=<your-generated-key>
   ```

3. **ENCRYPTION_KEY** - Used to encrypt connection credentials (Fernet key)
   ```bash
   # Generate a secure key:
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   
   # Then add to .env:
   ENCRYPTION_KEY=<your-generated-key>
   ```

**Automatic Security Checks:**
- ✅ The `docker-start.sh` and `docker-start.bat` scripts **automatically verify** that all required keys are set
- ✅ **Prevents startup** if keys are missing, empty, or using default/example values
- ✅ Provides clear error messages if security configuration is invalid
- ✅ No default passwords are allowed - you must generate your own secure keys

**Example of what happens if keys are missing:**
```
[ERROR] JWT_SECRET_KEY is not set or is using default value!
[ERROR] Please edit .env file and set a secure JWT_SECRET_KEY
```

### Troubleshooting Data Folder Issues

**Problem**: Docker container can't find the data folder
**Solution**: 
- ✅ **Use the start scripts**: `docker-start.sh` (Linux/Mac) or `docker-start.bat` (Windows) - they automatically detect the data folder
- ⚠️ If using manual `docker-compose up`, you must set `HOST_DATA_DIR` to an absolute path
- Check the start script output for the detected path: `[INFO] Automatically detected data folder: ...`
- Verify the data folder exists: The scripts will create it if missing
- Check docker-compose logs: `docker-compose logs backend`

**Problem**: "HOST_DATA_DIR is not set" error
**Solution**:
- Use `docker-start.sh` or `docker-start.bat` instead of manual `docker-compose` commands
- The start scripts automatically set `HOST_DATA_DIR` based on the project structure
- If you must use manual `docker-compose`, set: `export HOST_DATA_DIR=/absolute/path/to/data` (Linux/Mac) or `$env:HOST_DATA_DIR="C:/path/to/data"` (Windows)

**Problem**: Permission denied errors
**Solution**:
- Ensure the data folder has read/write permissions
- On Linux/Mac: `chmod -R 755 /path/to/data`
- On Windows: Ensure Docker Desktop has access to the drive/folder

**Problem**: Data not persisting after container restart
**Solution**:
- Verify the volume mount in `docker-compose ps` shows correct path
- The automatic detection should handle this - check the start script output for the detected path

## Troubleshooting

### Check service status
```bash
docker-compose ps
```

### View backend logs
```bash
docker-compose logs -f backend
```

### View frontend logs
```bash
docker-compose logs -f frontend
```

### Restart a service
```bash
docker-compose restart backend
docker-compose restart frontend
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

### Access backend shell
```bash
docker-compose exec backend bash
```

### Access frontend shell
```bash
docker-compose exec frontend sh
```

### Check database initialization
```bash
docker-compose exec backend python scripts/init/init_auth_database.py
```

## Production Considerations

1. **Set security keys**: **REQUIRED** - Set `JWT_SECRET_KEY`, `JWT_SYSTEM_SECRET_KEY`, and `ENCRYPTION_KEY` in `.env` file (not committed to git)
2. **Use environment variables**: Store all secrets in `.env` file (git-ignored)
3. **Enable HTTPS**: Use a reverse proxy (nginx, traefik) for HTTPS
4. **Resource limits**: Already configured in docker-compose.yml:
   - Backend: 2 CPU / 2GB RAM limit, 0.5 CPU / 512MB reserved
   - Frontend: 1 CPU / 1GB RAM limit, 0.25 CPU / 256MB reserved
   - Adjust based on your infrastructure needs
5. **Log rotation**: Configured with 10MB max size and 3 file rotation
6. **Backup strategy**: Regularly backup the `data/` directory
7. **Monitoring**: Set up monitoring for health checks and resource usage
8. **Data folder**: Automatically detected - no manual configuration needed when using start scripts

## Windows Server Compatibility

This Docker setup matches the Windows server configuration:
- Same environment variables
- Same directory structure
- Same initialization scripts
- Same port mappings

The only difference is the base paths (Windows uses `C:/Users/...` while Docker uses `/app/data`).

