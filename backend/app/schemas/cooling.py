"""
制冷系统 Schema - Pydantic v2
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# ==================== CoolingGroup Schemas ====================

class CoolingGroupBase(BaseModel):
    """群控组基础"""
    group_name: str
    group_mode: str = "independent"  # independent/linked
    description: Optional[str] = None


class CoolingGroupCreate(CoolingGroupBase):
    """创建群控组"""
    pass


class CoolingGroupUpdate(BaseModel):
    """更新群控组"""
    group_name: Optional[str] = None
    group_mode: Optional[str] = None
    description: Optional[str] = None


class CoolingGroupInfo(CoolingGroupBase):
    """群控组信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== CoolingUnit Schemas ====================

class CoolingUnitBase(BaseModel):
    """精密空调基础"""
    device_id: int
    unit_type: str = "indoor"  # indoor/outdoor
    cooling_capacity_kw: Optional[float] = None
    refrigerant_type: Optional[str] = None
    compressor_count: int = 1
    fan_count: int = 2
    group_id: Optional[int] = None
    description: Optional[str] = None


class CoolingUnitCreate(CoolingUnitBase):
    """创建精密空调"""
    pass


class CoolingUnitUpdate(BaseModel):
    """更新精密空调"""
    device_id: Optional[int] = None
    unit_type: Optional[str] = None
    cooling_capacity_kw: Optional[float] = None
    refrigerant_type: Optional[str] = None
    compressor_count: Optional[int] = None
    fan_count: Optional[int] = None
    group_id: Optional[int] = None
    description: Optional[str] = None


class CoolingUnitInfo(CoolingUnitBase):
    """精密空调信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 关联信息
    device_code: Optional[str] = None
    device_name: Optional[str] = None
    device_status: Optional[str] = None
    group_name: Optional[str] = None


# ==================== ColdAisle Schemas ====================

class ColdAisleBase(BaseModel):
    """冷通道基础"""
    device_id: int
    aisle_code: Optional[str] = None
    aisle_name: Optional[str] = None
    skylight_count: int = 2
    location: Optional[str] = None
    description: Optional[str] = None


class ColdAisleCreate(ColdAisleBase):
    """创建冷通道"""
    pass


class ColdAisleUpdate(BaseModel):
    """更新冷通道"""
    device_id: Optional[int] = None
    aisle_code: Optional[str] = None
    aisle_name: Optional[str] = None
    skylight_count: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None


class ColdAisleInfo(ColdAisleBase):
    """冷通道信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 关联信息
    device_code: Optional[str] = None
    device_name: Optional[str] = None
    device_status: Optional[str] = None


# ==================== Overview & Detail Schemas ====================

class CoolingOverviewSummary(BaseModel):
    """制冷系统总览统计"""
    ac_total: int = 0           # 空调总数
    ac_running: int = 0         # 运行中
    ac_stopped: int = 0         # 已停止
    ac_alarm: int = 0           # 告警中
    avg_supply_temp: float = 0.0  # 平均送风温度
    avg_return_temp: float = 0.0  # 平均回风温度
    cold_aisle_total: int = 0   # 冷通道总数
    group_total: int = 0        # 群控组总数
    group_linked: int = 0       # 联动模式组数


class CoolingUnitDetail(BaseModel):
    """空调详情（含关联信息）"""
    unit: CoolingUnitInfo
    device: Optional[dict] = None  # DeviceInfo
    points: List[dict] = []        # Point realtime values


class ColdAisleDetail(BaseModel):
    """冷通道详情（含关联信息）"""
    aisle: ColdAisleInfo
    device: Optional[dict] = None
    points: List[dict] = []
