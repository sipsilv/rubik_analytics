@echo off
echo ========================================
echo Rubik Analytics - Stop Docker Server
echo ========================================
echo.

cd /d "%~dp0"

echo [INFO] Stopping Docker containers...
docker-compose down

echo.
echo [SUCCESS] Docker environment stopped.
echo.
pause
