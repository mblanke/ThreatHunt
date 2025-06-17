@echo off
title Cyber Threat Hunter - Backend
cd /d "%~dp0\backend"
call venv\Scripts\activate.bat
python app.py
pause
