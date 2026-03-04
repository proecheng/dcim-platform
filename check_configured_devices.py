"""检查哪些设备配置了功率点"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models import PowerDevice
from sqlalchemy import select

async def check_devices():
    async with async_session() as db:
        # 获取所有设备
        result = await db.execute(select(PowerDevice))
        devices = result.scalars().all()
        
        print(f"设备总数: {len(devices)}")
        
        # 筛选已配置功率点的设备
        configured = [d for d in devices if d.power_point_id is not None]
        print(f"已配置功率点的设备数: {len(configured)}")
        
        if configured:
            print("\n前10个已配置设备:")
            for d in configured[:10]:
                print(f"ID: {d.id}, Name: {d.device_name}, Type: {d.device_type}, Power Point ID: {d.power_point_id}")

if __name__ == "__main__":
    asyncio.run(check_devices())
