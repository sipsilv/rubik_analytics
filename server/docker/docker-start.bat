@echo off
REM Rubik Analytics - Docker Start Script (Windows)
REM Starts all services using Docker Compose
REM Automatically detects data folder path

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===========================================
echo   Rubik Analytics - Docker Start
echo ===========================================
echo.

REM Automatically detect data folder path
REM Script is in server\docker\, so data folder is at ..\..\data
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."
set "PROJECT_ROOT=%CD%"
set "DATA_DIR=%PROJECT_ROOT%\data"

REM Convert to absolute path (already absolute on Windows)
set "HOST_DATA_DIR=%DATA_DIR%"

echo [INFO] Automatically detected data folder: %HOST_DATA_DIR%

REM Verify data folder exists or create it
if not exist "%HOST_DATA_DIR%" (
    echo [WARNING] Data folder does not exist. Creating directory structure...
    mkdir "%HOST_DATA_DIR%\auth\sqlite" 2>nul
    mkdir "%HOST_DATA_DIR%\analytics\duckdb" 2>nul
    mkdir "%HOST_DATA_DIR%\Company Fundamentals" 2>nul
    mkdir "%HOST_DATA_DIR%\symbols" 2>nul
    mkdir "%HOST_DATA_DIR%\connection\truedata" 2>nul
    mkdir "%HOST_DATA_DIR%\logs\app" 2>nul
    mkdir "%HOST_DATA_DIR%\logs\db_logs" 2>nul
    mkdir "%HOST_DATA_DIR%\logs\jobs" 2>nul
    mkdir "%HOST_DATA_DIR%\temp" 2>nul
    mkdir "%HOST_DATA_DIR%\backups" 2>nul
    echo [INFO] Created data folder structure at: %HOST_DATA_DIR%
)

cd /d "%SCRIPT_DIR%"

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker-compose version >nul 2>&1
if %errorlevel% equ 0 (
    set COMPOSE_CMD=docker-compose
) else (
    docker compose version >nul 2>&1
    if %errorlevel% equ 0 (
        set COMPOSE_CMD=docker compose
    ) else (
        echo [ERROR] docker-compose is not installed. Please install Docker Desktop.
        pause
        exit /b 1
    )
)

REM Check if .env file exists
if not exist .env (
    echo [INFO] .env file not found. Creating from .env.example...
    if exist .env.example (
        copy .env.example .env >nul
        echo [WARNING] Please edit .env file with your configuration before starting!
        echo [WARNING] You MUST set JWT_SECRET_KEY, JWT_SYSTEM_SECRET_KEY, and ENCRYPTION_KEY
        echo [WARNING] Generate keys using: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        pause
    )
)

REM Verify required environment variables are set (basic check)
if exist .env (
    findstr /C:"JWT_SECRET_KEY=your-secret-key-change-in-production" .env >nul 2>&1
    if %errorlevel% equ 0 (
        echo [ERROR] JWT_SECRET_KEY is using default value!
        echo [ERROR] Please edit .env file and set a secure JWT_SECRET_KEY
        pause
        exit /b 1
    )
    findstr /C:"JWT_SYSTEM_SECRET_KEY=your-system-secret-key-change-in-production" .env >nul 2>&1
    if %errorlevel% equ 0 (
        echo [ERROR] JWT_SYSTEM_SECRET_KEY is using default value!
        echo [ERROR] Please edit .env file and set a secure JWT_SYSTEM_SECRET_KEY
        pause
        exit /b 1
    )
    findstr /C:"ENCRYPTION_KEY=jT7ACJPNHdp-IwKWVDto-vohgPGxwP_95sjBlgsr9Eg=" .env >nul 2>&1
    if %errorlevel% equ 0 (
        echo [ERROR] ENCRYPTION_KEY is using default value!
        echo [ERROR] Please edit .env file and set a secure ENCRYPTION_KEY
        echo [INFO] Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        pause
        exit /b 1
    )
)

echo [INFO] Building and starting services...
%COMPOSE_CMD% up -d --build

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services
    pause
    exit /b 1
)

echo.
echo ===========================================
echo   Services Started
echo ===========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo To view logs: %COMPOSE_CMD% logs -f
echo To stop:      %COMPOSE_CMD% down
echo.
pause

