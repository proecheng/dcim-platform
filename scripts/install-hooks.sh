#!/bin/bash
# Git Hook 自动安装脚本 (Linux/macOS)

set -e

echo "================================"
echo "Git Hook 自动安装脚本"
echo "================================"
echo ""

# 检查是否在 Git 仓库中
if [ ! -d ".git" ]; then
    echo "❌ 错误: 当前目录不是 Git 仓库"
    exit 1
fi

# 检查 gh CLI
if ! command -v gh &> /dev/null; then
    echo "⚠️  警告: 未安装 GitHub CLI (gh)"
    echo "请访问 https://cli.github.com/ 安装"
    echo ""
    read -p "是否继续安装 hook？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# 创建 hooks 目录（如果不存在）
mkdir -p .git/hooks

# 复制 post-push hook
echo "📝 安装 post-push hook..."
cp scripts/post-push-hook.sh .git/hooks/post-push
chmod +x .git/hooks/post-push

echo "✅ post-push hook 已安装"
echo ""

# 测试 hook
echo "🧪 测试 hook..."
if .git/hooks/post-push; then
    echo "✅ Hook 测试通过"
else
    echo "⚠️  Hook 测试失败，但已安装"
fi

echo ""
echo "================================"
echo "✅ 安装完成！"
echo "================================"
echo ""
echo "现在每次 git push 后会自动监控 CI 运行"
echo ""
echo "手动检查 CI: python scripts/check-ci.py"
echo "卸载 hook:   rm .git/hooks/post-push"
echo ""
