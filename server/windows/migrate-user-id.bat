@echo off
REM Rubik Analytics - Migrate to User ID System
REM Adds user_id, last_active_at fields and updates AccessRequest model

cd /d "%~dp0\..\..\backend"

echo ========================================
echo Rubik Analytics - User ID Migration
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found
    echo Please run backend-setup.bat first
    pause
    exit /b 1
)

echo [INFO] Running migration script...
venv\Scripts\python.exe scripts\migrations\migrate_core_schema.py

if %errorlevel% neq 0 (
    echo [ERROR] Migration failed
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Migration completed!
echo.
echo Next steps:
echo 1. Restart the backend server
echo 2. Verify all users have user_id
echo 3. Test login with Email/Mobile/User ID
echo.
pause



