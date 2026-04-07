"""
数据追溯链相关的 Pydantic 模型
实现专利 S1/S3 - 数据追溯链展示和用户交互
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# ========== 追溯记录模型 ==========


class TraceRecordResponse(BaseModel):
    """追溯记录响应模型"""

    id: int
    trace_id: str = Field(..., description="全局唯一追溯标识")

    # 关联信息
    proposal_id: Optional[int] = Field(None, description="关联方案ID")
    measure_id: Optional[int] = Field(None, description="关联措施ID")

    # 参数信息
    param_code: str = Field(..., description="参数编码")
    param_name: Optional[str] = Field(None, description="参数名称")

    # 映射类型
    mapping_type: str = Field(..., description="映射类型: direct/aggregate/composite/ml_prediction")

    # 数据源信息
    source_table: Optional[str] = Field(None, description="源表名称")
    source_field: Optional[str] = Field(None, description="源字段名称")
    filter_condition: Optional[str] = Field(None, description="筛选条件")
    aggregation_type: Optional[str] = Field(None, description="聚合函数类型")
    time_range_start: Optional[datetime] = Field(None, description="时间范围开始")
    time_range_end: Optional[datetime] = Field(None, description="时间范围结束")

    # 计算信息
    formula: Optional[str] = Field(None, description="计算公式")
    formula_display: Optional[str] = Field(None, description="公式展示形式（带具体数值）")

    # 值信息
    raw_value: Optional[Decimal] = Field(None, description="原始值")
    formatted_value: Optional[str] = Field(None, description="格式化后的值")
    value_unit: Optional[str] = Field(None, description="值单位")

    # 树状结构
    parent_trace_id: Optional[str] = Field(None, description="父追溯ID")
    child_trace_ids: Optional[List[str]] = Field(None, description="子追溯ID列表")
    depth: int = Field(0, description="追溯深度")

    # ML 预测信息
    ml_model_type: Optional[str] = Field(None, description="ML模型类型")
    ml_model_version: Optional[str] = Field(None, description="模型版本号")
    ml_confidence: Optional[float] = Field(None, description="预测置信度 0-1")
    ml_input_features: Optional[Dict[str, Any]] = Field(None, description="模型输入特征摘要")
    ml_output_raw: Optional[Dict[str, Any]] = Field(None, description="模型原始输出")

    # 时间戳
    calculated_at: Optional[datetime] = Field(None, description="计算时间")

    model_config = ConfigDict(from_attributes=True)


class TraceNodeResponse(BaseModel):
    """追溯树节点响应模型"""

    trace_id: str = Field(..., description="追溯标识")
    param_name: str = Field(..., description="参数名称")
    mapping_type: str = Field(..., description="映射类型")
    formatted_value: Optional[str] = Field(None, description="格式化值")
    value_unit: Optional[str] = Field(None, description="单位")
    formula_display: Optional[str] = Field(None, description="公式展示")
    depth: int = Field(0, description="深度")

    # ML 信息 (如果是 ML 预测)
    ml_model_type: Optional[str] = Field(None, description="ML模型类型")
    ml_confidence: Optional[float] = Field(None, description="置信度")

    # 子节点
    children: List["TraceNodeResponse"] = Field(default_factory=list, description="子节点列表")

    model_config = ConfigDict(from_attributes=True)


TraceNodeResponse.model_rebuild()


class TraceTreeResponse(BaseModel):
    """追溯树响应模型"""

    root_trace_id: str = Field(..., description="根追溯ID")
    proposal_id: Optional[int] = Field(None, description="关联方案ID")
    measure_id: Optional[int] = Field(None, description="关联措施ID")
    total_nodes: int = Field(0, description="节点总数")
    max_depth: int = Field(0, description="最大深度")
    tree: TraceNodeResponse = Field(..., description="追溯树结构")


class TraceSummaryResponse(BaseModel):
    """追溯汇总响应"""

    proposal_id: int
    total_traces: int = Field(0, description="追溯记录总数")
    direct_count: int = Field(0, description="直接映射数量")
    aggregate_count: int = Field(0, description="聚合映射数量")
    composite_count: int = Field(0, description="复合映射数量")
    ml_prediction_count: int = Field(0, description="ML预测数量")

    # 按措施分组的追溯统计
    measures_traces: List[Dict[str, Any]] = Field(default_factory=list, description="各措施追溯统计")

    # ML 分析汇总
    ml_summary: Optional[Dict[str, Any]] = Field(None, description="ML分析汇总")


# ========== 措施详情模型 (含追溯) ==========


class MeasureTraceInfo(BaseModel):
    """措施追溯信息"""

    trace_count: int = Field(0, description="追溯记录数")
    key_traces: List[TraceRecordResponse] = Field(default_factory=list, description="关键追溯记录")
    trace_tree_available: bool = Field(False, description="是否有追溯树")


class MLPredictionInfo(BaseModel):
    """ML 预测信息"""

    has_ml_prediction: bool = Field(False, description="是否有ML预测")
    model_type: Optional[str] = Field(None, description="模型类型")
    confidence: Optional[float] = Field(None, description="置信度")
    prediction_details: Optional[Dict[str, Any]] = Field(None, description="预测详情")


class MeasureDetailResponse(BaseModel):
    """措施详情响应 (含追溯和ML信息)"""

    # 基本信息
    id: int
    measure_code: str = Field(..., description="措施编号")
    regulation_object: str = Field(..., description="调节对象")
    regulation_description: Optional[str] = Field(None, description="调节说明")

    # 状态信息
    current_state: Optional[Dict[str, Any]] = Field(None, description="当前状态")
    target_state: Optional[Dict[str, Any]] = Field(None, description="目标状态")
    state_comparison: Optional[Dict[str, Any]] = Field(None, description="状态对比")

    # 收益信息
    calculation_formula: Optional[str] = Field(None, description="计算公式")
    calculation_basis: Optional[str] = Field(None, description="计算依据")
    annual_benefit: Optional[Decimal] = Field(None, description="年收益 万元/年")
    investment: Optional[Decimal] = Field(0, description="投资 万元")

    # 选择状态
    is_selected: bool = Field(False, description="是否选择")
    user_status: str = Field("pending", description="用户状态: pending/accepted/rejected/deferred")
    execution_status: str = Field("pending", description="执行状态")

    # ML 预测信息
    ml_prediction: Optional[MLPredictionInfo] = Field(None, description="ML预测信息")

    # 追溯信息
    trace_info: Optional[MeasureTraceInfo] = Field(None, description="追溯信息")

    # 时间戳
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeasureStatusUpdate(BaseModel):
    """措施状态更新请求"""

    status: str = Field(..., description="新状态: accepted/rejected/deferred")
    reason: Optional[str] = Field(None, description="状态变更原因")


class BatchMeasureStatusUpdate(BaseModel):
    """批量措施状态更新请求"""

    measure_updates: List[Dict[str, Any]] = Field(
        ..., description="措施状态更新列表 [{measure_id: 1, status: 'accepted'}, ...]"
    )


class MeasureStatusResponse(BaseModel):
    """措施状态更新响应"""

    measure_id: int
    old_status: str
    new_status: str
    updated_at: datetime
    proposal_total_benefit_updated: Optional[Decimal] = Field(None, description="更新后的方案总收益")
