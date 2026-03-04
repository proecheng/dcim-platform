"""
测试 F1-AC-003 设备的功率趋势数据
"""
import asyncio
import sys
import json
sys.path.insert(0, 'backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.device_regulation_service import DeviceRegulationService

async def test_f1_ac3():
    engine = create_async_engine('sqlite+aiosqlite:///backend/dcim.db', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = DeviceRegulationService(session)
        
        device_id = 25  # F1-AC-003
        
        print("Testing F1-AC-003 (ID: 25)")
        print("=" * 80)
        
        # 测试30天数据
        print("\n[TEST] Loading 30-day trend...")
        try:
            trend_30 = await service.get_device_power_trend(device_id, 30)
            if trend_30:
                print(f"  [OK] Data loaded")
                print(f"  Device: {trend_30.get('device_name')}")
                print(f"  Days: {trend_30.get('days')}")
                print(f"  Data points: {len(trend_30.get('trend_data', []))}")
                print(f"  Rated power: {trend_30.get('rated_power')} kW")
                print(f"  Has real data: {trend_30.get('summary', {}).get('has_real_data')}")
                
                if trend_30.get('trend_data'):
                    sample = trend_30['trend_data'][0]
                    print(f"\n  Sample data point:")
                    print(f"    date: {sample.get('date')}")
                    print(f"    avg_power: {sample.get('avg_power')}")
                    print(f"    max_power: {sample.get('max_power')}")
                    print(f"    min_power: {sample.get('min_power')}")
                    print(f"    energy: {sample.get('energy')}")
                    print(f"    record_count: {sample.get('record_count')}")
            else:
                print("  [ERROR] No data returned")
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试推荐数据
        print("\n[TEST] Loading shift ratio recommendation...")
        try:
            recommendations = await service.get_ratio_recommendations(days=30)
            
            # 查找 F1-AC-003
            target = None
            for rec in recommendations['recommendations']:
                if rec['device_id'] == device_id:
                    target = rec
                    break
            
            if target:
                print(f"  [OK] Recommendation found")
                print(f"  Device: {target.get('device_name')}")
                print(f"  Current ratio: {target.get('current_ratio')}")
                print(f"  Recommended ratio: {target.get('recommended_ratio')}")
                print(f"  Has change: {target.get('has_change')}")
                print(f"  Confidence: {target.get('confidence')}")
                
                if target.get('calculation_details'):
                    details = target['calculation_details']
                    print(f"\n  Calculation details:")
                    print(f"    Limiting factor: {details.get('limiting_factor')}")
                    print(f"    Warnings: {details.get('warnings')}")
                    
                    if details.get('constraints'):
                        print(f"    Constraints:")
                        for name, constraint in details['constraints'].items():
                            print(f"      {name}: max_ratio={constraint.get('max_ratio')}, reason={constraint.get('reason')}")
            else:
                print(f"  [ERROR] Device not found in recommendations")
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_f1_ac3())
