"""
设备相关 Schema
"""
from typing import Optional, Dict
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class DeviceCreate(BaseModel):
    """创建设备"""
    device_code: str
    device_name: str
    device_type: str
    area_code: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    install_date: Optional[date] = None
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    description: Optional[str] = None


class DeviceUpdate(BaseModel):
    """更新设备"""
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    area_code: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    install_date: Optional[date] = None
    status: Optional[str] = None
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class DeviceInfo(BaseModel):
    """设备信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_code: str
    device_name: str
    device_type: str
    area_code: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    install_date: Optional[date] = None
    status: str = "online"
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    description: Optional[str] = None
    is_enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeviceTree(BaseModel):
    """设备树节点"""
    id: Optional[int] = None
    label: str
    code: Optional[str] = None
    status: Optional[str] = None
    children: Optional[list] = None


class DeviceStatusSummary(BaseModel):
    """设备状态汇总"""
    total: int
    enabled: int
    online: int
    offline: int
    alarm: int = 0
    maintenance: int = 0
    by_type: Dict[str, int] = {}
