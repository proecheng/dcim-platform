"""
检查数据库中的回路数据
"""
import asyncio
import sys
sys.path.insert(0, 'D:/mytest1/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

DATABASE_URL = "sqlite+aiosqlite:///D:/mytest1/backend/dcim.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def check_circuits():
    """检查回路数据"""
    print("=" * 60)
    print("检查数据库中的回路")
    print("=" * 60)

    async with async_session_maker() as db:
        # 查询回路
        result = await db.execute(text("SELECT id, circuit_code, circuit_name, panel_id FROM distribution_circuits LIMIT 20"))
        circuits = result.fetchall()

        print(f"找到 {len(circuits)} 个回路:")
        for c in circuits:
            print(f"  ID={c[0]}, code={c[1]}, name={c[2]}, panel_id={c[3]}")

        # 查询配电柜
        print("\n" + "=" * 60)
        print("检查数据库中的配电柜")
        print("=" * 60)
        result = await db.execute(text("SELECT id, panel_code, panel_name, meter_point_id FROM distribution_panels LIMIT 20"))
        panels = result.fetchall()

        print(f"找到 {len(panels)} 个配电柜:")
        for p in panels:
            print(f"  ID={p[0]}, code={p[1]}, name={p[2]}, meter_point_id={p[3]}")

if __name__ == "__main__":
    asyncio.run(check_circuits())
