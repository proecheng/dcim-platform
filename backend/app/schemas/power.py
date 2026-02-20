"""
供配电管理 Schema
"""

from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


# ========== UPS设备 ==========


class UPSDeviceCreate(BaseModel):
    """创建UPS设备"""

    device_id: int
    ups_type: Optional[str] = "standalone"
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    phase_count: Optional[int] = 3
    battery_group_count: Optional[int] = 1
    bypass_enabled: Optional[bool] = True
    description: Optional[str] = None


class UPSDeviceUpdate(BaseModel):
    """更新UPS设备"""

    ups_type: Optional[str] = None
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    phase_count: Optional[int] = None
    battery_group_count: Optional[int] = None
    bypass_enabled: Optional[bool] = None
    description: Optional[str] = None


class UPSDeviceInfo(BaseModel):
    """UPS设备信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    ups_type: Optional[str] = "standalone"
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    phase_count: int = 3
    battery_group_count: int = 1
    bypass_enabled: bool = True
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ========== 电池组 ==========


class BatteryGroupCreate(BaseModel):
    """创建电池组"""

    ups_device_id: int
    group_name: str
    battery_type: Optional[str] = "lead_acid"
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    cell_count: Optional[int] = None
    install_date: Optional[date] = None
    description: Optional[str] = None


class BatteryGroupUpdate(BaseModel):
    """更新电池组"""

    group_name: Optional[str] = None
    battery_type: Optional[str] = None
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    cell_count: Optional[int] = None
    install_date: Optional[date] = None
    description: Optional[str] = None


class BatteryGroupInfo(BaseModel):
    """电池组信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ups_device_id: Optional[int] = None
    group_name: Optional[str] = None
    battery_type: Optional[str] = "lead_acid"
    rated_capacity: Optional[float] = None
    rated_voltage: Optional[float] = None
    cell_count: Optional[int] = None
    install_date: Optional[date] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ========== 供配电总览 ==========


class PowerOverviewSummary(BaseModel):
    """供配电总览统计"""

    ups_total: int = 0
    ups_online: int = 0
    ups_offline: int = 0
    ups_alarm: int = 0
    battery_total: int = 0
    battery_avg_soh: float = 0.0
    battery_lowest_soc: float = 0.0
    cabinet_total: int = 0
    pdu_total: int = 0
    total_load_kw: float = 0.0
    avg_load_rate: float = 0.0
