@echo off
REM ============================================================
REM DCIM System Stopper v4.0 (Refactored)
REM Modular port cleanup
REM ============================================================

setlocal EnableDelayedExpansion

title DCIM System Stopper

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                    Stop Script v4.0
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM ============================================================
REM Step 1: Stop Service Windows
REM ============================================================
echo [1/3] Stopping service windows...

taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
if not errorlevel 1 echo       Backend window closed
taskkill /F /FI "WINDOWTITLE eq Proxy*" >nul 2>&1
if not errorlevel 1 echo       Proxy window closed
taskkill /F /FI "WINDOWTITLE eq Monitor-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Monitor-Proxy*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DCIM-Proxy*" >nul 2>&1

echo       Service windows closed

REM ============================================================
REM Step 2: Clean Ports (default + alternative)
REM ============================================================
echo.
echo [2/3] Cleaning default ports (8080, 3000)...
call scripts\clean-ports.bat 8080 3000

echo.
echo       Cleaning alternative ports (8083, 3002)...
call scripts\clean-ports.bat 8083 3002

REM ============================================================
REM Step 3: Final Verification
REM ============================================================
echo.
echo [3/3] Final verification...

set "ALL_CLEAR=1"
for %%p in (8080 3000 8083 3002) do (
    netstat -ano | findstr ":%%p" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo       [WARNING] Port %%p still in use (may be zombie port^)
        set "ALL_CLEAR=0"
    )
)

if "!ALL_CLEAR!"=="0" (
    echo.
    echo       Note: Zombie ports will be released automatically in 5-10 minutes
    echo       Or restart your computer for immediate cleanup
)

REM ============================================================
REM Result Message
REM ============================================================
echo.
echo ========================================================
if "!ALL_CLEAR!"=="1" (
    echo              All Services Stopped
    echo ========================================================
    echo.
    echo   All ports are now free
    echo   You can safely restart the system with start.bat
) else (
    echo          Services Stopped (with warnings)
    echo ========================================================
    echo.
    echo   Some ports may still be occupied (see warnings above^)
    echo   Wait a few minutes or restart the computer
)
echo.
echo ========================================================
echo.

pause

exit /b 0
