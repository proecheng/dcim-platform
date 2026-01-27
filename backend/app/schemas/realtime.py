"""
实时数据相关 Schema
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class RealtimeData(BaseModel):
    """实时数据"""
    point_id: int
    point_code: str
    point_name: str
    point_type: str
    device_type: str
    area_code: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    quality: int = 0
    status: str = "normal"
    alarm_level: Optional[str] = None
    updated_at: Optional[datetime] = None


class RealtimeSummary(BaseModel):
    """实时数据汇总"""
    total_points: int
    normal_count: int
    alarm_count: int
    offline_count: int
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    key_points: Dict[str, Any] = {}


class ControlCommand(BaseModel):
    """控制指令"""
    value: float
    remark: Optional[str] = None
