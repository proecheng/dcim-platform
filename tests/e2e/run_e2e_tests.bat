@echo off
REM E2E数据一致性测试启动脚本
REM 使用方法: run_e2e_tests.bat

echo ============================================
echo DCIM系统 E2E数据一致性测试
echo ============================================

cd /d D:\mytest1

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python环境
    pause
    exit /b 1
)

REM 检查Playwright
python -c "from playwright.sync_api import sync_playwright" >nul 2>&1
if errorlevel 1 (
    echo [提示] 安装Playwright...
    pip install playwright
    python -m playwright install chromium
)

REM 检查requests
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    pip install requests
)

echo.
echo [步骤1] 启动后端服务器 (端口8080)...
start "Backend" /D "D:\mytest1\backend" cmd /c "call .venv\Scripts\activate && python run.py"

echo [步骤2] 等待后端启动 (10秒)...
timeout /t 10 /nobreak >nul

REM 检查后端是否启动
curl -s http://localhost:8080/docs >nul 2>&1
if errorlevel 1 (
    echo [警告] 后端可能未启动，继续测试...
)

echo.
echo [步骤3] 启动前端服务器 (端口3000)...
start "Frontend" /D "D:\mytest1\frontend" cmd /c "npm run dev"

echo [步骤4] 等待前端启动 (15秒)...
timeout /t 15 /nobreak >nul

echo.
echo [步骤5] 运行E2E测试...
python tests\e2e\test_data_consistency.py

echo.
echo ============================================
echo 测试完成
echo ============================================
echo.
echo 报告位置: D:\mytest1\e2e_test_report.json
echo.
pause
