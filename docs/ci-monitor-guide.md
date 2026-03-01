# GitHub Actions CI 自动错误监控

## 功能特性

✅ **自动监控**: Git push 后自动监控 CI 运行状态  
✅ **智能解析**: 自动解析 Ruff、ESLint、Pytest 错误  
✅ **修复建议**: 为每个错误提供具体的修复建议  
✅ **实时反馈**: 实时显示 CI 运行进度  
✅ **跨平台**: 支持 Windows、Linux、macOS

---

## 快速开始

### 1. 安装 GitHub CLI

如果还未安装 GitHub CLI：

**Windows**:
```bash
winget install GitHub.cli
# 或下载安装包: https://cli.github.com/
```

**Linux/macOS**:
```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# 其他系统: https://github.com/cli/cli#installation
```

### 2. 认证 GitHub CLI

```bash
gh auth login
```

按提示选择：
- GitHub.com
- HTTPS
- 使用浏览器登录

### 3. 安装 Git Hook (可选)

#### 方法 A: 自动安装 (推荐)

```bash
# Windows
scripts\install-hooks.bat

# Linux/macOS
chmod +x scripts/install-hooks.sh
./scripts/install-hooks.sh
```

#### 方法 B: 手动安装

**Windows**:
```bash
# 1. 复制脚本
copy scripts\post-push-hook.bat .git\hooks\post-push.bat

# 2. 创建 Git hook 入口
echo #!/bin/sh > .git\hooks\post-push
echo cmd //c ".git/hooks/post-push.bat" >> .git\hooks\post-push
```

**Linux/macOS**:
```bash
# 1. 复制脚本
cp scripts/post-push-hook.sh .git/hooks/post-push

# 2. 添加执行权限
chmod +x .git/hooks/post-push
```

---

## 使用方法

### 自动模式 (推荐)

安装 Git hook 后，每次 `git push` 都会自动监控 CI：

```bash
git add .
git commit -m "feat: 添加新功能"
git push

# 自动输出:
# 🚀 代码已推送到 GitHub
# 📊 正在监控 CI 运行...
# ⏳ CI 正在运行，实时监控中...
# ✅ CI 检查全部通过！
```

如果 CI 失败，会自动显示详细错误：

```
❌ CI 检查失败
📄 正在获取失败的作业详情...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 失败的作业: 后端测试
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

backend/app/services/device_sync.py:123:45: E501 Line too long (125 > 120)
backend/app/api/v1/energy.py:45:1: F401 'typing.Optional' imported but unused

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 查看完整日志:
   gh run view 123456 --log

🔄 重新运行失败的作业:
   gh run rerun 123456 --failed

🌐 在浏览器中查看:
   gh run view 123456 --web
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 手动模式

不想自动监控？可以随时手动检查：

```bash
# 检查最新的 CI 运行
python scripts/check-ci.py

# 实时监控最新的 CI 运行
python scripts/check-ci.py --watch

# 检查特定的运行
python scripts/check-ci.py --run-id 123456
```

### 使用 gh CLI 直接查看

```bash
# 列出最近的运行
gh run list

# 查看特定运行
gh run view 123456

# 查看失败日志
gh run view 123456 --log-failed

# 在浏览器中查看
gh run view 123456 --web

# 重新运行失败的作业
gh run rerun 123456 --failed
```

---

## 错误类型和修复建议

### Ruff 错误

| 错误代码 | 说明 | 修复建议 |
|---------|------|---------|
| E501 | 行太长 | 拆分长行或添加 `# noqa: E501` |
| F401 | 未使用的导入 | 删除导入或添加 `# noqa: F401` |
| F841 | 未使用的变量 | 删除或重命名为 `_variable` |
| W293 | 空行包含空格 | 运行 `ruff format` 自动修复 |

**快速修复**:
```bash
cd backend
ruff check --fix app/
ruff format app/
```

### ESLint 错误

| 规则 | 说明 | 修复建议 |
|------|------|---------|
| no-unused-vars | 未使用的变量 | 删除或添加前缀 `_` |
| no-console | 使用了 console.log | 移除或添加 eslint-disable |
| @typescript-eslint/no-explicit-any | 使用了 any 类型 | 使用具体类型 |

**快速修复**:
```bash
cd frontend
npm run lint -- --fix
```

### Pytest 错误

测试失败通常需要手动检查：

```bash
cd backend
pytest tests/test_file.py::test_name -v
```

---

## 高级配置

### 自定义 Hook 行为

编辑 `.git/hooks/post-push` 或 `.git/hooks/post-push.bat`：

```bash
# 跳过监控（快速推送）
# 注释掉 hook 内容或设置环境变量
export SKIP_CI_MONITOR=1
git push
```

### 只在特定分支监控

修改 hook 脚本，添加分支检查：

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "master" ]; then
    echo "跳过 CI 监控（非 master 分支）"
    exit 0
fi
```

### 集成到 IDE

**VS Code**:
1. 安装 GitHub Actions 扩展
2. 或在终端中运行 `python scripts/check-ci.py`

**PyCharm/WebStorm**:
1. 配置外部工具: Settings > Tools > External Tools
2. 添加工具: `python scripts/check-ci.py`

---

## 故障排查

### 问题 1: "gh: command not found"

**解决**: 安装 GitHub CLI
```bash
# Windows
winget install GitHub.cli

# macOS
brew install gh

# Linux
sudo apt install gh
```

### 问题 2: "GitHub CLI 未认证"

**解决**: 运行认证命令
```bash
gh auth login
```

### 问题 3: Hook 不执行

**检查**:
```bash
# 检查 hook 是否存在
ls -la .git/hooks/post-push

# 检查权限 (Linux/macOS)
chmod +x .git/hooks/post-push

# 测试 hook
.git/hooks/post-push
```

### 问题 4: "未找到 CI 运行记录"

**原因**: CI 可能还未开始

**解决**: 等待几秒后手动检查
```bash
python scripts/check-ci.py
```

---

## 卸载

### 移除 Git Hook

```bash
# Windows
del .git\hooks\post-push
del .git\hooks\post-push.bat

# Linux/macOS
rm .git/hooks/post-push
```

### 保留脚本，按需使用

不想自动监控？只需删除 Git hook，保留脚本供手动使用：

```bash
python scripts/check-ci.py
```

---

## 常见问题

**Q: 会影响 push 速度吗？**  
A: 不会。Hook 在 push 完成后运行，不阻塞 push 操作。

**Q: 可以跳过监控吗？**  
A: 可以。按 Ctrl+C 退出监控，CI 会继续运行。

**Q: 支持其他 CI 系统吗？**  
A: 目前只支持 GitHub Actions。其他 CI 需要修改脚本。

**Q: 可以在 CI 中使用吗？**  
A: 不建议。这个工具是为本地开发设计的。

---

## 相关资源

- [GitHub CLI 文档](https://cli.github.com/manual/)
- [GitHub Actions 文档](https://docs.github.com/actions)
- [Ruff 文档](https://docs.astral.sh/ruff/)
- [ESLint 文档](https://eslint.org/docs/)

---

**版本**: 1.0.0  
**最后更新**: 2026-03-01  
**维护者**: proecheng
