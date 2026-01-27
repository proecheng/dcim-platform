#!/bin/bash
echo "================================================"
echo "  算力中心智能监控系统 - 启动脚本 (Linux/Mac)"
echo "================================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python，请先安装 Python 3.9+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

echo "[1/4] 安装后端依赖..."
cd backend
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q

echo "[2/4] 初始化数据库..."
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

echo "[3/4] 安装前端依赖..."
cd ../frontend
if [ ! -d "node_modules" ]; then
    npm install
fi

echo "[4/4] 启动服务..."
echo ""
echo "启动后端服务 (端口 8080)..."
cd ../backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

sleep 3

echo "启动前端服务 (端口 3000)..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "================================================"
echo "  服务启动完成！"
echo "================================================"
echo "  前端地址: http://localhost:3000"
echo "  后端API:  http://localhost:8080"
echo "  API文档:  http://localhost:8080/docs"
echo "  默认账户: admin / admin123"
echo "================================================"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# 等待后台进程
wait
