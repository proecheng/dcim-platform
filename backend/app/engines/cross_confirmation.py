"""
交叉确认服务 — 多传感器交叉确认升级为消防联动
Story 9-2: 消防分级联动策略
"""

import logging
import time
from typing import Dict, List

from .event_bus import Event, EventPriority, get_event_bus

logger = logging.getLogger(__name__)

# 消防传感器类型列表（SMOKE 为现有系统类型，其余为预留）
FIRE_SENSOR_TYPES = {"SMOKE", "SMOKE_DETECTOR", "VESDA", "VESDA_DETECTOR"}

# 交叉确认时间窗口（秒）
CROSS_CONFIRM_WINDOW = 60

# 过期清理阈值（秒）
EXPIRE_THRESHOLD = 120


class CrossConfirmationService:
    """交叉确认服务 — 同区域多传感器触发时升级为 fire_signal"""

    def __init__(self) -> None:
        # 按区域缓存最近的消防传感器告警
        # key: zone, value: [{device_type, timestamp, event}]
        self._recent_alarms: Dict[str, List[dict]] = {}

    async def on_alarm_event(self, event: Event) -> None:
        """事件处理入口 — 订阅 linkage 通道"""
        # 防重入：忽略交叉确认产生的事件
        device_type = event.payload.get("device_type")
        if device_type == "CROSS_CONFIRMED":
            return

        # 仅处理 alarm.triggered 事件
        if event.event_type != "alarm.triggered":
            return

        # 检查是否为消防传感器类型
        if device_type is None or device_type not in FIRE_SENSOR_TYPES:
            return

        # 获取区域信息
        zone = event.payload.get("zone")
        if zone is None:
            zone = event.payload.get("area_code")
        if zone is None:
            zone = "default"

        # 记录到缓存
        now = time.time()
        if zone not in self._recent_alarms:
            self._recent_alarms[zone] = []

        self._recent_alarms[zone].append(
            {
                "device_type": device_type,
                "timestamp": now,
                "event": event,
            }
        )

        # 清理过期记录
        self._cleanup_expired(now)

        # 检查交叉确认
        if self._check_cross_confirm(zone, now):
            logger.warning(
                "交叉确认触发: zone=%s, 多传感器确认火灾信号",
                zone,
            )
            await self._publish_fire_signal(zone, now)

    def _check_cross_confirm(self, zone: str, now: float) -> bool:
        """检查同区域是否有不同类型传感器在时间窗口内触发"""
        records = self._recent_alarms.get(zone, [])
        if len(records) < 2:
            return False

        # 收集时间窗口内的不同 device_type
        recent_types = set()
        for record in records:
            if now - record["timestamp"] <= CROSS_CONFIRM_WINDOW:
                recent_types.add(record["device_type"])

        # 至少 2 种不同类型
        return len(recent_types) >= 2

    async def _publish_fire_signal(self, zone: str, now: float) -> None:
        """发布交叉确认的 fire_signal 事件"""
        # 收集交叉确认详情
        records = self._recent_alarms.get(zone, [])
        details = []
        for record in records:
            if now - record["timestamp"] <= CROSS_CONFIRM_WINDOW:
                details.append(
                    {
                        "device_type": record["device_type"],
                        "timestamp": record["timestamp"],
                    }
                )

        fire_event = Event(
            event_type="alarm.triggered",
            source="cross_confirmation",
            priority=EventPriority.fire_signal,
            payload={
                "alarm_type": "threshold",
                "device_type": "CROSS_CONFIRMED",
                "zone": zone,
                "cross_confirm_details": details,
                "alarm_level": "critical",
                "alarm_message": f"交叉确认: {zone} 区域多传感器确认火灾信号",
            },
        )

        event_bus = get_event_bus()
        await event_bus.publish("linkage", fire_event)

        # 清除该区域的缓存（避免重复触发）
        self._recent_alarms[zone] = []

    def _cleanup_expired(self, now: float) -> None:
        """清理超过阈值的过期记录"""
        for zone in list(self._recent_alarms.keys()):
            self._recent_alarms[zone] = [
                r for r in self._recent_alarms[zone] if now - r["timestamp"] <= EXPIRE_THRESHOLD
            ]
            if not self._recent_alarms[zone]:
                del self._recent_alarms[zone]


# 全局单例
cross_confirmation_service = CrossConfirmationService()
