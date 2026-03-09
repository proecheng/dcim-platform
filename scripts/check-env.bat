@echo off
REM ============================================================
REM Environment Check Module
REM 检查 Python 和 Node.js 环境
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."

echo Checking runtime environment...

REM Check for Python in virtual environment first
set "PYTHON_CMD="
if exist "%SCRIPT_DIR%\backend\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%\backend\.venv\Scripts\python.exe"
    echo   Found Python in virtual environment
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
    exit /b 1
)

echo   Using: !PYTHON_CMD!
for /f "tokens=*" %%i in ('"!PYTHON_CMD!" --version 2^>^&1') do echo   %%i

REM Check Node.js
where node.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   Node.js %%i

REM Export PYTHON_CMD for parent script
echo !PYTHON_CMD!> "%TEMP%\dcim_python_cmd.txt"

exit /b 0
