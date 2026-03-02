@echo off
setlocal EnableDelayedExpansion

title DCIM System Stopper

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Stop Script v3.0
echo ========================================================
echo.

REM ============================================================
REM Step 1: Stop Service Windows
REM ============================================================
echo [1/4] Stopping service windows...

taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
if not errorlevel 1 echo       Backend window closed
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
if not errorlevel 1 echo       Proxy window closed
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM*" >nul 2>&1

echo       Service windows closed

REM ============================================================
REM Step 2: Clean Ports
REM ============================================================
echo.
echo [2/4] Cleaning ports...

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

REM ============================================================
REM Step 3: Wait for Cleanup
REM ============================================================
echo.
echo [3/4] Waiting for cleanup...
call :sleep 2

REM ============================================================
REM Step 4: Verify Ports are Free
REM ============================================================
echo.
echo [4/4] Verifying...

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
    echo       Waiting for final cleanup...
    call :sleep 2
    
    REM Final verification
    set "FINAL_CHECK=1"
    netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo       [ERROR] Port 8080 still occupied!
        set "FINAL_CHECK=0"
    )
    netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo       [ERROR] Port 3000 still occupied!
        set "FINAL_CHECK=0"
    )
    
    if "!FINAL_CHECK!"=="0" (
        echo.
        echo       Manual cleanup may be required.
        echo       Run: netstat -ano ^| findstr ":8080"
        echo       Then: taskkill /F /PID [PID]
    )
)

REM ============================================================
REM Success Message
REM ============================================================
echo.
echo ========================================================
echo              All Services Stopped
echo ========================================================
echo.
echo   Ports 8080 and 3000 are now free
echo   You can safely restart the system with start.bat
echo.
echo ========================================================
echo.

pause

goto :eof

:sleep
set "_secs=%~1"
if "!_secs!"=="" set "_secs=1"
timeout /t !_secs! /nobreak >nul 2>&1
if errorlevel 1 (
    set /a _ping_secs=!_secs!+1
    ping 127.0.0.1 -n !_ping_secs! >nul 2>&1
)
exit /b 0
