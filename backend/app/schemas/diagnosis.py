"""
诊断 Schema
Story 9-3: 智能故障诊断
Story 24.6: 诊断会话、审计日志、结果扩展
Story 25.3: UPS电池SOH预测
Story 25.4: N+X冗余拓扑与断路器保护逻辑
"""

from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


# ==================== Cause Item ====================


class DiagnosisCauseItem(BaseModel):
    """诊断原因条目"""

    cause: str
    confidence: int
    suggested_actions: List[str] = []


# ==================== Rule Schemas ====================


class DiagnosisRuleCreate(BaseModel):
    """创建诊断规则"""

    rule_code: str
    name: str
    description: Optional[str] = None
    category: str
    trigger_condition: dict
    diagnosis_logic: dict
    priority: int = 0
    is_enabled: bool = True


class DiagnosisRuleUpdate(BaseModel):
    """更新诊断规则"""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_condition: Optional[dict] = None
    diagnosis_logic: Optional[dict] = None
    priority: Optional[int] = None
    is_enabled: Optional[bool] = None


class DiagnosisRuleResponse(BaseModel):
    """诊断规则响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    name: str
    description: Optional[str] = None
    category: str
    trigger_condition: Optional[dict] = None
    diagnosis_logic: Optional[dict] = None
    priority: int
    is_enabled: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime


# ==================== Result Schemas ====================


class DiagnosisResultResponse(BaseModel):
    """诊断结果响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alarm_id: Optional[int] = None
    alarm_no: Optional[str] = None
    rule_id: Optional[int] = None
    rule_code: Optional[str] = None
    device_type: Optional[str] = None
    zone: Optional[str] = None
    causes: Optional[List[DiagnosisCauseItem]] = None
    diagnosis_time_ms: int = 0
    created_at: datetime

    # Story 24.6 扩展字段
    session_id: Optional[int] = None
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    reasoning_path: Optional[Any] = None
    evidence: Optional[Any] = None
    fault_tree_version: Optional[str] = None


# ==================== Session Schemas ====================


class DiagnosisSessionResponse(BaseModel):
    """诊断会话响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger_alarm_id: Optional[int] = None
    device_id: Optional[int] = None
    engine_level: str
    status: str
    push_status: str
    max_confidence: Optional[float] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    inference_time_ms: int = 0
    created_at: datetime
    result: Optional[DiagnosisResultResponse] = None


class DiagnosisSessionListQuery(BaseModel):
    """诊断会话列表查询参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    device_id: Optional[int] = Field(default=None, description="设备ID")
    engine_level: Optional[str] = Field(default=None, description="推理级别: L1/L2/L3")
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="最低置信度")
    start_date: Optional[datetime] = Field(default=None, description="开始时间")
    end_date: Optional[datetime] = Field(default=None, description="结束时间")


# ==================== Audit Log Schemas ====================


class DiagnosisAuditLogResponse(BaseModel):
    """诊断审计日志响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    engine_level: str
    inference_time_ms: int = 0
    fault_tree_version: Optional[str] = None
    created_at: datetime


# ==================== Category Schema ====================


class DiagnosisCategoryItem(BaseModel):
    """诊断分类条目"""

    code: str
    name: str
    count: int = 0


# ==================== Annotation Schemas ====================


class DiagnosisAnnotationCreate(BaseModel):
    """创建诊断标注"""

    session_id: int = Field(..., description="诊断会话ID")
    annotation: str = Field(..., description="标注结果: accurate/inaccurate/unknown")
    actual_root_cause: Optional[str] = Field(None, max_length=1000, description="实际根因(标注为inaccurate时必填)")
    notes: Optional[str] = Field(None, max_length=2000, description="备注")


class DiagnosisAnnotationResponse(BaseModel):
    """诊断标注响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    annotator_id: Optional[int] = None
    annotation: str
    actual_root_cause: Optional[str] = None
    notes: Optional[str] = None
    annotated_at: datetime
    created_at: datetime
    updated_at: datetime


class DiagnosisAnnotationListQuery(BaseModel):
    """诊断标注列表查询参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    session_id: Optional[int] = Field(default=None, description="会话ID")
    annotator_id: Optional[int] = Field(default=None, description="标注者ID")
    annotation: Optional[str] = Field(default=None, description="标注结果")


class DiagnosisAnnotationStatsResponse(BaseModel):
    """诊断标注统计响应"""

    total_annotations: int = Field(..., description="总标注数")
    accurate_count: int = Field(..., description="准确标注数")
    inaccurate_count: int = Field(..., description="不准确标注数")
    unknown_count: int = Field(..., description="未知标注数")
    accurate_rate: float = Field(..., description="准确率")
    user_stats: List[dict] = Field(..., description="用户标注统计")
    top_annotators: List[dict] = Field(..., description="Top标注者")


# ==================== Battery SOH Schemas ====================


class BatterySOHRecordCreate(BaseModel):
    """创建电池SOH记录"""

    device_id: int
    soh_percent: float = Field(ge=0, le=100, description="SOH百分比 [0-100]")
    resistance_mohm: Optional[float] = Field(default=None, gt=0, description="当前内阻(毫欧)")
    cycle_count: Optional[int] = Field(default=None, ge=0, description="充放电循环次数")
    weights_version: Optional[str] = None


class BatterySOHRecordResponse(BatterySOHRecordCreate):
    """电池SOH记录响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    calculated_at: datetime


class SOHWeightsConfig(BaseModel):
    """SOH权重配置"""

    w_r: float = Field(ge=0, le=1, description="内阻权重")
    w_c: float = Field(ge=0, le=1, description="循环次数权重")
    version: str = Field(default="v1.0", description="配置版本")

    @model_validator(mode='after')
    def validate_weights_sum(self):
        """验证权重之和约为 1.0（允许 ±0.1 误差）"""
        total = self.w_r + self.w_c
        if not (0.9 <= total <= 1.1):
            raise ValueError(f"权重之和应约为 1.0，当前为 {total:.2f}")
        return self


# ==================== Breaker Profile Schemas - Story 25.4 ====================


class BreakerProfileCreate(BaseModel):
    """创建断路器配置"""

    breaker_device_id: int = Field(..., description="断路器设备ID")
    trip_curve_type: str = Field(..., description="脱扣曲线类型: B/C/D")
    rated_current: float = Field(..., gt=0, description="额定电流 A")

    @field_validator('trip_curve_type')
    @classmethod
    def validate_trip_curve_type(cls, v: str) -> str:
        """验证脱扣曲线类型"""
        if v not in ('B', 'C', 'D'):
            raise ValueError("脱扣曲线类型必须是 'B', 'C', 或 'D'")
        return v


class BreakerProfileUpdate(BaseModel):
    """更新断路器配置"""

    trip_curve_type: Optional[str] = Field(None, description="脱扣曲线类型: B/C/D")
    rated_current: Optional[float] = Field(None, gt=0, description="额定电流 A")

    @field_validator('trip_curve_type')
    @classmethod
    def validate_trip_curve_type(cls, v: Optional[str]) -> Optional[str]:
        """验证脱扣曲线类型"""
        if v is not None and v not in ('B', 'C', 'D'):
            raise ValueError("脱扣曲线类型必须是 'B', 'C', 或 'D'")
        return v


class BreakerProfileResponse(BaseModel):
    """断路器配置响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    breaker_device_id: int
    trip_curve_type: str
    rated_current: float
    created_at: datetime
    updated_at: datetime
