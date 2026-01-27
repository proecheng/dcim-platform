"""
阈值配置相关 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ThresholdCreate(BaseModel):
    """创建阈值配置"""
    point_id: int
    threshold_type: str  # high_high, high, low, low_low, equal, change
    threshold_value: Optional[float] = None
    alarm_level: str = "minor"
    alarm_message: Optional[str] = None
    delay_seconds: int = 0
    dead_band: float = 0
    priority: int = 0


class ThresholdUpdate(BaseModel):
    """更新阈值配置"""
    threshold_type: Optional[str] = None
    threshold_value: Optional[float] = None
    alarm_level: Optional[str] = None
    alarm_message: Optional[str] = None
    delay_seconds: Optional[int] = None
    dead_band: Optional[float] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None


class ThresholdInfo(BaseModel):
    """阈值配置信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_id: int
    point_code: Optional[str] = None
    point_name: Optional[str] = None
    threshold_type: str
    threshold_value: Optional[float] = None
    alarm_level: str
    alarm_message: Optional[str] = None
    delay_seconds: int = 0
    dead_band: float = 0
    is_enabled: bool = True
    priority: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ThresholdBatchCreate(BaseModel):
    """批量创建阈值配置"""
    point_ids: List[int]
    threshold_type: str
    threshold_value: Optional[float] = None
    alarm_level: str = "minor"
    alarm_message: Optional[str] = None
    delay_seconds: int = 0
    dead_band: float = 0
