"""手动创建表"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session, engine
from app.models.topology_config import CabinetTemperatureSensor, CabinetITLoad
from sqlalchemy import text

async def create_tables():
    async with engine.begin() as conn:
        # 创建 cabinet_temperature_sensors 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cabinet_temperature_sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cabinet_id INTEGER NOT NULL,
                point_id INTEGER,
                sensor_location VARCHAR(20) NOT NULL,
                temp_warning_threshold FLOAT DEFAULT 27.0,
                temp_critical_threshold FLOAT DEFAULT 32.0,
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (cabinet_id) REFERENCES cabinets(id) ON DELETE CASCADE,
                FOREIGN KEY (point_id) REFERENCES points(id) ON DELETE SET NULL,
                UNIQUE (cabinet_id, sensor_location)
            )
        """))
        print("cabinet_temperature_sensors 表创建成功")
        
        # 创建 cabinet_it_loads 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cabinet_it_loads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cabinet_id INTEGER NOT NULL UNIQUE,
                power_point_id INTEGER,
                rated_power_kw FLOAT,
                design_load_kw FLOAT,
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (cabinet_id) REFERENCES cabinets(id) ON DELETE CASCADE,
                FOREIGN KEY (power_point_id) REFERENCES points(id) ON DELETE SET NULL
            )
        """))
        print("cabinet_it_loads 表创建成功")
        
        # 检查 cooling_zone_units 表是否有 is_primary 字段
        result = await conn.execute(text("PRAGMA table_info(cooling_zone_units)"))
        columns = result.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'is_primary' not in column_names:
            # SQLite 不支持 ADD COLUMN，需要重建表
            print("cooling_zone_units 表缺少 is_primary 字段，需要手动添加")
        else:
            print("cooling_zone_units 表已有 is_primary 字段")

if __name__ == "__main__":
    asyncio.run(create_tables())
