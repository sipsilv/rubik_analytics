@echo off
REM Rubik Analytics - Start All Servers
REM Starts both backend and frontend servers

setlocal enabledelayedexpansion

cd /d "%~dp0\..\.."

echo ========================================
echo Rubik Analytics - Starting All Servers
echo ========================================
echo.

REM Check prerequisites
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js and try again
    pause
    exit /b 1
)

REM Stop any existing servers first
echo [INFO] Checking for existing servers...
call "%~dp0stop-all.bat" >nul 2>&1
timeout /t 2 /nobreak >nul

REM Check backend setup
if not exist "backend\venv" (
    echo [INFO] Backend not set up. Running setup...
    call "%~dp0backend-setup.bat"
    if %errorlevel% neq 0 (
        echo [ERROR] Backend setup failed
        pause
        exit /b 1
    )
) else (
    REM Check if dependencies are installed
    echo [INFO] Checking backend dependencies...
    cd /d "%~dp0\..\..\backend"
    if exist "venv\Scripts\python.exe" (
        "venv\Scripts\python.exe" -c "import uvicorn, fastapi" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARNING] Backend dependencies not installed!
            echo [INFO] Running backend setup to install dependencies...
            cd /d "%~dp0\..\.."
            call "%~dp0backend-setup.bat"
            if !errorlevel! neq 0 (
                echo [ERROR] Backend setup failed - dependencies not installed
                echo [ERROR] Please run: server\windows\backend-setup.bat manually
                pause
                exit /b 1
            )
        ) else (
            echo [OK] Backend dependencies verified
        )
    ) else (
        echo [ERROR] Python executable not found in venv
        echo [INFO] Running backend setup...
        cd /d "%~dp0\..\.."
        call "%~dp0backend-setup.bat"
        if !errorlevel! neq 0 (
            echo [ERROR] Backend setup failed
            pause
            exit /b 1
        )
    )
    cd /d "%~dp0\..\.."
)

REM Check frontend setup
if not exist "frontend\node_modules" (
    echo [INFO] Frontend not set up. Running setup...
    call "%~dp0frontend-setup.bat"
    if %errorlevel% neq 0 (
        echo [ERROR] Frontend setup failed
        pause
        exit /b 1
    )
)

REM Database initialization is handled automatically by the backend on startup

REM Verify ports are free and try to free them if needed
echo [INFO] Checking if ports 8000 and 3000 are available...
netstat -ano | findstr :8000 >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 8000 is in use, attempting to free it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
        set PID_VAL=%%a
        if not "!PID_VAL!"=="" (
            taskkill /PID !PID_VAL! /F >nul 2>&1
            if !errorlevel! equ 0 (
                echo [OK] Freed port 8000 (PID: !PID_VAL!)
            )
        )
    )
    timeout /t 2 /nobreak >nul
) else (
    echo [OK] Port 8000 is available
)

netstat -ano | findstr :3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 3000 is in use, attempting to free it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
        set PID_VAL=%%a
        if not "!PID_VAL!"=="" (
            taskkill /PID !PID_VAL! /F >nul 2>&1
            if !errorlevel! equ 0 (
                echo [OK] Freed port 3000 (PID: !PID_VAL!)
            )
        )
    )
    timeout /t 2 /nobreak >nul
) else (
    echo [OK] Port 3000 is available
)
echo [OK] Ports are ready

echo.
echo [INFO] Starting Backend Server (port 8000)...
cd /d "%~dp0\..\..\backend"
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found
    echo Please run: server\windows\backend-setup.bat first
    pause
    exit /b 1
)

REM Stop any running Docker containers to free ports/locks
echo [INFO] Ensuring Docker containers are stopped...
docker compose -f "%~dp0\..\docker\docker-compose.yml" down >nul 2>&1
if %errorlevel% neq 0 (
    docker-compose -f "%~dp0\..\docker\docker-compose.yml" down >nul 2>&1
)
echo [OK] Docker environment clear

REM Get absolute paths (handle spaces in paths)
REM Get absolute paths (handle spaces in paths)
cd /d "%~dp0\..\.."
set "PROJECT_ROOT_RAW=%CD%"
REM Normalize to forward slashes for consistency with Python/SQLAlchemy/Docker config references
set "PROJECT_ROOT=%PROJECT_ROOT_RAW:\=/%"

set "BACKEND_DIR=%PROJECT_ROOT_RAW%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT_RAW%\frontend"

REM -----------------------------------------------------------------------------
REM Environment Variables (Matched with server/docker/docker-compose.yml)
REM -----------------------------------------------------------------------------
REM Use forward slashes for all path-based env vars
set "DATA_DIR=%PROJECT_ROOT%/data"
set "DATABASE_URL=sqlite:///%PROJECT_ROOT%/data/auth/sqlite/auth.db"
set "DUCKDB_PATH=%PROJECT_ROOT%/data/analytics/duckdb"

REM JWT Configuration - Loaded from .env file
REM Security - Loaded from .env file
set "CORS_ORIGINS=http://localhost:3000,http://frontend:3000,http://127.0.0.1:3000,http://rubik-frontend:3000"

REM TrueData
set "TRUEDATA_DEFAULT_AUTH_URL=https://auth.truedata.in/token"
set "TRUEDATA_DEFAULT_WEBSOCKET_PORT=8086"
REM -----------------------------------------------------------------------------

REM Start backend server ( Integrated with Workers )
start "Rubik Backend" cmd /k "%~dp0run-integrated-backend.bat"

timeout /t 5 /nobreak >nul

echo [INFO] Starting Frontend Server (port 3000)...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [WARNING] Frontend dependencies not found. Running setup...
    call "%~dp0frontend-setup.bat"
    if %errorlevel% neq 0 (
        echo [ERROR] Frontend setup failed
        echo Please run: server\windows\frontend-setup.bat manually
        pause
        exit /b 1
    )
)

REM Start frontend server directly
start "Rubik Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

timeout /t 3 /nobreak >nul

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo Servers Started Successfully
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Two windows have been opened for the servers.
echo Close those windows to stop the servers.
echo.
echo To stop all servers, run: stop-all.bat
echo.
pause
