"""
告警相关 Schema
"""
from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AlarmInfo(BaseModel):
    """告警信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    alarm_no: str
    point_id: int
    point_code: Optional[str] = None
    point_name: Optional[str] = None
    alarm_level: str
    alarm_type: Optional[str] = None
    alarm_message: str
    trigger_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: str
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    ack_remark: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolve_remark: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: Optional[datetime] = None


class AlarmAcknowledge(BaseModel):
    """确认告警"""
    remark: Optional[str] = None


class AlarmResolve(BaseModel):
    """解决告警"""
    remark: Optional[str] = None
    resolve_type: str = "manual"


class AlarmCount(BaseModel):
    """告警数量统计"""
    critical: int = 0
    major: int = 0
    minor: int = 0
    info: int = 0
    total: int = 0


class AlarmStatistics(BaseModel):
    """告警统计"""
    total: int
    by_level: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    avg_duration_seconds: int = 0
    start_time: datetime
    end_time: datetime


class AlarmTrend(BaseModel):
    """告警趋势"""
    date: str
    critical: int = 0
    major: int = 0
    minor: int = 0
    info: int = 0


# 向后兼容
class AlarmThresholdBase(BaseModel):
    point_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str = "minor"
    alarm_message: Optional[str] = None
    delay_seconds: int = 0


class AlarmThresholdCreate(AlarmThresholdBase):
    pass


class AlarmThresholdUpdate(BaseModel):
    threshold_type: Optional[str] = None
    threshold_value: Optional[float] = None
    alarm_level: Optional[str] = None
    alarm_message: Optional[str] = None
    delay_seconds: Optional[int] = None
    is_enabled: Optional[bool] = None


class AlarmThresholdResponse(AlarmThresholdBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_enabled: bool


AlarmResponse = AlarmInfo


class AlarmStats(BaseModel):
    """告警统计"""
    total: int
    active: int
    acknowledged: int
    resolved: int
    by_level: dict
