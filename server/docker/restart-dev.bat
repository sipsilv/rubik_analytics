@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Rubik Analytics - Restart Docker Dev Mode
echo ========================================
echo.

cd /d "%~dp0"

:: Detect Docker Compose Command
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

echo [INFO] Stopping dev containers...
%DOCKER_CMD% -f docker-compose.dev.yml down

echo.
echo [INFO] Recreating dev containers with updated environment...
%DOCKER_CMD% -f docker-compose.dev.yml up -d --force-recreate

if !errorlevel! equ 0 (
    echo.
    echo [SUCCESS] Dev containers restarted.
    echo.
    echo [INFO] Waiting for services to start...
    timeout /t 5 /nobreak >nul
    echo.
    echo [INFO] Container status:
    %DOCKER_CMD% -f docker-compose.dev.yml ps
    echo.
    echo Backend:  http://localhost:8000
    echo Frontend: http://localhost:3000
) else (
    echo.
    echo [ERROR] Failed to restart containers.
    echo Check the error messages above for details.
)

echo.
pause

