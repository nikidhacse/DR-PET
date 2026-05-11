@echo off
title Dr. PET - Multi-Modal Behavior Intelligence
echo ==========================================
echo    Dr. PET: Behavioral Intelligence
echo ==========================================
echo.

:: Check if requirements are installed (optional but helpful)
echo [1/3] Checking environment...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b
)

:: Start Backend in a separate window
echo [2/3] Starting Backend Server (FastAPI)...
start "Dr. PET Backend" cmd /k "python backend/main.py"

:: Wait for backend to warm up
timeout /t 5 /nobreak > nul

:: Open Frontend
echo [3/3] Launching Dashboard...
start "" "frontend/index.html"

echo.
echo Dr. PET is now operational!
echo Backend logs are running in the separate window.
echo.
timeout /t 5
exit
