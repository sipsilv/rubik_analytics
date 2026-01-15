@echo off
REM Rubik Analytics - Restart Docker (Robust)
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===========================================
echo   Rubik Analytics - Docker Restart
echo ===========================================
echo.

REM 1. Detect Data Directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."
set "PROJECT_ROOT=%CD%"
set "DATA_DIR=%PROJECT_ROOT%\data"
set "HOST_DATA_DIR=%DATA_DIR%"
echo [INFO] Data Directory: %HOST_DATA_DIR%

REM 2. Verify .env exists
cd /d "%SCRIPT_DIR%"
if not exist .env (
    if exist .env.example (
        echo [INFO] .env not found. Creating from .env.example...
        copy .env.example .env >nul
        echo [WARNING] Created .env. Please configure secrets!
    ) else (
        echo [ERROR] .env file missing and .env.example not found!
        pause
        exit /b 1
    )
)

REM 3. Check Docker Compose
docker-compose version >nul 2>&1
if %errorlevel% equ 0 (
    set COMPOSE_CMD=docker-compose
) else (
    docker compose version >nul 2>&1
    if %errorlevel% equ 0 (
        set COMPOSE_CMD=docker compose
    ) else (
        echo [ERROR] docker-compose not found. Install Docker Desktop.
        pause
        exit /b 1
    )
)

REM 4. Stop Containers
echo.
echo [INFO] Stopping containers...
%COMPOSE_CMD% down

REM 5. Start Containers (Build + Force Recreate to pick up code/dependency changes)
echo.
echo [INFO] Rebuilding and Starting containers...
%COMPOSE_CMD% up -d --build --force-recreate

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start containers. Check logs above.
    pause
    exit /b 1
)

echo.
echo ===========================================
echo   Restart Complete
echo ===========================================
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
pause
