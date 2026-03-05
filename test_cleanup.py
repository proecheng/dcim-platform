"""测试历史数据清理功能"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models.point import PointHistory
from app.core.config import get_settings

async def test_cleanup():
    settings = get_settings()
    
    async with async_session() as session:
        # 统计总记录数
        result = await session.execute(select(PointHistory))
        total_count = len(result.all())
        print(f"历史记录总数: {total_count}")
        
        # 统计过期记录数
        cutoff = datetime.now() - timedelta(days=settings.data_retention_days)
        result = await session.execute(
            select(PointHistory).where(PointHistory.recorded_at < cutoff)
        )
        expired_count = len(result.all())
        print(f"过期记录数 (>{settings.data_retention_days}天): {expired_count}")
        
        if expired_count > 0:
            print(f"\n将清理 {cutoff.strftime('%Y-%m-%d %H:%M:%S')} 之前的数据")
            confirm = input("是否执行清理? (y/n): ")
            
            if confirm.lower() == 'y':
                result = await session.execute(
                    delete(PointHistory).where(PointHistory.recorded_at < cutoff)
                )
                deleted_count = result.rowcount
                await session.commit()
                print(f"✓ 清理完成，删除 {deleted_count} 条记录")
            else:
                print("已取消")
        else:
            print("\n✓ 没有需要清理的过期数据")

if __name__ == "__main__":
    asyncio.run(test_cleanup())
