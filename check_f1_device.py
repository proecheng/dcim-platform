"""
检查 F1 精密空调-3 设备数据
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.energy import PowerDevice

async def check_device():
    engine = create_async_engine('sqlite+aiosqlite:///backend/dcim.db', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 查找包含 "F1" 和 "空调" 的设备
        result = await session.execute(
            select(PowerDevice).where(
                PowerDevice.device_name.like('%F1%')
            ).where(
                PowerDevice.device_name.like('%空调%')
            )
        )
        devices = result.scalars().all()
        
        print(f"Found {len(devices)} devices matching 'F1' and '空调':")
        print("=" * 80)
        
        for device in devices:
            print(f"\nID: {device.id}")
            print(f"Code: {device.device_code}")
            print(f"Name: {device.device_name}")
            print(f"Type: {device.device_type}")
            print(f"Rated Power: {device.rated_power} kW")
            print(f"Enabled: {device.is_enabled}")
            print(f"Critical: {device.is_critical}")
            
            # 检查是否有功率点位
            if device.power_point_id:
                print(f"Power Point ID: {device.power_point_id}")
            else:
                print("Power Point ID: None (no power monitoring)")

if __name__ == '__main__':
    asyncio.run(check_device())
