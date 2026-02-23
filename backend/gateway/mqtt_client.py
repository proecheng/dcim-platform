"""MQTT 上报客户端。实现 Story: 2.5"""

import json
import logging
import time
from typing import Any, Optional

from .adapters.base import NormalizedReading, DataQuality
from .cache import OfflineCache

logger = logging.getLogger(__name__)

QUALITY_MAP = {
    DataQuality.NORMAL: 0,
    DataQuality.UNRELIABLE: 1,
    DataQuality.ABNORMAL: 2,
}


def format_point_data(gateway_id: str, readings: list[NormalizedReading]) -> dict:
    """将 NormalizedReading 列表转换为 MQTT 数据消息"""
    return {
        "gw_id": gateway_id,
        "ts": int(time.time()),
        "points": [
            {
                "id": r.point_id,
                "v": r.value,
                "q": QUALITY_MAP.get(r.quality, 0),
                "t": int(r.timestamp.timestamp()),
            }
            for r in readings
        ],
    }


class GatewayMqttClient:
    """网关 MQTT 客户端 — 数据上报 + 离线缓存降级"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        cache: Optional[OfflineCache] = None,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._cache = cache
        self._client: Any = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def data_topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/data"

    async def publish(self, topic: str, payload: str, qos: int = 1) -> None:
        """发布消息，断开时降级到离线缓存"""
        if self._connected and self._client:
            try:
                await self._client.publish(topic, payload, qos=qos)
                return
            except Exception:
                logger.warning("MQTT 发布失败，降级到离线缓存")
                self._connected = False

        # 降级到离线缓存
        if self._cache:
            await self._cache.enqueue(topic, payload)
        else:
            logger.error("MQTT 断开且无离线缓存，数据丢失: topic=%s", topic)

    async def publish_readings(self, readings: list[NormalizedReading]) -> None:
        """上报采集数据"""
        if not readings:
            return
        msg = format_point_data(self._gateway_id, readings)
        await self.publish(self.data_topic, json.dumps(msg))

    def set_connected(self, client: Any) -> None:
        """设置连接状态（由外部连接管理器调用）"""
        self._client = client
        self._connected = True

    def set_disconnected(self) -> None:
        """设置断开状态"""
        self._client = None
        self._connected = False
