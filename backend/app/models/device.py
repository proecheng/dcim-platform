"""
设备模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Date

from ..core.database import Base


class Device(Base):
    """设备表"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_code = Column(String(50), unique=True, nullable=False, comment="设备编码")
    device_name = Column(String(100), nullable=False, comment="设备名称")
    device_type = Column(String(20), nullable=False, comment="设备类型: UPS/AC/PDU/TH/DOOR/SMOKE/WATER")
    area_code = Column(String(10), nullable=False, comment="区域代码")
    manufacturer = Column(String(100), comment="制造商")
    model = Column(String(100), comment="型号")
    serial_number = Column(String(100), comment="序列号")
    install_date = Column(Date, comment="安装日期")
    status = Column(String(20), default="online", comment="状态: online/offline/maintenance/alarm")
    location_x = Column(Float, comment="平面图X坐标")
    location_y = Column(Float, comment="平面图Y坐标")
    description = Column(Text, comment="描述")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
