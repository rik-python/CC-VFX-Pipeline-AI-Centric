@echo off
REM One-click updater for CC Pipeline (AI Centric). Double-click to get the latest pipeline.
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo.
    echo Git is not installed or not on PATH.
    echo Install Git from https://git-scm.com/download/win then try again.
    echo.
    pause
    exit /b 1
)

echo ============================================
echo   Updating CC Pipeline (AI Centric)...
echo ============================================
echo.
git pull
if errorlevel 1 (
    echo.
    echo Update FAILED. If it mentions "local changes", you edited a repo file.
    echo Do not edit files inside this folder. Ask Rikin for help.
    echo.
    pause
    exit /b 1
)

echo.
where python >nul 2>&1
if errorlevel 1 (
    echo Python not found - skipping folder sync.
    echo Install Python 3 so updates can add new folders to your shots.
) else (
    echo Syncing folder structure to existing shots...
    python pipeline_core.py sync
)

echo.
echo ============================================
echo   Done. RESTART NUKE to load the update.
echo ============================================
echo.
pause
