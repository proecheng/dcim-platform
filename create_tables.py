import sys
sys.path.insert(0, 'D:/mytest1/backend')

import asyncio
from app.core.database import engine, Base
from app.models import *  # 导入所有模型

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建成功")

if __name__ == '__main__':
    asyncio.run(create_tables())
