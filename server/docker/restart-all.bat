@echo off
echo ========================================
echo Rubik Analytics - Restart Docker Server
echo ========================================
echo.

cd /d "%~dp0"

echo [INFO] Stopping...
call stop-all.bat >nul 2>&1

echo.
echo [INFO] Starting...
call start-all.bat
