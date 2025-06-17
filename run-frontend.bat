@echo off
title Cyber Threat Hunter - Frontend
cd /d "%~dp0\frontend"

echo Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo Installing dependencies...
npm install

echo Starting development server...
npm run dev
pause
    echo   "dependencies": {>> package.json
    echo     "react": "^18.3.1",>> package.json
    echo     "react-dom": "^18.3.1",>> package.json
    echo     "react-router-dom": "^6.26.1",>> package.json
    echo     "lucide-react": "^0.515.0">> package.json
    echo   },>> package.json
    echo   "devDependencies": {>> package.json
    echo     "@vitejs/plugin-react": "^4.3.1",>> package.json
    echo     "vite": "^5.3.4">> package.json
    echo   }>> package.json
    echo }>> package.json
)

REM Check if Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

REM Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo Installing npm dependencies...
    npm install
    if errorlevel 1 (
        echo Error: Failed to install npm dependencies
        pause
        exit /b 1
    )
)

echo Starting Cyber Threat Hunter Frontend...
npm run dev
pause
