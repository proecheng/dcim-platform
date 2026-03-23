@echo off
REM ============================================================
REM Start Services Module
REM Start backend and proxy services
REM Usage: start-services.bat [script_dir] [python_cmd] [backend_port] [proxy_port]
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
set "PYTHON_CMD=%~2"
set "BACKEND_PORT=%~3"
set "PROXY_PORT=%~4"

if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."
if "%PYTHON_CMD%"=="" (
    if exist "%TEMP%\dcim_python_cmd.txt" (
        set /p PYTHON_CMD=<"%TEMP%\dcim_python_cmd.txt"
    ) else (
        set "PYTHON_CMD=python"
    )
)
if "!BACKEND_PORT!"=="" set "BACKEND_PORT=8080"
if "!PROXY_PORT!"=="" set "PROXY_PORT=3000"

set "BACKEND_DIR=%SCRIPT_DIR%\backend"
set "PROXY_DIR=%SCRIPT_DIR%\proxy"

echo Starting services...
echo.

echo Starting backend service (port !BACKEND_PORT!)...
start "Monitor-Backend" cmd /k "title Backend [Port !BACKEND_PORT!] && cd /d %BACKEND_DIR% && echo Starting backend... && "%PYTHON_CMD%" -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT!"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul 2>&1

echo Starting proxy service (port !PROXY_PORT!)...
start "Monitor-Proxy" cmd /k "title Proxy [Port !PROXY_PORT!] && cd /d %PROXY_DIR% && set PROXY_PORT=!PROXY_PORT! && set BACKEND_PORT=!BACKEND_PORT! && echo Starting proxy... && node server.js"

echo.
timeout /t 5 /nobreak >nul 2>&1

REM Verify services
echo Verifying services...

curl -s http://localhost:!BACKEND_PORT!/docs >nul 2>&1
if errorlevel 1 (
    echo   [WARNING] Backend may not be ready yet
) else (
    echo   Backend: OK
)

curl -s http://localhost:!PROXY_PORT! >nul 2>&1
if errorlevel 1 (
    echo   [WARNING] Proxy may not be ready yet
) else (
    echo   Proxy: OK
)

exit /b 0
