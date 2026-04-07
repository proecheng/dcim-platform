"""预测性维护 Schema — Story 36.3 + 36.4"""

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


# ==================== Story 36.4: Dashboard Schema ====================


class DashboardSummary(BaseModel):
    """仪表盘统计概览"""

    total: int
    healthy: int  # 健康
    attention: int  # 关注
    warning: int  # 预警
    danger: int  # 危险


class DeviceHealthItem(BaseModel):
    """设备健康度列表项"""

    device_id: int
    device_name: str | None = None
    device_type: str | None = None
    score: float
    health_level: Literal["健康", "关注", "预警", "危险"]
    data_sufficiency: str | None = None
    degradation_score: float | None = None
    alarm_count: int = 0
    calculated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseModel):
    """仪表盘响应"""

    summary: DashboardSummary
    devices: list[DeviceHealthItem]


class ScoreFactorDetail(BaseModel):
    """评分因子明细"""

    degradation: dict | None = None
    alarm: dict | None = None
    maintenance: dict | None = None
    data_sufficiency: str | None = None
    plugin_key: str | None = None


class DeviceDetailResponse(BaseModel):
    """设备健康度详情响应"""

    health: DeviceHealthItem
    factors: ScoreFactorDetail | None = None
    advices: list[MaintenanceAdviceInfo] = []
