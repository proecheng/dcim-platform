"""
容量管理数据模型
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.capacity import CapacityType, CapacityStatus


# ==================== 空间容量 Schemas ====================

class SpaceCapacityBase(BaseModel):
    """空间容量基础模型"""
    name: str = Field(..., description="名称")
    location: Optional[str] = Field(None, description="位置")
    total_area: Optional[float] = Field(None, description="总面积(平方米)")
    used_area: Optional[float] = Field(None, description="已用面积(平方米)")
    total_cabinets: Optional[int] = Field(None, description="总机柜数")
    used_cabinets: Optional[int] = Field(None, description="已用机柜数")
    total_u_positions: Optional[int] = Field(None, description="总U位数")
    used_u_positions: Optional[int] = Field(None, description="已用U位数")
    warning_threshold: Optional[float] = Field(80, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(95, description="严重告警阈值(%)")


class SpaceCapacityCreate(SpaceCapacityBase):
    """创建空间容量"""
    pass


class SpaceCapacityUpdate(BaseModel):
    """更新空间容量"""
    name: Optional[str] = Field(None, description="名称")
    location: Optional[str] = Field(None, description="位置")
    total_area: Optional[float] = Field(None, description="总面积(平方米)")
    used_area: Optional[float] = Field(None, description="已用面积(平方米)")
    total_cabinets: Optional[int] = Field(None, description="总机柜数")
    used_cabinets: Optional[int] = Field(None, description="已用机柜数")
    total_u_positions: Optional[int] = Field(None, description="总U位数")
    used_u_positions: Optional[int] = Field(None, description="已用U位数")
    warning_threshold: Optional[float] = Field(None, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(None, description="严重告警阈值(%)")


class SpaceCapacityResponse(SpaceCapacityBase):
    """空间容量响应"""
    id: int = Field(..., description="ID")
    status: CapacityStatus = Field(CapacityStatus.normal, description="容量状态")
    usage_rate: Optional[float] = Field(None, description="使用率(%)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 电力容量 Schemas ====================

class PowerCapacityBase(BaseModel):
    """电力容量基础模型"""
    name: str = Field(..., description="名称")
    location: Optional[str] = Field(None, description="位置")
    capacity_type: Optional[str] = Field(None, description="容量类型")
    total_capacity_kva: Optional[float] = Field(None, description="总容量(kVA)")
    used_capacity_kva: Optional[float] = Field(None, description="已用容量(kVA)")
    total_capacity_kw: Optional[float] = Field(None, description="总容量(kW)")
    used_capacity_kw: Optional[float] = Field(None, description="已用容量(kW)")
    redundancy_mode: Optional[str] = Field(None, description="冗余模式")
    warning_threshold: Optional[float] = Field(70, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(85, description="严重告警阈值(%)")
    parent_id: Optional[int] = Field(None, description="父级ID")


class PowerCapacityCreate(PowerCapacityBase):
    """创建电力容量"""
    pass


class PowerCapacityUpdate(BaseModel):
    """更新电力容量"""
    name: Optional[str] = Field(None, description="名称")
    location: Optional[str] = Field(None, description="位置")
    capacity_type: Optional[str] = Field(None, description="容量类型")
    total_capacity_kva: Optional[float] = Field(None, description="总容量(kVA)")
    used_capacity_kva: Optional[float] = Field(None, description="已用容量(kVA)")
    total_capacity_kw: Optional[float] = Field(None, description="总容量(kW)")
    used_capacity_kw: Optional[float] = Field(None, description="已用容量(kW)")
    redundancy_mode: Optional[str] = Field(None, description="冗余模式")
    warning_threshold: Optional[float] = Field(None, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(None, description="严重告警阈值(%)")
    parent_id: Optional[int] = Field(None, description="父级ID")


class PowerCapacityResponse(PowerCapacityBase):
    """电力容量响应"""
    id: int = Field(..., description="ID")
    status: CapacityStatus = Field(CapacityStatus.normal, description="容量状态")
    usage_rate: Optional[float] = Field(None, description="使用率(%)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 制冷容量 Schemas ====================

class CoolingCapacityBase(BaseModel):
    """制冷容量基础模型"""
    name: str = Field(..., description="名称")
    location: Optional[str] = Field(None, description="位置")
    total_cooling_kw: Optional[float] = Field(None, description="总制冷量(kW)")
    used_cooling_kw: Optional[float] = Field(None, description="已用制冷量(kW)")
    target_temperature: Optional[float] = Field(24, description="目标温度(℃)")
    current_temperature: Optional[float] = Field(None, description="当前温度(℃)")
    humidity_target: Optional[float] = Field(50, description="目标湿度(%)")
    current_humidity: Optional[float] = Field(None, description="当前湿度(%)")
    warning_threshold: Optional[float] = Field(75, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(90, description="严重告警阈值(%)")


class CoolingCapacityCreate(CoolingCapacityBase):
    """创建制冷容量"""
    pass


class CoolingCapacityUpdate(BaseModel):
    """更新制冷容量"""
    name: Optional[str] = Field(None, description="名称")
    location: Optional[str] = Field(None, description="位置")
    total_cooling_kw: Optional[float] = Field(None, description="总制冷量(kW)")
    used_cooling_kw: Optional[float] = Field(None, description="已用制冷量(kW)")
    target_temperature: Optional[float] = Field(None, description="目标温度(℃)")
    current_temperature: Optional[float] = Field(None, description="当前温度(℃)")
    humidity_target: Optional[float] = Field(None, description="目标湿度(%)")
    current_humidity: Optional[float] = Field(None, description="当前湿度(%)")
    warning_threshold: Optional[float] = Field(None, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(None, description="严重告警阈值(%)")


class CoolingCapacityResponse(CoolingCapacityBase):
    """制冷容量响应"""
    id: int = Field(..., description="ID")
    status: CapacityStatus = Field(CapacityStatus.normal, description="容量状态")
    usage_rate: Optional[float] = Field(None, description="使用率(%)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 承重容量 Schemas ====================

class WeightCapacityBase(BaseModel):
    """承重容量基础模型"""
    name: str = Field(..., description="名称")
    location: Optional[str] = Field(None, description="位置")
    capacity_type: Optional[str] = Field(None, description="容量类型")
    total_weight_kg: Optional[float] = Field(None, description="总承重(kg)")
    used_weight_kg: Optional[float] = Field(None, description="已用承重(kg)")
    warning_threshold: Optional[float] = Field(80, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(95, description="严重告警阈值(%)")


class WeightCapacityCreate(WeightCapacityBase):
    """创建承重容量"""
    pass


class WeightCapacityUpdate(BaseModel):
    """更新承重容量"""
    name: Optional[str] = Field(None, description="名称")
    location: Optional[str] = Field(None, description="位置")
    capacity_type: Optional[str] = Field(None, description="容量类型")
    total_weight_kg: Optional[float] = Field(None, description="总承重(kg)")
    used_weight_kg: Optional[float] = Field(None, description="已用承重(kg)")
    warning_threshold: Optional[float] = Field(None, description="告警阈值(%)")
    critical_threshold: Optional[float] = Field(None, description="严重告警阈值(%)")


class WeightCapacityResponse(WeightCapacityBase):
    """承重容量响应"""
    id: int = Field(..., description="ID")
    status: CapacityStatus = Field(CapacityStatus.normal, description="容量状态")
    usage_rate: Optional[float] = Field(None, description="使用率(%)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 容量规划 Schemas ====================

class CapacityPlanBase(BaseModel):
    """容量规划基础模型"""
    name: str = Field(..., description="规划名称")
    description: Optional[str] = Field(None, description="规划描述")
    device_count: Optional[int] = Field(None, description="设备数量")
    required_u: Optional[int] = Field(None, description="所需U位")
    required_power_kw: Optional[float] = Field(None, description="所需电力(kW)")
    required_cooling_kw: Optional[float] = Field(None, description="所需制冷量(kW)")
    required_weight_kg: Optional[float] = Field(None, description="所需承重(kg)")
    target_cabinet_id: Optional[int] = Field(None, description="目标机柜ID")


class CapacityPlanCreate(CapacityPlanBase):
    """创建容量规划"""
    created_by: Optional[str] = Field(None, description="创建人")


class CapacityPlanResponse(CapacityPlanBase):
    """容量规划响应"""
    id: int = Field(..., description="ID")
    is_feasible: Optional[bool] = Field(None, description="是否可行")
    feasibility_notes: Optional[str] = Field(None, description="可行性说明")
    created_by: Optional[str] = Field(None, description="创建人")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 容量统计 Schemas ====================

class CapacityStatistics(BaseModel):
    """容量统计信息"""
    space: Dict[str, float] = Field(default_factory=dict, description="空间容量统计")
    power: Dict[str, float] = Field(default_factory=dict, description="电力容量统计")
    cooling: Dict[str, float] = Field(default_factory=dict, description="制冷容量统计")
    weight: Dict[str, float] = Field(default_factory=dict, description="承重容量统计")


class CapacityTrend(BaseModel):
    """容量趋势"""
    timestamps: List[datetime] = Field(default_factory=list, description="时间戳列表")
    values: List[float] = Field(default_factory=list, description="数值列表")
    capacity_type: CapacityType = Field(..., description="容量类型")
