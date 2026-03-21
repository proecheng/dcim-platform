@echo off
REM ============================================================
REM Port Cleanup Module (Enhanced with Fallback)
REM Clean occupied ports with fallback to alternative ports
REM ============================================================

setlocal EnableDelayedExpansion

set "PORT_8080=%~1"
set "PORT_3000=%~2"
set "FALLBACK_MODE=%~3"

if "%PORT_8080%"=="" set "PORT_8080=8080"
if "%PORT_3000%"=="" set "PORT_3000=3000"
if "%FALLBACK_MODE%"=="" set "FALLBACK_MODE=0"

echo Cleaning ports %PORT_8080% and %PORT_3000%...

REM Kill service processes by window title (not launcher/stopper windows)
taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Proxy*" >nul 2>&1

REM Kill processes on port 8080
set "KILLED_8080=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT_8080%" ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port %PORT_8080%
    taskkill /F /PID %%a >nul 2>&1
    powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
    set "KILLED_8080=1"
)
if "!KILLED_8080!"=="0" echo   Port %PORT_8080% already free

REM Kill processes on port 3000
set "KILLED_3000=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT_3000%" ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port %PORT_3000%
    taskkill /F /PID %%a >nul 2>&1
    powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
    set "KILLED_3000=1"
)
if "!KILLED_3000!"=="0" echo   Port %PORT_3000% already free

REM Wait if we killed any processes
if "!KILLED_8080!!KILLED_3000!" NEQ "00" (
    echo   Waiting for ports to release...
    timeout /t 3 /nobreak >nul 2>&1
)

REM Verify ports are free (with retry)
set "RETRY_COUNT=0"
:port_check_loop
set "PORT_OK=1"

netstat -ano | findstr ":%PORT_8080%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [WARNING] Port %PORT_8080% still in use
    set "PORT_OK=0"
)

netstat -ano | findstr ":%PORT_3000%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [WARNING] Port %PORT_3000% still in use
    set "PORT_OK=0"
)

if "!PORT_OK!"=="0" (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! LEQ 2 (
        echo   Retrying port cleanup (attempt !RETRY_COUNT!/2)...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT_8080%" ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
        )
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT_3000%" ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
        )
        timeout /t 3 /nobreak >nul 2>&1
        goto port_check_loop
    ) else (
        REM Check if fallback mode is enabled
        if "%FALLBACK_MODE%"=="1" (
            echo.
            echo   [WARNING] Failed to free ports after 3 attempts
            echo   Switching to alternative ports...
            echo.
            REM Find available ports
            set "ALT_BACKEND=8083"
            set "ALT_PROXY=3002"

            REM Check if alternative ports are free
            netstat -ano | findstr ":8083" | findstr "LISTENING" >nul 2>&1
            if not errorlevel 1 set "ALT_BACKEND=8084"

            netstat -ano | findstr ":3002" | findstr "LISTENING" >nul 2>&1
            if not errorlevel 1 set "ALT_PROXY=3003"

            echo   Using alternative ports: Backend=!ALT_BACKEND!, Proxy=!ALT_PROXY!
            echo !ALT_BACKEND!> "%TEMP%\dcim_backend_port.txt"
            echo !ALT_PROXY!> "%TEMP%\dcim_proxy_port.txt"
            exit /b 2
        ) else (
            echo.
            echo   [ERROR] Failed to free ports after 3 attempts
            echo.
            echo   This is likely a zombie port issue (Windows TCP/IP stack problem)
            echo.
            echo   Solutions:
            echo   1. Wait 5-10 minutes for Windows to auto-release the port
            echo   2. Restart your computer (most reliable)
            echo   3. Check Task Manager for hidden processes
            echo.
            echo   If you need to start immediately:
            echo   - Run: start-alt-ports.bat (uses ports 8083 and 3002)
            echo.
            exit /b 1
        )
    )
)

echo   Ports cleaned successfully
exit /b 0
