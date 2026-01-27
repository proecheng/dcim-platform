@echo off
chcp 65001 >nul 2>&1

title DCIM Backend - Restart
color 0B

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              DCIM 后端服务 - 重启脚本                        ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo [1/2] 停止现有后端进程...

:: Kill processes on port 8080
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080.*LISTENING"') do (
    echo       终止进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul
echo       进程已清理 ✓

echo.
echo [2/2] 启动后端服务...

cd /d D:\mytest1\backend

:: Check virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo.
echo 后端服务启动中 (端口 8080)...
echo 按 Ctrl+C 可停止服务
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
