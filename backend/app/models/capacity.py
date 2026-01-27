"""
容量管理模型
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from ..core.database import Base


# ==================== 枚举定义 ====================

class CapacityType(str, PyEnum):
    """容量类型枚举"""
    space = "space"         # 空间
    power = "power"         # 电力
    cooling = "cooling"     # 制冷
    weight = "weight"       # 承重
    network = "network"     # 网络


class CapacityStatus(str, PyEnum):
    """容量状态枚举"""
    normal = "normal"       # 正常
    warning = "warning"     # 警告
    critical = "critical"   # 严重
    full = "full"           # 已满


# ==================== 空间容量模型 ====================

class SpaceCapacity(Base):
    """空间容量表"""
    __tablename__ = "space_capacities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    total_area = Column(Float, comment="总面积(平方米)")
    used_area = Column(Float, comment="已用面积(平方米)")
    total_cabinets = Column(Integer, comment="总机柜数")
    used_cabinets = Column(Integer, comment="已用机柜数")
    total_u_positions = Column(Integer, comment="总U位数")
    used_u_positions = Column(Integer, comment="已用U位数")
    warning_threshold = Column(Float, default=80, comment="告警阈值(%)")
    critical_threshold = Column(Float, default=95, comment="严重告警阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal, comment="容量状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


# ==================== 电力容量模型 ====================

class PowerCapacity(Base):
    """电力容量表"""
    __tablename__ = "power_capacities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    capacity_type = Column(String(50), comment="容量类型")
    total_capacity_kva = Column(Float, comment="总容量(kVA)")
    used_capacity_kva = Column(Float, comment="已用容量(kVA)")
    total_capacity_kw = Column(Float, comment="总容量(kW)")
    used_capacity_kw = Column(Float, comment="已用容量(kW)")
    redundancy_mode = Column(String(50), comment="冗余模式")
    warning_threshold = Column(Float, default=70, comment="告警阈值(%)")
    critical_threshold = Column(Float, default=85, comment="严重告警阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal, comment="容量状态")
    parent_id = Column(Integer, ForeignKey("power_capacities.id"), comment="父级ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 自引用关系
    parent = relationship("PowerCapacity", remote_side=[id], backref="children")


# ==================== 制冷容量模型 ====================

class CoolingCapacity(Base):
    """制冷容量表"""
    __tablename__ = "cooling_capacities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    total_cooling_kw = Column(Float, comment="总制冷量(kW)")
    used_cooling_kw = Column(Float, comment="已用制冷量(kW)")
    target_temperature = Column(Float, default=24, comment="目标温度(℃)")
    current_temperature = Column(Float, comment="当前温度(℃)")
    humidity_target = Column(Float, default=50, comment="目标湿度(%)")
    current_humidity = Column(Float, comment="当前湿度(%)")
    warning_threshold = Column(Float, default=75, comment="告警阈值(%)")
    critical_threshold = Column(Float, default=90, comment="严重告警阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal, comment="容量状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


# ==================== 承重容量模型 ====================

class WeightCapacity(Base):
    """承重容量表"""
    __tablename__ = "weight_capacities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    capacity_type = Column(String(50), comment="容量类型")
    total_weight_kg = Column(Float, comment="总承重(kg)")
    used_weight_kg = Column(Float, comment="已用承重(kg)")
    warning_threshold = Column(Float, default=80, comment="告警阈值(%)")
    critical_threshold = Column(Float, default=95, comment="严重告警阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal, comment="容量状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


# ==================== 容量规划模型 ====================

class CapacityPlan(Base):
    """容量规划表"""
    __tablename__ = "capacity_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="规划名称")
    description = Column(Text, comment="规划描述")
    device_count = Column(Integer, comment="设备数量")
    required_u = Column(Integer, comment="所需U位")
    required_power_kw = Column(Float, comment="所需电力(kW)")
    required_cooling_kw = Column(Float, comment="所需制冷量(kW)")
    required_weight_kg = Column(Float, comment="所需承重(kg)")
    target_cabinet_id = Column(Integer, ForeignKey("cabinets.id"), comment="目标机柜ID")
    is_feasible = Column(Boolean, comment="是否可行")
    feasibility_notes = Column(Text, comment="可行性说明")
    created_by = Column(String(100), comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    target_cabinet = relationship("Cabinet")


# ==================== 容量历史模型 ====================

class CapacityHistory(Base):
    """容量历史记录表"""
    __tablename__ = "capacity_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capacity_type = Column(Enum(CapacityType), nullable=False, comment="容量类型")
    reference_id = Column(Integer, nullable=False, comment="关联ID")
    reference_name = Column(String(100), comment="关联名称")
    total_value = Column(Float, comment="总量")
    used_value = Column(Float, comment="已用量")
    usage_rate = Column(Float, comment="使用率(%)")
    recorded_at = Column(DateTime, default=datetime.now, comment="记录时间")
