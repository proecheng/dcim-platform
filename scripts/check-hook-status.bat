@echo off
REM Check Git Hook Installation Status

echo ================================
echo Git Hook Status Check
echo ================================
echo.

REM Check if in Git repository
if not exist ".git" (
    echo ERROR: Not a Git repository
    echo.
    pause
    exit /b 1
)

REM Check if hooks are installed
if exist ".git\hooks\post-push" (
    echo [OK] post-push hook found
) else (
    echo [MISSING] post-push hook not found
)

if exist ".git\hooks\post-push.bat" (
    echo [OK] post-push.bat hook found
) else (
    echo [MISSING] post-push.bat hook not found
)

echo.

REM Check gh CLI
where gh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] GitHub CLI installed
    gh --version
) else (
    echo [MISSING] GitHub CLI not installed
    echo Please visit https://cli.github.com/
)

echo.

REM Check gh auth
gh auth status >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] GitHub CLI authenticated
) else (
    echo [MISSING] GitHub CLI not authenticated
    echo Please run: gh auth login
)

echo.
echo ================================
echo Summary
echo ================================
echo.

if exist ".git\hooks\post-push" (
    if exist ".git\hooks\post-push.bat" (
        echo Git Hook: INSTALLED
        echo.
        echo Now when you run 'git push', CI will be
        echo automatically monitored.
        echo.
        echo You can also manually check CI status:
        echo   python scripts\check-ci.py
    ) else (
        echo Git Hook: PARTIALLY INSTALLED
        echo Please run: scripts\install-hooks.bat
    )
) else (
    echo Git Hook: NOT INSTALLED
    echo Please run: scripts\install-hooks.bat
)

echo.
pause
