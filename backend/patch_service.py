import sys
import re

content = open("app/services/device_regulation_service.py", "r", encoding="utf-8").read()

new_method = """
    async def get_device_power_trend(self, device_id: int, days: int = 30) -> Optional[Dict[str, Any]]:
        \"\"\"
        获取设备功率趋势数据（按天聚合）
        
        Args:
            device_id: 设备ID
            days: 查询天数
            
        Returns:
            Dict: 包含设备信息和每日功率数据
        \"\"\"
        # 查询设备
        device_result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = device_result.scalar_one_or_none()
        
        if not device:
            return None
        
        # 查询设备的功率点位
        from ..models.point import Point
        from ..models.history import PointHistory
        power_point_query = select(Point.id).where(
            and_(
                Point.device_id == device.monitor_device_id,
                Point.point_name.like("%功率%"),
                Point.point_type == "AI"
            )
        )
        power_point_result = await self.db.execute(power_point_query)
        power_point_id = power_point_result.scalar_one_or_none()
        
        if not power_point_id:
            # 没有功率点位，返回空数据
            return {
                "device_id": device.id,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "rated_power": device.rated_power,
                "daily_data": []
            }
        
        # 计算查询起始日期
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 按天分组聚合 PointHistory - 使用 strftime 转换为字符串
        result = await self.db.execute(
            select(
                func.strftime('%Y-%m-%d', PointHistory.recorded_at).label("date"),
                func.avg(PointHistory.value).label("avg_power"),
                func.max(PointHistory.value).label("max_power"),
                func.min(PointHistory.value).label("min_power"),
                func.count(PointHistory.id).label("record_count"),
            )
            .where(
                and_(
                    PointHistory.point_id == power_point_id,
                    PointHistory.recorded_at >= cutoff_date,
                    PointHistory.value.isnot(None)
                )
            )
            .group_by(func.strftime('%Y-%m-%d', PointHistory.recorded_at))
            .order_by(func.strftime('%Y-%m-%d', PointHistory.recorded_at))
        )
        
        rows = result.all()
        
        # 处理结果
        daily_data = []
        for row in rows:
            avg_power = float(row.avg_power or 0)
            daily_data.append({
                "date": row.date,  # 已经是字符串格式
                "avg_power": round(avg_power, 2),
                "max_power": round(float(row.max_power or 0), 2),
                "min_power": round(float(row.min_power or 0), 2),
                "energy": round(avg_power * 24, 2),  # 估算日能耗 (kWh)
                "record_count": row.record_count or 0
            })
        
        return {
            "device_id": device.id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": device.rated_power,
            "daily_data": daily_data,
            "query_days": days,
            "data_points": len(daily_data)
        }
"""

if "def get_device_power_trend" not in content:
    content = content + "\n" + new_method
    open("app/services/device_regulation_service.py", "w", encoding="utf-8").write(content)
    print("Added get_device_power_trend to service")
else:
    print("Method already exists")
