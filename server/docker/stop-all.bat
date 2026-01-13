@echo off
REM Rubik Analytics - Stop Docker (Robust)
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===========================================
echo   Rubik Analytics - Docker Stop
echo ===========================================
echo.

REM 1. Autodetect Data Directory (needed for compose file variable resolution)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."
set "PROJECT_ROOT=%CD%"
set "DATA_DIR=%PROJECT_ROOT%\data"
set "HOST_DATA_DIR=%DATA_DIR%"

cd /d "%SCRIPT_DIR%"

REM 2. Check Docker Compose
docker-compose version >nul 2>&1
if %errorlevel% equ 0 (
    set COMPOSE_CMD=docker-compose
) else (
    docker compose version >nul 2>&1
    if %errorlevel% equ 0 (
        set COMPOSE_CMD=docker compose
    ) else (
        echo [ERROR] docker-compose not found.
        pause
        exit /b 1
    )
)

REM 3. Stop
echo [INFO] Stopping services...
%COMPOSE_CMD% down

if %errorlevel% equ 0 (
    echo.
    echo [OK] All services stopped.
) else (
    echo.
    echo [ERROR] Failed to stop services.
)

echo.
pause
