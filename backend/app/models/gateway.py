"""网关和数据源模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, Index, UniqueConstraint

from ..core.database import Base


class Gateway(Base):
    """采集网关"""
    __tablename__ = "gateways"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(50), unique=True, nullable=False, comment="网关唯一标识")
    name = Column(String(100), nullable=False, comment="网关名称")
    ip_address = Column(String(45), comment="IP 地址")
    version = Column(String(50), comment="固件版本")
    status = Column(String(20), default="offline", comment="状态: online/offline")
    capabilities = Column(JSON, comment="能力列表")
    cpu_usage = Column(Float, comment="CPU 使用率 %")
    memory_usage = Column(Float, comment="内存使用率 %")
    disk_usage = Column(Float, comment="磁盘使用率 %")
    last_heartbeat = Column(DateTime, comment="最后心跳时间")
    site_id = Column(Integer, default=1, comment="站点 ID")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DataSource(Base):
    """数据源 — 一个协议连接配置"""
    __tablename__ = "datasources"
    __table_args__ = (
        Index("ix_datasources_gateway_enabled", "gateway_id", "is_enabled"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="数据源名称")
    protocol_type = Column(String(30), nullable=False, comment="协议类型")
    gateway_id = Column(Integer, comment="关联网关 ID")
    connection_config = Column(JSON, nullable=False, comment="连接配置")
    collection_interval = Column(Integer, default=5, comment="采集周期（秒）1-60")
    write_enabled = Column(Boolean, default=False, comment="是否允许写入")
    status = Column(String(30), default="disconnected", comment="连接状态")
    last_communication = Column(DateTime, comment="最后通信时间")
    consecutive_failures = Column(Integer, default=0, comment="连续失败次数")
    retry_base_delay = Column(Float, default=1.0, comment="重试基础延迟（秒）")
    retry_max_delay = Column(Float, default=60.0, comment="重试最大延迟（秒）")
    retry_max_failures = Column(Integer, default=5, comment="连续失败阈值")
    site_id = Column(Integer, default=1, comment="站点 ID")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DataSourcePoint(Base):
    """数据源点位映射"""
    __tablename__ = "datasource_points"
    __table_args__ = (
        UniqueConstraint("datasource_id", "address", name="uq_datasource_point_address"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(Integer, nullable=False, comment="数据源 ID")
    point_id = Column(Integer, comment="关联 Point 表 ID")
    address = Column(String(100), nullable=False, comment="协议地址")
    data_type = Column(String(30), comment="数据类型: int16/uint16/int32/float32/bool/string")
    scale = Column(Float, default=1.0, comment="缩放系数")
    offset = Column(Float, default=0.0, comment="偏移量")
    enum_mapping = Column(JSON, comment="枚举映射 JSON")
    is_dry_contact = Column(Boolean, default=False, comment="是否干接点类型")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class GatewayEvent(Base):
    """网关事件记录"""
    __tablename__ = "gateway_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(50), nullable=False, index=True, comment="网关标识")
    event_type = Column(String(30), nullable=False, comment="事件类型: status_change/resource_warning")
    old_status = Column(String(20), comment="旧状态")
    new_status = Column(String(20), comment="新状态")
    detail = Column(JSON, comment="事件详情")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class ConfigPushRecord(Base):
    """配置下发记录"""
    __tablename__ = "config_push_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(50), nullable=False, index=True, comment="网关标识")
    config_snapshot = Column(JSON, nullable=False, comment="下发的配置快照")
    status = Column(String(20), default="pending", comment="状态: pending/delivered/failed")
    error_message = Column(String(500), comment="错误信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PointDataLatest(Base):
    """点位最新数据"""
    __tablename__ = "point_data_latest"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(String(100), unique=True, nullable=False, index=True, comment="点位ID")
    value = Column(String(200), comment="最新值（字符串存储）")
    quality = Column(Integer, default=0, comment="质量码: 0=正常, 1=不可靠, 2=异常")
    timestamp = Column(DateTime, comment="采集时间")
    gateway_id = Column(String(50), comment="来源网关")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DeviceTemplate(Base):
    """设备模板 — 预置点位配置"""
    __tablename__ = "device_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    manufacturer = Column(String(100), nullable=False, comment="厂商")
    model = Column(String(100), nullable=False, comment="型号")
    protocol_type = Column(String(30), nullable=False, comment="协议类型")
    description = Column(String(500), comment="描述")
    point_config = Column(JSON, nullable=False, comment="预置点位配置列表")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
