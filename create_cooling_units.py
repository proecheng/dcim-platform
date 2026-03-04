"""创建cooling_units表"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import engine
from sqlalchemy import text

async def create_cooling_units():
    async with engine.begin() as conn:
        # 创建 cooling_groups 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cooling_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name VARCHAR(100) NOT NULL,
                group_mode VARCHAR(20) DEFAULT 'independent',
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        print("cooling_groups 表创建成功")
        
        # 创建 cooling_units 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cooling_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                unit_type VARCHAR(20) DEFAULT 'indoor',
                cooling_capacity_kw FLOAT,
                refrigerant_type VARCHAR(20),
                compressor_count INTEGER DEFAULT 1,
                fan_count INTEGER DEFAULT 2,
                group_id INTEGER,
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (group_id) REFERENCES cooling_groups(id)
            )
        """))
        print("cooling_units 表创建成功")

if __name__ == "__main__":
    asyncio.run(create_cooling_units())
