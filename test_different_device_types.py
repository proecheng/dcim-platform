"""测试不同设备类型的约束计算"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models import PowerDevice
from app.services.datacenter_shift_strategy import calculate_shift_recommendation
from sqlalchemy import select

async def test_device_types():
    async with async_session() as db:
        # 测试不同设备类型
        device_types = ['AC', 'UPS', 'IT_SERVER', 'PUMP', 'LIGHTING']
        
        for device_type in device_types:
            print(f"\n{'='*60}")
            print(f"Testing device type: {device_type}")
            print('='*60)
            
            # 查找该类型的设备
            result = await db.execute(
                select(PowerDevice)
                .where(PowerDevice.device_type == device_type)
                .limit(1)
            )
            device = result.scalar_one_or_none()
            
            if not device:
                print(f"[SKIP] No device found for type {device_type}")
                continue
            
            print(f"Device: {device.device_name} (ID: {device.id})")
            print(f"Rated Power: {device.rated_power} kW")
            print(f"Area: {device.area_code}")
            
            try:
                # 调用算法
                recommendation = await calculate_shift_recommendation(
                    db, device, target_reduction_ratio=0.3
                )
                
                print(f"\nRecommended Ratio: {recommendation.recommended_ratio * 100:.1f}%")
                print(f"Limiting Factor: {recommendation.limiting_factor}")
                
                # 显示约束
                if recommendation.constraints:
                    print("\nConstraints:")
                    for name, constraint in recommendation.constraints.items():
                        if hasattr(constraint, 'max_reduction_ratio'):
                            ratio = constraint.max_reduction_ratio * 100
                        elif isinstance(constraint, dict):
                            ratio = constraint.get('max_reduction_ratio', 0) * 100
                        else:
                            ratio = 0
                        print(f"  {name}: {ratio:.1f}%")
                
                # 显示警告
                if recommendation.warnings:
                    print("\nWarnings:")
                    for warning in recommendation.warnings:
                        print(f"  - {warning[:100]}")
                
                print("[SUCCESS]")
                
            except Exception as e:
                print(f"[ERROR] {str(e)[:200]}")

if __name__ == "__main__":
    asyncio.run(test_device_types())
