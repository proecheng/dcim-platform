@echo off
setlocal EnableDelayedExpansion

echo Testing start.bat logic...
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Test Step 1: Environment Check
echo [1/6] Testing environment check...
call scripts\check-env.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo FAILED: Environment check failed
    exit /b 1
)
echo PASSED: Environment check

REM Get Python command
if exist "%TEMP%\dcim_python_cmd.txt" (
    set /p PYTHON_CMD=<"%TEMP%\dcim_python_cmd.txt"
    echo Python command: !PYTHON_CMD!
)

REM Test Step 2: Port Cleanup
echo.
echo [2/6] Testing port cleanup...
call scripts\clean-ports.bat 8080 3000
if errorlevel 1 (
    echo FAILED: Port cleanup failed
    exit /b 1
)
echo PASSED: Port cleanup

REM Test Step 3: Backend Setup
echo.
echo [3/6] Testing backend setup...
call scripts\setup-backend.bat "%SCRIPT_DIR%" "%PYTHON_CMD%"
if errorlevel 1 (
    echo FAILED: Backend setup failed
    exit /b 1
)
echo PASSED: Backend setup

REM Test Step 4: Proxy Setup
echo.
echo [4/6] Testing proxy setup...
call scripts\setup-proxy.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo FAILED: Proxy setup failed
    exit /b 1
)
echo PASSED: Proxy setup

REM Test Step 5: Frontend Setup
echo.
echo [5/6] Testing frontend setup...
call scripts\setup-frontend.bat "%SCRIPT_DIR%"
if errorlevel 1 (
    echo FAILED: Frontend setup failed
    exit /b 1
)
echo PASSED: Frontend setup

echo.
echo ========================================
echo All tests passed!
echo ========================================
echo.
echo Note: Services not started in test mode
echo To start services, run: start.bat
echo.
