@echo off
echo ========================================
echo Rubik Analytics - Restart Docker Services
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH
    pause
    exit /b 1
)

echo [INFO] Stopping existing services...
docker compose down

echo.
echo [INFO] Starting services...
docker compose up --build

pause
