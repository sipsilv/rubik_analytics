@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Rubik Analytics - Restart Docker
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
        pause
        exit /b 1
    )
)

echo [INFO] Stopping containers...
%DOCKER_CMD% down

echo.
echo [INFO] Restarting containers...
%DOCKER_CMD% up -d --force-recreate

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo [SUCCESS] Containers restarted!
    echo ========================================
    echo.
    echo Frontend: http://localhost:3000
    echo Backend:  http://localhost:8000
) else (
    echo.
    echo [ERROR] Failed to restart containers.
)

echo.
pause
