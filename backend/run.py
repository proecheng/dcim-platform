"""
启动脚本 - 初始化点位并启动服务
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from init_points import init_points


async def main():
    print("=" * 50)
    print("算力中心智能监控系统 - 初始化")
    print("=" * 50)

    # 初始化点位
    await init_points()

    print("\n初始化完成！")
    print("\n启动后端服务:")
    print("  cd backend")
    print("  pip install -r requirements.txt")
    print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8080")
    print("\n启动前端服务:")
    print("  cd frontend")
    print("  npm install")
    print("  npm run dev")
    print("\n访问地址:")
    print("  前端: http://localhost:3000")
    print("  后端API: http://localhost:8080")
    print("  API文档: http://localhost:8080/docs")
    print("\n默认账户: admin / admin123")


if __name__ == "__main__":
    asyncio.run(main())
