@echo off
REM First-time installer for CC Pipeline (AI Centric). Double-click to run.
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python 3 is not installed or not on PATH.
    echo Install it from https://www.python.org/downloads/ (tick "Add Python to PATH"), then re-run.
    echo.
    pause
    exit /b 1
)

python install.py
echo.
pause
