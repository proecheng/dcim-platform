"""
联动策略 Schema
Story 9-1: 联动引擎核心框架
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ==================== Action Schemas ====================

class LinkageActionCreate(BaseModel):
    """创建联动动作"""
    action_type: str
    action_config: dict
    sort_order: int = 0
    timeout_seconds: int = 3
    retry_count: int = 0


class LinkageActionResponse(BaseModel):
    """联动动作响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    action_type: str
    action_config: dict
    sort_order: int
    timeout_seconds: int
    retry_count: int
    created_at: datetime


# ==================== Policy Schemas ====================

class LinkagePolicyCreate(BaseModel):
    """创建联动策略"""
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_condition: dict
    priority: str = "normal"
    is_enabled: bool = True
    actions: List[LinkageActionCreate] = []


class LinkagePolicyUpdate(BaseModel):
    """更新联动策略"""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_condition: Optional[dict] = None
    priority: Optional[str] = None
    is_enabled: Optional[bool] = None
    actions: Optional[List[LinkageActionCreate]] = None


class LinkagePolicyResponse(BaseModel):
    """联动策略响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_condition: dict
    priority: str
    is_enabled: bool
    is_system: bool
    actions: List[LinkageActionResponse] = []
    created_at: datetime
    updated_at: datetime


# ==================== Execution / Log Schemas ====================

class LinkageLogResponse(BaseModel):
    """联动执行日志响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    action_id: Optional[int] = None
    action_type: str
    action_config: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class LinkageExecutionResponse(BaseModel):
    """联动执行记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    policy_name: Optional[str] = None
    event_id: str
    trigger_source: Optional[str] = None
    trigger_event: Optional[dict] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[int] = None
    logs: List[LinkageLogResponse] = []


# ==================== Test / Info Schemas ====================

class LinkagePolicyTestRequest(BaseModel):
    """联动策略测试请求"""
    event_type: Optional[str] = None
    payload: dict = {}


class ActionTypeInfo(BaseModel):
    """动作类型信息"""
    action_type: str
    description: str
    is_implemented: bool
