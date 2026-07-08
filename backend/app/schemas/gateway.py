"""网关和数据源 Schema"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
import ipaddress


# --- Gateway ---
class GatewayBase(BaseModel):
    gateway_id: str
    name: str
    ip_address: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[dict] = None
    site_id: Optional[int] = None
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
    site_id: Optional[int] = None
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
    parent_datasource_id: Optional[int] = None
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
    extra_config: Optional[dict] = None


class DeviceTemplateCreate(DeviceTemplateBase):
    pass


class DeviceTemplateUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    protocol_type: Optional[str] = None
    description: Optional[str] = None
    point_config: Optional[list[dict]] = None
    extra_config: Optional[dict] = None


class DeviceTemplateResponse(DeviceTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuiltinDeviceTemplateResponse(DeviceTemplateBase):
    key: str
    point_count: int = 0


class GatewayAssignSite(BaseModel):
    """网关站点分配请求"""

    site_id: int = Field(..., description="目标站点ID")


# --- BACnet MS/TP 网关相关 Schema ---


class MstpDownstreamDevice(BaseModel):
    """MS/TP 下挂设备"""

    mac_address: int = Field(ge=1, le=127, description="MS/TP MAC 地址")
    device_instance: int = Field(ge=0, le=4194302, description="BACnet 设备实例号")
    device_name: str = Field(description="设备名称")
    model: Optional[str] = Field(default=None, description="设备型号")


class MstpConfig(BaseModel):
    """MS/TP 总线配置"""

    network_number: int = Field(default=1, ge=1, description="网络号")
    mac_range: list[int] = Field(default=[1, 127], description="MAC 地址范围 [min, max]")
    baud_rate: Literal[9600, 19200, 38400, 76800, 115200] = Field(default=9600, description="波特率")
    parity: Literal["none", "even", "odd"] = Field(default="none", description="校验位")

    @model_validator(mode="after")
    def validate_mac_range(self):
        """mac_range 必须是两个元素且 [0] <= [1]，范围 1-127"""
        r = self.mac_range
        if len(r) != 2:
            raise ValueError("mac_range 必须是 [min, max] 两个元素")
        if not (1 <= r[0] <= 127 and 1 <= r[1] <= 127):
            raise ValueError("mac_range 元素必须在 1-127 范围内")
        if r[0] > r[1]:
            raise ValueError("mac_range[0] 不能大于 mac_range[1]")
        return self


class BbmdConfig(BaseModel):
    """BBMD 配置"""

    enabled: bool = Field(default=False, description="是否启用 BBMD")
    bdt_entries: list[str] = Field(default_factory=list, description="BDT 条目列表")


class MstpGatewayExtraConfig(BaseModel):
    """MS/TP 转换网关 extra_config 验证 Schema"""

    gateway_type: Literal["bacnet_mstp_to_ip"]
    gateway_device_instance: int = Field(ge=0, le=4194302, description="网关自身 BACnet 设备实例号")
    mstp_config: MstpConfig = Field(default_factory=MstpConfig)
    bbmd_config: Optional[BbmdConfig] = None
    downstream_devices: list[MstpDownstreamDevice] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_downstream_uniqueness(self):
        """downstream_devices 内 mac_address 和 device_instance 不得重复"""
        devices = self.downstream_devices
        if not devices:
            return self
        mac_addrs = [d.mac_address for d in devices]
        if len(mac_addrs) != len(set(mac_addrs)):
            raise ValueError("downstream_devices 中存在重复的 mac_address")
        dev_instances = [d.device_instance for d in devices]
        if len(dev_instances) != len(set(dev_instances)):
            raise ValueError("downstream_devices 中存在重复的 device_instance")
        return self


class CreateMstpDatasourcesRequest(BaseModel):
    """批量创建 MS/TP 数据源请求"""

    gateway_ip: str = Field(description="网关 IP 地址（IPv4）")
    port: int = Field(default=47808, ge=1, le=65535, description="BACnet/IP 端口")
    site_id: Optional[int] = Field(default=None, description="站点 ID")

    @model_validator(mode="after")
    def validate_gateway_ip(self):
        """验证 gateway_ip 为合法 IPv4 单播地址并规范化"""
        try:
            addr = ipaddress.IPv4Address(self.gateway_ip)
        except (ipaddress.AddressValueError, ValueError):
            raise ValueError(f"gateway_ip 必须是合法的 IPv4 地址，收到: {self.gateway_ip!r}")
        if addr.is_unspecified or addr.is_multicast or addr == ipaddress.IPv4Address("255.255.255.255"):
            raise ValueError(f"gateway_ip 不能是广播/多播/全零地址: {self.gateway_ip}")
        self.gateway_ip = str(addr)
        return self


class CreateMstpDatasourcesResponse(BaseModel):
    """批量创建 MS/TP 数据源响应"""

    gateway: DataSourceResponse
    devices: list[DataSourceResponse]
    total_devices: int
