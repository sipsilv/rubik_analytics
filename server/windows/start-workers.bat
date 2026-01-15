@echo off
REM Rubik Analytics - Start Background Workers
REM Starts Telegram Listener, Extractor, Deduplicator, and Scorer

setlocal enabledelayedexpansion

cd /d "%~dp0\..\.."
set "PROJECT_ROOT=%CD%"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"

echo ========================================
echo Rubik Analytics - Starting Workers
echo ========================================
echo.


REM Set UTF-8 for Python to avoid charmap crashes
set PYTHONUTF8=1

if not exist "%BACKEND_DIR%\venv\Scripts\activate.bat" (
    echo [ERROR] Backend venv not found. Please run backend-setup.bat first.
    pause
    exit /b 1
)

echo [INFO] Starting Telegram Raw Listener...
start "Telegram Listener" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && python -m app.services.telegram_raw_listener.main"

echo [INFO] Starting Telegram Extractor...
start "Telegram Extractor" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && python -m app.services.telegram_extractor.main"

echo [INFO] Starting Telegram Deduplicator...
start "Telegram Deduplicator" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && python -m app.services.telegram_deduplication.main"

echo [INFO] Starting News Scoring Engine...
start "News Scorer" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && python -m app.services.news_scoring.main"

echo.
echo [SUCCESS] 4 Worker processes started in new windows.
echo.
pause
