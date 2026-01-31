@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title Computing Center Intelligent Monitoring System Launcher

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Startup Script v5.0
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/7] Checking runtime environment...

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       %%i

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo       Node.js %%i

echo.
echo [2/7] Cleaning occupied ports...

REM Use PowerShell to reliably kill processes on ports
echo       Checking port 3000...
powershell -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { $p = $_.OwningProcess; if ($p -gt 0) { Write-Host '       Stopping PID:' $p; Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }" 2>nul

echo       Checking port 8080...
powershell -Command "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { $p = $_.OwningProcess; if ($p -gt 0) { Write-Host '       Stopping PID:' $p; Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }" 2>nul

REM Fallback: kill all node processes with specific window titles
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1

echo       Waiting for ports to release...
ping 127.0.0.1 -n 5 >nul

REM Verify ports are free
powershell -Command "$p3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue; $p8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue; if ($p3000 -or $p8080) { Write-Host '       [WARNING] Some ports still in use, retrying...'; Start-Sleep -Seconds 3 }" 2>nul

echo       Ports cleaned

echo.
echo [3/7] Checking backend environment...
cd /d "%SCRIPT_DIR%backend"

if exist ".venv\Scripts\activate.bat" (
    echo       Using virtual environment
    call .venv\Scripts\activate.bat
) else (
    echo       Using global Python
)

echo       Checking dependencies...
python -c "import uvicorn, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo       Installing backend dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Backend dependency installation failed
        pause
        exit /b 1
    )
)
echo       Backend dependencies OK

echo.
echo [4/7] Checking database...
if not exist "dcim.db" (
    echo       Initializing database...
    python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())" 2>nul
    echo       Database initialized
) else (
    echo       Database exists
)

echo.
echo [5/7] Checking proxy service...
cd /d "%SCRIPT_DIR%proxy"

if not exist "node_modules" (
    echo       Installing proxy dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Proxy dependency installation failed
        pause
        exit /b 1
    )
)
echo       Proxy dependencies OK

echo.
echo [6/7] Checking frontend environment...
cd /d "%SCRIPT_DIR%frontend"

if not exist "node_modules" (
    echo       Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Frontend dependency installation failed
        pause
        exit /b 1
    )
)
echo       Frontend dependencies OK

echo.
echo [7/7] Checking frontend build...
if not exist "dist\index.html" (
    echo       Frontend not built, building now...
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed
        pause
        exit /b 1
    )
    echo       Frontend build complete
) else (
    echo       Frontend build OK
)

echo.
echo ========================================================
echo                   Starting Services
echo ========================================================
echo.

set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "PROXY_DIR=%SCRIPT_DIR%proxy"

echo Starting backend service (port 8080)...

if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    start "Monitor-Backend" cmd /k "title Backend [Port 8080] && cd /d %BACKEND_DIR% && call .venv\Scripts\activate.bat && echo Starting backend... && python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"
) else (
    start "Monitor-Backend" cmd /k "title Backend [Port 8080] && cd /d %BACKEND_DIR% && echo Starting backend... && python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"
)

echo Waiting for backend to start...
ping 127.0.0.1 -n 6 >nul

echo Starting proxy service (port 3000)...
start "Monitor-Proxy" cmd /k "title Proxy [Port 3000] && cd /d %PROXY_DIR% && echo Starting proxy... && node server.js"

echo.
ping 127.0.0.1 -n 6 >nul

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Local Access:    http://localhost:3000
echo   Remote Access:   http://powerlab.cn:3000
echo   API Docs:        http://localhost:8080/docs
echo.
echo   Default Account: admin / admin123
echo.
echo ========================================================
echo.
echo   Running service windows:
echo   1. "Backend [Port 8080]"  - FastAPI backend service
echo   2. "Proxy [Port 3000]"    - Reverse proxy service
echo.
echo   Architecture:
echo   - Proxy (3000) serves frontend static files
echo   - Proxy (3000) forwards /api requests to backend (8080)
echo   - Router only needs to forward port 3000
echo.
echo ========================================================
echo.

echo Opening browser...
start "" "http://localhost:3000"

echo.
echo Press any key to close this launcher window...
echo (Service windows will keep running)
pause >nul
