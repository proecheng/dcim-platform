@echo off
REM ============================================================
REM Proxy Setup Module
REM 准备代理服务环境
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."

cd /d "%SCRIPT_DIR%\proxy"

echo Checking proxy service...

REM Check dependencies
if not exist "node_modules" (
    echo   Installing proxy dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Proxy dependency installation failed
        exit /b 1
    )
)
echo   Proxy dependencies OK

exit /b 0
