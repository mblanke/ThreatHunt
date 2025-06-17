@echo off
echo Quick Start - Velo Threat Hunter

cd backend
call venv\Scripts\activate
pip install flask flask-cors python-dotenv requests werkzeug
start "Backend" cmd /k "python app.py"
cd ..

timeout /t 3 /nobreak >nul

cd frontend
if exist package.json (
    start "Frontend" cmd /k "npm run dev"
) else (
    echo Frontend not configured yet
)
cd ..

echo.
echo Servers starting...
pause
