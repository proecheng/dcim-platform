"""检查cooling_zone_units表"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from sqlalchemy import text

async def check_table():
    async with async_session() as db:
        # 检查表是否存在
        result = await db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cooling_zone_units'"
        ))
        table_exists = result.scalar()
        print(f"cooling_zone_units table exists: {table_exists is not None}")
        
        if table_exists:
            # 获取表结构
            result = await db.execute(text("PRAGMA table_info(cooling_zone_units)"))
            columns = result.fetchall()
            print(f"\nColumns ({len(columns)}):")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")

if __name__ == "__main__":
    asyncio.run(check_table())
