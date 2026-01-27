@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title DCIM System Launcher

echo.
echo ========================================================
echo           DCIM Data Center Management System
echo                 Startup Script v2.4
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/6] Checking environment...

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.9+
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       %%i

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found, please install Node.js
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo       %%i

echo.
echo [2/6] Cleaning up ports...

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo       Stopping process on port 3000 [PID: %%a]
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080.*LISTENING"') do (
    echo       Stopping process on port 8080 [PID: %%a]
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul
echo       Ports cleaned

echo.
echo [3/6] Checking backend...
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
        echo [ERROR] Failed to install backend dependencies
        pause
        exit /b 1
    )
)
echo       Backend dependencies OK

echo.
echo [4/6] Checking database...
if not exist "dcim.db" (
    echo       Initializing database...
    python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())" 2>nul
    echo       Database initialized
) else (
    echo       Database exists
)

echo.
echo [5/6] Checking proxy...
cd /d "%SCRIPT_DIR%proxy"

if not exist "node_modules" (
    echo       Installing proxy dependencies...
    npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install proxy dependencies
        pause
        exit /b 1
    )
)
echo       Proxy dependencies OK

echo.
echo [6/6] Checking frontend...
cd /d "%SCRIPT_DIR%frontend"
if not exist "dist\index.html" (
    echo       [WARNING] Frontend not built
    echo       Run: cd frontend ^&^& npm run build
) else (
    echo       Frontend build OK
)

echo.
echo ========================================================
echo                  Starting Services
echo ========================================================
echo.

set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "PROXY_DIR=%SCRIPT_DIR%proxy"

echo Starting backend on port 8080...

if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    start "DCIM-Backend" cmd /k "title DCIM Backend [Port 8080] & cd /d "%BACKEND_DIR%" & call .venv\Scripts\activate.bat & echo Starting backend... & python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"
) else (
    start "DCIM-Backend" cmd /k "title DCIM Backend [Port 8080] & cd /d "%BACKEND_DIR%" & echo Starting backend... & python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"
)

echo Waiting for backend startup...
timeout /t 3 /nobreak >nul

echo Starting proxy on port 3000...
start "DCIM-Proxy" cmd /k "title DCIM Proxy [Port 3000] & cd /d "%PROXY_DIR%" & echo Starting proxy... & node server.js"

echo.
timeout /t 5 /nobreak >nul

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Local Access:     http://localhost:3000
echo   External Access:  http://powerlab.cn:3000
echo   API Docs:         http://localhost:8080/docs
echo.
echo   Account: admin / admin123
echo.
echo ========================================================
echo.
echo   TWO windows will be running:
echo   1. "DCIM Backend [Port 8080]"  - FastAPI backend
echo   2. "DCIM Proxy [Port 3000]"    - Reverse proxy
echo.
echo   Port 3000 forwards requests to port 8080
echo   Only port 3000 needs router forwarding
echo.
echo ========================================================
echo.

echo Opening browser...
start "" "http://localhost:3000"

echo.
echo Press any key to close this launcher window...
echo (The service windows will keep running)
pause >nul
