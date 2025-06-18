@echo off
echo Setting up production environment...

REM Create environment file
echo Creating .env.prod file...
(
echo DB_USER=threat_hunter_user
echo DB_PASSWORD=%RANDOM%%RANDOM%
echo SECRET_KEY=%RANDOM%%RANDOM%%RANDOM%
echo FLASK_ENV=production
) > .env.prod

REM Setup SSL certificates
echo Setting up SSL certificates...
mkdir ssl
REM Add your SSL certificate generation here

REM Create backup directory
mkdir backups
mkdir logs

REM Setup firewall rules
echo Configuring firewall...
netsh advfirewall firewall add rule name="HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="HTTPS" dir=in action=allow protocol=TCP localport=443

echo Production setup complete!
echo Please update .env.prod with your actual values
pause
