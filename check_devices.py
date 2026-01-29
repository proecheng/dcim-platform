"""
检查现有设备编码
"""
import asyncio
import sys
sys.path.insert(0, 'D:/mytest1/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:///D:/mytest1/backend/dcim.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def check_devices():
    """检查设备数据"""
    print("=" * 60)
    print("检查数据库中的设备")
    print("=" * 60)

    async with async_session_maker() as db:
        result = await db.execute(text("SELECT id, device_code, device_name, device_type, circuit_id FROM power_devices ORDER BY id"))
        devices = result.fetchall()

        print(f"找到 {len(devices)} 个设备:")
        for d in devices:
            print(f"  ID={d[0]}, code={d[1]}, name={d[2]}, type={d[3]}, circuit_id={d[4]}")

        # 检查编码模式
        print("\n编码分析:")
        codes = [d[1] for d in devices]
        for prefix in ['SRV-', 'AC-', 'UPS-', 'DEV-', 'LIGHT-', 'IT-', 'TEST-']:
            matching = [c for c in codes if c and c.startswith(prefix)]
            if matching:
                print(f"  {prefix}*: {len(matching)} 个 - {matching[:3]}...")

if __name__ == "__main__":
    asyncio.run(check_devices())
