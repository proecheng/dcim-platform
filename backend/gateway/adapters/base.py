"""协议适配器基类和数据类型定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from enum import Enum
from datetime import datetime


class DataQuality(Enum):
    """数据质量标记"""

    NORMAL = "normal"
    UNRELIABLE = "unreliable"
    ABNORMAL = "abnormal"


class AdapterState(Enum):
    """适配器状态"""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    COMMUNICATION_INTERRUPTED = "communication_interrupted"
    CONFIG_ERROR = "config_error"


@dataclass
class PointConfig:
    """点位采集配置"""

    point_id: str
    address: str
    data_type: str
    scale: float = 1.0
    offset: float = 0.0
    enum_mapping: Optional[dict] = None
    is_dry_contact: bool = False
    fire_signal: bool = False


@dataclass
class DataSourceConfig:
    """数据源配置"""

    datasource_id: str
    protocol_type: str
    connection_params: dict
    collection_interval: int = 5
    write_enabled: bool = False
    points: list[PointConfig] = field(default_factory=list)
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_max_failures: int = 5


@dataclass
class PointValue:
    """点位采集值"""

    point_id: str
    value: Any
    quality: DataQuality
    timestamp: datetime


@dataclass
class ConnectionResult:
    """连接测试结果"""

    success: bool
    message: str
    sample_data: Optional[dict] = None
    latency_ms: Optional[float] = None


@dataclass
class AdapterStatus:
    """适配器状态"""

    state: AdapterState
    connected_since: Optional[datetime] = None
    last_read_time: Optional[datetime] = None
    consecutive_failures: int = 0
    error_message: Optional[str] = None


@dataclass
class NormalizedReading:
    """归一化后的读数 — 下游消费者统一契约"""

    point_id: str
    value: Union[float, str, bool]
    raw_value: Any
    quality: DataQuality
    timestamp: datetime
    datasource_id: str


class BaseProtocolAdapter(ABC):
    """所有协议适配器的抽象基类"""

    @abstractmethod
    async def connect(self, config: DataSourceConfig) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]: ...

    @abstractmethod
    async def write_point(self, point_id: str, value: Any) -> bool: ...

    @abstractmethod
    async def test_connection(self) -> ConnectionResult: ...

    @abstractmethod
    def get_status(self) -> AdapterStatus: ...
