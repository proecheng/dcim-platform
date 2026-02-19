"""
数据采集模拟服务 - 自动生成模拟数据
"""
import asyncio
import json as _json
import random
import uuid
from datetime import datetime
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import logging

from ..models import Point, PointRealtime, PointHistory, Alarm
from ..core.database import async_session
from ..core.redis import redis_service
from ..engines.alarm_engine import alarm_engine
from .websocket import ws_manager
from ..models.capacity import (
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityHistory, CapacityType
)

logger = logging.getLogger(__name__)


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

        # 检查告警（使用告警引擎替代内联检测）
        status = "normal"
        alarms_to_create = []

        point_quality = alarm_engine.get_point_quality(point.id)

        if point.point_type in ["AI", "DI"] and point_quality < 2:
            triggered_list = alarm_engine.evaluate(point.id, new_value, point.point_type)

            if triggered_list:
                status = "alarm"
                # 大面积告警检测
                device_type = point.device_type
                is_comm_suspect = alarm_engine.check_mass_alarm(device_type) if device_type else False

                for triggered in triggered_list:
                    # 检查是否已有活动告警（同一点位+同一阈值）
                    existing = await session.execute(
                        select(Alarm).where(
                            Alarm.point_id == point.id,
                            Alarm.threshold_id == triggered.threshold_id,
                            Alarm.status == "active"
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # 已有活动告警，跳过

                    alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                    alarm_msg = triggered.alarm_message or f"{point.point_name} 告警"
                    if is_comm_suspect:
                        alarm_msg = f"[疑似通信异常] {alarm_msg}"

                    alarm = Alarm(
                        alarm_no=alarm_no,
                        point_id=point.id,
                        threshold_id=triggered.threshold_id,
                        alarm_level=triggered.alarm_level,
                        alarm_type="communication" if is_comm_suspect else "threshold",
                        alarm_message=alarm_msg,
                        trigger_value=new_value,
                        threshold_value=triggered.threshold_value,
                    )
                    alarms_to_create.append(alarm)
            else:
                # 值在安全范围内 — 自动恢复活动告警
                if alarm_engine.is_value_safe(point.id, new_value):
                    active_result = await session.execute(
                        select(Alarm).where(
                            Alarm.point_id == point.id,
                            Alarm.status == "active"
                        )
                    )
                    active_alarms = active_result.scalars().all()
                    for active_alarm in active_alarms:
                        active_alarm.status = "resolved"
                        active_alarm.resolve_type = "auto"
                        active_alarm.resolved_at = datetime.now()
                        if active_alarm.created_at:
                            active_alarm.duration_seconds = int(
                                (datetime.now() - active_alarm.created_at).total_seconds()
                            )
                        # 广播恢复消息
                        try:
                            await ws_manager.broadcast_alarm({
                                "action": "resolve",
                                "id": active_alarm.id,
                                "alarm_no": active_alarm.alarm_no,
                                "point_id": active_alarm.point_id,
                                "alarm_level": active_alarm.alarm_level,
                                "status": "resolved",
                                "resolve_type": "auto",
                                "resolved_at": datetime.now().isoformat(),
                            })
                        except Exception as e:
                            logger.warning("WebSocket 告警恢复推送失败: %s", e)
                        # Redis 告警统计递减
                        try:
                            if redis_service.is_available:
                                key = f"alarm:stats:{active_alarm.alarm_level}"
                                current = await redis_service.get(key)
                                count = max(0, int(current or 0) - 1)
                                await redis_service.set(key, str(count), ttl=86400)
                        except Exception:
                            pass

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

        # 创建告警记录并广播
        for alarm in alarms_to_create:
            session.add(alarm)

        if alarms_to_create:
            await session.flush()  # flush 获取告警 ID

            for alarm in alarms_to_create:
                # WebSocket 广播告警到前端
                try:
                    await ws_manager.broadcast_alarm({
                        "action": "new",
                        "id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "point_id": alarm.point_id,
                        "point_code": point.point_code,
                        "point_name": point.point_name,
                        "alarm_level": alarm.alarm_level,
                        "alarm_type": alarm.alarm_type,
                        "alarm_message": alarm.alarm_message,
                        "trigger_value": alarm.trigger_value,
                        "threshold_value": alarm.threshold_value,
                        "status": "active",
                        "created_at": datetime.now().isoformat(),
                    })
                except Exception as e:
                    logger.warning("WebSocket 告警推送失败: %s", e)

                # 发布告警事件到联动引擎
                try:
                    from ..engines.event_bus import get_event_bus, Event, EventPriority
                    _priority_map = {
                        "critical": EventPriority.critical,
                        "major": EventPriority.critical,
                        "minor": EventPriority.normal,
                        "info": EventPriority.normal,
                    }
                    _evt = Event(
                        event_type="alarm.triggered",
                        source="alarm_engine",
                        priority=_priority_map.get(alarm.alarm_level, EventPriority.normal),
                        payload={
                            "alarm_id": alarm.id,
                            "alarm_no": alarm.alarm_no,
                            "alarm_level": alarm.alarm_level,
                            "alarm_type": alarm.alarm_type,
                            "alarm_message": alarm.alarm_message,
                            "point_id": alarm.point_id,
                            "trigger_value": alarm.trigger_value,
                            "threshold_value": alarm.threshold_value,
                            "threshold_type": triggered.threshold_type if triggered else "",
                            "device_type": point.device_type if point.device_type is not None else "",
                            "zone": point.area_code if point.area_code is not None else "default",
                        },
                    )
                    await get_event_bus().publish("linkage", _evt)
                except Exception as e:
                    logger.warning("联动事件发布失败: %s", e)

                # Redis 告警统计递增
                try:
                    if redis_service.is_available:
                        key = f"alarm:stats:{alarm.alarm_level}"
                        current = await redis_service.get(key)
                        count = int(current or 0) + 1
                        await redis_service.set(key, str(count), ttl=86400)
                except Exception:
                    pass  # Redis 不可用时静默失败

        # 写入 Redis 缓存 — Story 4.1
        if redis_service.is_available:
            try:
                value_text = None
                if point.point_type == "DI":
                    value_text = "告警" if new_value == 1 else "正常"
                cache_data = _json.dumps({
                    "value": new_value if point.point_type == "AI" else int(new_value),
                    "value_text": value_text,
                    "quality": point_quality,
                    "status": status,
                    "alarm_level": None,
                    "updated_at": datetime.utcnow().isoformat(),
                })
                await redis_service.set(f"point:{point.id}:latest", cache_data, ttl=60)
            except Exception:
                pass  # Redis 写入失败不影响主流程

        # 写入设备在线状态到 Redis — Story 4.3
        if redis_service.is_available and point.device_id:
            try:
                await redis_service.set(
                    f"device:{point.device_id}:online",
                    datetime.now().isoformat(),
                    ttl=60
                )
            except Exception:
                pass

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

            # 本轮采集结束，重置大面积告警统计
            alarm_engine.reset_cycle_stats()

    async def _snapshot_capacity_history(self):
        """容量历史快照 — 独立事务，使用 SQL SUM 聚合"""
        try:
            async with async_session() as session:
                for cap_type, model, total_field, used_field in [
                    (CapacityType.space, SpaceCapacity, 'total_u_positions', 'used_u_positions'),
                    (CapacityType.power, PowerCapacity, 'total_capacity_kw', 'used_capacity_kw'),
                    (CapacityType.cooling, CoolingCapacity, 'total_cooling_kw', 'used_cooling_kw'),
                    (CapacityType.weight, WeightCapacity, 'total_weight_kg', 'used_weight_kg'),
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
                        session.add(CapacityHistory(
                            capacity_type=cap_type, reference_id=0,
                            reference_name="全局聚合", total_value=total_val,
                            used_value=used_val, usage_rate=rate,
                        ))
                    except Exception as e:
                        logger.warning(f"容量快照 {cap_type} 失败: {e}")

                await session.commit()
        except Exception as e:
            logger.warning(f"容量快照事务失败: {e}")

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
