"""网关和数据源 Schema"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# --- Gateway ---
class GatewayBase(BaseModel):
    gateway_id: str
    name: str
    ip_address: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[dict] = None
    site_id: int = 1
    is_enabled: bool = True


class GatewayCreate(GatewayBase):
    pass


class GatewayUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    capabilities: Optional[dict] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    is_enabled: Optional[bool] = None


class GatewayResponse(GatewayBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str = "offline"
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- DataSource ---
class DataSourceBase(BaseModel):
    name: str
    protocol_type: str
    gateway_id: Optional[int] = None
    connection_config: dict
    collection_interval: int = Field(default=5, ge=1, le=60)
    write_enabled: bool = False
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_max_failures: int = 5
    site_id: int = 1
    is_enabled: bool = True


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    protocol_type: Optional[str] = None
    gateway_id: Optional[int] = None
    connection_config: Optional[dict] = None
    collection_interval: Optional[int] = Field(default=None, ge=1, le=60)
    write_enabled: Optional[bool] = None
    retry_base_delay: Optional[float] = None
    retry_max_delay: Optional[float] = None
    retry_max_failures: Optional[int] = None
    is_enabled: Optional[bool] = None


class DataSourceResponse(DataSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str = "disconnected"
    last_communication: Optional[datetime] = None
    consecutive_failures: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- DataSourcePoint ---
class DataSourcePointBase(BaseModel):
    datasource_id: int
    point_id: Optional[int] = None
    address: str
    data_type: Optional[str] = None
    scale: float = 1.0
    offset: float = 0.0
    enum_mapping: Optional[dict] = None
    is_dry_contact: bool = False


class DataSourcePointCreate(DataSourcePointBase):
    pass


class DataSourcePointResponse(DataSourcePointBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- ConnectionTest ---
class ConnectionTestRequest(BaseModel):
    protocol_type: str
    connection_config: dict  # 与 DataSource 模型字段名一致


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    sample_data: Optional[dict] = None


class GatewayStatusSummary(BaseModel):
    """网关状态汇总"""
    total: int
    online: int
    offline: int


class GatewayDetailResponse(GatewayResponse):
    """网关详情（含关联统计）"""
    datasource_count: int = 0
    point_count: int = 0


class GatewayEventResponse(BaseModel):
    """网关事件"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    gateway_id: str
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    detail: Optional[dict] = None
    created_at: Optional[datetime] = None


class ConfigPushResponse(BaseModel):
    """配置下发响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    gateway_id: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class ConfigPushRecordResponse(BaseModel):
    """配置下发记录详情"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    gateway_id: str
    config_snapshot: dict
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- DeviceTemplate ---
class DeviceTemplateBase(BaseModel):
    name: str
    manufacturer: str
    model: str
    protocol_type: str
    description: Optional[str] = None
    point_config: list[dict]


class DeviceTemplateCreate(DeviceTemplateBase):
    pass


class DeviceTemplateUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    protocol_type: Optional[str] = None
    description: Optional[str] = None
    point_config: Optional[list[dict]] = None


class DeviceTemplateResponse(DeviceTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
