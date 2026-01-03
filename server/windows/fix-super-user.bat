@echo off
REM Rubik Analytics - Fix Super User Access
REM Comprehensive fix for Super User login issues

setlocal enabledelayedexpansion

cd /d "%~dp0\..\..\backend"

REM Check if venv exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found
    echo Please run: server\windows\backend-setup.bat first
    pause
    exit /b 1
)

REM Check if venv\Scripts\python.exe exists
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python executable not found in virtual environment
    echo Please run: server\windows\backend-setup.bat first
    pause
    exit /b 1
)

echo ========================================
echo Super User Access Fix
echo ========================================
echo.

REM Use Python from virtual environment directly
"venv\Scripts\python.exe" scripts\init\init_auth_database.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Fix failed
    echo.
    echo Troubleshooting:
    echo   1. Make sure virtual environment is set up: server\windows\backend-setup.bat
    echo   2. Check that all dependencies are installed
    echo   3. Verify database connection settings
    pause
    exit /b 1
)

echo.
echo ========================================
echo Fix Complete
echo ========================================
echo.
echo Default Login:
echo   Username: admin
echo   Password: admin123
echo.
echo Super User should now be able to log in successfully.
echo.
pause
