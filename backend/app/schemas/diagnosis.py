"""
诊断 Schema
Story 9-3: 智能故障诊断
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


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
    diagnosis_time_ms: int
    created_at: datetime


# ==================== Category Schema ====================

class DiagnosisCategoryItem(BaseModel):
    """诊断分类条目"""
    code: str
    name: str
    count: int = 0
