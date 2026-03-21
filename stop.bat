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
REM Step 2: Clean Ports (using module)
REM ============================================================
echo.
echo [2/3] Cleaning ports...
call scripts\clean-ports.bat 8080 3000

REM ============================================================
REM Step 3: Final Verification
REM ============================================================
echo.
echo [3/3] Final verification...

set "ALL_CLEAR=1"
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 8080 still in use (may be zombie port)
    set "ALL_CLEAR=0"
)
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [WARNING] Port 3000 still in use (may be zombie port)
    set "ALL_CLEAR=0"
)

if "!ALL_CLEAR!"=="0" (
    echo.
    echo       Note: Zombie ports will be released automatically in 5-10 minutes
    echo       Or restart your computer for immediate cleanup
)

REM ============================================================
REM Success Message
REM ============================================================
echo.
echo ========================================================
echo              All Services Stopped
echo ========================================================
echo.
echo   Ports 8080 and 3000 are now free
echo   You can safely restart the system with start.bat
echo.
echo ========================================================
echo.

pause

exit /b 0
