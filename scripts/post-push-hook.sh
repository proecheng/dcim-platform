#!/bin/bash
# Git Post-Push Hook - 自动监控 GitHub Actions CI 运行结果
# 
# 安装方法:
#   1. 将此文件复制到 .git/hooks/post-push
#   2. chmod +x .git/hooks/post-push
#
# 功能:
#   - 自动监控 CI 运行状态
#   - 失败时显示详细错误信息
#   - 解析 Ruff 和 ESLint 错误

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 代码已推送到 GitHub${NC}"
echo -e "${BLUE}📊 正在监控 CI 运行...${NC}"
echo ""

# 检查是否安装了 gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ 错误: 未安装 GitHub CLI (gh)${NC}"
    echo -e "${YELLOW}请访问 https://cli.github.com/ 安装${NC}"
    exit 0
fi

# 检查是否已认证
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ 错误: GitHub CLI 未认证${NC}"
    echo -e "${YELLOW}请运行: gh auth login${NC}"
    exit 0
fi

# 等待工作流开始（最多等待 10 秒）
echo -e "${YELLOW}⏳ 等待 CI 工作流启动...${NC}"
sleep 5

# 获取最新的工作流运行
echo -e "${BLUE}📋 获取最新的 CI 运行...${NC}"
RUN_INFO=$(gh run list --limit 1 --json databaseId,status,conclusion,name,headBranch 2>/dev/null)

if [ -z "$RUN_INFO" ] || [ "$RUN_INFO" = "[]" ]; then
    echo -e "${YELLOW}⚠️  未找到 CI 运行记录${NC}"
    echo -e "${YELLOW}提示: CI 可能还未开始，请稍后手动检查${NC}"
    echo -e "${BLUE}命令: gh run list${NC}"
    exit 0
fi

RUN_ID=$(echo "$RUN_INFO" | jq -r '.[0].databaseId')
RUN_STATUS=$(echo "$RUN_INFO" | jq -r '.[0].status')
RUN_NAME=$(echo "$RUN_INFO" | jq -r '.[0].name')
RUN_BRANCH=$(echo "$RUN_INFO" | jq -r '.[0].headBranch')

echo -e "${BLUE}工作流: ${RUN_NAME}${NC}"
echo -e "${BLUE}分支: ${RUN_BRANCH}${NC}"
echo -e "${BLUE}运行 ID: ${RUN_ID}${NC}"
echo ""

# 如果还在运行，监控进度
if [ "$RUN_STATUS" = "in_progress" ] || [ "$RUN_STATUS" = "queued" ]; then
    echo -e "${YELLOW}⏳ CI 正在运行，实时监控中...${NC}"
    echo -e "${YELLOW}(按 Ctrl+C 可以退出监控，CI 会继续运行)${NC}"
    echo ""
    
    # 使用 gh run watch 监控运行
    if gh run watch $RUN_ID --exit-status 2>/dev/null; then
        echo ""
        echo -e "${GREEN}✅ CI 检查全部通过！${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}❌ CI 检查失败${NC}"
    fi
else
    # 已经完成，检查结果
    RUN_CONCLUSION=$(echo "$RUN_INFO" | jq -r '.[0].conclusion')
    
    if [ "$RUN_CONCLUSION" = "success" ]; then
        echo -e "${GREEN}✅ CI 检查全部通过！${NC}"
        exit 0
    elif [ "$RUN_CONCLUSION" = "failure" ]; then
        echo -e "${RED}❌ CI 检查失败${NC}"
    else
        echo -e "${YELLOW}⚠️  CI 状态: ${RUN_CONCLUSION}${NC}"
        exit 0
    fi
fi

# 获取失败的作业详情
echo ""
echo -e "${BLUE}📄 正在获取失败的作业详情...${NC}"
echo ""

# 获取所有作业
JOBS=$(gh run view $RUN_ID --json jobs --jq '.jobs[] | select(.conclusion == "failure") | {name: .name, id: .databaseId}')

if [ -z "$JOBS" ]; then
    echo -e "${YELLOW}⚠️  未找到失败的作业详情${NC}"
    echo -e "${BLUE}查看完整日志: gh run view $RUN_ID --log${NC}"
    exit 1
fi

# 解析每个失败的作业
echo "$JOBS" | jq -c '.' | while read -r job; do
    JOB_NAME=$(echo "$job" | jq -r '.name')
    JOB_ID=$(echo "$job" | jq -r '.id')
    
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ 失败的作业: ${JOB_NAME}${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # 获取失败步骤的日志
    gh run view $RUN_ID --log-failed | grep -A 50 "$JOB_NAME" | head -100
    
    echo ""
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 查看完整日志:${NC}"
echo -e "${BLUE}   gh run view $RUN_ID --log${NC}"
echo ""
echo -e "${BLUE}🔄 重新运行失败的作业:${NC}"
echo -e "${BLUE}   gh run rerun $RUN_ID --failed${NC}"
echo ""
echo -e "${BLUE}🌐 在浏览器中查看:${NC}"
echo -e "${BLUE}   gh run view $RUN_ID --web${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit 1
