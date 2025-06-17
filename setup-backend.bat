@echo off
title Setup Backend
echo Setting up Cyber Threat Hunter Backend...

cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Make sure Python is installed
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Flask and dependencies...
pip install flask==3.0.0
pip install flask-cors==4.0.0
pip install python-dotenv==1.0.0
pip install requests==2.31.0
pip install werkzeug==3.0.1

echo Backend setup complete!
pause
