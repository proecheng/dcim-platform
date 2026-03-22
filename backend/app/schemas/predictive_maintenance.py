"""预测性维护 Schema — Story 36.3"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MaintenanceAdviceInfo(BaseModel):
    """维护建议信息"""
    id: int
    device_id: int
    device_name: str | None = None
    device_type: str | None = None
    health_score: float | None = None
    urgency: Literal["high", "medium"] | None = None
    reason: str | None = None
    suggested_action: str | None = None
    status: Literal["pending", "converted", "rejected", "auto_closed"]
    feedback: str | None = None
    work_order_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: int | None = None
    model_config = ConfigDict(from_attributes=True)


class AdviceRejectRequest(BaseModel):
    """拒绝建议请求"""
    feedback: str = Field(..., min_length=2, max_length=500)


class AdviceConfirmResponse(BaseModel):
    """确认建议响应"""
    advice_id: int
    work_order_id: int
    work_order_no: str
    status: str = "converted"
