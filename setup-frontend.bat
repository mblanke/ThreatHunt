@echo off
title Setup Frontend
echo Setting up Cyber Threat Hunter Frontend...

cd frontend

REM Clean up corrupted files
if exist "package-lock.json" del /f "package-lock.json"
if exist "node_modules" rmdir /s /q "node_modules" 2>nul

echo Creating clean package.json...
(
echo {
echo   "name": "cyber-threat-hunter",
echo   "private": true,
echo   "version": "1.0.0",
echo   "type": "module",
echo   "scripts": {
echo     "dev": "vite",
echo     "build": "vite build",
echo     "preview": "vite preview"
echo   },
echo   "dependencies": {
echo     "react": "^18.3.1",
echo     "react-dom": "^18.3.1",
echo     "react-router-dom": "^6.26.1",
echo     "lucide-react": "^0.515.0"
echo   },
echo   "devDependencies": {
echo     "@vitejs/plugin-react": "^4.3.1",
echo     "vite": "^5.3.4"
echo   }
echo }
) > package.json

echo Installing npm dependencies...
npm cache clean --force
npm install

echo Frontend setup complete!
pause
