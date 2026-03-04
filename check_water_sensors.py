# -*- coding: utf-8 -*-
import asyncio
from backend.app.core.database import async_session
from backend.app.models.point import Point
from sqlalchemy import select

async def check_water_sensors():
    async with async_session() as db:
        result = await db.execute(select(Point).where(Point.device_type == 'WATER'))
        points = result.scalars().all()
        print(f'WATER 传感器数量: {len(points)}')
        
        if points:
            print('\n前 5 个 WATER 传感器:')
            for p in points[:5]:
                print(f'  - {p.point_code}: {p.point_name} ({p.device_type})')
        else:
            print('\n数据库中没有 WATER 类型的传感器！')
            
            # 检查所有设备类型
            result_all = await db.execute(select(Point.device_type).distinct())
            device_types = result_all.scalars().all()
            print(f'\n数据库中存在的设备类型: {sorted(device_types)}')

if __name__ == '__main__':
    asyncio.run(check_water_sensors())
