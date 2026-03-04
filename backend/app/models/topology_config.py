"""
配电与制冷拓扑配置模型 — 机柜→PDU三相接线映射、制冷区域
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from ..core.database import Base


class PowerPhaseMapping(Base):
    """机柜→PDU 三相接线映射"""

    __tablename__ = "power_phase_mappings"
    __table_args__ = (UniqueConstraint("cabinet_id", "feed_type", name="uq_cabinet_feed_type"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False, comment="机柜ID")
    pdu_device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, comment="PDU设备ID")
    phase = Column(String(1), nullable=False, comment="相位: A/B/C")
    feed_type = Column(String(10), nullable=False, comment="馈电类型: primary/backup")
    rated_current = Column(Float, nullable=True, comment="额定电流(A)")
    description = Column(Text, nullable=True, comment="描述")


class CoolingZone(Base):
    """制冷区域"""

    __tablename__ = "cooling_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_code = Column(String(50), unique=True, nullable=False, comment="区域编码")
    zone_name = Column(String(100), nullable=False, comment="区域名称")
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True, comment="所属房间ID")
    design_capacity_kw = Column(Float, nullable=True, comment="设计制冷量(kW)")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CoolingZoneCabinet(Base):
    """制冷区域↔机柜关联"""

    __tablename__ = "cooling_zone_cabinets"
    __table_args__ = (UniqueConstraint("zone_id", "cabinet_id", name="uq_zone_cabinet"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("cooling_zones.id", ondelete="CASCADE"), nullable=False, comment="制冷区域ID")
    cabinet_id = Column(Integer, ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False, comment="机柜ID")


class CoolingZoneUnit(Base):
    """制冷区域↔空调关联"""

    __tablename__ = "cooling_zone_units"
    __table_args__ = (UniqueConstraint("zone_id", "cooling_unit_id", name="uq_zone_cooling_unit"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("cooling_zones.id", ondelete="CASCADE"), nullable=False, comment="制冷区域ID")
    cooling_unit_id = Column(
        Integer, ForeignKey("cooling_units.id", ondelete="CASCADE"), nullable=False, comment="空调ID"
    )

    is_primary = Column(Integer, default=1, comment="是否主空调: 1=主, 0=备")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CabinetTemperatureSensor(Base):
    """机柜温度传感器配置"""

    __tablename__ = "cabinet_temperature_sensors"
    __table_args__ = (UniqueConstraint("cabinet_id", "sensor_location", name="uq_cabinet_sensor_location"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False, comment="机柜ID")
    point_id = Column(Integer, ForeignKey("points.id", ondelete="SET NULL"), nullable=True, comment="温度点位ID")
    sensor_location = Column(String(20), nullable=False, comment="传感器位置: inlet/outlet/ambient")
    temp_warning_threshold = Column(Float, default=27.0, comment="温度告警阈值(℃)")
    temp_critical_threshold = Column(Float, default=32.0, comment="温度严重告警阈值(℃)")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CabinetITLoad(Base):
    """机柜IT负载监控配置"""

    __tablename__ = "cabinet_it_loads"
    __table_args__ = (UniqueConstraint("cabinet_id", name="uq_cabinet_it_load"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False, comment="机柜ID")
    power_point_id = Column(Integer, ForeignKey("points.id", ondelete="SET NULL"), nullable=True, comment="功率点位ID")
    rated_power_kw = Column(Float, nullable=True, comment="额定功率(kW)")
    design_load_kw = Column(Float, nullable=True, comment="设计负载(kW)")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")