@echo off
title Cyber Threat Hunter - Clean Start
echo ========================================
echo  Cyber Threat Hunter - Clean Startup
echo ========================================

REM Clean backend
echo Cleaning backend...
cd backend
if exist "__pycache__" rmdir /s /q "__pycache__" 2>nul
if exist "*.pyc" del /f "*.pyc" 2>nul

REM Clean frontend
echo Cleaning frontend...
cd ..\frontend
if exist "node_modules" rmdir /s /q "node_modules" 2>nul
if exist "package-lock.json" del /f "package-lock.json" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul

echo.
echo Clean complete. Run start.bat to restart.
pause
