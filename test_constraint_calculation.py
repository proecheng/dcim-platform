"""直接测试约束计算算法"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models import PowerDevice
from app.services.datacenter_shift_strategy import calculate_shift_recommendation
from sqlalchemy import select

async def test_constraint_calculation():
    async with async_session() as db:
        # 获取一个空调设备
        result = await db.execute(
            select(PowerDevice)
            .where(PowerDevice.device_type == 'AC')
            .limit(1)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            print("未找到空调设备")
            return
        
        print(f"测试设备: {device.device_name} (ID: {device.id})")
        print(f"设备类型: {device.device_type}")
        print(f"额定功率: {device.rated_power} kW")
        print()
        
        # 调用新算法
        try:
            recommendation = await calculate_shift_recommendation(
                db, device, target_reduction_ratio=0.3
            )
            
            print("=" * 60)
            print("约束计算结果:")
            print("=" * 60)
            print(f"推荐转移比例: {recommendation.recommended_ratio * 100:.1f}%")
            print(f"主要限制因素: {recommendation.limiting_factor}")
            print()
            
            print("各约束详情:")
            print("-" * 60)
            
            # 温度约束
            if 'temperature' in recommendation.constraints:
                temp = recommendation.constraints['temperature']
                print(f"[温度约束]")
                print(f"  最大转移比例: {temp.max_reduction_ratio * 100:.1f}%")
                print(f"  原因: {temp.reason}")
                print(f"  当前温度: {temp.current_temps}")
                print(f"  受影响机柜: {', '.join(temp.affected_cabinets) if temp.affected_cabinets else '无'}")
                print()
            
            # 冗余约束
            if 'redundancy' in recommendation.constraints:
                red = recommendation.constraints['redundancy']
                print(f"[冗余约束]")
                print(f"  最大转移比例: {red.max_reduction_ratio * 100:.1f}%")
                print(f"  原因: {red.reason}")
                print(f"  冗余组设备: {len(red.redundancy_group)}个")
                print(f"  总容量: {red.total_capacity:.1f} kW")
                print(f"  当前负载: {red.current_load:.1f} kW")
                print(f"  N+1容量: {red.n_plus_one_capacity:.1f} kW")
                print()
            
            # PUE约束
            if 'pue' in recommendation.constraints:
                pue = recommendation.constraints['pue']
                print(f"[PUE约束]")
                print(f"  最大转移比例: {pue.max_reduction_ratio * 100:.1f}%")
                print(f"  原因: {pue.reason}")
                print(f"  当前PUE: {pue.current_pue:.2f}")
                print(f"  预测PUE: {pue.predicted_pue:.2f}")
                print()
            
            # 设备约束
            if 'device' in recommendation.constraints:
                dev = recommendation.constraints['device']
                print(f"[设备约束]")
                print(f"  最大转移比例: {dev['max_reduction_ratio'] * 100:.1f}%")
                print(f"  原因: {dev['reason']}")
                print()
            
            # 警告信息
            if recommendation.warnings:
                print("警告信息:")
                print("-" * 60)
                for warning in recommendation.warnings:
                    print(f"  [WARNING] {warning}")
            
            print("=" * 60)
            print("[SUCCESS] 约束计算成功")
            
        except Exception as e:
            print(f"[ERROR] 约束计算失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_constraint_calculation())
