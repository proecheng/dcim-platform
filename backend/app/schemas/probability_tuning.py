"""
概率调参 Schema
Story 26.3: 闭环学习自动调参
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProbabilityAdjustmentBase(BaseModel):
    """概率调参基础 Schema"""

    tree_id: int = Field(..., description="故障树ID")
    node_id: int = Field(..., description="节点ID")
    node_name: str = Field(..., max_length=200, description="节点名称")
    node_type: str = Field(..., max_length=20, description="节点类型: root/intermediate/leaf")
    current_probability: float = Field(..., ge=0.0, le=1.0, description="当前先验概率")
    proposed_probability: float = Field(..., ge=0.0, le=1.0, description="建议先验概率")
    adjustment_percent: float = Field(..., description="调整百分比")
    sample_count: int = Field(..., ge=0, description="样本数")
    accurate_count: int = Field(..., ge=0, description="准确标注次数")
    inaccurate_count: int = Field(..., ge=0, description="不准确标注次数")
    accuracy_rate: float = Field(..., ge=0.0, le=1.0, description="准确率")


class ProbabilityAdjustmentCreate(ProbabilityAdjustmentBase):
    """创建概率调参记录"""

    pass


class ProbabilityAdjustmentResponse(ProbabilityAdjustmentBase):
    """概率调参记录响应"""

    id: int
    status: str = Field(..., description="状态: pending/approved/rejected")
    reason: Optional[str] = Field(None, description="审批理由或拒绝原因")
    approved_by: Optional[int] = Field(None, description="审批人ID")
    approved_at: Optional[datetime] = Field(None, description="审批时间")
    version: int = Field(..., description="乐观锁版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    # 扩展字段（通过 JOIN 获取）
    tree_name: Optional[str] = Field(None, description="故障树名称")

    model_config = ConfigDict(from_attributes=True)


class ProbabilityAdjustmentListResponse(BaseModel):
    """概率调参记录列表响应"""

    items: list[ProbabilityAdjustmentResponse]
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

    tree_id: Optional[int] = Field(None, description="故障树ID（可选，不指定则分析所有活跃故障树）")


class AnalyzeResponse(BaseModel):
    """调参分析响应"""

    analyzed_trees: int = Field(..., description="分析的故障树数量")
    total_adjustments: int = Field(..., description="生成的调参建议总数")
    pending_approvals: int = Field(..., description="待审批的调参建议数量")


class RollbackResponse(BaseModel):
    """回滚响应"""

    message: str
    tree_id: int
    active_version: str
    previous_version: str
