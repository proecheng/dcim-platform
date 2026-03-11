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
        default=None,
        description="制冷功率计划(kW)，长度=int(hours×12)，null则使用当前功率"
    )
    hours: float = Field(
        default=1.0,
        ge=0.5,
        le=24.0,
        description="预测时长(小时)"
    )


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
