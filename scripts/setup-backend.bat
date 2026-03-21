@echo off
REM ============================================================
REM Backend Setup Module
REM Setup backend environment and database
REM ============================================================

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~1"
set "PYTHON_CMD=%~2"

if "%SCRIPT_DIR%"=="" set "SCRIPT_DIR=%~dp0.."
if "%PYTHON_CMD%"=="" (
    if exist "%TEMP%\dcim_python_cmd.txt" (
        set /p PYTHON_CMD=<"%TEMP%\dcim_python_cmd.txt"
    ) else (
        set "PYTHON_CMD=python"
    )
)

cd /d "%SCRIPT_DIR%\backend"

echo Checking backend environment...

REM Check dependencies
echo   Checking dependencies...
"%PYTHON_CMD%" -c "import uvicorn, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo   Installing backend dependencies...
    "%PYTHON_CMD%" -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Backend dependency installation failed
        exit /b 1
    )
)
echo   Backend dependencies OK

REM Check database
echo Checking database...
if not exist "dcim.db" (
    echo   Initializing database...
    "%PYTHON_CMD%" -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())" 2>nul
    if errorlevel 1 (
        echo [ERROR] Database initialization failed
        exit /b 1
    )
    echo   Database initialized
) else (
    echo   Database exists
)

REM Data consistency fix (optional)
if exist "scripts\fix_circuit_bindings.py" (
    echo   Running data consistency fix...
    "%PYTHON_CMD%" scripts\fix_circuit_bindings.py >nul 2>&1
    if not errorlevel 1 (
        echo   Data consistency fix completed
    )
)

exit /b 0
