"""干接点状态变化监测器"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .adapters.base import DataSourceConfig, NormalizedReading, DataQuality

logger = logging.getLogger(__name__)


@dataclass
class DryContactEvent:
    """干接点状态变化事件"""
    datasource_id: str
    point_id: str
    old_value: Any          # 归一化后的值（枚举映射后，如 "正常"/"火警"）
    new_value: Any          # 归一化后的值
    raw_old_value: Any      # 原始值（0/1 整数）
    raw_new_value: Any      # 原始值
    is_fire_signal: bool
    timestamp: datetime


class DryContactMonitor:
    """干接点状态变化监测器

    使用 raw_value（原始值 0/1）做状态比较，避免枚举映射后字符串比较不可靠。
    事件中同时提供归一化后的值和原始值。
    """

    def __init__(self) -> None:
        # key: "{datasource_id}:{point_id}", value: (last_raw_value, last_value)
        self._last_values: dict[str, tuple[Any, Any]] = {}

    def check(
        self,
        readings: list[NormalizedReading],
        config: DataSourceConfig,
    ) -> list[DryContactEvent]:
        """检测干接点状态变化，返回变化事件列表"""
        point_map = {p.point_id: p for p in config.points}
        events: list[DryContactEvent] = []

        for reading in readings:
            point_config = point_map.get(reading.point_id)
            if not point_config or not point_config.is_dry_contact:
                continue

            # 数据质量异常时跳过
            if reading.quality == DataQuality.ABNORMAL:
                logger.debug(
                    "干接点 %s 数据质量异常，跳过状态检测",
                    reading.point_id,
                )
                continue

            key = f"{reading.datasource_id}:{reading.point_id}"
            last = self._last_values.get(key)

            # 首次采集：记录初始值，不触发事件
            if last is None:
                self._last_values[key] = (reading.raw_value, reading.value)
                logger.info(
                    "干接点 %s 初始状态: raw=%s, value=%s",
                    reading.point_id, reading.raw_value, reading.value,
                )
                continue

            old_raw, old_value = last

            # 用 raw_value 做状态变化检测（0/1 整数比较更可靠）
            if reading.raw_value != old_raw:
                self._last_values[key] = (reading.raw_value, reading.value)
                is_fire = point_config.fire_signal
                event = DryContactEvent(
                    datasource_id=reading.datasource_id,
                    point_id=reading.point_id,
                    old_value=old_value,
                    new_value=reading.value,
                    raw_old_value=old_raw,
                    raw_new_value=reading.raw_value,
                    is_fire_signal=is_fire,
                    timestamp=reading.timestamp,
                )
                events.append(event)
                logger.warning(
                    "干接点状态变化: %s raw=%s→%s value=%s→%s (fire_signal=%s)",
                    reading.point_id, old_raw, reading.raw_value,
                    old_value, reading.value, is_fire,
                )

        return events

    def reset(self, datasource_id: str) -> None:
        """清除指定数据源的所有干接点状态"""
        prefix = f"{datasource_id}:"
        keys_to_remove = [k for k in self._last_values if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._last_values[k]
        if keys_to_remove:
            logger.info("已清除数据源 %s 的 %d 个干接点状态", datasource_id, len(keys_to_remove))

    def clear_all(self) -> None:
        """清除所有干接点状态（调度器停止时调用）"""
        count = len(self._last_values)
        self._last_values.clear()
        if count:
            logger.info("已清除全部 %d 个干接点状态", count)
