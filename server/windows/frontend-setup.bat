@echo off
echo ========================================
echo Rubik Analytics - Frontend Setup
echo ========================================
echo.

cd /d "%~dp0\..\..\frontend"

echo [INFO] Installing dependencies...
call npm install

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Frontend setup complete!
echo ========================================
echo.
echo To start the frontend server:
echo   npm run dev
echo.
pause
