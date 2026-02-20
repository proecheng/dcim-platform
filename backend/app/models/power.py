"""
供配电管理模型 - UPS设备、电池组
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Date, ForeignKey

from ..core.database import Base


class UPSDevice(Base):
    """UPS设备扩展表"""

    __tablename__ = "ups_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, comment="关联设备ID")
    ups_type = Column(String(20), default="standalone", comment="UPS类型: standalone/modular")
    rated_capacity = Column(Float, comment="额定容量(kVA)")
    rated_voltage = Column(Float, comment="额定电压(V)")
    phase_count = Column(Integer, default=3, comment="相数: 1/3")
    battery_group_count = Column(Integer, default=1, comment="电池组数量")
    bypass_enabled = Column(Boolean, default=True, comment="旁路是否启用")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class BatteryGroup(Base):
    """电池组表"""

    __tablename__ = "battery_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ups_device_id = Column(Integer, ForeignKey("ups_devices.id"), comment="关联UPS设备ID")
    group_name = Column(String(100), comment="电池组名称")
    battery_type = Column(String(20), default="lead_acid", comment="电池类型: lead_acid/lithium")
    rated_capacity = Column(Float, comment="额定容量(Ah)")
    rated_voltage = Column(Float, comment="额定电压(V)")
    cell_count = Column(Integer, comment="电芯数量")
    install_date = Column(Date, comment="安装日期")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
