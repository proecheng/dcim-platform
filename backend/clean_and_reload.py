"""清理旧历史数据并重新加载"""
import asyncio
from app.core.database import async_session
from app.models import PointHistory
from sqlalchemy import delete

async def clean_and_reload():
    async with async_session() as session:
        # 1. 删除所有历史数据
        print("正在删除旧历史数据...")
        result = await session.execute(delete(PointHistory))
        await session.commit()
        print(f"已删除 {result.rowcount:,} 条历史记录")
        
        # 2. 触发重新加载
        print("\n现在请通过浏览器或 API 重新加载演示数据")
        print("POST http://localhost:8080/api/v1/demo/load")

if __name__ == "__main__":
    asyncio.run(clean_and_reload())
