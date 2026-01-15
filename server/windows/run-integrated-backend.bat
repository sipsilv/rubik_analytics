@echo off
cd /d "%~dp0\..\..\backend"

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Backend venv not found.
    echo Please run server\windows\backend-setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ====================================================
echo   STARTING INTEGRATED BACKEND API SERVER
echo ====================================================
echo.
echo [INFO] Backend will automatically start all workers:
echo   - Telegram Listener
echo   - Telegram Extractor
echo   - Telegram Deduplication  
echo   - News Scorer
echo   - AI Enrichment Worker
echo.
echo [INFO] Starting Uvicorn API Server...
echo [INFO] Safe Auto-Reload ENABLED (Kill-Wait-Start method)
echo ====================================================
echo.

REM Uses custom python script to handle safe restarts for DuckDB
python ..\server\windows\safe-reload.py

echo.
echo [INFO] Backend server stopped.
pause
