@echo off
REM ============================================================
REM DCIM Quick Start (Alternative Ports)
REM Use alternative ports 8083/3002 to avoid conflicts
REM ============================================================

setlocal EnableDelayedExpansion

title DCIM Quick Start (Alternative Ports)

echo.
echo ========================================================
echo       DCIM Quick Start (Using Alternative Ports)
echo       Backend: 8083, Proxy: 3002
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Find Python
set "PYTHON_CMD=backend\.venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=python"

echo [1/2] Starting backend on port 8083...
start "DCIM-Backend-8083" cmd /k "title Backend [Port 8083] && cd /d %SCRIPT_DIR%backend && echo Starting backend on port 8083... && "%PYTHON_CMD%" -m uvicorn app.main:app --host 0.0.0.0 --port 8083"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul 2>&1

echo.
echo [2/2] Starting proxy on port 3002...
start "DCIM-Proxy-3002" cmd /k "title Proxy [Port 3002] && cd /d %SCRIPT_DIR%proxy && set PROXY_PORT=3002 && set BACKEND_PORT=8083 && echo Starting proxy on port 3002... && node server.js"

echo.
timeout /t 5 /nobreak >nul 2>&1

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Access: http://localhost:3002
echo   Backend: http://localhost:8083
echo.
echo   Note: Using alternative ports to avoid conflicts
echo ========================================================
echo.

start "" "http://localhost:3002"

echo Press any key to close this window...
pause >nul

exit /b 0
