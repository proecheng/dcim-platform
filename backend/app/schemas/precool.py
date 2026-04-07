"""
预冷系统 Pydantic Schema

Story 29.4: 温度预测 API 端点
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """温度预测请求"""

    q_cool_schedule: Optional[List[float]] = Field(
        default=None, description="制冷功率计划(kW)，长度=int(hours×12)，null则使用当前功率"
    )
    hours: float = Field(default=1.0, ge=0.5, le=24.0, description="预测时长(小时)")


class PredictResponse(BaseModel):
    """温度预测响应"""

    model_config = {"protected_namespaces": ()}

    zone_id: int
    predicted_temp: float
    prediction_horizon_min: int
    temperature_trajectory: List[float]
    time_steps: List[str]
    model_version: str
    data_quality: Optional[dict] = None
    thm_result: Optional[dict] = None


class ThermalParameterOut(BaseModel):
    """热参数标定记录输出"""

    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: int
    cooling_zone_id: int
    thermal_R: Optional[float] = None
    thermal_C: Optional[float] = None
    fitting_r_squared: Optional[float] = None
    fitting_method: Optional[str] = None
    sample_count: Optional[int] = None
    calibrated_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime


class ValidationReport(BaseModel):
    """模型验证报告"""

    zone_id: int
    mae_1h: Optional[float] = None
    mae_3h: Optional[float] = None
    max_deviation: Optional[float] = None
    sample_count: int = 0
    period_days: int = 7


class DashboardZone(BaseModel):
    """仪表盘单个区域数据"""

    model_config = {"protected_namespaces": ()}

    zone_id: int
    zone_name: str
    current_temp: Optional[float] = None
    headroom: Optional[float] = None
    model_mode: str
    shiftable_ratio: Optional[float] = None


class DashboardResponse(BaseModel):
    """仪表盘聚合响应"""

    zones: List[DashboardZone]
    status_summary: Dict[str, int]
    today_savings: float = 0.0


# ==================== Story 30.3: 回退保护 API Schema ====================


class RollbackTriggerInfo(BaseModel):
    """回退触发条件信息"""

    trigger_type: str
    since: Optional[datetime] = None
    event_id: Optional[int] = None
    recovering: bool = False


class RollbackStatusResponse(BaseModel):
    """回退状态响应"""

    zone_id: int
    has_active_rollback: bool
    active_triggers: List[RollbackTriggerInfo]


class RollbackEventOut(BaseModel):
    """回退事件历史输出"""

    model_config = {"from_attributes": True}

    id: int
    zone_id: int
    trigger_type: str
    trigger_value: Optional[float] = None
    threshold: Optional[float] = None
    action: str
    status: str
    context_json: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class RollbackOverviewResponse(BaseModel):
    """回退全局概览"""

    total_zones: int
    zones_with_active_rollback: int
    total_active_triggers: int
    trigger_type_counts: Dict[str, int]
    recent_events_24h: int
    zone_statuses: List[RollbackStatusResponse]


# ==================== Story 31.3: 预冷计划 API Schema ====================


class ScheduleCreateRequest(BaseModel):
    """预冷计划生成请求"""

    schedule_date: Optional[str] = Field(
        default=None,
        description="计划日期 YYYY-MM-DD，默认明天",
    )


class ScheduleListItem(BaseModel):
    """预冷计划列表项（不含 trajectory，减少传输量）"""

    model_config = {"from_attributes": True}

    id: int
    cooling_zone_id: int
    schedule_date: str
    precool_start_time: str
    precool_end_time: str
    target_temp: float
    peak_start_time: str
    peak_end_time: str
    planned_savings_kwh: Optional[float] = None
    actual_savings_kwh: Optional[float] = None
    status: str
    abort_reason: Optional[str] = None
    is_validated: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduleDetailOut(BaseModel):
    """预冷计划详情（含完整 trajectory）"""

    model_config = {"from_attributes": True}

    id: int
    cooling_zone_id: int
    schedule_date: str
    precool_start_time: str
    precool_end_time: str
    target_temp: float
    peak_start_time: str
    peak_end_time: str
    planned_savings_kwh: Optional[float] = None
    actual_savings_kwh: Optional[float] = None
    status: str
    abort_reason: Optional[str] = None
    temperature_trajectory: Optional[dict] = None
    is_validated: bool = False
    validated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduleAbortRequest(BaseModel):
    """中止计划请求"""

    reason: Optional[str] = Field(
        default="manual_abort",
        max_length=500,
        description="中止原因",
    )


class ScheduleAbortResponse(BaseModel):
    """中止计划响应"""

    status: str
    abort_reason: Optional[str] = None


# ==================== Story 31.4: 预冷配置 Schema ====================


class PrecoolConfigOut(BaseModel):
    """预冷配置输出"""

    zone_id: int
    precool_enabled: bool = False
    precool_target_temp: float = 18.0


class PrecoolConfigUpdate(BaseModel):
    """预冷配置更新请求"""

    precool_enabled: Optional[bool] = Field(
        default=None,
        description="是否启用预冷功能",
    )
    precool_target_temp: Optional[float] = Field(
        default=None,
        ge=18.0,
        le=25.0,
        description="预冷目标温度 °C（范围 18-25）",
    )


# ==================== Story 32.2: 部署阶段 Schema ====================


class DeploymentPhaseOut(BaseModel):
    """部署阶段查询响应"""

    current_phase: int = Field(ge=1, le=4)
    phase_name: str
    description: str
    updated_at: Optional[str] = None


class DeploymentPhaseUpdate(BaseModel):
    """部署阶段切换请求"""

    phase: int = Field(ge=1, le=4, description="目标阶段: 1=THM, 2=校准, 3=TCL上线, 4=VPP接入")
    force: bool = Field(default=False, description="强制跳过前置检查（仅 admin）")


class PreconditionCheckResult(BaseModel):
    """前置检查结果"""

    passed: bool
    details: List[str] = []


# ==================== Story 33.1: VPP 可调容量 Schema ====================


class VppZoneCapacity(BaseModel):
    """VPP 单区域可调容量"""

    model_config = {"from_attributes": True}

    zone_id: int
    zone_name: str
    T_current: Optional[float] = None
    headroom_down: float  # TEMP_MAX - T_current（温度上升空间，用于向下可调）
    headroom_up: float  # T_current - TEMP_MIN（温度下降空间，用于向上可调）
    down_adjustable_thermal_kw: float
    up_adjustable_thermal_kw: float
    down_adjustable_kw: float
    up_adjustable_kw: float
    cop: float


class VppDispatchRequest(BaseModel):
    """VPP 调控指令请求"""

    command_type: str  # Literal 验证在端点层做
    target_power_kw: float
    duration_minutes: int
    priority: int = 1


class VppDispatchResponse(BaseModel):
    """VPP 调控指令响应"""

    dispatch_id: str
    command_type: str
    target_power_kw: float
    duration_minutes: int
    status: str  # accepted / rejected
    reject_reason: Optional[str] = None
    max_adjustable_kw: Optional[float] = None
    accepted_power_kw: Optional[float] = None
    aborted_schedule_id: Optional[int] = None


class VppDispatchListItem(BaseModel):
    """VPP 调控指令列表项（Story 33.3）"""

    dispatch_id: str
    command_type: str
    target_power_kw: float
    duration_minutes: int
    status: str
    reject_reason: Optional[str] = None
    max_adjustable_kw: Optional[float] = None
    accepted_power_kw: Optional[float] = None
    aborted_schedule_id: Optional[int] = None
    created_at: Optional[str] = None


class VppStatisticsResponse(BaseModel):
    """VPP 需求响应统计（Story 33.3）"""

    daily: dict  # {count, total_power_kw, estimated_savings_yuan}
    monthly: dict  # {count, total_power_kw, estimated_savings_yuan}


class VppCapacityResponse(BaseModel):
    """VPP 聚合可调容量响应"""

    down_adjustable_kw: float  # 聚合向下可调电功率
    up_adjustable_kw: float  # 聚合向上可调电功率
    down_adjustable_thermal_kw: float
    up_adjustable_thermal_kw: float
    T_current: Optional[float] = None  # 代表温度（所有区域最高）
    headroom_down: float  # 各区域最小向下裕度
    headroom_up: float  # 各区域最小向上裕度
    response_window_hours: float
    zones: List[VppZoneCapacity]
    cached_at: Optional[str] = None
