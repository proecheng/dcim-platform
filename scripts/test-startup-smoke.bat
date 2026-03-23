@echo off
REM ============================================================
REM Startup Scripts Smoke Test
REM Validates key behaviors without actually starting services
REM ============================================================

setlocal EnableDelayedExpansion

echo.
echo ========================================================
echo       Startup Scripts Smoke Test
echo ========================================================
echo.

set "PASS=0"
set "FAIL=0"
set "SCRIPT_DIR=%~dp0..\\"

REM ============================================================
REM Test 1: check-env.bat finds Python
REM ============================================================
echo [TEST 1] check-env.bat - Python detection
call "%SCRIPT_DIR%scripts\check-env.bat" "%SCRIPT_DIR%"
if errorlevel 1 (
    echo   FAIL: check-env.bat returned error
    set /a FAIL+=1
) else (
    if exist "%TEMP%\dcim_python_cmd.txt" (
        set /p TEST_PY=<"%TEMP%\dcim_python_cmd.txt"
        if "!TEST_PY!"=="" (
            echo   FAIL: Python cmd file is empty
            set /a FAIL+=1
        ) else (
            echo   PASS: Python found: !TEST_PY!
            set /a PASS+=1
        )
    ) else (
        echo   FAIL: Python cmd temp file not created
        set /a FAIL+=1
    )
)

REM ============================================================
REM Test 2: check-env.bat finds Node.js
REM ============================================================
echo.
echo [TEST 2] Node.js availability
where node.exe >nul 2>&1
if errorlevel 1 (
    echo   FAIL: Node.js not found in PATH
    set /a FAIL+=1
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   PASS: Node.js %%v
    set /a PASS+=1
)

REM ============================================================
REM Test 3: clean-ports.bat exits 0 when ports are free
REM ============================================================
echo.
echo [TEST 3] clean-ports.bat - free ports return code 0
REM First ensure ports are free
netstat -ano | findstr ":18080" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    REM Port 18080 should be free (unlikely to be used)
    call "%SCRIPT_DIR%scripts\clean-ports.bat" 18080 18081
    if errorlevel 1 (
        echo   FAIL: clean-ports.bat returned error for free ports
        set /a FAIL+=1
    ) else (
        echo   PASS: Returns 0 for free ports
        set /a PASS+=1
    )
) else (
    echo   SKIP: Port 18080 unexpectedly in use
)

REM ============================================================
REM Test 4: clean-ports.bat fallback writes temp files
REM ============================================================
echo.
echo [TEST 4] clean-ports.bat - fallback mode produces temp files
REM Use ports that are likely busy (or not) - we test the code path
del "%TEMP%\dcim_backend_port.txt" >nul 2>&1
del "%TEMP%\dcim_proxy_port.txt" >nul 2>&1
REM With fallback=1 and free ports, should still return 0 (no fallback needed)
call "%SCRIPT_DIR%scripts\clean-ports.bat" 18080 18081 1
if "!errorlevel!"=="0" (
    echo   PASS: Fallback mode returns 0 when ports free ^(no fallback needed^)
    set /a PASS+=1
) else if "!errorlevel!"=="2" (
    if exist "%TEMP%\dcim_backend_port.txt" (
        echo   PASS: Fallback mode created temp files ^(exit code 2^)
        set /a PASS+=1
    ) else (
        echo   FAIL: Fallback exit 2 but no temp files
        set /a FAIL+=1
    )
) else (
    echo   FAIL: Unexpected exit code !errorlevel!
    set /a FAIL+=1
)

REM ============================================================
REM Test 5: proxy/server.js port validation (Node.js)
REM ============================================================
echo.
echo [TEST 5] proxy/server.js - port validation rejects invalid ports
cd /d "%SCRIPT_DIR%proxy"

REM Test: invalid PROXY_PORT should exit with code 1
set "PROXY_PORT=abc"
set "BACKEND_PORT=8080"
node -e "process.env.PROXY_PORT='abc'; process.env.BACKEND_PORT='8080'; try { require('./server.js'); } catch(e) {}" >nul 2>&1
REM server.js calls process.exit(1) on invalid port
if errorlevel 1 (
    echo   PASS: Rejects invalid PROXY_PORT='abc'
    set /a PASS+=1
) else (
    echo   FAIL: Did not reject invalid PROXY_PORT='abc'
    set /a FAIL+=1
)

REM Test: same port should exit with code 1
node -e "process.env.PROXY_PORT='8080'; process.env.BACKEND_PORT='8080'; try { require('./server.js'); } catch(e) {}" >nul 2>&1
if errorlevel 1 (
    echo   PASS: Rejects same PROXY_PORT and BACKEND_PORT
    set /a PASS+=1
) else (
    echo   FAIL: Did not reject same ports
    set /a FAIL+=1
)

REM Reset env vars
set "PROXY_PORT="
set "BACKEND_PORT="

REM ============================================================
REM Test 6: All script files exist
REM ============================================================
echo.
echo [TEST 6] Script file existence
set "ALL_EXIST=1"
for %%f in (
    start.bat
    start-smart.bat
    start-alt-ports.bat
    stop.bat
    scripts\check-env.bat
    scripts\clean-ports.bat
    scripts\setup-backend.bat
    scripts\setup-frontend.bat
    scripts\setup-proxy.bat
    scripts\start-services.bat
    proxy\server.js
) do (
    if not exist "%SCRIPT_DIR%%%f" (
        echo   FAIL: Missing %%f
        set "ALL_EXIST=0"
        set /a FAIL+=1
    )
)
if "!ALL_EXIST!"=="1" (
    echo   PASS: All 11 script files present
    set /a PASS+=1
)

REM ============================================================
REM Test 7: No orphan server-alt.js
REM ============================================================
echo.
echo [TEST 7] server-alt.js removed (merged into server.js)
if exist "%SCRIPT_DIR%proxy\server-alt.js" (
    echo   FAIL: server-alt.js still exists ^(should be deleted^)
    set /a FAIL+=1
) else (
    echo   PASS: server-alt.js removed
    set /a PASS+=1
)

REM ============================================================
REM Test 8: No orphan clean-ports-enhanced.bat
REM ============================================================
echo.
echo [TEST 8] clean-ports-enhanced.bat removed (merged into clean-ports.bat)
if exist "%SCRIPT_DIR%scripts\clean-ports-enhanced.bat" (
    echo   FAIL: clean-ports-enhanced.bat still exists ^(should be deleted^)
    set /a FAIL+=1
) else (
    echo   PASS: clean-ports-enhanced.bat removed
    set /a PASS+=1
)

REM ============================================================
REM Results
REM ============================================================
echo.
echo ========================================================
echo   Results: !PASS! passed, !FAIL! failed
echo ========================================================
echo.

if "!FAIL!" NEQ "0" (
    echo   Some tests failed - review output above
    exit /b 1
)

echo   All tests passed!
exit /b 0
