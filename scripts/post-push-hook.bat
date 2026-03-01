@echo off
REM Git Post-Push Hook - Auto-monitor GitHub Actions CI (Windows)

setlocal enabledelayedexpansion

echo.
echo Code pushed to GitHub
echo Monitoring CI run...
echo.

REM Check if gh CLI is installed
where gh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: GitHub CLI (gh) not installed
    echo Please visit https://cli.github.com/ to install
    exit /b 0
)

REM Check if authenticated
gh auth status >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: GitHub CLI not authenticated
    echo Please run: gh auth login
    exit /b 0
)

REM Wait for workflow to start
echo Waiting for CI workflow to start...
timeout /t 5 /nobreak >nul

REM Get latest workflow run
echo Getting latest CI run...
for /f "delims=" %%i in ('gh run list --limit 1 --json databaseId^,status^,conclusion^,name^,headBranch 2^>nul') do set RUN_INFO=%%i

if "!RUN_INFO!"=="" (
    echo WARNING: No CI run found
    echo Tip: CI may not have started yet, check manually later
    echo Command: gh run list
    exit /b 0
)

if "!RUN_INFO!"=="[]" (
    echo WARNING: No CI run found
    echo Tip: CI may not have started yet, check manually later
    echo Command: gh run list
    exit /b 0
)

REM Parse JSON using PowerShell
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].databaseId"') do set RUN_ID=%%i
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].status"') do set RUN_STATUS=%%i
for /f "delims=" %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].name"') do set RUN_NAME=%%i
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].headBranch"') do set RUN_BRANCH=%%i

echo Workflow: !RUN_NAME!
echo Branch: !RUN_BRANCH!
echo Run ID: !RUN_ID!
echo.

REM If running, monitor progress
if "!RUN_STATUS!"=="in_progress" (
    echo CI is running, monitoring...
    echo (Press Ctrl+C to exit, CI will continue)
    echo.
    
    gh run watch !RUN_ID! --exit-status 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo CI checks passed!
        exit /b 0
    ) else (
        echo.
        echo CI checks failed
    )
) else if "!RUN_STATUS!"=="queued" (
    echo CI is queued, monitoring...
    echo.
    
    gh run watch !RUN_ID! --exit-status 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo CI checks passed!
        exit /b 0
    ) else (
        echo.
        echo CI checks failed
    )
) else (
    REM Already completed, check result
    for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].conclusion"') do set RUN_CONCLUSION=%%i
    
    if "!RUN_CONCLUSION!"=="success" (
        echo CI checks passed!
        exit /b 0
    ) else if "!RUN_CONCLUSION!"=="failure" (
        echo CI checks failed
    ) else (
        echo CI status: !RUN_CONCLUSION!
        exit /b 0
    )
)

REM Get failed job details
echo.
echo Getting failed job details...
echo.

REM Show failed logs
gh run view !RUN_ID! --log-failed

echo.
echo ============================================
echo View full log:    gh run view !RUN_ID! --log
echo Rerun failed:     gh run rerun !RUN_ID! --failed
echo View in browser:  gh run view !RUN_ID! --web
echo ============================================

exit /b 1
