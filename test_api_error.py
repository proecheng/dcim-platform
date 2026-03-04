"""
测试 shift-ratio API 错误
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.device_regulation_service import DeviceRegulationService

async def test_recommendations():
    # 创建数据库连接
    engine = create_async_engine('sqlite+aiosqlite:///backend/dcim.db', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = DeviceRegulationService(session)
        try:
            result = await service.get_ratio_recommendations(days=30)
            print("[OK] API call successful")
            print(f"Total devices: {result['total_devices']}")
            print(f"Devices with changes: {result['devices_with_change']}")
        except Exception as e:
            print(f"[ERROR] API call failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_recommendations())
