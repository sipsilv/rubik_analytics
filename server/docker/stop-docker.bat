@echo off
echo ========================================
echo Rubik Analytics - Stop Docker Services
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

echo [INFO] Stopping Docker services...
echo.

docker compose down

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to stop Docker services
    pause
    exit /b 1
)

echo.
echo [OK] Docker services stopped
echo.
pause
