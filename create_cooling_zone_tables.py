"""创建cooling_zone_units表"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import engine
from sqlalchemy import text

async def create_cooling_zone_units():
    async with engine.begin() as conn:
        # 先创建 cooling_zones 表（如果不存在）
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cooling_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_code VARCHAR(50) UNIQUE NOT NULL,
                zone_name VARCHAR(100) NOT NULL,
                room_id INTEGER,
                design_capacity_kw FLOAT,
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            )
        """))
        print("cooling_zones 表创建成功")
        
        # 创建 cooling_zone_cabinets 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cooling_zone_cabinets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                cabinet_id INTEGER NOT NULL,
                FOREIGN KEY (zone_id) REFERENCES cooling_zones(id) ON DELETE CASCADE,
                FOREIGN KEY (cabinet_id) REFERENCES cabinets(id) ON DELETE CASCADE,
                UNIQUE (zone_id, cabinet_id)
            )
        """))
        print("cooling_zone_cabinets 表创建成功")
        
        # 创建 cooling_zone_units 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cooling_zone_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                cooling_unit_id INTEGER NOT NULL,
                is_primary INTEGER DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (zone_id) REFERENCES cooling_zones(id) ON DELETE CASCADE,
                FOREIGN KEY (cooling_unit_id) REFERENCES cooling_units(id) ON DELETE CASCADE,
                UNIQUE (zone_id, cooling_unit_id)
            )
        """))
        print("cooling_zone_units 表创建成功")

if __name__ == "__main__":
    asyncio.run(create_cooling_zone_units())
