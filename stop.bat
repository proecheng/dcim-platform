@echo off
setlocal EnableDelayedExpansion

title DCIM System Stopper

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Stop Script v2.0
echo ========================================================
echo.

echo [1/3] Stopping service windows...

taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
if not errorlevel 1 echo       Backend window closed
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
if not errorlevel 1 echo       Proxy window closed
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM*" >nul 2>&1

echo.
echo [2/3] Cleaning ports...

set "KILLED_8080=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo       Killing PID %%a on port 8080
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED_8080=1"
)
if "!KILLED_8080!"=="0" echo       Port 8080 already free

set "KILLED_3000=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo       Killing PID %%a on port 3000
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED_3000=1"
)
if "!KILLED_3000!"=="0" echo       Port 3000 already free

echo.
echo [3/3] Verifying...
timeout /t 2 /nobreak >nul

set "ALL_CLEAR=1"
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 8080 still in use, retrying...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    set "ALL_CLEAR=0"
)
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 3000 still in use, retrying...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    set "ALL_CLEAR=0"
)

if "!ALL_CLEAR!"=="0" (
    timeout /t 2 /nobreak >nul
)

echo.
echo ========================================================
echo              All Services Stopped
echo ========================================================
echo.

pause
