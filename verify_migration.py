"""验证新表是否创建成功"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from sqlalchemy import text

async def verify_tables():
    async with async_session() as db:
        # 检查 cabinet_temperature_sensors 表
        result = await db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cabinet_temperature_sensors'"
        ))
        temp_table = result.scalar()
        print(f"cabinet_temperature_sensors 表: {'[OK]' if temp_table else '[MISSING]'}")
        
        # 检查 cabinet_it_loads 表
        result = await db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cabinet_it_loads'"
        ))
        load_table = result.scalar()
        print(f"cabinet_it_loads 表: {'[OK]' if load_table else '[MISSING]'}")
        
        # 检查 cooling_zone_units 表的新字段
        result = await db.execute(text(
            "PRAGMA table_info(cooling_zone_units)"
        ))
        columns = result.fetchall()
        column_names = [col[1] for col in columns]
        print(f"\ncooling_zone_units 表字段: {', '.join(column_names)}")
        print(f"is_primary 字段: {'[OK]' if 'is_primary' in column_names else '[MISSING]'}")

if __name__ == "__main__":
    asyncio.run(verify_tables())
