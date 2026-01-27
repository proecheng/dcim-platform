@echo off
chcp 65001 >nul 2>&1

title DCIM System - Stop Service

echo.
echo ========================================================
echo           DCIM System - Stop Services
echo ========================================================
echo.

echo Stopping services on ports 3000 and 8080...

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo       Killing process on port 3000 [PID: %%a]
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080.*LISTENING"') do (
    echo       Killing process on port 8080 [PID: %%a]
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo Closing service windows...
taskkill /FI "WINDOWTITLE eq DCIM*" /F >nul 2>&1

echo.
echo ========================================================
echo              Services stopped!
echo ========================================================
echo.
echo Press any key to close...
pause >nul
