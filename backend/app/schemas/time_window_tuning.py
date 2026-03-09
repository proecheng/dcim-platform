"""
时间窗口调参 Schema
Story 26.4: 时间窗口自适应
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TimeWindowAdjustmentBase(BaseModel):
    """时间窗口调参基础 Schema"""

    device_type: str = Field(..., max_length=100, description="设备类型")
    current_window_minutes: int = Field(..., ge=1, le=120, description="当前时间窗口(分钟)")
    proposed_window_minutes: int = Field(..., ge=1, le=120, description="建议时间窗口(分钟)")
    adjustment_percent: float = Field(..., description="调整百分比")
    sample_count: int = Field(..., ge=0, description="样本数")
    p50_duration_seconds: float = Field(..., ge=0, description="P50持续时长(秒)")
    p90_duration_seconds: float = Field(..., ge=0, description="P90持续时长(秒)")


class TimeWindowAdjustmentCreate(TimeWindowAdjustmentBase):
    """创建时间窗口调参记录"""

    pass


class TimeWindowAdjustmentResponse(TimeWindowAdjustmentBase):
    """时间窗口调参记录响应"""

    id: int
    status: str = Field(..., description="状态: pending/approved/rejected")
    reason: Optional[str] = Field(None, description="审批理由或拒绝原因")
    approved_by: Optional[int] = Field(None, description="审批人ID")
    approved_at: Optional[datetime] = Field(None, description="审批时间")
    version: int = Field(..., description="乐观锁版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class TimeWindowAdjustmentListResponse(BaseModel):
    """时间窗口调参记录列表响应"""

    items: list[TimeWindowAdjustmentResponse]
    total: int
    page: int
    page_size: int


class ApprovalRequest(BaseModel):
    """审批请求"""

    reason: Optional[str] = Field(None, max_length=500, description="审批理由（可选）")


class RejectRequest(BaseModel):
    """拒绝请求"""

    reason: str = Field(..., max_length=500, description="拒绝理由")


class AnalyzeRequest(BaseModel):
    """调参分析请求"""

    device_type: Optional[str] = Field(None, description="设备类型（可选，不指定则分析所有设备类型）")


class AnalyzeResponse(BaseModel):
    """调参分析响应"""

    analyzed_device_types: int = Field(..., description="分析的设备类型数量")
    total_adjustments: int = Field(..., description="生成的调参建议总数")
    pending_approvals: int = Field(..., description="待审批的调参建议数量")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""

    device_type: str = Field(..., max_length=100, description="设备类型")
    time_window_minutes: int = Field(..., ge=1, le=120, description="时间窗口(分钟)")


class ConfigUpdateResponse(BaseModel):
    """配置更新响应"""

    message: str
    device_type: str
    time_window_minutes: int
