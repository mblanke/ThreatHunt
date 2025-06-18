@echo off
echo Starting Cyber Threat Hunter with Docker...

docker-compose down
docker-compose build
docker-compose up -d

echo.
echo ========================================
echo  Cyber Threat Hunter is starting...
echo  Frontend: http://localhost:3000
echo  Backend API: http://localhost:5000
echo  Database: PostgreSQL on port 5432
echo ========================================
echo.
echo Default credentials:
echo Username: admin
echo Password: admin123
echo.
pause
