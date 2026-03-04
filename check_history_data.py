# -*- coding: utf-8 -*-
import asyncio
from backend.app.core.database import async_session
from backend.app.models.history import PointHistory
from sqlalchemy import select, func
from datetime import datetime, timedelta

async def check_history():
    async with async_session() as db:
        # 总记录数
        count = await db.scalar(select(func.count()).select_from(PointHistory))
        print(f'PointHistory 表记录数: {count}')
        
        if count > 0:
            # 最新的 5 条记录
            result = await db.execute(
                select(PointHistory)
                .order_by(PointHistory.recorded_at.desc())
                .limit(5)
            )
            records = result.scalars().all()
            print('\n最新 5 条记录:')
            for r in records:
                print(f'  point_id={r.point_id}, value={r.value}, time={r.recorded_at}')
            
            # 昨天的记录数
            yesterday = datetime.now() - timedelta(days=1)
            start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
            
            yesterday_count = await db.scalar(
                select(func.count())
                .select_from(PointHistory)
                .where(
                    PointHistory.recorded_at >= start_time,
                    PointHistory.recorded_at < end_time
                )
            )
            print(f'\n昨天的记录数: {yesterday_count}')
        else:
            print('\n[WARNING] PointHistory 表为空！')
            print('可能原因：')
            print('  1. 数据模拟器未启动')
            print('  2. 数据模拟器刚启动，还没有积累历史数据')
            print('  3. 只有 AI 类型点位会保存历史数据')

if __name__ == '__main__':
    asyncio.run(check_history())
