@echo off
setlocal EnableDelayedExpansion

title DCIM System Maintenance

echo.
echo ========================================================
echo       Computing Center Intelligent Monitoring System
echo                  Maintenance Tool v1.0
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Find Python
set "PYTHON_CMD="
if exist "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"
) else (
    where python.exe >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=*" %%i in ('where python.exe 2^>nul ^| findstr /v WindowsApps') do (
            if "!PYTHON_CMD!"=="" set "PYTHON_CMD=%%i"
        )
    )
)

if "!PYTHON_CMD!"=="" (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

:MENU
cls
echo.
echo ========================================================
echo              DCIM Maintenance Menu
echo ========================================================
echo.
echo   1. Fix Data Consistency (circuit_id bindings)
echo   2. Verify Data Consistency
echo   3. View System Status
echo   4. Clean Database (Reset to Demo Data)
echo   5. Backup Database
echo   6. Exit
echo.
echo ========================================================
echo.

set /p choice="Select option (1-6): "

if "%choice%"=="1" goto FIX_DATA
if "%choice%"=="2" goto VERIFY_DATA
if "%choice%"=="3" goto SYSTEM_STATUS
if "%choice%"=="4" goto CLEAN_DB
if "%choice%"=="5" goto BACKUP_DB
if "%choice%"=="6" goto EXIT

echo Invalid option, please try again.
timeout /t 2 /nobreak >nul
goto MENU

REM ============================================================
REM Option 1: Fix Data Consistency
REM ============================================================
:FIX_DATA
cls
echo.
echo ========================================================
echo            Fix Data Consistency
echo ========================================================
echo.
echo This will fix circuit_id bindings for all PowerDevices.
echo.
echo Checking if services are running...

netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo [WARNING] Backend service is running!
    echo Please stop services first: stop.bat
    echo.
    pause
    goto MENU
)

echo Services are stopped, proceeding...
echo.

cd /d "%SCRIPT_DIR%backend"
if exist "scripts\fix_circuit_bindings.py" (
    echo Running fix script...
    echo.
    "!PYTHON_CMD!" scripts\fix_circuit_bindings.py
    echo.
    echo Fix completed!
) else (
    echo [ERROR] Fix script not found!
)

echo.
pause
goto MENU

REM ============================================================
REM Option 2: Verify Data Consistency
REM ============================================================
:VERIFY_DATA
cls
echo.
echo ========================================================
echo          Verify Data Consistency
echo ========================================================
echo.

cd /d "%SCRIPT_DIR%backend"
if exist "scripts\verify_data_consistency.py" (
    echo Running verification...
    echo.
    "!PYTHON_CMD!" scripts\verify_data_consistency.py
    echo.
) else (
    echo [ERROR] Verification script not found!
)

echo.
pause
goto MENU

REM ============================================================
REM Option 3: System Status
REM ============================================================
:SYSTEM_STATUS
cls
echo.
echo ========================================================
echo              System Status
echo ========================================================
echo.

echo Checking services...
echo.

netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   Backend (8080):  [RUNNING]
) else (
    echo   Backend (8080):  [STOPPED]
)

netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   Proxy (3000):    [RUNNING]
) else (
    echo   Proxy (3000):    [STOPPED]
)

echo.
echo Checking database...
if exist "%SCRIPT_DIR%backend\dcim.db" (
    for %%A in ("%SCRIPT_DIR%backend\dcim.db") do (
        echo   Database:        [EXISTS] (%%~zA bytes)
    )
) else (
    echo   Database:        [NOT FOUND]
)

echo.
echo Checking frontend build...
if exist "%SCRIPT_DIR%frontend\dist\index.html" (
    echo   Frontend Build:  [OK]
) else (
    echo   Frontend Build:  [NOT BUILT]
)

echo.
pause
goto MENU

REM ============================================================
REM Option 4: Clean Database
REM ============================================================
:CLEAN_DB
cls
echo.
echo ========================================================
echo            Clean Database
echo ========================================================
echo.
echo [WARNING] This will DELETE the current database!
echo All data will be lost and reset to demo data.
echo.
set /p confirm="Are you sure? (yes/no): "

if not "%confirm%"=="yes" (
    echo Operation cancelled.
    timeout /t 2 /nobreak >nul
    goto MENU
)

echo.
echo Checking if services are running...

netstat -ano | findstr ":8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo [ERROR] Backend service is running!
    echo Please stop services first: stop.bat
    echo.
    pause
    goto MENU
)

echo Services are stopped, proceeding...
echo.

cd /d "%SCRIPT_DIR%backend"
if exist "dcim.db" (
    echo Deleting database...
    del /F /Q dcim.db
    echo Database deleted.
    echo.
    echo Please restart the system to initialize fresh database.
) else (
    echo Database not found, nothing to clean.
)

echo.
pause
goto MENU

REM ============================================================
REM Option 5: Backup Database
REM ============================================================
:BACKUP_DB
cls
echo.
echo ========================================================
echo            Backup Database
echo ========================================================
echo.

cd /d "%SCRIPT_DIR%backend"
if not exist "dcim.db" (
    echo [ERROR] Database not found!
    echo.
    pause
    goto MENU
)

REM Create backup directory
if not exist "backups" mkdir backups

REM Generate timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set timestamp=%datetime:~0,8%_%datetime:~8,6%

set "BACKUP_FILE=backups\dcim_backup_%timestamp%.db"

echo Creating backup...
copy /Y dcim.db "%BACKUP_FILE%" >nul

if exist "%BACKUP_FILE%" (
    echo.
    echo Backup created successfully!
    echo Location: backend\%BACKUP_FILE%
    for %%A in ("%BACKUP_FILE%") do (
        echo Size: %%~zA bytes
    )
) else (
    echo [ERROR] Backup failed!
)

echo.
pause
goto MENU

REM ============================================================
REM Exit
REM ============================================================
:EXIT
echo.
echo Exiting maintenance tool...
exit /b 0
