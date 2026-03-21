@echo off
REM ============================================================
REM DCIM System Launcher v8.0 (Refactored)
REM Modular launcher script
REM ============================================================

setlocal EnableDelayedExpansion

title DCIM System Launcher

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Startup Script v8.0
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
REM Step 2: Port Cleanup
REM ============================================================
echo.
echo [2/6] Cleaning occupied ports...
call scripts\clean-ports.bat 8080 3000
if errorlevel 1 (
    echo.
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
REM Step 6: Start Services
REM ============================================================
echo.
echo [6/6] Starting services...
echo.
echo ========================================================
echo                   Starting Services
echo ========================================================
echo.

call scripts\start-services.bat "%SCRIPT_DIR%" "%PYTHON_CMD%"

REM ============================================================
REM Success Message
REM ============================================================
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
echo   Troubleshooting:
echo   - If pages show errors, wait 10s for services to fully start
echo   - Check backend/proxy windows for error messages
echo   - Run stop.bat before restarting if issues persist
echo.
echo ========================================================
echo.

echo Opening browser...
start "" "http://localhost:3000"

echo.
echo Press any key to close this launcher window...
echo (Service windows will keep running)
pause >nul

REM Cleanup temp file
del "%TEMP%\dcim_python_cmd.txt" >nul 2>&1

exit /b 0
