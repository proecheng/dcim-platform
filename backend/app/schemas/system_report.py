"""
系统报告 Schema
Story 26.2: 误诊反馈报告
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SystemReportBase(BaseModel):
    """系统报告基础 Schema"""

    report_type: str = Field(..., description="报告类型")
    report_period: str = Field(..., description="报告周期 YYYY-MM")
    report_version: Optional[str] = Field(default="v1.0", description="报告模板版本")
    content: str = Field(..., description="Markdown 格式报告内容")
    summary: Optional[dict] = Field(default=None, description="报告摘要（关键指标）")
    generated_by: Optional[str] = Field(default=None, description="生成者")


class SystemReportCreate(SystemReportBase):
    """创建系统报告 Schema"""

    pass


class SystemReportInfo(SystemReportBase):
    """系统报告信息 Schema"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    generated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiagnosisImprovementRuleBase(BaseModel):
    """诊断改进建议规则基础 Schema"""

    rule_type: str = Field(..., description="规则类型: false_positive 或 false_negative")
    node_id: Optional[str] = Field(default=None, description="故障树节点ID（误报规则）")
    fault_type: Optional[str] = Field(default=None, description="故障类型（漏报规则）")
    suggestion_template: str = Field(..., description="建议模板（支持变量替换）")
    priority: Optional[int] = Field(default=0, description="优先级（数字越大优先级越高）")
    is_active: Optional[bool] = Field(default=True, description="是否启用")


class DiagnosisImprovementRuleCreate(DiagnosisImprovementRuleBase):
    """创建诊断改进建议规则 Schema"""

    pass


class DiagnosisImprovementRuleInfo(DiagnosisImprovementRuleBase):
    """诊断改进建议规则信息 Schema"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
