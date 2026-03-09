@echo off
REM ============================================================
REM Configure Firewall for DCIM Ports
REM 配置防火墙规则，开放所有需要的端口
REM ============================================================

echo.
echo ========================================================
echo       DCIM Firewall Configuration
echo ========================================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script requires administrator privileges
    echo Please right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo Configuring firewall rules...
echo.

REM Remove old rules if they exist
netsh advfirewall firewall delete rule name="DCIM Frontend 3000" >nul 2>&1
netsh advfirewall firewall delete rule name="DCIM Frontend 3002" >nul 2>&1
netsh advfirewall firewall delete rule name="DCIM Backend 8080" >nul 2>&1
netsh advfirewall firewall delete rule name="DCIM Backend 8083" >nul 2>&1

REM Add rules for default ports
echo [1/4] Adding rule for port 3000 (Frontend - Default)...
netsh advfirewall firewall add rule name="DCIM Frontend 3000" dir=in action=allow protocol=TCP localport=3000
if errorlevel 1 (
    echo [ERROR] Failed to add rule for port 3000
) else (
    echo       Port 3000: OK
)

REM Add rules for alternative ports
echo [2/4] Adding rule for port 3002 (Frontend - Alternative)...
netsh advfirewall firewall add rule name="DCIM Frontend 3002" dir=in action=allow protocol=TCP localport=3002
if errorlevel 1 (
    echo [ERROR] Failed to add rule for port 3002
) else (
    echo       Port 3002: OK
)

echo [3/4] Adding rule for port 8080 (Backend - Default)...
netsh advfirewall firewall add rule name="DCIM Backend 8080" dir=in action=allow protocol=TCP localport=8080
if errorlevel 1 (
    echo [ERROR] Failed to add rule for port 8080
) else (
    echo       Port 8080: OK
)

echo [4/4] Adding rule for port 8083 (Backend - Alternative)...
netsh advfirewall firewall add rule name="DCIM Backend 8083" dir=in action=allow protocol=TCP localport=8083
if errorlevel 1 (
    echo [ERROR] Failed to add rule for port 8083
) else (
    echo       Port 8083: OK
)

echo.
echo ========================================================
echo       Firewall Configuration Complete
echo ========================================================
echo.
echo Configured ports:
echo   - 3000 (Frontend - Default)
echo   - 3002 (Frontend - Alternative)
echo   - 8080 (Backend - Default)
echo   - 8083 (Backend - Alternative)
echo.
echo ========================================================
echo.

pause
