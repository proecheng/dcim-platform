@echo off
REM ============================================================
REM Start Services Module
REM Start backend and proxy services
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
set "PYTHON_CMD=%~2"

if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."
if "%PYTHON_CMD%"=="" (
    if exist "%TEMP%\dcim_python_cmd.txt" (
        set /p PYTHON_CMD=<"%TEMP%\dcim_python_cmd.txt"
    ) else (
        set "PYTHON_CMD=python"
    )
)

set "BACKEND_DIR=%SCRIPT_DIR%\backend"
set "PROXY_DIR=%SCRIPT_DIR%\proxy"

echo Starting services...
echo.

echo Starting backend service (port 8080)...
start "Monitor-Backend" cmd /k "title Backend [Port 8080] && cd /d %BACKEND_DIR% && echo Starting backend... && "%PYTHON_CMD%" -m uvicorn app.main:app --host 0.0.0.0 --port 8080"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul 2>&1

echo Starting proxy service (port 3000)...
start "Monitor-Proxy" cmd /k "title Proxy [Port 3000] && cd /d %PROXY_DIR% && echo Starting proxy... && node server.js"

echo.
timeout /t 5 /nobreak >nul 2>&1

REM Verify services
echo Verifying services...

curl -s http://localhost:8080/docs >nul 2>&1
if errorlevel 1 (
    echo   [WARNING] Backend may not be ready yet
) else (
    echo   Backend: OK
)

curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo   [WARNING] Proxy may not be ready yet
) else (
    echo   Proxy: OK
)

exit /b 0
