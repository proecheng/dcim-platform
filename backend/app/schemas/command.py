"""
控制命令分级确认 Schema
Story 9-6: 控制命令分级确认
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ==================== 命令提交 ====================


class CommandSubmitRequest(BaseModel):
    """提交控制命令请求"""

    command_type: str  # 命令类型标识: ac_temp_set, power_off 等
    target_device_id: int
    target_device_name: str
    command_content: dict  # 命令参数


class CommandSubmitResponse(BaseModel):
    """提交控制命令响应"""

    status: str  # executed / pending_approval
    message: str
    approval_id: Optional[int] = None
    audit_log_id: Optional[int] = None


# ==================== 审批工单 ====================


class CommandApprovalResponse(BaseModel):
    """审批工单响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    command_type: str
    risk_level: str
    target_device_id: int
    target_device_name: str
    command_content: Optional[dict] = None
    requester_id: int
    requester_name: str
    approver_id: Optional[int] = None
    approver_name: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    timeout_minutes: int
    created_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expired_at: datetime


class ApprovalRejectRequest(BaseModel):
    """驳回审批请求"""

    reason: str


# ==================== 审计日志 ====================


class CommandAuditLogResponse(BaseModel):
    """命令审计日志响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    command_type: str
    risk_level: str
    target_device_id: int
    target_device_name: str
    command_content: Optional[dict] = None
    operator_id: int
    operator_name: str
    approval_id: Optional[int] = None
    result: str
    result_message: Optional[str] = None
    created_at: datetime


# ==================== 风险配置 ====================


class RiskConfigItem(BaseModel):
    """单条风险配置"""

    command_type: str
    risk_level: str  # normal / critical
    minimum_risk: Optional[str] = None
    description: Optional[str] = None


class RiskConfigUpdateRequest(BaseModel):
    """批量更新风险配置请求"""

    configs: List[RiskConfigItem]
