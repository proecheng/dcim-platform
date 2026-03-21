@echo off
REM ============================================================
REM DCIM Quick Start (Skip Port Check)
REM Quick start script - use alternative ports, skip port cleanup
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

REM Create temporary proxy config for port 3002
echo const express = require('express'); > proxy\server-alt.js
echo const { createProxyMiddleware } = require('http-proxy-middleware'); >> proxy\server-alt.js
echo const httpProxy = require('http-proxy'); >> proxy\server-alt.js
echo const cors = require('cors'); >> proxy\server-alt.js
echo const path = require('path'); >> proxy\server-alt.js
echo. >> proxy\server-alt.js
echo const app = express(); >> proxy\server-alt.js
echo const PORT = 3002; >> proxy\server-alt.js
echo const BACKEND_PORT = 8083; >> proxy\server-alt.js
echo const BACKEND_URL = 'http://localhost:' + BACKEND_PORT; >> proxy\server-alt.js
echo const BACKEND_WS_URL = 'ws://localhost:' + BACKEND_PORT; >> proxy\server-alt.js
echo. >> proxy\server-alt.js
echo app.use(cors({ origin: '*', credentials: true })); >> proxy\server-alt.js
echo app.use((req, res, next) =^> { console.log('[' + new Date().toISOString() + '] ' + req.method + ' ' + req.url); next(); }); >> proxy\server-alt.js
echo app.get('/health', (req, res) =^> { res.json({ status: 'ok', timestamp: new Date().toISOString() }); }); >> proxy\server-alt.js
echo app.use('/api', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true, onError: (err, req, res) =^> { console.error('Proxy error: ' + err.message); if (res ^&^& typeof res.status === 'function') { res.status(502).json({ error: 'Backend service unavailable' }); } else if (res ^&^& typeof res.end === 'function') { res.end(); } } })); >> proxy\server-alt.js
echo app.use('/docs', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true })); >> proxy\server-alt.js
echo app.use('/openapi.json', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true })); >> proxy\server-alt.js
echo const frontendDist = path.join(__dirname, '..', 'frontend', 'dist'); >> proxy\server-alt.js
echo app.use(express.static(frontendDist)); >> proxy\server-alt.js
echo app.get('*', (req, res) =^> { res.sendFile(path.join(frontendDist, 'index.html')); }); >> proxy\server-alt.js
echo const server = app.listen(PORT, '0.0.0.0', () =^> { console.log('========================================'); console.log('   DCIM Proxy Server Started (Alt Ports)'); console.log('========================================'); console.log('   Local:    http://localhost:' + PORT); console.log('   Backend:  http://localhost:' + BACKEND_PORT); console.log('========================================'); }); >> proxy\server-alt.js
echo const wsProxy = httpProxy.createProxyServer({ target: BACKEND_WS_URL, ws: true, changeOrigin: true }); >> proxy\server-alt.js
echo wsProxy.on('error', (err, req, res) =^> { console.error('WebSocket proxy error:', err.message); }); >> proxy\server-alt.js
echo server.on('upgrade', (req, socket, head) =^> { if (req.url.startsWith('/ws')) { console.log('[WS] Upgrading:', req.url); wsProxy.ws(req, socket, head); } }); >> proxy\server-alt.js

start "DCIM-Proxy-3002" cmd /k "title Proxy [Port 3002] && cd /d %SCRIPT_DIR%proxy && echo Starting proxy on port 3002... && node server-alt.js"

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
