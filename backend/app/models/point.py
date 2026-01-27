"""
点位模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey

from ..core.database import Base


class Point(Base):
    """点位表 - 核心表"""
    __tablename__ = "points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_code = Column(String(50), unique=True, nullable=False, comment="点位编码")
    point_name = Column(String(100), nullable=False, comment="点位名称")
    point_type = Column(String(2), nullable=False, comment="点位类型: AI/DI/AO/DO")
    device_id = Column(Integer, ForeignKey("devices.id"), comment="关联设备ID")
    device_type = Column(String(20), nullable=False, comment="设备类型: TH/UPS/PDU/AC/DOOR/SMOKE/WATER/IR/FAN/LIGHT")
    area_code = Column(String(10), nullable=False, comment="区域代码: A1/A2/B1/B2")
    unit = Column(String(20), comment="单位")
    data_type = Column(String(10), default="float", comment="数据类型: float/boolean")
    min_range = Column(Float, comment="量程最小值")
    max_range = Column(Float, comment="量程最大值")
    precision = Column(Integer, default=2, comment="小数位数")
    collect_interval = Column(Integer, default=10, comment="采集周期(秒)")
    store_interval = Column(Integer, default=60, comment="存储周期(秒)")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_virtual = Column(Boolean, default=False, comment="是否虚拟点位")
    calc_formula = Column(Text, comment="计算公式(虚拟点)")
    description = Column(Text, comment="描述")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PointRealtime(Base):
    """点位实时值表"""
    __tablename__ = "point_realtime"

    point_id = Column(Integer, ForeignKey("points.id"), primary_key=True, comment="点位ID")
    raw_value = Column(Float, comment="原始值")
    value = Column(Float, comment="工程值")
    value_text = Column(String(50), comment="状态文本")
    quality = Column(Integer, default=0, comment="数据质量: 0=好 1=不确定 2=坏")
    status = Column(String(20), default="normal", comment="状态: normal/alarm/offline")
    alarm_level = Column(String(20), comment="当前告警级别")
    change_count = Column(Integer, default=0, comment="变化次数")
    last_change_at = Column(DateTime, comment="最后变化时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PointGroup(Base):
    """点位分组表"""
    __tablename__ = "point_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(100), nullable=False, comment="分组名称")
    group_type = Column(String(20), comment="分组类型: area/device_type/custom")
    parent_id = Column(Integer, comment="父分组ID")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class PointGroupMember(Base):
    """点位分组关系表"""
    __tablename__ = "point_group_members"

    group_id = Column(Integer, ForeignKey("point_groups.id"), primary_key=True, comment="分组ID")
    point_id = Column(Integer, ForeignKey("points.id"), primary_key=True, comment="点位ID")
