"""
节能方案相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# ========== 措施相关模型 ==========

class MeasureResponse(BaseModel):
    """措施响应模型"""
    id: int
    measure_code: str = Field(..., description="措施编号")
    regulation_object: str = Field(..., description="调节对象")
    regulation_description: Optional[str] = Field(None, description="调节说明")
    current_state: Optional[Dict[str, Any]] = Field(None, description="当前状态")
    target_state: Optional[Dict[str, Any]] = Field(None, description="目标状态")
    calculation_formula: Optional[str] = Field(None, description="计算公式")
    calculation_basis: Optional[str] = Field(None, description="计算依据")
    annual_benefit: Optional[Decimal] = Field(None, description="年收益 万元/年")
    investment: Optional[Decimal] = Field(0, description="投资 万元")
    is_selected: bool = Field(False, description="是否选择")
    execution_status: str = Field("pending", description="执行状态")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


# ========== 方案相关模型 ==========

class ProposalResponse(BaseModel):
    """方案响应模型"""
    id: int
    proposal_code: str = Field(..., description="方案编号")
    proposal_type: str = Field(..., description="方案类型 A/B")
    template_id: str = Field(..., description="模板ID")
    template_name: str = Field(..., description="模板名称")
    total_benefit: Optional[Decimal] = Field(None, description="总收益 万元/年")
    total_investment: Optional[Decimal] = Field(0, description="总投资 万元")
    current_situation: Optional[Dict[str, Any]] = Field(None, description="当前状况")
    status: str = Field("pending", description="状态")
    created_at: datetime
    updated_at: datetime
    measures: List[MeasureResponse] = Field(default_factory=list, description="措施列表")

    class Config:
        from_attributes = True


class ProposalCreate(BaseModel):
    """创建方案请求模型"""
    template_id: str = Field(..., description="模板ID: A1/A2/A3/A4/A5/B1")
    analysis_days: int = Field(30, description="分析天数", ge=1, le=365)


class MeasureAcceptRequest(BaseModel):
    """接受方案请求模型"""
    selected_measure_ids: List[int] = Field(..., description="选中的措施ID列表")


# ========== 监控相关模型 ==========

class ExecutionLogResponse(BaseModel):
    """执行日志响应"""
    id: int
    execution_time: datetime
    power_before: Optional[Decimal]
    power_after: Optional[Decimal]
    power_saved: Optional[Decimal]
    expected_power_saved: Optional[Decimal]
    result: Optional[str]
    result_message: Optional[str]

    class Config:
        from_attributes = True


class MeasureMonitoringResponse(BaseModel):
    """措施监控响应"""
    measure_id: int
    measure_code: str
    regulation_object: str
    expected_benefit: Optional[Decimal]
    actual_benefit: Optional[Decimal] = Field(None, description="实际收益（从日志计算）")
    execution_count: int = Field(0, description="执行次数")
    success_count: int = Field(0, description="成功次数")
    latest_execution: Optional[ExecutionLogResponse] = None

    class Config:
        from_attributes = True


class ProposalMonitoringResponse(BaseModel):
    """方案监控响应"""
    proposal_id: int
    proposal_code: str
    template_name: str
    total_expected_benefit: Optional[Decimal]
    total_actual_benefit: Optional[Decimal] = Field(None, description="累计实际收益")
    measures: List[MeasureMonitoringResponse]
