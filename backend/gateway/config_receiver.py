"""远程配置接收。实现 Story: 2.3"""
import json
import logging
from typing import Any, Callable, Optional

from .adapters.base import DataSourceConfig, PointConfig

logger = logging.getLogger(__name__)


class ConfigReceiver:
    """远程配置接收器 — 解析 MQTT config 消息，回调通知上层热加载"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        on_config_received: Optional[Callable[[list[DataSourceConfig]], Any]] = None,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._on_config_received = on_config_received

    @property
    def topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/config"

    def handle_message(self, payload_str: str) -> list[DataSourceConfig]:
        """解析配置消息，返回 DataSourceConfig 列表"""
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.error("配置消息 JSON 解析失败")
            return []

        if not isinstance(data, dict) or "datasources" not in data:
            logger.warning("配置消息格式无效: 缺少 datasources 字段")
            return []

        configs: list[DataSourceConfig] = []
        for ds_raw in data["datasources"]:
            try:
                points = [
                    PointConfig(
                        point_id=p["point_id"],
                        address=p["address"],
                        data_type=p.get("data_type", "float32"),
                        scale=float(p.get("scale", 1.0)),
                        offset=float(p.get("offset", 0.0)),
                        enum_mapping=p.get("enum_mapping"),
                        is_dry_contact=bool(p.get("is_dry_contact", False)),
                    )
                    for p in ds_raw.get("points", [])
                ]
                config = DataSourceConfig(
                    datasource_id=ds_raw["datasource_id"],
                    protocol_type=ds_raw["protocol_type"],
                    connection_params=ds_raw.get("connection_params", {}),
                    collection_interval=int(ds_raw.get("collection_interval", 5)),
                    write_enabled=bool(ds_raw.get("write_enabled", False)),
                    points=points,
                )
                configs.append(config)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("解析数据源配置失败，跳过: %s", e)
                continue

        logger.info("收到远程配置: %d 个数据源", len(configs))

        if self._on_config_received and configs:
            self._on_config_received(configs)

        return configs