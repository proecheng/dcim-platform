@echo off
REM ============================================================
REM DCIM Smart Launcher v8.1
REM 智能启动脚本 - 自动处理端口冲突
REM ============================================================

setlocal EnableDelayedExpansion

title DCIM Smart Launcher

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                Smart Startup Script v8.1
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM ============================================================
REM Step 1: Environment Check
REM ============================================================
echo [1/6] Checking runtime environment...
call scripts\check-env.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

REM Get Python command from temp file
set /p PYTHON_CMD=<"%TEMP%\dcim_python_cmd.txt"

REM ============================================================
REM Step 2: Smart Port Cleanup (with fallback)
REM ============================================================
echo.
echo [2/6] Cleaning occupied ports (smart mode)...
call scripts\clean-ports-enhanced.bat 8080 3000 1
set "PORT_RESULT=%errorlevel%"

if "%PORT_RESULT%"=="0" (
    echo       Using default ports: 8080, 3000
    set "BACKEND_PORT=8080"
    set "PROXY_PORT=3000"
) else if "%PORT_RESULT%"=="2" (
    echo       Using alternative ports
    set /p BACKEND_PORT=<"%TEMP%\dcim_backend_port.txt"
    set /p PROXY_PORT=<"%TEMP%\dcim_proxy_port.txt"
    echo       Backend: !BACKEND_PORT!, Proxy: !PROXY_PORT!
) else (
    echo       Port cleanup failed
    pause
    exit /b 1
)

REM ============================================================
REM Step 3: Backend Setup
REM ============================================================
echo.
echo [3/6] Setting up backend...
call scripts\setup-backend.bat "%SCRIPT_DIR%" "%PYTHON_CMD%"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM Step 4: Proxy Setup
REM ============================================================
echo.
echo [4/6] Setting up proxy...
call scripts\setup-proxy.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM Step 5: Frontend Setup
REM ============================================================
echo.
echo [5/6] Setting up frontend...
call scripts\setup-frontend.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM Step 6: Start Services (with dynamic ports)
REM ============================================================
echo.
echo [6/6] Starting services...
echo.
echo ========================================================
echo                   Starting Services
echo ========================================================
echo.

set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "PROXY_DIR=%SCRIPT_DIR%proxy"

echo Starting backend service (port !BACKEND_PORT!)...
start "Monitor-Backend" cmd /k "title Backend [Port !BACKEND_PORT!] && cd /d %BACKEND_DIR% && echo Starting backend... && "%PYTHON_CMD%" -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT!"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul 2>&1

REM Create dynamic proxy config if using alternative ports
if not "!PROXY_PORT!"=="3000" (
    echo Creating dynamic proxy configuration...
    call :create_proxy_config !BACKEND_PORT! !PROXY_PORT!
    set "PROXY_SCRIPT=server-dynamic.js"
) else (
    set "PROXY_SCRIPT=server.js"
)

echo Starting proxy service (port !PROXY_PORT!)...
start "Monitor-Proxy" cmd /k "title Proxy [Port !PROXY_PORT!] && cd /d %PROXY_DIR% && echo Starting proxy... && node !PROXY_SCRIPT!"

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

REM ============================================================
REM Success Message
REM ============================================================
echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Local Access:    http://localhost:!PROXY_PORT!
echo   API Docs:        http://localhost:!BACKEND_PORT!/docs
echo.
echo   Default Account: admin / admin123
echo.
echo ========================================================
echo.

echo Opening browser...
start "" "http://localhost:!PROXY_PORT!"

echo.
echo Press any key to close this launcher window...
echo (Service windows will keep running)
pause >nul

REM Cleanup temp files
del "%TEMP%\dcim_python_cmd.txt" >nul 2>&1
del "%TEMP%\dcim_backend_port.txt" >nul 2>&1
del "%TEMP%\dcim_proxy_port.txt" >nul 2>&1

exit /b 0

REM ============================================================
REM Subroutine: Create Dynamic Proxy Config
REM ============================================================
:create_proxy_config
set "BE_PORT=%~1"
set "PR_PORT=%~2"

(
echo const express = require('express'^);
echo const { createProxyMiddleware } = require('http-proxy-middleware'^);
echo const httpProxy = require('http-proxy'^);
echo const cors = require('cors'^);
echo const path = require('path'^);
echo.
echo const app = express(^);
echo const PORT = %PR_PORT%;
echo const BACKEND_PORT = %BE_PORT%;
echo const BACKEND_URL = 'http://localhost:' + BACKEND_PORT;
echo const BACKEND_WS_URL = 'ws://localhost:' + BACKEND_PORT;
echo.
echo app.use(cors({ origin: '*', credentials: true }^)^);
echo app.use((req, res, next^) =^> { console.log('[' + new Date(^).toISOString(^) + '] ' + req.method + ' ' + req.url^); next(^); }^);
echo app.get('/health', (req, res^) =^> { res.json({ status: 'ok', timestamp: new Date(^).toISOString(^) }^); }^);
echo app.use('/api', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true, onError: (err, req, res^) =^> { console.error('Proxy error: ' + err.message^); if (res ^&^& typeof res.status === 'function'^) { res.status(502^).json({ error: 'Backend service unavailable' }^); } else if (res ^&^& typeof res.end === 'function'^) { res.end(^); } } }^)^);
echo app.use('/docs', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true }^)^);
echo app.use('/openapi.json', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true }^)^);
echo const frontendDist = path.join(__dirname, '..', 'frontend', 'dist'^);
echo app.use(express.static(frontendDist^)^);
echo app.get('*', (req, res^) =^> { res.sendFile(path.join(frontendDist, 'index.html'^)^); }^);
echo const server = app.listen(PORT, '0.0.0.0', (^) =^> { console.log('========================================'^); console.log('   DCIM Proxy Server Started (Dynamic Ports^)'^); console.log('========================================'^); console.log('   Local:    http://localhost:' + PORT^); console.log('   Backend:  http://localhost:' + BACKEND_PORT^); console.log('========================================'^); }^);
echo const wsProxy = httpProxy.createProxyServer({ target: BACKEND_WS_URL, ws: true, changeOrigin: true }^);
echo wsProxy.on('error', (err, req, res^) =^> { console.error('WebSocket proxy error:', err.message^); }^);
echo server.on('upgrade', (req, socket, head^) =^> { if (req.url.startsWith('/ws'^)^) { console.log('[WS] Upgrading:', req.url^); wsProxy.ws(req, socket, head^); } }^);
) > "%PROXY_DIR%\server-dynamic.js"

exit /b 0
