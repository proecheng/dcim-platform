"""
大楼点位初始化脚本 - 初始化约250个监控点位
"""
import asyncio
from datetime import datetime
from app.core.database import async_session, init_db
from app.models import Point, PointRealtime, AlarmThreshold
from app.data.building_points import get_all_points, get_threshold_for_point


async def init_building_points():
    """初始化大楼所有点位"""
    await init_db()

    async with async_session() as session:
        # 检查是否已初始化
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Point.id)))
        existing_count = result.scalar()

        if existing_count > 100:
            print(f"点位已初始化 ({existing_count}个)，跳过")
            return

        points = get_all_points()
        total_created = 0

        for point_type, point_list in points.items():
            for p in point_list:
                # 创建点位
                point = Point(
                    point_code=p["point_code"],
                    point_name=p["point_name"],
                    point_type=point_type,
                    device_type=p["device_type"],
                    area_code=p["point_code"].split("_")[0],  # 从编码提取楼层
                    unit=p.get("unit", ""),
                    data_type=p.get("data_type", "float" if point_type == "AI" else "boolean"),
                    min_range=p.get("min_range"),
                    max_range=p.get("max_range"),
                    collect_interval=p.get("collect_interval", 10),
                    is_enabled=True,
                )
                session.add(point)
                await session.flush()

                # 创建实时数据记录
                realtime = PointRealtime(
                    point_id=point.id,
                    value=0,
                    status="normal",
                )
                session.add(realtime)

                # 创建告警阈值
                thresholds = get_threshold_for_point(p["point_code"], p["point_name"])
                for t in thresholds:
                    threshold = AlarmThreshold(
                        point_id=point.id,
                        threshold_type=t["type"],
                        threshold_value=t["value"],
                        alarm_level=t["level"],
                        alarm_message=t["message"],
                        is_enabled=True,
                    )
                    session.add(threshold)

                total_created += 1

        await session.commit()
        print(f"成功创建 {total_created} 个点位")


if __name__ == "__main__":
    asyncio.run(init_building_points())
