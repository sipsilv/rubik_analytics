@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Rubik Analytics - Stop Docker
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

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Containers stopped.
) else (
    echo.
    echo [WARNING] Some containers may not have stopped.
)

echo.
pause
