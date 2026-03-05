"""计算预期的历史记录数"""
import asyncio
from app.core.database import async_session
from app.models import Point
from sqlalchemy import select, func

async def calculate_expected():
    async with async_session() as session:
        # 统计启用的点位数
        result = await session.execute(
            select(func.count()).select_from(Point).where(Point.is_enabled == True)
        )
        enabled_points = result.scalar()
        
        print(f"启用的点位数: {enabled_points:,}")
        
        # 计算预期记录数
        days = 30
        store_interval = 900  # 15 分钟
        
        # 每个点位的记录数 = 30 天 × 24 小时 × 3600 秒 / 900 秒
        records_per_point = (days * 24 * 3600) // store_interval
        total_expected = enabled_points * records_per_point
        
        print(f"\n配置:")
        print(f"  天数: {days} 天")
        print(f"  存储间隔: {store_interval} 秒 (15 分钟)")
        print(f"\n预期:")
        print(f"  每点位记录数: {records_per_point:,}")
        print(f"  总记录数: {total_expected:,}")
        print(f"\n对比:")
        print(f"  旧方案 (按小时): {enabled_points * days * 24:,} 条")
        print(f"  新方案 (15分钟): {total_expected:,} 条")
        print(f"  增加: {((total_expected - enabled_points * days * 24) / (enabled_points * days * 24) * 100):.1f}%")

if __name__ == "__main__":
    asyncio.run(calculate_expected())
