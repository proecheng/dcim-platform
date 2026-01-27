@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title DCIM System Launcher (Proxy Mode)

echo.
echo ========================================================
echo           DCIM Data Center Management System
echo              Startup Script v2.1 (Proxy Mode)
echo ========================================================
echo.
echo This mode uses a unified proxy server for external access.
echo Only ONE port needs to be forwarded in router.
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/6] Checking environment...

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)
echo       Python OK

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found
    pause
    exit /b 1
)
echo       Node.js OK

echo.
echo [2/6] Cleaning up ports...

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080.*LISTENING"') do (
    echo       Killing process on port 8080: %%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":80[^0-9].*LISTENING"') do (
    echo       Killing process on port 80: %%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo       Killing process on port 3000: %%a
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul
echo       Ports cleaned

echo.
echo [3/6] Checking backend dependencies...
cd /d "%SCRIPT_DIR%backend"

if exist ".venv\Scripts\activate.bat" (
    echo       Using virtual environment
    call .venv\Scripts\activate.bat
) else (
    echo       Using global Python
)

python -c "import uvicorn, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo       Installing backend dependencies...
    pip install -r requirements.txt -q
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
echo [5/6] Checking frontend build...
cd /d "%SCRIPT_DIR%frontend"
if not exist "dist\index.html" (
    echo       Building frontend (this may take a while)...
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed
        pause
        exit /b 1
    )
)
echo       Frontend build OK

echo.
echo [6/6] Starting services...

:: Start backend (internal only, port 8080)
echo.
echo       Starting backend (internal port 8080)...
cd /d "%SCRIPT_DIR%backend"

if exist ".venv\Scripts\activate.bat" (
    start "DCIM-Backend" cmd /k "cd /d %SCRIPT_DIR%backend && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 127.0.0.1 --port 8080"
) else (
    start "DCIM-Backend" cmd /k "cd /d %SCRIPT_DIR%backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8080"
)

echo       Waiting for backend...
timeout /t 5 /nobreak >nul

:: Start proxy server (external, port 80)
echo.
echo       Starting proxy server (port 80)...
cd /d "%SCRIPT_DIR%proxy"
start "DCIM-Proxy" cmd /k "cd /d %SCRIPT_DIR%proxy && node proxy.js"

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   External Access: http://powerlab.cn
echo   Local Access:    http://localhost
echo   API Docs:        http://localhost/docs
echo.
echo   Account: admin / admin123
echo.
echo ========================================================
echo.
echo   IMPORTANT: Only port 80 needs to be forwarded
echo   in your router to enable external access.
echo.
echo ========================================================

timeout /t 3 /nobreak >nul
echo Opening browser...
start http://localhost

echo.
echo Press any key to close this window...
pause >nul
