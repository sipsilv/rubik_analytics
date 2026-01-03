@echo off
REM Rubik Analytics - Database Migration
REM Adds missing columns to match the User model

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
echo Database Migration Tool
echo ========================================
echo.

REM Use Python from virtual environment directly
"venv\Scripts\python.exe" scripts\migrations\migrate_core_schema.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Migration failed
    pause
    exit /b 1
)

echo.
REM Migration complete
