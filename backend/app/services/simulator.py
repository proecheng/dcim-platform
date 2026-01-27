"""
数据采集模拟服务 - 自动生成模拟数据
"""
import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import Point, PointRealtime, PointHistory, Alarm, AlarmThreshold
from ..core.database import async_session
from .websocket import ws_manager


class DataSimulator:
    """数据模拟采集器"""

    def __init__(self):
        self.running = False
        self.task = None
        # 点位当前值缓存（用于模拟连续变化）
        self.value_cache: Dict[int, float] = {}

    def generate_ai_value(self, point: Point, current_value: float = None) -> float:
        """生成模拟量输入值 - 增强版（支持设备特定逻辑）"""
        min_val = point.min_range or 0
        max_val = point.max_range or 100

        # 根据设备类型设置基准值
        if current_value is None:
            if "温度" in point.point_name and point.device_type == "TH":
                current_value = 24 + random.uniform(-2, 2)
            elif "湿度" in point.point_name:
                current_value = 50 + random.uniform(-5, 5)
            elif "负载率" in point.point_name:
                current_value = 45 + random.uniform(-10, 10)
            elif "电池电量" in point.point_name:
                current_value = 85 + random.uniform(-5, 5)
            elif "电压" in point.point_name and "输入" in point.point_name:
                current_value = 380 + random.uniform(-5, 5)
            elif "电压" in point.point_name and "输出" in point.point_name:
                current_value = 220 + random.uniform(-2, 2)
            elif "频率" in point.point_name:
                current_value = 50 + random.uniform(-0.5, 0.5)
            elif "冷冻水" in point.point_name and "出水" in point.point_name:
                current_value = 7 + random.uniform(-1, 1)
            elif "冷冻水" in point.point_name and "回水" in point.point_name:
                current_value = 12 + random.uniform(-1, 1)
            elif "冷却水" in point.point_name:
                current_value = 32 + random.uniform(-3, 3)
            elif "电流" in point.point_name and point.device_type == "PDU":
                current_value = 8 + random.uniform(-2, 2)  # PDU电流约8A
            elif "功率" in point.point_name and point.device_type == "PDU":
                current_value = 3 + random.uniform(-1, 1)  # PDU功率约3kW
            elif "压力" in point.point_name:
                current_value = 0.5 + random.uniform(-0.1, 0.1)  # 水压约0.5MPa
            else:
                current_value = (min_val + max_val) / 2

        # 模拟小幅波动
        variation = (max_val - min_val) * 0.02
        delta = random.uniform(-variation, variation)
        new_value = current_value + delta

        # 确保在量程范围内
        new_value = max(min_val, min(max_val, new_value))
        return round(new_value, 2)

    def generate_di_value(self, point: Point) -> int:
        """生成开关量输入值"""
        # 大部分时间为正常状态(0)，小概率触发告警(1)
        # 门禁状态除外，可能经常变化
        if "门禁" in point.point_name:
            return random.choice([0, 0, 0, 0, 1])  # 20% 概率开门
        else:
            return 0 if random.random() > 0.005 else 1  # 0.5% 概率触发

    async def collect_and_save(self, session: AsyncSession, point: Point) -> dict:
        """采集并保存点位数据"""
        # 获取当前缓存值
        current_value = self.value_cache.get(point.id)

        # 生成新值
        if point.point_type == "AI":
            new_value = self.generate_ai_value(point, current_value)
        elif point.point_type == "DI":
            new_value = self.generate_di_value(point)
        elif point.point_type in ["AO", "DO"]:
            # 输出点位保持当前设定值
            result = await session.execute(
                select(PointRealtime).where(PointRealtime.point_id == point.id)
            )
            realtime = result.scalar_one_or_none()
            new_value = realtime.value if realtime else 0
        else:
            new_value = 0

        # 更新缓存
        self.value_cache[point.id] = new_value

        # 检查告警
        status = "normal"
        alarms_to_create = []

        if point.point_type in ["AI", "DI"]:
            result = await session.execute(
                select(AlarmThreshold).where(
                    AlarmThreshold.point_id == point.id,
                    AlarmThreshold.is_enabled == True
                )
            )
            thresholds = result.scalars().all()

            for threshold in thresholds:
                triggered = False
                if threshold.threshold_type == "high" and new_value > threshold.threshold_value:
                    triggered = True
                elif threshold.threshold_type == "low" and new_value < threshold.threshold_value:
                    triggered = True
                elif threshold.threshold_type == "equal" and new_value == threshold.threshold_value:
                    triggered = True

                if triggered:
                    status = "alarm"
                    # 检查是否已有活动告警
                    existing = await session.execute(
                        select(Alarm).where(
                            Alarm.point_id == point.id,
                            Alarm.status == "active"
                        )
                    )
                    if not existing.scalar_one_or_none():
                        message = threshold.alarm_message or f"{point.point_name} 告警"
                        alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                        alarm = Alarm(
                            alarm_no=alarm_no,
                            point_id=point.id,
                            alarm_level=threshold.alarm_level,
                            alarm_message=message,
                            trigger_value=new_value,
                            threshold_value=threshold.threshold_value
                        )
                        alarms_to_create.append(alarm)

        # 更新实时值
        result = await session.execute(
            select(PointRealtime).where(PointRealtime.point_id == point.id)
        )
        realtime = result.scalar_one_or_none()

        if realtime:
            realtime.value = new_value
            realtime.status = status
            realtime.updated_at = datetime.utcnow()
            if point.point_type == "DI":
                realtime.value_text = "告警" if new_value == 1 else "正常"
        else:
            realtime = PointRealtime(
                point_id=point.id,
                value=new_value,
                status=status
            )
            session.add(realtime)

        # 保存历史数据（AI类型）
        if point.point_type == "AI":
            history = PointHistory(
                point_id=point.id,
                value=new_value
            )
            session.add(history)

        # 创建告警
        for alarm in alarms_to_create:
            session.add(alarm)

        return {
            "point_id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "point_type": point.point_type,
            "value": new_value,
            "unit": point.unit,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def run_collection_cycle(self):
        """执行一次采集周期"""
        async with async_session() as session:
            # 获取所有启用的点位
            result = await session.execute(
                select(Point).where(Point.is_enabled == True)
            )
            points = result.scalars().all()

            for point in points:
                try:
                    data = await self.collect_and_save(session, point)
                    # 广播实时数据
                    await ws_manager.broadcast_realtime(data)
                except Exception as e:
                    print(f"采集点位 {point.point_code} 失败: {e}")

            await session.commit()

    async def start(self, interval: int = None):
        """启动数据采集"""
        from ..core.config import get_settings
        settings = get_settings()

        if not settings.simulation_enabled:
            print("模拟模式已禁用，跳过启动")
            return

        if self.running:
            return

        # 使用配置中的间隔或传入的参数
        if interval is None:
            interval = settings.simulation_interval

        self.running = True
        print(f"数据采集模拟器启动，采集间隔: {interval}秒")

        while self.running:
            try:
                await self.run_collection_cycle()
            except Exception as e:
                print(f"采集周期执行失败: {e}")

            await asyncio.sleep(interval)

    def stop(self):
        """停止数据采集"""
        self.running = False
        if self.task:
            self.task.cancel()
        print("数据采集模拟器已停止")


# 全局模拟器实例
simulator = DataSimulator()
