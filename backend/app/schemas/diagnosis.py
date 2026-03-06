"""
诊断 Schema
Story 9-3: 智能故障诊断
Story 24.6: 诊断会话、审计日志、结果扩展
"""

from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field


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
