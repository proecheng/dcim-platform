"""优化配置总结与验证"""
import asyncio
from app.core.database import async_session
from app.models import Point, PointHistory
from sqlalchemy import select, func

async def generate_report():
    print("=" * 60)
    print("演示数据优化配置报告")
    print("=" * 60)
    
    async with async_session() as session:
        # 统计点位
        result = await session.execute(
            select(func.count()).select_from(Point).where(Point.is_enabled == True)
        )
        enabled_points = result.scalar()
        
        # 统计当前历史记录
        result = await session.execute(select(func.count()).select_from(PointHistory))
        current_records = result.scalar()
        
        print(f"\n【点位统计】")
        print(f"  启用点位数: {enabled_points:,}")
        
        print(f"\n【当前数据】")
        print(f"  历史记录数: {current_records:,}")
        
        print(f"\n【配置方案】")
        print(f"  实时采集:")
        print(f"    - 采集间隔: 60 秒")
        print(f"    - 存储间隔: 300 秒 (5 分钟)")
        print(f"    - 降采样率: 80% (每 5 条采集数据存储 1 条)")
        print(f"  ")
        print(f"  历史数据:")
        print(f"    - 生成间隔: 900 秒 (15 分钟)")
        print(f"    - 保留天数: 30 天 (软限制)")
        print(f"    - 硬限制: 60 天 (自动清理)")
        
        print(f"\n【预期数据量】")
        days = 30
        
        # 历史数据（15分钟间隔）
        history_interval = 900
        records_per_point_history = (days * 24 * 3600) // history_interval
        total_history = enabled_points * records_per_point_history
        
        print(f"  30 天历史数据:")
        print(f"    - 每点位: {records_per_point_history:,} 条")
        print(f"    - 总计: {total_history:,} 条")
        print(f"    - 预估大小: ~{total_history * 50 / 1024 / 1024:.1f} MB")
        
        # 实时数据增长（5分钟间隔）
        realtime_interval = 300
        records_per_day = (24 * 3600) // realtime_interval
        daily_growth = enabled_points * records_per_day
        
        print(f"  ")
        print(f"  每日新增 (实时采集):")
        print(f"    - 每点位: {records_per_day:,} 条/天")
        print(f"    - 总计: {daily_growth:,} 条/天")
        print(f"    - 预估大小: ~{daily_growth * 50 / 1024 / 1024:.1f} MB/天")
        
        print(f"\n【对比分析】")
        old_records = enabled_points * days * 24  # 旧方案：1小时间隔
        print(f"  旧方案 (1小时间隔): {old_records:,} 条")
        print(f"  新方案 (15分钟间隔): {total_history:,} 条")
        print(f"  增加: {((total_history - old_records) / old_records * 100):.1f}%")
        
        print(f"\n【自动清理机制】")
        print(f"  - 每日 02:00 自动清理")
        print(f"  - 保留最近 30 天数据")
        print(f"  - 超过 60 天强制删除")
        print(f"  - 清理后记录数据库大小")
        
        print(f"\n【下一步操作】")
        if current_records == 0:
            print(f"  [OK] 旧数据已清理")
            print(f"  -> 请通过浏览器或 API 重新加载演示数据")
            print(f"  -> POST http://localhost:8080/api/v1/demo/load")
        else:
            print(f"  [!] 当前有 {current_records:,} 条历史记录")
            print(f"  -> 如需重新加载，请先运行: python clean_and_reload.py")
            print(f"  → 如需重新加载，请先运行: python clean_and_reload.py")
        
        print(f"\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(generate_report())
