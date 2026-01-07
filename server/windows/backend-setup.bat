@echo off
echo ========================================
echo Rubik Analytics - Backend Setup
echo ========================================
echo.

cd /d "%~dp0\..\..\backend"

echo [INFO] Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)

echo.
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [INFO] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [INFO] Creating data directories...
if not exist "..\data" mkdir "..\data"
if not exist "..\data\auth" mkdir "..\data\auth"
if not exist "..\data\auth\sqlite" mkdir "..\data\auth\sqlite"
if not exist "..\data\analytics" mkdir "..\data\analytics"
if not exist "..\data\analytics\duckdb" mkdir "..\data\analytics\duckdb"
if not exist "..\data\logs" mkdir "..\data\logs"
if not exist "connections" mkdir "connections"

echo.
echo [INFO] Initializing database...
python scripts\init\init_auth_database.py

if %errorlevel% neq 0 (
    echo [ERROR] Database initialization failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Backend setup complete!
echo ========================================
echo.
echo To start the backend server:
echo   venv\Scripts\activate
echo   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --no-access-log
echo.
pause
