"""监控数据库大小和增长情况"""
import asyncio
import os
from datetime import datetime, timedelta
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models import Point, PointHistory
from sqlalchemy import select, func

async def monitor_database():
    """监控数据库状态"""
    
    print("=" * 70)
    print("数据库监控报告")
    print("=" * 70)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 数据库文件大小
    db_path = 'dcim.db'
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / 1024 / 1024
        size_gb = size_bytes / 1024 / 1024 / 1024
        
        print("📊 数据库文件")
        print(f"  路径: {os.path.abspath(db_path)}")
        print(f"  大小: {size_mb:.2f} MB ({size_gb:.3f} GB)")
        print()
    else:
        print("❌ 数据库文件不存在")
        return
    
    async with async_session() as session:
        # 2. 点位统计
        result = await session.execute(
            select(
                Point.point_type,
                func.count(Point.id)
            ).group_by(Point.point_type)
        )
        
        print("📍 点位统计")
        total_points = 0
        for point_type, count in result.all():
            print(f"  {point_type}: {count} 个")
            total_points += count
        print(f"  总计: {total_points} 个")
        print()
        
        # 3. 历史数据统计
        result = await session.execute(
            select(func.count()).select_from(PointHistory)
        )
        history_count = result.scalar()
        
        result = await session.execute(
            select(
                func.min(PointHistory.recorded_at),
                func.max(PointHistory.recorded_at)
            )
        )
        min_time, max_time = result.one()
        
        print("📈 历史数据")
        print(f"  记录总数: {history_count:,} 条")
        if min_time and max_time:
            days = (max_time - min_time).days
            print(f"  时间范围: {min_time.strftime('%Y-%m-%d')} ~ {max_time.strftime('%Y-%m-%d')}")
            print(f"  跨度天数: {days} 天")
            
            # 计算平均每天记录数
            if days > 0:
                avg_per_day = history_count / days
                print(f"  平均每天: {avg_per_day:,.0f} 条")
        print()
        
        # 4. 存储效率分析
        if history_count > 0:
            bytes_per_record = size_bytes / history_count
            print("💾 存储效率")
            print(f"  每条记录: {bytes_per_record:.1f} 字节")
            print(f"  100万条记录: {bytes_per_record * 1000000 / 1024 / 1024:.2f} MB")
            print()
        
        # 5. 增长预测
        if min_time and max_time and days > 0:
            avg_per_day = history_count / days
            mb_per_day = (size_mb / days) if days > 0 else 0
            
            print("📊 增长预测（基于当前数据）")
            print(f"  每天新增: {avg_per_day:,.0f} 条记录 ({mb_per_day:.2f} MB)")
            print(f"  7天预计: {avg_per_day * 7:,.0f} 条 ({mb_per_day * 7:.2f} MB)")
            print(f"  30天预计: {avg_per_day * 30:,.0f} 条 ({mb_per_day * 30:.2f} MB)")
            print(f"  60天预计: {avg_per_day * 60:,.0f} 条 ({mb_per_day * 60:.2f} MB)")
            print()
        
        # 6. 配置检查
        result = await session.execute(
            select(
                Point.collect_interval,
                Point.store_interval,
                func.count()
            ).where(Point.point_type == 'AI')
            .group_by(Point.collect_interval, Point.store_interval)
        )
        
        print("⚙️  点位配置（AI类型）")
        for collect, store, count in result.all():
            print(f"  collect={collect}s, store={store}s: {count} 个点位")
        print()
        
        # 7. 健康检查
        print("✅ 健康检查")
        
        # 检查是否超过60天
        if min_time and max_time:
            if days > 60:
                print(f"  ⚠️  数据跨度 {days} 天，超过60天限制")
            else:
                print(f"  ✓ 数据跨度 {days} 天，在60天限制内")
        
        # 检查数据库大小
        if size_gb > 5:
            print(f"  ⚠️  数据库大小 {size_gb:.2f} GB，建议清理")
        elif size_gb > 10:
            print(f"  ❌ 数据库大小 {size_gb:.2f} GB，需要立即清理")
        else:
            print(f"  ✓ 数据库大小 {size_gb:.2f} GB，正常")
        
        print()
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(monitor_database())
