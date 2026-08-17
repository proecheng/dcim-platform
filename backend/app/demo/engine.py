"""
数据采集模拟服务 - 自动生成模拟数据
"""

import asyncio
import random
from typing import Dict
from sqlalchemy import select, func

import logging

from ..models import Point, PointRealtime
from ..core.database import async_session
from ..models.capacity import (
    SpaceCapacity,
    PowerCapacity,
    CoolingCapacity,
    WeightCapacity,
    CapacityHistory,
    CapacityType,
)

logger = logging.getLogger(__name__)


class DataSimulator:
    """数据模拟采集器"""

    def __init__(self):
        self.running = False
        self.task = None
        # 点位当前值缓存（用于模拟连续变化）
        self.value_cache: Dict[int, float] = {}
        self._point_offset = 0

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
            elif "健康度" in point.point_name or "soh" in (point.point_code or "").lower():
                current_value = 92 + random.uniform(-2, 2)  # SOH约92%，缓慢下降
            elif "荷电状态" in point.point_name or "soc" in (point.point_code or "").lower():
                current_value = 85 + random.uniform(-10, 10)  # SOC在60-100%循环
            elif "内阻" in point.point_name or "internal_resistance" in (point.point_code or "").lower():
                current_value = 2.5 + random.uniform(-0.5, 0.5)  # 内阻约2.5mΩ
            elif "备电时间" in point.point_name or "backup_time" in (point.point_code or "").lower():
                current_value = 60 + random.uniform(-10, 10)  # 备电时间约60min
            elif "母排温度" in point.point_name or "bus_temp" in (point.point_code or "").lower():
                current_value = 35 + random.uniform(-3, 3)  # 母排温度约35℃
            elif "总功率" in point.point_name or "total_power" in (point.point_code or "").lower():
                current_value = 150 + random.uniform(-20, 20)  # 总功率约150kW
            elif "功率因数" in point.point_name or "power_factor" in (point.point_code or "").lower():
                current_value = 0.95 + random.uniform(-0.05, 0.05)
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

    async def run_collection_cycle(self):
        """执行一次采集周期 — 生成模拟值并通过统一管道入库"""
        from ..services.ingest_pipeline import IngestPoint, process_payload
        from ..core.config import get_settings

        async with async_session() as session:
            # 获取所有启用的点位
            result = await session.execute(select(Point).where(Point.is_enabled == True).order_by(Point.id))
            all_points = result.scalars().all()

            batch_size = get_settings().simulation_batch_size
            if len(all_points) > batch_size:
                start = self._point_offset if self._point_offset < len(all_points) else 0
                end = min(start + batch_size, len(all_points))
                points = all_points[start:end]
                self._point_offset = 0 if end >= len(all_points) else end
            else:
                points = all_points
                self._point_offset = 0

            # 预取 AO/DO 点位实时值，避免逐点查询导致 N+1
            ao_do_ids = [point.id for point in points if point.point_type in ["AO", "DO"]]
            realtime_value_map: dict[int, float] = {}
            if ao_do_ids:
                realtime_result = await session.execute(
                    select(PointRealtime.point_id, PointRealtime.value).where(PointRealtime.point_id.in_(ao_do_ids))
                )
                realtime_value_map = {row[0]: float(row[1] or 0) for row in realtime_result.all()}

            # 生成模拟值
            ingest_points: list[IngestPoint] = []
            for point in points:
                try:
                    current_value = self.value_cache.get(point.id)
                    if point.point_type == "AI":
                        new_value = self.generate_ai_value(point, current_value)
                    elif point.point_type == "DI":
                        new_value = self.generate_di_value(point)
                    elif point.point_type in ["AO", "DO"]:
                        new_value = realtime_value_map.get(point.id, 0)
                    else:
                        new_value = 0
                    self.value_cache[point.id] = new_value
                    ingest_points.append(
                        IngestPoint(
                            point_id=point.id,
                            value=float(new_value),
                            quality=0,
                            source="demo",
                        )
                    )
                except Exception as e:
                    logger.warning("生成点位 %s 模拟值失败: %s", point.point_code, e)

            # 统一管道入库（包含 DB + 告警 + WS + Redis）
            if ingest_points:
                await process_payload(ingest_points, session=session)

    async def _snapshot_capacity_history(self):
        """容量历史快照 — 独立事务，使用 SQL SUM 聚合"""
        try:
            async with async_session() as session:
                for cap_type, model, total_field, used_field in [
                    (CapacityType.space, SpaceCapacity, "total_u_positions", "used_u_positions"),
                    (CapacityType.power, PowerCapacity, "total_capacity_kw", "used_capacity_kw"),
                    (CapacityType.cooling, CoolingCapacity, "total_cooling_kw", "used_cooling_kw"),
                    (CapacityType.weight, WeightCapacity, "total_weight_kg", "used_weight_kg"),
                ]:
                    try:
                        result = await session.execute(
                            select(
                                func.coalesce(func.sum(getattr(model, total_field)), 0),
                                func.coalesce(func.sum(getattr(model, used_field)), 0),
                            )
                        )
                        total_val, used_val = result.one()
                        total_val = float(total_val)
                        used_val = float(used_val)
                        rate = round(used_val / total_val * 100, 2) if total_val > 0 else 0
                        session.add(
                            CapacityHistory(
                                capacity_type=cap_type,
                                reference_id=0,
                                reference_name="全局聚合",
                                total_value=total_val,
                                used_value=used_val,
                                usage_rate=rate,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"容量快照 {cap_type} 失败: {e}")

                await session.commit()
        except Exception as e:
            logger.warning(f"容量快照事务失败: {e}")

    async def start(self, interval: int = None):
        """启动数据采集"""
        from ..core.config import get_settings

        settings = get_settings()

        if self.running:
            return

        # 使用配置中的间隔或传入的参数
        if interval is None:
            interval = settings.simulation_interval

        self.running = True
        print(f"数据采集模拟器启动，采集间隔: {interval}秒")

        cycle_count = 0
        while self.running:
            try:
                await self.run_collection_cycle()
            except Exception as e:
                print(f"采集周期执行失败: {e}")

            cycle_count += 1
            if cycle_count % 12 == 0:
                await self._snapshot_capacity_history()
                cycle_count = 0

            await asyncio.sleep(interval)

    def stop(self):
        """停止数据采集"""
        self.running = False
        if self.task:
            self.task.cancel()
        print("数据采集模拟器已停止")


# 全局模拟器实例
simulator = DataSimulator()
