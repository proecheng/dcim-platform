"""检查设备数据和功率点配置"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models import PowerDevice, Point, PointHistory
from sqlalchemy import select, func

async def check_device():
    async with async_session() as db:
        # 检查设备9
        result = await db.execute(select(PowerDevice).where(PowerDevice.id == 9))
        device = result.scalar_one_or_none()
        
        if device:
            print(f"设备: {device.device_name}")
            print(f"设备代码: {device.device_code}")
            print(f"功率点ID: {device.power_point_id}")
            
            if device.power_point_id:
                # 检查功率点
                result = await db.execute(select(Point).where(Point.id == device.power_point_id))
                point = result.scalar_one_or_none()
                
                if point:
                    print(f"功率点: {point.point_name} ({point.point_code})")
                    
                    # 检查历史数据
                    result = await db.execute(
                        select(func.count(PointHistory.id))
                        .where(PointHistory.point_id == device.power_point_id)
                    )
                    count = result.scalar()
                    print(f"历史记录数: {count}")
                    
                    if count > 0:
                        # 获取最新记录
                        result = await db.execute(
                            select(PointHistory)
                            .where(PointHistory.point_id == device.power_point_id)
                            .order_by(PointHistory.timestamp.desc())
                            .limit(1)
                        )
                        latest = result.scalar_one_or_none()
                        if latest:
                            print(f"最新记录: {latest.timestamp}, 值: {latest.value}")
                else:
                    print("功率点不存在")
            else:
                print("未配置功率点")
        else:
            print("设备不存在")

if __name__ == "__main__":
    asyncio.run(check_device())
