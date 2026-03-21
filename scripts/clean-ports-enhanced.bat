@echo off
REM Port Cleanup Module (Enhanced with Fallback)
setlocal EnableDelayedExpansion

set "PORT1=%~1"
set "PORT2=%~2"
set "FALLBACK=%~3"
if "%PORT1%"=="" set "PORT1=8080"
if "%PORT2%"=="" set "PORT2=3000"
if "%FALLBACK%"=="" set "FALLBACK=0"

echo Cleaning ports %PORT1% and %PORT2%...

taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Proxy*" >nul 2>&1

set "KILLED1=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT1%" ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port %PORT1%
    taskkill /F /PID %%a >nul 2>&1
    powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
    set "KILLED1=1"
)
if "!KILLED1!"=="0" echo   Port %PORT1% already free

set "KILLED2=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT2%" ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port %PORT2%
    taskkill /F /PID %%a >nul 2>&1
    powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
    set "KILLED2=1"
)
if "!KILLED2!"=="0" echo   Port %PORT2% already free

if "!KILLED1!!KILLED2!" NEQ "00" (
    echo   Waiting for ports to release...
    timeout /t 3 /nobreak >nul 2>&1
)

set "RETRY=0"
:port_check_loop
set "OK=1"
netstat -ano | findstr ":%PORT1%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [WARNING] Port %PORT1% still in use
    set "OK=0"
)
netstat -ano | findstr ":%PORT2%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [WARNING] Port %PORT2% still in use
    set "OK=0"
)
if "!OK!"=="0" (
    set /a RETRY+=1
    if !RETRY! LEQ 2 (
        echo   Retrying port cleanup attempt !RETRY!/2
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT1%" ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
        )
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT2%" ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
        )
        timeout /t 3 /nobreak >nul 2>&1
        goto port_check_loop
    )
    if "%FALLBACK%"=="1" (
        echo   [WARNING] Ports busy, switching to alternative ports
        set "ALT1=8083"
        set "ALT2=3002"
        netstat -ano | findstr ":8083" | findstr "LISTENING" >nul 2>&1
        if not errorlevel 1 set "ALT1=8084"
        netstat -ano | findstr ":3002" | findstr "LISTENING" >nul 2>&1
        if not errorlevel 1 set "ALT2=3003"
        echo   Alternative ports: Backend=!ALT1!, Proxy=!ALT2!
        echo !ALT1!> "%TEMP%\dcim_backend_port.txt"
        echo !ALT2!> "%TEMP%\dcim_proxy_port.txt"
        exit /b 2
    )
    echo   [ERROR] Failed to free ports after 3 attempts
    exit /b 1
)
echo   Ports cleaned successfully
exit /b 0
