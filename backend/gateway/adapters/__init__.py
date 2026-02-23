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

# 触发 @register_adapter 装饰器 — 缺少可选依赖时静默跳过
try:
    from . import modbus_tcp
except ImportError:
    pass
try:
    from . import modbus_rtu
except ImportError:
    pass
try:
    from . import snmp
except ImportError:
    pass
try:
    from . import mqtt_device
except ImportError:
    pass
try:
    from . import http_rest
except ImportError:
    pass
try:
    from . import bacnet_ip
except ImportError:
    pass
try:
    from . import opc_ua
except ImportError:
    pass

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
