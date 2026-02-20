"""配置加载器，支持从本地 YAML 文件加载数据源配置"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import yaml

from .adapters.base import DataSourceConfig, PointConfig

logger = logging.getLogger(__name__)


class ConfigLoader(ABC):
    """配置加载器抽象基类"""

    @abstractmethod
    async def load_datasources(self) -> list[DataSourceConfig]:
        """加载全部数据源配置"""

    @abstractmethod
    async def load_datasource(self, datasource_id: str) -> Optional[DataSourceConfig]:
        """加载指定数据源配置"""


class LocalFileConfigLoader(ConfigLoader):
    """本地 YAML 文件配置加载器

    从指定路径读取 YAML 配置文件，解析为 DataSourceConfig 列表。
    """

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)

    async def load_datasources(self) -> list[DataSourceConfig]:
        """从 YAML 文件加载全部数据源配置

        Returns:
            数据源配置列表

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML 解析失败
        """
        data = self._load_yaml()

        if not data or "datasources" not in data:
            logger.warning("配置文件中未找到 'datasources' 字段")
            return []

        configs: list[DataSourceConfig] = []
        for ds_raw in data["datasources"]:
            try:
                config = self._parse_datasource(ds_raw)
                configs.append(config)
            except (KeyError, TypeError) as e:
                logger.warning("解析数据源配置失败，跳过: %s", e)
                continue

        logger.info("从 '%s' 加载了 %d 个数据源配置", self._file_path, len(configs))
        return configs

    async def load_datasource(self, datasource_id: str) -> Optional[DataSourceConfig]:
        """加载指定 ID 的数据源配置

        Args:
            datasource_id: 数据源ID

        Returns:
            匹配的数据源配置，未找到返回 None
        """
        configs = await self.load_datasources()
        for config in configs:
            if config.datasource_id == datasource_id:
                return config
        logger.warning("未找到数据源配置: %s", datasource_id)
        return None

    def _load_yaml(self) -> dict[str, Any]:
        """读取并解析 YAML 文件"""
        try:
            content = self._file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("配置文件不存在: %s", self._file_path)
            raise

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.error("YAML 解析失败: %s", e)
            raise

        return data or {}

    @staticmethod
    def _parse_datasource(raw: dict[str, Any]) -> DataSourceConfig:
        """解析单个数据源配置字典"""
        # 解析点位列表
        points: list[PointConfig] = []
        for p in raw.get("points", []):
            points.append(
                PointConfig(
                    point_id=p["point_id"],
                    address=p["address"],
                    data_type=p["data_type"],
                    scale=float(p.get("scale", 1.0)),
                    offset=float(p.get("offset", 0.0)),
                    enum_mapping=p.get("enum_mapping"),
                    is_dry_contact=bool(p.get("is_dry_contact", False)),
                    fire_signal=bool(p.get("fire_signal", False)),
                )
            )

        return DataSourceConfig(
            datasource_id=raw["datasource_id"],
            protocol_type=raw["protocol_type"],
            connection_params=raw.get("connection_params", {}),
            collection_interval=int(raw.get("collection_interval", 5)),
            write_enabled=bool(raw.get("write_enabled", False)),
            points=points,
            retry_base_delay=float(raw.get("retry_base_delay", 1.0)),
            retry_max_delay=float(raw.get("retry_max_delay", 60.0)),
            retry_max_failures=int(raw.get("retry_max_failures", 5)),
        )
