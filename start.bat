@echo off
setlocal EnableDelayedExpansion

title DCIM System Launcher

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Startup Script v5.3
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/7] Checking runtime environment...

REM Check for Python in virtual environment first
set "PYTHON_CMD="
if exist "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"
    echo       Found Python in virtual environment
) else (
    REM Try common Python locations
    where python.exe >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=*" %%i in ('where python.exe 2^>nul ^| findstr /v WindowsApps') do (
            if "!PYTHON_CMD!"=="" set "PYTHON_CMD=%%i"
        )
    )
    if "!PYTHON_CMD!"=="" (
        if exist "C:\Python311\python.exe" set "PYTHON_CMD=C:\Python311\python.exe"
        if exist "C:\Python310\python.exe" set "PYTHON_CMD=C:\Python310\python.exe"
        if exist "C:\Python39\python.exe" set "PYTHON_CMD=C:\Python39\python.exe"
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    )
)

if "!PYTHON_CMD!"=="" (
    echo [ERROR] Python not found. Please install Python 3.9+
    echo         Make sure Python is added to PATH
    echo.
    pause
    exit /b 1
)

echo       Using: !PYTHON_CMD!
for /f "tokens=*" %%i in ('"!PYTHON_CMD!" --version 2^>^&1') do echo       %%i

REM Check Node.js
where node.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo       Node.js %%i

echo.
echo [2/7] Cleaning occupied ports...

REM Kill processes by window title first
taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1

REM Kill processes on port 8080
echo       Cleaning port 8080...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo       Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill processes on port 3000
echo       Cleaning port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo       Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo       Waiting for ports to release...
timeout /t 3 /nobreak >nul

REM Verify ports are free
set "PORT_OK=1"
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 8080 still in use!
    set "PORT_OK=0"
)
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 3000 still in use!
    set "PORT_OK=0"
)

if "!PORT_OK!"=="0" (
    echo.
    echo       Retrying port cleanup...
    timeout /t 2 /nobreak >nul
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo       Ports cleaned

echo.
echo [3/7] Checking backend environment...
cd /d "%SCRIPT_DIR%backend"

echo       Checking dependencies...
"!PYTHON_CMD!" -c "import uvicorn, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo       Installing backend dependencies...
    "!PYTHON_CMD!" -m pip install -r requirements.txt -q
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
    "!PYTHON_CMD!" -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())" 2>nul
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
start "Monitor-Backend" cmd /k "title Backend [Port 8080] && cd /d %BACKEND_DIR% && echo Starting backend... && "%PYTHON_CMD%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul

echo Starting proxy service (port 3000)...
start "Monitor-Proxy" cmd /k "title Proxy [Port 3000] && cd /d %PROXY_DIR% && echo Starting proxy... && node server.js"

echo.
timeout /t 5 /nobreak >nul

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Local Access:    http://localhost:3000
echo   API Docs:        http://localhost:8080/docs
echo.
echo   Default Account: admin / admin123
echo.
echo ========================================================
echo.

echo Opening browser...
start "" "http://localhost:3000"

echo.
echo Press any key to close this launcher window...
echo (Service windows will keep running)
pause >nul
