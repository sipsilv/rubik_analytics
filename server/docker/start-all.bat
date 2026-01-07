@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Rubik Analytics - Start Docker
echo ========================================
echo.

cd /d "%~dp0"

:: Check Docker Compose
set DOCKER_CMD=
docker compose version >nul 2>&1
if !errorlevel! equ 0 (
    set DOCKER_CMD=docker compose
) else (
    docker-compose --version >nul 2>&1
    if !errorlevel! equ 0 (
        set DOCKER_CMD=docker-compose
    ) else (
        echo [ERROR] Docker Compose not found!
        echo Please install Docker Desktop.
        pause
        exit /b 1
    )
)

:: Check Docker Engine
echo [INFO] Checking Docker...
set /a retries=0
:RETRY_LOOP
docker info >nul 2>&1
if %errorlevel% equ 0 goto DOCKER_READY

set /a retries+=1
if %retries% geq 5 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop.
    pause
    exit /b 1
)
echo [WAIT] Waiting for Docker... (Attempt %retries%/5)
timeout /t 5 /nobreak >nul
goto RETRY_LOOP

:DOCKER_READY
echo [OK] Docker is running.

:: Start Containers
echo.
echo [INFO] Starting containers...
%DOCKER_CMD% down >nul 2>&1
%DOCKER_CMD% up --build -d

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start containers.
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Rubik Analytics Started!
echo ========================================
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Commands:
echo   stop-all.bat    - Stop servers
echo   restart-all.bat - Restart servers
echo.
pause
