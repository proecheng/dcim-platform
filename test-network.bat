@echo off
chcp 65001 >nul 2>&1

echo ========================================================
echo           DCIM System - Network Access Test
echo ========================================================
echo.

echo [Test 1] Checking if backend is listening...
netstat -ano | findstr "8080" | findstr "LISTENING"
if errorlevel 1 (
    echo [FAILED] Backend is not listening on port 8080
    pause
    exit /b 1
)
echo [OK] Backend is listening on 0.0.0.0:8080
echo.

echo [Test 2] Testing backend API locally...
curl -s -o nul -w "%%{http_code}" http://localhost:8080/docs > temp_status.txt
set /p STATUS=<temp_status.txt
del temp_status.txt
if "%STATUS%"=="200" (
    echo [OK] Backend responds on localhost: %STATUS%
) else (
    echo [FAILED] Backend not responding: %STATUS%
)
echo.

echo [Test 3] Testing login API...
curl -s http://localhost:8080/api/v1/auth/login -X POST -d "username=admin&password=admin123" > temp_login.txt
findstr "access_token" temp_login.txt >nul
if errorlevel 1 (
    echo [FAILED] Login API not working
    type temp_login.txt
) else (
    echo [OK] Login API working correctly
)
del temp_login.txt
echo.

echo [Test 4] Checking firewall rules...
netsh advfirewall firewall show rule name="DCIM Backend 8080" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Firewall rule not found for port 8080
    echo Creating firewall rule...
    netsh advfirewall firewall add rule name="DCIM Backend 8080" dir=in action=allow protocol=TCP localport=8080
) else (
    echo [OK] Firewall rule exists for port 8080
)
echo.

netsh advfirewall firewall show rule name="DCIM Frontend 3000" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Firewall rule not found for port 3000
    echo Creating firewall rule...
    netsh advfirewall firewall add rule name="DCIM Frontend 3000" dir=in action=allow protocol=TCP localport=3000
) else (
    echo [OK] Firewall rule exists for port 3000
)
echo.

echo ========================================================
echo                    Test Results
echo ========================================================
echo.
echo If all tests passed, the issue might be:
echo.
echo 1. Router/Gateway Configuration:
echo    - Port forwarding needed: 8080 and 3000
echo    - Check router admin panel
echo.
echo 2. ISP/Network Provider:
echo    - Some ISPs block non-standard ports
echo    - Contact ISP if needed
echo.
echo 3. Test from external network:
echo    - Use mobile data or ask someone external
echo    - Test URL: http://powerlab.cn:8080/docs
echo    - Test login: http://powerlab.cn:3000
echo.
echo To test backend from external network, run:
echo   curl http://powerlab.cn:8080/docs
echo.
echo ========================================================
pause
