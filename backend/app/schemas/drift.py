"""
传感器数据漂移检测 Schema
Story 9-7: 传感器数据漂移检测
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DriftDetectionResultResponse(BaseModel):
    """漂移检测结果响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_id: int
    point_code: str
    point_name: str
    area_code: Optional[str] = None
    status: str  # suspected / confirmed / resolved
    mean_value: float
    std_value: float
    current_value: float
    deviation_sigma: float
    cross_validation_result: Optional[str] = None
    diagnosis: str
    detected_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DriftDetectionSummary(BaseModel):
    """漂移检测概览"""
    total_checked: int
    suspected_count: int
    confirmed_count: int
    resolved_count: int
    skipped_count: int  # 数据不足跳过的点位数


class DriftDetectResponse(BaseModel):
    """触发漂移检测响应"""
    message: str
    total_checked: int
    new_suspected: int
    new_confirmed: int
    auto_resolved: int
