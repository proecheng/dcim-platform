"""测试降采样功能"""
import asyncio
from datetime import datetime, timedelta
import sys
sys.path.insert(0, 'backend')

from app.services.ingest_pipeline import process_payload, IngestPoint
from app.core.database import async_session
from app.models.point import Point, PointHistory
from sqlalchemy import select, func

async def test_downsampling():
    """测试降采样逻辑"""
    
    # 1. 查找一个AI点位
    async with async_session() as session:
        result = await session.execute(
            select(Point).where(Point.point_type == "AI", Point.is_enabled == True).limit(1)
        )
        point = result.scalar_one_or_none()
        
        if not point:
            print("❌ 没有找到可用的AI点位，请先加载演示数据")
            return
        
        print(f"✓ 测试点位: {point.point_code} ({point.point_name})")
        print(f"  collect_interval: {point.collect_interval}秒")
        print(f"  store_interval: {point.store_interval}秒")
        print()
        
        # 2. 清空该点位的历史数据
        await session.execute(
            PointHistory.__table__.delete().where(PointHistory.point_id == point.id)
        )
        await session.commit()
        print("✓ 已清空测试点位的历史数据")
        print()
        
    # 3. 模拟连续写入（每60秒一次，共10次）
    print("开始模拟数据写入...")
    base_time = datetime.now() - timedelta(minutes=10)
    
    for i in range(10):
        timestamp = base_time + timedelta(seconds=i * 60)
        value = 20.0 + i * 0.5
        
        ingest_point = IngestPoint(
            point_id=point.id,
            value=value,
            timestamp=timestamp,
            source="test"
        )
        
        result = await process_payload([ingest_point])
        print(f"  [{i+1}/10] 时间: {timestamp.strftime('%H:%M:%S')}, 值: {value:.1f}, 写入: {result.written}")
    
    print()
    
    # 4. 检查实际存储的历史记录数
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(PointHistory).where(PointHistory.point_id == point.id)
        )
        history_count = result.scalar()
        
        result = await session.execute(
            select(PointHistory.recorded_at, PointHistory.value)
            .where(PointHistory.point_id == point.id)
            .order_by(PointHistory.recorded_at)
        )
        records = result.all()
        
        print(f"✓ 历史记录数: {history_count}")
        print(f"  预期: 2-3 条（降采样间隔 {point.store_interval}秒）")
        print()
        
        if records:
            print("存储的记录:")
            for i, (ts, val) in enumerate(records):
                print(f"  {i+1}. {ts.strftime('%H:%M:%S')} - {val:.1f}")
            print()
        
        # 5. 验证降采样效果
        if history_count <= 3:
            print("✅ 降采样功能正常！")
            print(f"   写入10次，实际存储{history_count}条，降采样率: {(1 - history_count/10)*100:.0f}%")
        else:
            print("⚠️  降采样可能未生效")
            print(f"   写入10次，实际存储{history_count}条")

if __name__ == "__main__":
    asyncio.run(test_downsampling())
