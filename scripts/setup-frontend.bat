@echo off
REM ============================================================
REM Frontend Setup Module
REM 准备前端环境和构建
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."

cd /d "%SCRIPT_DIR%\frontend"

echo Checking frontend environment...

REM Check dependencies
if not exist "node_modules" (
    echo   Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Frontend dependency installation failed
        exit /b 1
    )
)
echo   Frontend dependencies OK

REM Check build
echo Checking frontend build...
if not exist "dist\index.html" (
    echo   Frontend not built, building now...
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed
        exit /b 1
    )
    echo   Frontend build complete
) else (
    echo   Frontend build OK
)

exit /b 0
