@echo off
chcp 65001 >nul
echo ========================================
echo 设备调节能力配置初始化工具
echo ========================================
echo.
echo 此工具将为所有用电设备自动生成:
echo   1. 设备负荷转移配置
echo   2. 设备参数调节配置
echo.
echo 根据设备类型自动判断:
echo   - 空调(AC/HVAC): 可转移30-35%%, 可调节温度
echo   - 照明(LIGHT): 可转移50%%, 可调节亮度
echo   - 水泵(PUMP): 可转移40%%, 可调节频率
echo   - IT设备/UPS: 关键负荷，不可转移
echo.
pause

cd /d "%~dp0"
echo.
echo 正在初始化设备配置...
echo.

python init_device_regulation.py

if errorlevel 1 (
    echo.
    echo [错误] 初始化失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo 初始化完成！
echo ========================================
echo.
echo 下一步操作:
echo   1. 刷新前端浏览器页面
echo   2. 进入 "能源管理 → 节能建议"
echo   3. 点击任一建议的 "查看详情"
echo   4. 切换到 "参数调整" 标签页
echo   5. 现在应该可以看到 "参与设备" 列表了
echo.
pause
