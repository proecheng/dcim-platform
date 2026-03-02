#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========================================================"
echo "       算力中心智能监控系统 - 启动脚本 (Linux/Mac)"
echo "                    Startup Script v5.3"
echo "========================================================"
echo ""

echo "[1/7] 检查运行环境..."

# 检查 Python
PYTHON_CMD=""
if [ -f "$SCRIPT_DIR/backend/.venv/bin/python3" ]; then
    PYTHON_CMD="$SCRIPT_DIR/backend/.venv/bin/python3"
    echo "       找到虚拟环境 Python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "[错误] 未找到 Python，请先安装 Python 3.9+"
    exit 1
fi
echo "       使用: $PYTHON_CMD"
$PYTHON_CMD --version

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi
echo "       Node.js $(node --version)"

echo ""
echo "[2/7] 清理占用端口..."

# 清理 8080 端口
echo "       清理端口 8080..."
for pid in $(lsof -ti:8080 2>/dev/null); do
    echo "       杀掉 PID $pid"
    kill -9 "$pid" 2>/dev/null
done

# 清理 3000 端口
echo "       清理端口 3000..."
for pid in $(lsof -ti:3000 2>/dev/null); do
    echo "       杀掉 PID $pid"
    kill -9 "$pid" 2>/dev/null
done

echo "       等待端口释放..."
sleep 3
echo "       端口已清理"

echo ""
echo "[3/7] 检查后端环境..."
cd "$SCRIPT_DIR/backend"

if [ ! -d ".venv" ]; then
    echo "       创建虚拟环境..."
    $PYTHON_CMD -m venv .venv
fi

source .venv/bin/activate

echo "       检查依赖..."
python -c "import uvicorn, fastapi, sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "       安装后端依赖..."
    pip install -r requirements.txt -q
fi
echo "       后端依赖 OK"

echo ""
echo "[4/7] 检查数据库..."
if [ ! -f "dcim.db" ]; then
    echo "       初始化数据库..."
    python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
    echo "       数据库已初始化"
else
    echo "       数据库已存在"
fi

echo ""
echo "[5/7] 检查代理服务..."
cd "$SCRIPT_DIR/proxy"

if [ ! -d "node_modules" ]; then
    echo "       安装代理依赖..."
    npm install
fi
echo "       代理依赖 OK"

echo ""
echo "[6/7] 检查前端环境..."
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "       安装前端依赖..."
    npm install
fi
echo "       前端依赖 OK"

echo ""
echo "[7/7] 检查前端构建..."
if [ ! -f "dist/index.html" ]; then
    echo "       前端未构建，正在构建..."
    npm run build
    echo "       前端构建完成"
else
    echo "       前端构建 OK"
fi

echo ""
echo "========================================================"
echo "                   启动服务"
echo "========================================================"
echo ""

echo "启动后端服务 (端口 8080)..."
cd "$SCRIPT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

echo "等待后端启动..."
sleep 6

echo "启动代理服务 (端口 3000)..."
cd "$SCRIPT_DIR/proxy"
node server.js &
PROXY_PID=$!

sleep 3

echo ""
echo "========================================================"
echo "                  服务启动完成！"
echo "========================================================"
echo ""
echo "  系统入口:    http://localhost:3000"
echo "  大屏展示:    http://localhost:3000/bigscreen"
echo "  API 文档:    http://localhost:8080/docs"
echo ""
echo "  默认账户:    admin / admin123"
echo ""
echo "========================================================"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
trap "kill $BACKEND_PID $PROXY_PID 2>/dev/null; exit" SIGINT SIGTERM

# 等待后台进程
wait
