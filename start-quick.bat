@echo off
REM ============================================================
REM DCIM Quick Start (No Environment Check)
REM 快速启动脚本 - 跳过环境检查和依赖安装
REM ============================================================

setlocal EnableDelayedExpansion

title DCIM Quick Start

echo.
echo ========================================================
echo       DCIM Quick Start (No Environment Check)
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM ============================================================
REM Step 1: Clean Ports
REM ============================================================
echo [1/2] Cleaning ports...
call scripts\clean-ports.bat 8080 3000
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM Step 2: Start Services
REM ============================================================
echo.
echo [2/2] Starting services...

REM Find Python
set "PYTHON_CMD=backend\.venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=python"

call scripts\start-services.bat "%SCRIPT_DIR%" "%PYTHON_CMD%"

echo.
echo ========================================================
echo                  Services Started!
echo ========================================================
echo.
echo   Access: http://localhost:3000
echo.
echo ========================================================
echo.

start "" "http://localhost:3000"

echo Press any key to close this window...
pause >nul

exit /b 0
