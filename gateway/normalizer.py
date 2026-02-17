"""数据归一化层"""
import logging
from datetime import timezone
from .adapters.base import PointValue, DataSourceConfig, NormalizedReading, DataQuality

logger = logging.getLogger(__name__)


class DataNormalizer:
    """数据归一化处理器"""

    def normalize(self, raw_values: dict[str, PointValue], config: DataSourceConfig) -> list[NormalizedReading]:
        """将原始采集值转换为归一化读数"""
        readings = []
        point_map = {p.point_id: p for p in config.points}

        for point_id, raw in raw_values.items():
            point_config = point_map.get(point_id)
            if not point_config:
                logger.warning("点位 %s 未找到配置，跳过归一化", point_id)
                continue

            # 缩放和偏移转换
            try:
                if point_config.is_dry_contact and point_config.enum_mapping and str(raw.value) in point_config.enum_mapping:
                    # 干接点类型优先走枚举映射（值通常是 0/1 整数）
                    value = point_config.enum_mapping[str(raw.value)]
                elif isinstance(raw.value, (int, float)):
                    value = raw.value * point_config.scale + point_config.offset
                elif point_config.enum_mapping and str(raw.value) in point_config.enum_mapping:
                    value = point_config.enum_mapping[str(raw.value)]
                else:
                    value = raw.value
            except (TypeError, ValueError) as e:
                logger.warning("点位 %s 归一化失败: %s", point_id, e)
                value = raw.value

            # 时间戳统一为 UTC
            ts = raw.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)

            readings.append(NormalizedReading(
                point_id=point_id,
                value=value,
                raw_value=raw.value,
                quality=raw.quality,
                timestamp=ts,
                datasource_id=config.datasource_id,
            ))

        return readings
