"""协议适配器包 — 导出所有公共类型"""
from .base import (
    BaseProtocolAdapter,
    DataSourceConfig,
    PointConfig,
    PointValue,
    ConnectionResult,
    AdapterStatus,
    NormalizedReading,
    DataQuality,
    AdapterState,
)
from .registry import (
    ADAPTER_REGISTRY,
    register_adapter,
    get_adapter,
    list_adapters,
)

from . import modbus_tcp  # 触发 @register_adapter 装饰器
from . import modbus_rtu  # 触发 @register_adapter 装饰器
from . import snmp  # 触发 @register_adapter 装饰器
from . import mqtt_device  # 触发 @register_adapter 装饰器
from . import http_rest  # 触发 @register_adapter 装饰器
from . import bacnet_ip  # 触发 @register_adapter 装饰器

__all__ = [
    "BaseProtocolAdapter",
    "DataSourceConfig",
    "PointConfig",
    "PointValue",
    "ConnectionResult",
    "AdapterStatus",
    "NormalizedReading",
    "DataQuality",
    "AdapterState",
    "ADAPTER_REGISTRY",
    "register_adapter",
    "get_adapter",
    "list_adapters",
]
