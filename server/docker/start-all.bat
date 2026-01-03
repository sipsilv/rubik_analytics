@echo off
echo ========================================
echo Rubik Analytics - Start Docker Server
echo ========================================
echo.

cd /d "%~dp0"

echo [INFO] Stopping existing servers...
REM Stop any local Windows servers first to free ports
call ..\windows\stop-all.bat >nul 2>&1

echo.
echo [INFO] Checking Docker status...

set /a retries=0
:RETRY_LOOP
docker info >nul 2>&1
if %errorlevel% equ 0 goto DOCKER_READY

set /a retries+=1
if %retries% geq 5 (
    echo [ERROR] Docker is NOT running!
    echo Please start Docker Desktop and wait for the engine to start.
    pause
    exit /b 1
)
echo [WAIT] Waiting for Docker to start... (Attempt %retries%/5)
timeout /t 5 /nobreak >nul
goto RETRY_LOOP

:DOCKER_READY
echo [OK] Docker is running.

echo.
echo [INFO] Building and starting Docker containers...
docker-compose down
docker-compose up --build -d

if %errorlevel% neq 0 (
    echo [ERROR] Docker failed to start.
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
echo   call stop-all.bat
echo.
pause
