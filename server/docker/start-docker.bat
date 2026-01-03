@echo off
echo ========================================
echo Rubik Analytics - Start Docker Server
echo ========================================
echo.

cd /d "%~dp0"

echo [INFO] Stopping existing servers...
REM Call stop-all.bat from the windows directory
call ..\windows\stop-all.bat >nul 2>&1

echo.
echo [INFO] Building and starting Docker containers...
REM We are already in server/docker

REM Check if Docker acts responsively
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is NOT running!
    echo Please start Docker Desktop and wait for the engine to start.
    pause
    exit /b 1
)

docker-compose down
docker-compose up --build -d

if %errorlevel% neq 0 (
    echo [ERROR] Docker failed to start. Make sure Docker Desktop is running.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Docker containers started!
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo To view logs:
echo   cd server\docker
echo   docker-compose logs -f
echo.
echo To stop servers:
echo   cd server\docker
echo   docker-compose down
echo.
pause
