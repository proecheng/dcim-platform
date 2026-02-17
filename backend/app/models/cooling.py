"""
制冷系统模型 - 精密空调、群控组、冷通道
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey

from ..core.database import Base


class CoolingGroup(Base):
    """空调群控组"""
    __tablename__ = "cooling_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(100), nullable=False, comment="群控组名称")
    group_mode = Column(String(20), default="independent", comment="模式: independent/linked")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CoolingUnit(Base):
    """精密空调扩展表"""
    __tablename__ = "cooling_units"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, comment="关联设备ID")
    unit_type = Column(String(20), default="indoor", comment="类型: indoor/outdoor")
    cooling_capacity_kw = Column(Float, comment="制冷量(kW)")
    refrigerant_type = Column(String(20), comment="制冷剂类型")
    compressor_count = Column(Integer, default=1, comment="压缩机数量")
    fan_count = Column(Integer, default=2, comment="风机数量")
    group_id = Column(Integer, ForeignKey("cooling_groups.id"), nullable=True, comment="群控组ID")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class ColdAisle(Base):
    """冷通道（天窗系统）"""
    __tablename__ = "cold_aisles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, comment="关联设备ID")
    aisle_code = Column(String(50), comment="通道编码")
    aisle_name = Column(String(100), comment="通道名称")
    skylight_count = Column(Integer, default=2, comment="天窗数量")
    location = Column(String(100), comment="位置描述")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
