@echo off
REM Git Hook 自动安装脚本 (Windows)

echo ================================
echo Git Hook 自动安装脚本
echo ================================
echo.

REM 检查是否在 Git 仓库中
if not exist ".git" (
    echo [91m❌ 错误: 当前目录不是 Git 仓库[0m
    exit /b 1
)

REM 检查 gh CLI
where gh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [93m⚠️  警告: 未安装 GitHub CLI (gh)[0m
    echo 请访问 https://cli.github.com/ 安装
    echo.
    set /p CONTINUE="是否继续安装 hook？(y/N) "
    if /i not "%CONTINUE%"=="y" exit /b 0
)

REM 创建 hooks 目录（如果不存在）
if not exist ".git\hooks" mkdir .git\hooks

REM 复制 post-push hook
echo [94m📝 安装 post-push hook...[0m
copy /Y scripts\post-push-hook.bat .git\hooks\post-push.bat >nul

REM 创建 Git hook 入口
echo #!/bin/sh > .git\hooks\post-push
echo cmd //c ".git/hooks/post-push.bat" >> .git\hooks\post-push

echo [92m✅ post-push hook 已安装[0m
echo.

REM 测试 hook
echo [94m🧪 测试 hook...[0m
call .git\hooks\post-push.bat
if %ERRORLEVEL% EQU 0 (
    echo [92m✅ Hook 测试通过[0m
) else (
    echo [93m⚠️  Hook 测试失败，但已安装[0m
)

echo.
echo ================================
echo [92m✅ 安装完成！[0m
echo ================================
echo.
echo 现在每次 git push 后会自动监控 CI 运行
echo.
echo 手动检查 CI: python scripts\check-ci.py
echo 卸载 hook:   del .git\hooks\post-push*
echo.

pause
