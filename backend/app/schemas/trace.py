"""
数据追溯链 Pydantic Schema
用于 API 请求/响应的数据验证和序列化
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==================== 数据源映射 Schema ====================


class DataSourceMappingBase(BaseModel):
    """数据源映射基础Schema"""

    param_code: str = Field(..., description="参数编码")
    param_name: str = Field(..., description="参数名称")
    param_unit: Optional[str] = Field(None, description="参数单位")
    mapping_type: str = Field(..., description="映射类型: direct/aggregate/composite")
    description: Optional[str] = Field(None, description="参数说明")


class DataSourceMappingCreate(DataSourceMappingBase):
    """创建数据源映射"""

    # 直接映射字段
    source_table: Optional[str] = Field(None, description="源表名称")
    source_field: Optional[str] = Field(None, description="源字段名称")

    # 聚合映射字段
    aggregation_type: Optional[str] = Field(None, description="聚合函数类型")
    aggregation_params: Optional[Dict[str, Any]] = Field(None, description="聚合参数")
    filter_condition: Optional[str] = Field(None, description="筛选条件")
    time_range_type: Optional[str] = Field(None, description="时间范围类型")

    # 复合映射字段
    formula: Optional[str] = Field(None, description="计算公式")
    child_params: Optional[List[str]] = Field(None, description="子参数编码列表")

    template_ids: Optional[List[str]] = Field(None, description="适用模板ID列表")


class DataSourceMappingResponse(DataSourceMappingBase):
    """数据源映射响应"""

    id: int
    source_table: Optional[str] = None
    source_field: Optional[str] = None
    aggregation_type: Optional[str] = None
    aggregation_params: Optional[Dict[str, Any]] = None
    filter_condition: Optional[str] = None
    time_range_type: Optional[str] = None
    formula: Optional[str] = None
    child_params: Optional[List[str]] = None
    template_ids: Optional[List[str]] = None
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 追溯记录 Schema ====================


class TraceSourceInfo(BaseModel):
    """追溯数据源信息"""

    table: Optional[str] = Field(None, description="源表名称")
    field: Optional[str] = Field(None, description="源字段名称")
    filter: Optional[str] = Field(None, description="筛选条件")
    aggregation: Optional[str] = Field(None, description="聚合类型")
    params: Optional[Dict[str, Any]] = Field(None, description="聚合参数")
    time_range: Optional[Dict[str, str]] = Field(None, description="时间范围")


class TraceRecordBase(BaseModel):
    """追溯记录基础Schema"""

    trace_id: str = Field(..., description="追溯标识")
    param_code: str = Field(..., description="参数编码")
    param_name: Optional[str] = Field(None, description="参数名称")
    mapping_type: str = Field(..., description="映射类型")
    value: Optional[float] = Field(None, description="数值")
    formatted_value: Optional[str] = Field(None, description="格式化值")
    unit: Optional[str] = Field(None, description="单位")
    depth: int = Field(0, description="追溯深度")


class TraceRecordResponse(TraceRecordBase):
    """追溯记录响应"""

    id: int
    proposal_id: Optional[int] = None
    measure_id: Optional[int] = None
    source: Optional[TraceSourceInfo] = None
    formula: Optional[str] = None
    formula_display: Optional[str] = None
    query_sql: Optional[str] = None
    calculated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TraceTreeNode(BaseModel):
    """追溯树节点"""

    trace_id: str = Field(..., description="追溯标识")
    param_code: str = Field(..., description="参数编码")
    param_name: Optional[str] = Field(None, description="参数名称")
    mapping_type: str = Field(..., description="映射类型: direct/aggregate/composite")
    value: Optional[float] = Field(None, description="数值")
    formatted_value: Optional[str] = Field(None, description="格式化值")
    unit: Optional[str] = Field(None, description="单位")
    depth: int = Field(0, description="节点深度")
    calculated_at: Optional[str] = Field(None, description="计算时间")

    # 数据源信息 (direct/aggregate)
    source: Optional[TraceSourceInfo] = Field(None, description="数据源信息")
    query_sql: Optional[str] = Field(None, description="执行的SQL")

    # 公式信息 (composite)
    formula: Optional[str] = Field(None, description="计算公式")
    formula_display: Optional[str] = Field(None, description="公式展示(带数值)")

    # 子节点
    children: Optional[List["TraceTreeNode"]] = Field(None, description="子节点列表")


# 支持递归引用
TraceTreeNode.model_rebuild()


class TraceTreeResponse(BaseModel):
    """追溯树响应"""

    root_trace_id: str = Field(..., description="根追溯ID")
    tree: TraceTreeNode = Field(..., description="追溯树")
    total_nodes: int = Field(..., description="总节点数")
    max_depth: int = Field(..., description="最大深度")
    data_sources: List[str] = Field(..., description="涉及的数据源表")


# ==================== 措施追溯数据 Schema ====================


class MeasureTraceStep(BaseModel):
    """措施计算步骤"""

    step: int = Field(..., description="步骤序号")
    description: str = Field(..., description="步骤描述")
    trace_id: str = Field(..., description="关联追溯ID")
    formula: Optional[str] = Field(None, description="计算公式")
    result: Optional[float] = Field(None, description="计算结果")
    unit: Optional[str] = Field(None, description="单位")


class MeasureTraceData(BaseModel):
    """措施追溯数据"""

    root_trace_id: str = Field(..., description="根追溯ID")
    traces: Dict[str, str] = Field(..., description="参数编码到追溯ID的映射")
    calculation_steps: List[MeasureTraceStep] = Field(..., description="计算步骤列表")


class ProposalTraceSummary(BaseModel):
    """方案追溯汇总"""

    total_traces: int = Field(..., description="追溯记录总数")
    data_sources: List[str] = Field(..., description="涉及的数据源表")
    time_range: Dict[str, str] = Field(..., description="数据时间范围")
    root_trace_ids: List[str] = Field(..., description="根追溯ID列表")
    measures_count: int = Field(..., description="措施数量")


# ==================== API 请求 Schema ====================


class TraceQueryRequest(BaseModel):
    """追溯查询请求"""

    trace_id: str = Field(..., description="追溯ID")
    expand_depth: int = Field(10, description="展开深度, -1表示全部展开")
    include_sql: bool = Field(False, description="是否包含SQL语句")


class ProposalTraceRequest(BaseModel):
    """方案追溯请求"""

    proposal_id: int = Field(..., description="方案ID")
    include_measures: bool = Field(True, description="是否包含措施追溯")


# ==================== 模板参数 Schema ====================


class TemplateParameterBase(BaseModel):
    """模板参数基础Schema"""

    template_id: str = Field(..., description="模板ID")
    param_code: str = Field(..., description="参数编码")
    param_name: str = Field(..., description="参数显示名称")
    param_description: Optional[str] = Field(None, description="参数说明")


class TemplateParameterCreate(TemplateParameterBase):
    """创建模板参数"""

    mapping_id: Optional[int] = Field(None, description="关联映射配置ID")
    default_value: Optional[float] = Field(None, description="默认值")
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    is_required: bool = Field(True, description="是否必需")
    sort_order: int = Field(0, description="排序顺序")


class TemplateParameterResponse(TemplateParameterBase):
    """模板参数响应"""

    id: int
    template_name: Optional[str] = None
    mapping_id: Optional[int] = None
    default_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_required: bool = True
    sort_order: int = 0
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 通用响应 Schema ====================


class TraceListResponse(BaseModel):
    """追溯记录列表响应"""

    items: List[TraceRecordResponse]
    total: int
    page: int = 1
    page_size: int = 20


class MappingListResponse(BaseModel):
    """数据源映射列表响应"""

    items: List[DataSourceMappingResponse]
    total: int
