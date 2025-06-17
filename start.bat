@echo off
title Cyber Threat Hunter
echo ========================================
echo  Cyber Threat Hunter
echo ========================================

REM Check if setup is needed
if not exist "backend\venv" (
    echo Backend not set up. Running setup...
    call setup-backend.bat
)

if not exist "frontend\node_modules" (
    echo Frontend not set up. Running setup...
    call setup-frontend.bat
)

echo Starting servers...

REM Start Backend
start "Backend" cmd /k "start-backend.bat"

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start Frontend
start "Frontend" cmd /k "start-frontend.bat"

echo.
echo ========================================
echo  Servers are starting...
echo  Backend:  http://localhost:5000
echo  Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit...
pause >nul
echo  Backend:  http://localhost:5000
echo  Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit...
pause >nul
