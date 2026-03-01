@echo off
REM Git Post-Push Hook - 自动监控 GitHub Actions CI 运行结果 (Windows 版本)
REM 
REM 安装方法:
REM   1. 将此文件复制到 .git\hooks\post-push.bat
REM   2. 创建 .git\hooks\post-push 文件（无扩展名），内容为:
REM      #!/bin/sh
REM      cmd //c ".git/hooks/post-push.bat"
REM
REM 功能:
REM   - 自动监控 CI 运行状态
REM   - 失败时显示详细错误信息
REM   - 解析 Ruff 和 ESLint 错误

setlocal enabledelayedexpansion

echo.
echo [94m🚀 代码已推送到 GitHub[0m
echo [94m📊 正在监控 CI 运行...[0m
echo.

REM 检查是否安装了 gh CLI
where gh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [91m❌ 错误: 未安装 GitHub CLI (gh)[0m
    echo [93m请访问 https://cli.github.com/ 安装[0m
    exit /b 0
)

REM 检查是否已认证
gh auth status >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [91m❌ 错误: GitHub CLI 未认证[0m
    echo [93m请运行: gh auth login[0m
    exit /b 0
)

REM 等待工作流开始
echo [93m⏳ 等待 CI 工作流启动...[0m
timeout /t 5 /nobreak >nul

REM 获取最新的工作流运行
echo [94m📋 获取最新的 CI 运行...[0m
for /f "delims=" %%i in ('gh run list --limit 1 --json databaseId^,status^,conclusion^,name^,headBranch 2^>nul') do set RUN_INFO=%%i

if "!RUN_INFO!"=="" (
    echo [93m⚠️  未找到 CI 运行记录[0m
    echo [93m提示: CI 可能还未开始，请稍后手动检查[0m
    echo [94m命令: gh run list[0m
    exit /b 0
)

if "!RUN_INFO!"=="[]" (
    echo [93m⚠️  未找到 CI 运行记录[0m
    echo [93m提示: CI 可能还未开始，请稍后手动检查[0m
    echo [94m命令: gh run list[0m
    exit /b 0
)

REM 解析 JSON (需要 PowerShell)
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].databaseId"') do set RUN_ID=%%i
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].status"') do set RUN_STATUS=%%i
for /f "delims=" %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].name"') do set RUN_NAME=%%i
for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].headBranch"') do set RUN_BRANCH=%%i

echo [94m工作流: !RUN_NAME![0m
echo [94m分支: !RUN_BRANCH![0m
echo [94m运行 ID: !RUN_ID![0m
echo.

REM 如果还在运行，监控进度
if "!RUN_STATUS!"=="in_progress" (
    echo [93m⏳ CI 正在运行，实时监控中...[0m
    echo [93m(按 Ctrl+C 可以退出监控，CI 会继续运行)[0m
    echo.
    
    gh run watch !RUN_ID! --exit-status 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo [92m✅ CI 检查全部通过！[0m
        exit /b 0
    ) else (
        echo.
        echo [91m❌ CI 检查失败[0m
    )
) else if "!RUN_STATUS!"=="queued" (
    echo [93m⏳ CI 正在排队，实时监控中...[0m
    echo.
    
    gh run watch !RUN_ID! --exit-status 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo [92m✅ CI 检查全部通过！[0m
        exit /b 0
    ) else (
        echo.
        echo [91m❌ CI 检查失败[0m
    )
) else (
    REM 已经完成，检查结果
    for /f %%i in ('powershell -Command "('!RUN_INFO!' | ConvertFrom-Json)[0].conclusion"') do set RUN_CONCLUSION=%%i
    
    if "!RUN_CONCLUSION!"=="success" (
        echo [92m✅ CI 检查全部通过！[0m
        exit /b 0
    ) else if "!RUN_CONCLUSION!"=="failure" (
        echo [91m❌ CI 检查失败[0m
    ) else (
        echo [93m⚠️  CI 状态: !RUN_CONCLUSION![0m
        exit /b 0
    )
)

REM 获取失败的作业详情
echo.
echo [94m📄 正在获取失败的作业详情...[0m
echo.

REM 显示失败日志
gh run view !RUN_ID! --log-failed

echo.
echo [94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m
echo [94m📊 查看完整日志:[0m
echo [94m   gh run view !RUN_ID! --log[0m
echo.
echo [94m🔄 重新运行失败的作业:[0m
echo [94m   gh run rerun !RUN_ID! --failed[0m
echo.
echo [94m🌐 在浏览器中查看:[0m
echo [94m   gh run view !RUN_ID! --web[0m
echo [94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m

exit /b 1
