@echo off
REM ==============================================================================
REM Amity University Chhattisgarh - Automatic Attendance Planner Launcher (Windows)
REM ==============================================================================

cd /d "%~dp0"

echo ====================================================================
echo     AMITY AUTOMATIC ATTENDANCE CALCULATOR ^& STRATEGY PLANNER        
echo ====================================================================

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Python is not installed or not in PATH.
    echo Please download and install Python from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Setup virtual environment if not present or broken
if not exist "venv\Scripts\python.exe" (
    echo [Setup] Creating Python virtual environment in .\venv...
    if exist "venv" rd /s /q venv
    python -m venv venv
)

REM Install dependencies using venv python
if exist "requirements.txt" (
    echo [Setup] Checking dependencies...
    venv\Scripts\python.exe -m pip install -q -r requirements.txt
)

echo [Launch] Starting attendance planner...
echo.
venv\Scripts\python.exe attendance_planner.py %*

pause
