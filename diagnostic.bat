@echo off
chcp 65001 >nul 2>&1
title DCIM System - Network Diagnostic

echo.
echo ========================================================
echo           DCIM System - Network Diagnostic
echo ========================================================
echo.

echo [1] Checking public IP...
for /f "tokens=*" %%i in ('powershell -Command "(Invoke-WebRequest -Uri http://ipinfo.io/ip -UseBasicParsing).Content.Trim()"') do set PUBLIC_IP=%%i
echo       Public IP: %PUBLIC_IP%

echo.
echo [2] Checking local IP...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr "IPv4"') do (
    set LOCAL_IP=%%i
    goto :found_ip
)
:found_ip
echo       Local IP: %LOCAL_IP%

echo.
echo [3] Checking DNS resolution...
for /f "tokens=2" %%i in ('nslookup powerlab.cn 2^>nul ^| findstr "Address:" ^| findstr /v ":" ^| findstr "[0-9]"') do set RESOLVED_IP=%%i
echo       powerlab.cn resolves to: %RESOLVED_IP%
if "%PUBLIC_IP%"=="%RESOLVED_IP%" (
    echo       [OK] DNS matches public IP
) else (
    echo       [WARNING] DNS does not match public IP!
)

echo.
echo [4] Checking services...
netstat -ano | findstr ":3000.*LISTENING" >nul
if %errorlevel%==0 (
    echo       [OK] Proxy service running on port 3000
) else (
    echo       [ERROR] Proxy service NOT running on port 3000
)

netstat -ano | findstr ":8080.*LISTENING" >nul
if %errorlevel%==0 (
    echo       [OK] Backend service running on port 8080
) else (
    echo       [ERROR] Backend service NOT running on port 8080
)

echo.
echo [5] Checking firewall...
powershell -Command "if ((Get-NetFirewallRule -DisplayName 'DCIM Frontend 3000' -ErrorAction SilentlyContinue).Enabled) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo       [OK] Firewall rule enabled for port 3000
) else (
    echo       [WARNING] Firewall rule NOT enabled
)

echo.
echo [6] Testing local access...
curl -s -m 2 "http://localhost:3000/health" >nul 2>&1
if %errorlevel%==0 (
    echo       [OK] Local access works (http://localhost:3000/)
) else (
    echo       [ERROR] Local access FAILED
)

echo.
echo [7] Testing internal network access...
curl -s -m 2 "http://%LOCAL_IP:~1%:3000/health" >nul 2>&1
if %errorlevel%==0 (
    echo       [OK] Internal network access works
) else (
    echo       [WARNING] Internal network access FAILED
)

echo.
echo ========================================================
echo                  Diagnostic Summary
echo ========================================================
echo.
echo   Service Status: Check if both services are [OK] above
echo   Firewall:       Check if firewall rule is [OK] above
echo   Network:        Check if internal access is [OK] above
echo.
echo ========================================================
echo              Router Port Forwarding Check
echo ========================================================
echo.
echo   To test external access, please:
echo.
echo   1. Use your PHONE with 4G/5G (NOT WiFi)
echo   2. Visit: http://powerlab.cn:3000/
echo   3. Take a screenshot of the error
echo.
echo   If you cannot access, please check router settings:
echo   - External Port: 3000
echo   - Internal IP:  %LOCAL_IP:~1%
echo   - Internal Port: 3000
echo   - Protocol: TCP
echo.
echo   Online port checker (use phone):
echo   - https://www.yougetsignal.com/tools/open-ports/
echo   - Enter port: 3000
echo   - If "Closed", router forwarding is NOT working
echo.
echo ========================================================
echo.
pause
