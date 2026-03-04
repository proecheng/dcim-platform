"""
测试30/90天切换功能
"""
import asyncio
import sys
import json
sys.path.insert(0, 'backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.device_regulation_service import DeviceRegulationService

async def test_power_trend():
    engine = create_async_engine('sqlite+aiosqlite:///backend/dcim.db', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = DeviceRegulationService(session)
        
        # 获取第一个设备
        result = await service.get_ratio_recommendations(days=30)
        if not result['recommendations']:
            print("[ERROR] No devices found")
            return
        
        device_id = result['recommendations'][0]['device_id']
        device_name = result['recommendations'][0]['device_name']
        
        print(f"Testing device: {device_name} (ID: {device_id})")
        print("=" * 80)
        
        # 测试30天
        print("\n[TEST] 30天数据:")
        trend_30 = await service.get_device_power_trend(device_id, 30)
        if trend_30:
            print(f"  days: {trend_30.get('days')}")
            print(f"  trend_data length: {len(trend_30.get('trend_data', []))}")
            if trend_30.get('trend_data'):
                sample = trend_30['trend_data'][0]
                print(f"  Sample data point:")
                print(f"    date: {sample.get('date')}")
                print(f"    avg_power: {sample.get('avg_power')}")
                print(f"    max_power: {sample.get('max_power')}")
                print(f"    min_power: {sample.get('min_power')}")
                print(f"    energy: {sample.get('energy')}")
        else:
            print("  [ERROR] No data returned")
        
        # 测试90天
        print("\n[TEST] 90天数据:")
        trend_90 = await service.get_device_power_trend(device_id, 90)
        if trend_90:
            print(f"  days: {trend_90.get('days')}")
            print(f"  trend_data length: {len(trend_90.get('trend_data', []))}")
            if trend_90.get('trend_data'):
                sample = trend_90['trend_data'][0]
                print(f"  Sample data point:")
                print(f"    date: {sample.get('date')}")
                print(f"    avg_power: {sample.get('avg_power')}")
                print(f"    max_power: {sample.get('max_power')}")
                print(f"    min_power: {sample.get('min_power')}")
                print(f"    energy: {sample.get('energy')}")
        else:
            print("  [ERROR] No data returned")
        
        print("\n" + "=" * 80)
        print("[OK] Test completed successfully!")

if __name__ == '__main__':
    asyncio.run(test_power_trend())
