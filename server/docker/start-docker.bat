@echo off
echo ========================================
echo Rubik Analytics - Start Docker Services
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose is not available
    echo Please ensure Docker Desktop is running
    pause
    exit /b 1
)

echo [INFO] Checking for running Docker containers...
docker compose ps 2>nul | findstr "Up" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Found running containers, stopping them first...
    docker compose down
    if %errorlevel% equ 0 (
        echo [OK] Containers stopped
    )
    echo [INFO] Waiting for containers to stop...
    timeout /t 3 /nobreak >nul
) else (
    echo [INFO] No running containers found
)

echo.
echo [INFO] Starting Docker services...
echo [INFO] This will build and start:
echo   - Backend service (Port 8000)
echo   - Frontend service (Port 3000)
echo.
echo [INFO] Building and starting containers...
echo.

docker compose up --build

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start Docker services
    echo.
    echo Troubleshooting:
    echo   1. Ensure Docker Desktop is running
    echo   2. Check if ports 8000 and 3000 are available
    echo   3. Try: docker compose down (to stop existing containers)
    echo.
    pause
    exit /b 1
)

pause
