@echo off
setlocal EnableDelayedExpansion

echo Testing port cleanup logic...
echo.

REM Kill processes on port 8080
set "KILLED_8080=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo Killing PID %%a on port 8080
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED_8080=1"
)
if "!KILLED_8080!"=="0" echo Port 8080 already free

REM Kill processes on port 3000
set "KILLED_3000=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo Killing PID %%a on port 3000
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED_3000=1"
)
if "!KILLED_3000!"=="0" echo Port 3000 already free

REM Wait longer if we killed any processes
if "!KILLED_8080!!KILLED_3000!" NEQ "00" (
    echo Waiting for ports to release...
    timeout /t 3 /nobreak >nul 2>&1
)

REM Verify ports are free (with retry)
set "RETRY_COUNT=0"
:port_check_loop
set "PORT_OK=1"

netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8080 still in use
    set "PORT_OK=0"
)

netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 3000 still in use
    set "PORT_OK=0"
)

if "!PORT_OK!"=="0" (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! LEQ 2 (
        echo Retrying port cleanup (attempt !RETRY_COUNT!/2)...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
        timeout /t 3 /nobreak >nul 2>&1
        goto port_check_loop
    ) else (
        echo.
        echo [ERROR] Failed to free ports after 3 attempts
        echo Please run stop.bat first, then try again
        echo.
        exit /b 1
    )
)

echo Ports cleaned successfully
echo.
echo Test completed!
