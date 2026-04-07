"""
Pydantic Schema for Chaos Drill - Story 26.7
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class DrillScheduleResponse(BaseModel):
    """演练计划响应"""

    enabled: bool = False
    cron_expression: str = "0 2 * * 0"
    window_minutes: int = 120
    scenarios: List[str] = ["circuit_breaker_degradation", "db_timeout_fallback"]
    confirmed: bool = False
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[str] = None
    next_run_time: Optional[str] = None


class DrillScheduleUpdateRequest(BaseModel):
    """更新演练计划请求"""

    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    window_minutes: Optional[int] = Field(None, ge=10, le=480)
    scenarios: Optional[List[str]] = None


class DrillTriggerRequest(BaseModel):
    """手动触发演练请求"""

    scenarios: List[str] = Field(
        default=["circuit_breaker_degradation", "db_timeout_fallback"],
        description="要执行的演练场景列表",
    )


class DrillTriggerResponse(BaseModel):
    """触发演练响应"""

    message: str
    drill_id: str


class DrillStopResponse(BaseModel):
    """终止演练响应"""

    message: str
    drill_id: Optional[str] = None


class DrillHistoryItem(BaseModel):
    """演练历史列表项"""

    id: int
    report_name: Optional[str] = None
    report_type: str
    status: Optional[str] = None
    report_data: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DrillHistoryResponse(BaseModel):
    """演练历史响应"""

    total: int
    items: List[DrillHistoryItem]
