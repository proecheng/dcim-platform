"""
Load Shift Schemas - Pydantic models for load shifting API
负荷转移数据模型
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date, time


# ========== Enums ==========

class ShiftPeriodType(str, Enum):
    """Shift period type - 转移时段类型"""
    PEAK = "peak"           # 尖峰时段
    SHARP = "sharp"         # 高峰时段
    FLAT = "flat"           # 平段
    VALLEY = "valley"       # 谷段


class ShiftPlanStatus(str, Enum):
    """Shift plan status - 转移计划状态"""
    DRAFT = "draft"                     # 草稿
    PENDING_APPROVAL = "pending_approval"  # 待审批
    APPROVED = "approved"               # 已批准
    REJECTED = "rejected"               # 已拒绝
    EXECUTING = "executing"             # 执行中
    COMPLETED = "completed"             # 已完成
    FAILED = "failed"                   # 执行失败
    CANCELLED = "cancelled"             # 已取消


class ApprovalStatus(str, Enum):
    """Approval status - 审批状态"""
    PENDING = "pending"     # 待审批
    APPROVED = "approved"   # 已批准
    REJECTED = "rejected"   # 已拒绝


class ExecutionStatus(str, Enum):
    """Execution status - 执行状态"""
    NOT_STARTED = "not_started"  # 未开始
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


class ConstraintType(str, Enum):
    """Constraint type - 约束类型"""
    POWER = "power"         # 功率约束
    TIME = "time"           # 时间约束
    DEVICE = "device"       # 设备约束
    COOLING = "cooling"     # 制冷约束
    SAFETY = "safety"       # 安全约束
    ELECTRICAL = "electrical"  # 电气约束


class OpportunityStatus(str, Enum):
    """Opportunity status - 机会状态"""
    PENDING = "pending"         # 待处理
    CONVERTED = "converted"     # 已转换为计划
    REJECTED = "rejected"       # 已拒绝
    EXPIRED = "expired"         # 已过期

class OpportunityPriority(str, Enum):
    """Opportunity priority - 机会优先级"""
    HIGH = "high"       # 高优先级
    MEDIUM = "medium"   # 中优先级
    LOW = "low"         # 低优先级


class AnalysisType(str, Enum):
    """Analysis type - 分析类型"""
    FEASIBILITY = "feasibility"  # 可行性分析
    CONSTRAINT = "constraint"    # 约束检查
    RISK = "risk"                # 风险评估
    BENEFIT = "benefit"          # 效益分析


# ========== Shift Plan Schemas ==========

class ShiftPlanBase(BaseModel):
    """Shift plan base model - 转移计划基础模型"""
    plan_name: str = Field(..., description="计划名称")
    shift_from_period: ShiftPeriodType = Field(..., description="转出时段")
    shift_to_period: ShiftPeriodType = Field(..., description="转入时段")
    shift_date: date = Field(..., description="转移日期")
    start_time: time = Field(..., description="开始时间")
    end_time: time = Field(..., description="结束时间")
    target_shift_power: float = Field(..., gt=0, description="目标转移功率 kW")
    selected_devices: List[int] = Field(default_factory=list, description="选中设备ID列表")
    constraints: Optional[Dict[str, Any]] = Field(None, description="约束配置")
    expected_cost_saving: Optional[float] = Field(None, description="预期成本节省 元")
    expected_energy_saving: Optional[float] = Field(None, description="预期节能量 kWh")
    description: Optional[str] = Field(None, description="计划描述")


class ShiftPlanCreate(ShiftPlanBase):
    """Create shift plan - 创建转移计划"""
    pass


class ShiftPlanUpdate(BaseModel):
    """Update shift plan - 更新转移计划"""
    plan_name: Optional[str] = None
    shift_from_period: Optional[ShiftPeriodType] = None
    shift_to_period: Optional[ShiftPeriodType] = None
    shift_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    target_shift_power: Optional[float] = Field(None, gt=0)
    selected_devices: Optional[List[int]] = None
    constraints: Optional[Dict[str, Any]] = None
    expected_cost_saving: Optional[float] = None
    expected_energy_saving: Optional[float] = None
    description: Optional[str] = None
    status: Optional[ShiftPlanStatus] = None


class ShiftPlanResponse(ShiftPlanBase):
    """Shift plan response - 转移计划响应"""
    id: int
    plan_code: str
    status: ShiftPlanStatus
    approval_status: ApprovalStatus
    execution_status: ExecutionStatus
    actual_shift_power: Optional[float] = None
    actual_cost_saving: Optional[float] = None
    actual_energy_saving: Optional[float] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShiftPlanDetail(ShiftPlanResponse):
    """Shift plan detail - 转移计划详情"""
    constraint_check_result: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    device_details: Optional[List[Dict[str, Any]]] = None
    execution_records: Optional[List[Dict[str, Any]]] = None


class ShiftPlanApproval(BaseModel):
    """Shift plan approval - 转移计划审批"""
    approval_status: ApprovalStatus = Field(..., description="审批状态")
    approval_comment: Optional[str] = Field(None, description="审批意见")


# ========== Shift Execution Schemas ==========

class ShiftExecutionBase(BaseModel):
    """Shift execution base model - 转移执行基础模型"""
    plan_id: int = Field(..., description="计划ID")
    execution_status: ExecutionStatus = Field(..., description="执行状态")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    before_power: float = Field(..., description="转移前功率 kW")
    after_power: float = Field(..., description="转移后功率 kW")
    actual_shift_power: float = Field(..., description="实际转移功率 kW")
    device_execution_details: Optional[Dict[str, Any]] = Field(None, description="设备执行详情")
    cooling_linkage_data: Optional[Dict[str, Any]] = Field(None, description="制冷联动数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class ShiftExecutionCreate(ShiftExecutionBase):
    """Create shift execution - 创建转移执行记录"""
    pass


class ShiftExecutionResponse(ShiftExecutionBase):
    """Shift execution response - 转移执行响应"""
    id: int
    execution_code: str
    duration_minutes: Optional[int] = None
    success_rate: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShiftExecutionDetail(ShiftExecutionResponse):
    """Shift execution detail - 转移执行详情"""
    plan_details: Optional[ShiftPlanResponse] = None
    device_execution_list: Optional[List[Dict[str, Any]]] = None
    cooling_linkage_records: Optional[List[Dict[str, Any]]] = None


# ========== Shift Opportunity Schemas ==========

class ShiftOpportunityBase(BaseModel):
    """Shift opportunity base model - 转移机会基础模型"""
    analysis_date: date = Field(..., description="分析日期")
    shift_from_period: ShiftPeriodType = Field(..., description="转出时段")
    shift_to_period: ShiftPeriodType = Field(..., description="转入时段")
    recommended_shift_power: float = Field(..., gt=0, description="推荐转移功率 kW")
    recommended_devices: List[int] = Field(default_factory=list, description="推荐设备ID列表")
    estimated_cost_saving: float = Field(..., description="预测成本节省 元")
    estimated_energy_saving: float = Field(..., description="预测节能量 kWh")
    confidence_score: float = Field(..., ge=0, le=1, description="置信度评分 0-1")
    reason: Optional[str] = Field(None, description="推荐原因")


class ShiftOpportunityResponse(ShiftOpportunityBase):
    """Shift opportunity response - 转移机会响应"""
    id: int
    opportunity_code: str
    opportunity_name: str = Field(..., description="机会名称")
    status: OpportunityStatus
    converted_plan_id: Optional[int] = None
    priority: str = Field(..., description="优先级")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShiftOpportunityDetail(ShiftOpportunityResponse):
    """Shift opportunity detail - 转移机会详情"""
    feasibility_analysis: Optional[Dict[str, Any]] = None
    constraint_check: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None


class ConvertOpportunityRequest(BaseModel):
    """Convert opportunity to plan - 转换机会为计划"""
    plan_name: str = Field(..., description="计划名称")
    description: Optional[str] = Field(None, description="计划描述")


# ========== Shift Constraint Schemas ==========

class ShiftConstraintBase(BaseModel):
    """Shift constraint base model - 转移约束基础模型"""
    constraint_name: str = Field(..., description="约束名称")
    constraint_type: ConstraintType = Field(..., description="约束类型")
    constraint_config: Dict[str, Any] = Field(..., description="约束配置")
    device_id: Optional[int] = Field(None, description="设备ID (null表示全局约束)")
    is_enabled: bool = Field(True, description="是否启用")
    priority: int = Field(1, ge=1, le=10, description="优先级 1-10")
    description: Optional[str] = Field(None, description="约束描述")


class ShiftConstraintCreate(ShiftConstraintBase):
    """Create shift constraint - 创建转移约束"""
    pass


class ShiftConstraintUpdate(BaseModel):
    """Update shift constraint - 更新转移约束"""
    constraint_name: Optional[str] = None
    constraint_type: Optional[ConstraintType] = None
    constraint_config: Optional[Dict[str, Any]] = None
    device_id: Optional[int] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    description: Optional[str] = None


class ShiftConstraintResponse(ShiftConstraintBase):
    """Shift constraint response - 转移约束响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== Analysis Schemas ==========

class FeasibilityAnalysisRequest(BaseModel):
    """Feasibility analysis request - 可行性分析请求"""
    shift_date: date = Field(..., description="转移日期")
    shift_from_period: ShiftPeriodType = Field(..., description="转出时段")
    shift_to_period: ShiftPeriodType = Field(..., description="转入时段")
    target_shift_power: float = Field(..., gt=0, description="目标转移功率 kW")
    selected_devices: Optional[List[int]] = Field(None, description="选中设备ID列表")


class FeasibilityAnalysisResponse(BaseModel):
    """Feasibility analysis response - 可行性分析响应"""
    is_feasible: bool = Field(..., description="是否可行")
    feasibility_score: float = Field(..., ge=0, le=1, description="可行性评分 0-1")
    available_devices: List[Dict[str, Any]] = Field(default_factory=list, description="可用设备列表")
    max_shift_power: float = Field(..., description="最大可转移功率 kW")
    recommended_devices: List[int] = Field(default_factory=list, description="推荐设备ID列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    suggestions: List[str] = Field(default_factory=list, description="建议信息")


class ConstraintCheckResult(BaseModel):
    """Constraint check result - 约束检查结果"""
    is_valid: bool = Field(..., description="是否通过")
    violated_constraints: List[Dict[str, Any]] = Field(default_factory=list, description="违反的约束")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    constraint_details: Dict[str, Any] = Field(default_factory=dict, description="约束详情")


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response - 风险评估响应"""
    overall_risk_level: str = Field(..., description="总体风险等级: low/medium/high")
    risk_score: float = Field(..., ge=0, le=1, description="风险评分 0-1")
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list, description="风险因素")
    mitigation_measures: List[str] = Field(default_factory=list, description="缓解措施")


class BenefitAnalysisResponse(BaseModel):
    """Benefit analysis response - 效益分析响应"""
    cost_saving: float = Field(..., description="成本节省 元")
    energy_saving: float = Field(..., description="节能量 kWh")
    peak_reduction: float = Field(..., description="削峰量 kW")
    valley_filling: float = Field(..., description="填谷量 kW")
    payback_period_days: Optional[int] = Field(None, description="投资回收期 天")
    roi: Optional[float] = Field(None, description="投资回报率")
    benefit_details: Dict[str, Any] = Field(default_factory=dict, description="效益详情")


# ========== Device Schemas ==========

class DeviceShiftPotentialResponse(BaseModel):
    """Device shift potential response - 设备转移潜力响应"""
    device_id: int
    device_name: str
    device_type: str
    rated_power: float
    current_power: float
    shift_potential: float = Field(..., description="转移潜力 kW")
    is_shiftable: bool = Field(..., description="是否可转移")
    shift_score: float = Field(..., ge=0, le=1, description="转移评分 0-1")
    constraints: List[str] = Field(default_factory=list, description="约束条件")
    last_shift_time: Optional[datetime] = Field(None, description="上次转移时间")
    shift_count_today: int = Field(0, description="今日转移次数")


# ========== Dashboard Schemas ==========

class ShiftDashboardOverview(BaseModel):
    """Shift dashboard overview - 转移仪表盘概览"""
    total_plans: int = Field(0, description="总计划数")
    pending_approval: int = Field(0, description="待审批数")
    executing: int = Field(0, description="执行中数")
    completed_today: int = Field(0, description="今日完成数")
    total_cost_saving_today: float = Field(0, description="今日成本节省 元")
    total_energy_saving_today: float = Field(0, description="今日节能量 kWh")
    total_shift_power_today: float = Field(0, description="今日转移功率 kW")
    success_rate: float = Field(0, ge=0, le=1, description="成功率")
    opportunities_count: int = Field(0, description="待处理机会数")


class ShiftRealtimeData(BaseModel):
    """Shift realtime data - 转移实时数据"""
    current_shift_power: float = Field(0, description="当前转移功率 kW")
    target_shift_power: float = Field(0, description="目标转移功率 kW")
    completion_rate: float = Field(0, ge=0, le=1, description="完成率")
    active_devices: int = Field(0, description="活跃设备数")
    cooling_status: Dict[str, Any] = Field(default_factory=dict, description="制冷状态")
    execution_status: str = Field("idle", description="执行状态")


class ShiftTrendData(BaseModel):
    """Shift trend data - 转移趋势数据"""
    date: date
    total_plans: int = Field(0, description="计划数")
    completed_plans: int = Field(0, description="完成数")
    total_shift_power: float = Field(0, description="转移功率 kW")
    cost_saving: float = Field(0, description="成本节省 元")
    energy_saving: float = Field(0, description="节能量 kWh")
    success_rate: float = Field(0, ge=0, le=1, description="成功率")


# ========== Statistics Schemas ==========

class ShiftStatisticsSummary(BaseModel):
    """Shift statistics summary - 转移统计汇总"""
    period: str = Field(..., description="统计周期: daily/weekly/monthly/yearly")
    start_date: date
    end_date: date
    total_plans: int = Field(0, description="总计划数")
    completed_plans: int = Field(0, description="完成数")
    failed_plans: int = Field(0, description="失败数")
    total_shift_power: float = Field(0, description="总转移功率 kW")
    total_cost_saving: float = Field(0, description="总成本节省 元")
    total_energy_saving: float = Field(0, description="总节能量 kWh")
    average_success_rate: float = Field(0, ge=0, le=1, description="平均成功率")
    peak_reduction_total: float = Field(0, description="总削峰量 kW")
    valley_filling_total: float = Field(0, description="总填谷量 kW")


class ShiftMonthlyReport(BaseModel):
    """Shift monthly report - 转移月度报告"""
    year: int
    month: int
    summary: ShiftStatisticsSummary
    daily_trends: List[ShiftTrendData] = Field(default_factory=list, description="日趋势")
    top_devices: List[Dict[str, Any]] = Field(default_factory=list, description="Top设备")
    cost_breakdown: Dict[str, float] = Field(default_factory=dict, description="成本分解")
    recommendations: List[str] = Field(default_factory=list, description="优化建议")


class ShiftYearlyReport(BaseModel):
    """Shift yearly report - 转移年度报告"""
    year: int
    summary: ShiftStatisticsSummary
    monthly_trends: List[Dict[str, Any]] = Field(default_factory=list, description="月趋势")
    seasonal_analysis: Dict[str, Any] = Field(default_factory=dict, description="季节分析")
    roi_analysis: Dict[str, Any] = Field(default_factory=dict, description="ROI分析")
    recommendations: List[str] = Field(default_factory=list, description="优化建议")
