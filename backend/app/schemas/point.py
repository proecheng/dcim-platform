"""
点位相关 Schema
"""
from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PointCreate(BaseModel):
    """创建点位"""
    point_code: str
    point_name: str
    point_type: str  # AI, DI, AO, DO
    device_id: Optional[int] = None
    device_type: str
    area_code: str
    unit: Optional[str] = None
    data_type: str = "float"
    min_range: Optional[float] = None
    max_range: Optional[float] = None
    precision: int = 2
    collect_interval: int = 10
    store_interval: int = 60
    is_virtual: bool = False
    calc_formula: Optional[str] = None
    description: Optional[str] = None


class PointUpdate(BaseModel):
    """更新点位"""
    point_name: Optional[str] = None
    device_id: Optional[int] = None
    device_type: Optional[str] = None
    area_code: Optional[str] = None
    unit: Optional[str] = None
    min_range: Optional[float] = None
    max_range: Optional[float] = None
    precision: Optional[int] = None
    collect_interval: Optional[int] = None
    store_interval: Optional[int] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class PointInfo(BaseModel):
    """点位信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_code: str
    point_name: str
    point_type: str
    device_id: Optional[int] = None
    device_type: str
    area_code: str
    unit: Optional[str] = None
    data_type: str = "float"
    min_range: Optional[float] = None
    max_range: Optional[float] = None
    precision: int = 2
    collect_interval: int = 10
    store_interval: int = 60
    is_enabled: bool = True
    is_virtual: bool = False
    description: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 用能设备关联
    energy_device_id: Optional[int] = None
    energy_device_name: Optional[str] = None  # 关联的用能设备名称
    energy_device_code: Optional[str] = None  # 关联的用能设备编码


class PointTypesSummary(BaseModel):
    """点位类型统计"""
    total: int
    enabled: int
    ai: int = 0
    di: int = 0
    ao: int = 0
    do: int = 0
    by_device_type: Dict[str, int] = {}


class PointGroupCreate(BaseModel):
    """创建点位分组"""
    group_name: str
    group_type: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0


class PointGroupInfo(BaseModel):
    """点位分组信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_name: str
    group_type: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None


# 保持向后兼容
PointBase = PointCreate
PointResponse = PointInfo


class PointRealtimeResponse(BaseModel):
    """点位实时数据响应"""
    model_config = ConfigDict(from_attributes=True)

    point_id: int
    point_code: str
    point_name: str
    point_type: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    quality: int = 0
    status: str = "normal"
    updated_at: Optional[datetime] = None


class PointHistoryResponse(BaseModel):
    """点位历史数据响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_id: int
    value: float
    quality: int
    recorded_at: datetime


class PointTypeStats(BaseModel):
    """点位类型统计"""
    point_type: str
    count: int
    enabled_count: int


class RealtimeSummary(BaseModel):
    """实时数据汇总"""
    total: int
    normal: int
    alarm: int
    offline: int
