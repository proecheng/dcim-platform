"""
数据模拟采集服务
"""
import asyncio
import random
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import Point, PointRealtime, PointHistory, Alarm, AlarmThreshold


class DataCollector:
    """数据采集模拟器"""

    def __init__(self):
        self.running = False

    async def collect_point_data(self, session: AsyncSession, point: Point) -> float:
        """模拟采集单个点位数据"""
        if point.point_type == "AI":
            # 模拟量输入: 在量程范围内生成随机值
            min_val = point.min_range or 0
            max_val = point.max_range or 100
            base = (min_val + max_val) / 2
            variation = (max_val - min_val) * 0.1
            value = base + random.uniform(-variation, variation)
            return round(value, 2)

        elif point.point_type == "DI":
            # 开关量输入: 大部分时间为正常状态
            return 0 if random.random() > 0.02 else 1

        elif point.point_type == "AO":
            # 模拟量输出: 返回当前设定值
            result = await session.execute(
                select(PointRealtime).where(PointRealtime.point_id == point.id)
            )
            realtime = result.scalar_one_or_none()
            if realtime and realtime.value is not None:
                return realtime.value
            return (point.min_range or 0 + point.max_range or 100) / 2

        elif point.point_type == "DO":
            # 开关量输出: 返回当前状态
            result = await session.execute(
                select(PointRealtime).where(PointRealtime.point_id == point.id)
            )
            realtime = result.scalar_one_or_none()
            return realtime.value if realtime and realtime.value is not None else 0

        return 0

    async def check_thresholds(
        self, session: AsyncSession, point: Point, value: float
    ) -> list:
        """检查阈值并生成告警"""
        result = await session.execute(
            select(AlarmThreshold).where(
                AlarmThreshold.point_id == point.id,
                AlarmThreshold.is_enabled == True
            )
        )
        thresholds = result.scalars().all()
        alarms = []

        for threshold in thresholds:
            triggered = False
            if threshold.threshold_type == "high" and value > threshold.threshold_value:
                triggered = True
                message = f"{point.point_name} 超过上限: {value}{point.unit or ''} > {threshold.threshold_value}{point.unit or ''}"
            elif threshold.threshold_type == "low" and value < threshold.threshold_value:
                triggered = True
                message = f"{point.point_name} 低于下限: {value}{point.unit or ''} < {threshold.threshold_value}{point.unit or ''}"
            elif threshold.threshold_type == "equal" and value == threshold.threshold_value:
                triggered = True
                message = f"{point.point_name} 状态异常"

            if triggered:
                alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                alarm = Alarm(
                    alarm_no=alarm_no,
                    point_id=point.id,
                    alarm_level=threshold.alarm_level,
                    alarm_message=threshold.alarm_message or message,
                    trigger_value=value,
                    threshold_value=threshold.threshold_value
                )
                alarms.append(alarm)

        return alarms

    async def update_realtime(
        self, session: AsyncSession, point_id: int, value: float, status: str = "normal"
    ):
        """更新实时值"""
        result = await session.execute(
            select(PointRealtime).where(PointRealtime.point_id == point_id)
        )
        realtime = result.scalar_one_or_none()

        if realtime:
            realtime.value = value
            realtime.status = status
            realtime.updated_at = datetime.utcnow()
        else:
            realtime = PointRealtime(
                point_id=point_id,
                value=value,
                status=status
            )
            session.add(realtime)

    async def save_history(self, session: AsyncSession, point_id: int, value: float):
        """保存历史数据"""
        history = PointHistory(
            point_id=point_id,
            value=value
        )
        session.add(history)


# 全局采集器实例
collector = DataCollector()
