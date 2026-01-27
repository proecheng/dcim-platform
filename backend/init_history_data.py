"""
历史数据初始化脚本
生成30天的模拟历史数据用于系统展示
"""
import asyncio
import sys

from app.core.database import init_db
from app.services.history_generator import run_history_generation


async def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    print(f"=== 算力中心智能监控系统 - 历史数据初始化 ===")
    print(f"将生成 {days} 天的历史数据...")
    print()

    await init_db()
    await run_history_generation(days=days)

    print()
    print("=== 初始化完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
