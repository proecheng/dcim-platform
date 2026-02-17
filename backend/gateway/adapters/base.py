# gateway.adapters stub
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DataSourceConfig:
    datasource_id: str = ""
    protocol_type: str = ""
    connection_params: dict = field(default_factory=dict)

@dataclass
class ConnectionResult:
    success: bool = False
    message: str = ""
    latency_ms: Optional[float] = None
