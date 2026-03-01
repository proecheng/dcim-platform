@echo off
REM Git Hook Auto-Install Script (Windows)

echo ================================
echo Git Hook Auto-Install Script
echo ================================
echo.

REM Check if in Git repository
if not exist ".git" (
    echo ERROR: Not a Git repository
    exit /b 1
)

REM Check gh CLI
where gh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: GitHub CLI not installed
    echo Please visit https://cli.github.com/
    echo.
    echo Hook will be installed anyway
    echo.
)

REM Create hooks directory
if not exist ".git\hooks" mkdir .git\hooks

REM Copy post-push hook
echo Installing post-push hook...
copy /Y scripts\post-push-hook.bat .git\hooks\post-push.bat >nul

REM Create Git hook entry point
echo #!/bin/sh > .git\hooks\post-push
echo cmd //c ".git/hooks/post-push.bat" >> .git\hooks\post-push

echo.
echo ================================
echo Installation Complete!
echo ================================
echo.
echo Post-push hook installed
echo.
echo Usage:
echo   git push  (auto-monitor)
echo   python scripts\check-ci.py  (manual check)
echo.
echo Uninstall: del .git\hooks\post-push*
echo.

pause
