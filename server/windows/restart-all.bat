@echo off
REM Rubik Analytics - Restart All Servers
REM Stops all servers, then starts them again

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo Rubik Analytics - Restarting All Servers
echo ========================================
echo.

echo [INFO] Stopping all servers...
call "%~dp0stop-all.bat"

echo.
echo [INFO] Waiting before restart...
timeout /t 3 /nobreak >nul

echo.
echo [INFO] Starting all servers...
call "%~dp0start-all.bat"
