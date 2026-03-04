"""
测试约束条件数据结构
"""
import asyncio
import sys
import json
sys.path.insert(0, 'backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.device_regulation_service import DeviceRegulationService

async def test_constraints():
    engine = create_async_engine('sqlite+aiosqlite:///backend/dcim.db', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = DeviceRegulationService(session)
        try:
            result = await service.get_ratio_recommendations(days=30)
            
            # 找第一个有 calculation_details 的设备
            for rec in result['recommendations']:
                if rec.get('calculation_details'):
                    print("=" * 80)
                    print(f"设备: {rec['device_name']} ({rec['device_code']})")
                    print("=" * 80)
                    print("\ncalculation_details 结构:")
                    print(json.dumps(rec['calculation_details'], indent=2, ensure_ascii=False))
                    print("\n")
                    
                    # 检查约束字段
                    constraints = rec['calculation_details'].get('constraints', {})
                    print("约束字段:")
                    for name, constraint in constraints.items():
                        print(f"\n  {name}:")
                        print(f"    类型: {type(constraint)}")
                        print(f"    内容: {constraint}")
                        if isinstance(constraint, dict):
                            print(f"    max_ratio: {constraint.get('max_ratio')}")
                            print(f"    reason: {constraint.get('reason')}")
                    
                    break  # 只检查第一个
            
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_constraints())
