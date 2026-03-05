"""检查数据库实际记录数"""
import asyncio
from app.core.database import async_session
from app.models import PointHistory
from sqlalchemy import select, func

async def check():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(PointHistory))
        count = result.scalar()
        print(f'实际记录数: {count:,}')
        return count

if __name__ == "__main__":
    asyncio.run(check())
