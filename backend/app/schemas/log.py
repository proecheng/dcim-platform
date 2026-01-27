"""
日志相关 Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OperationLogInfo(BaseModel):
    """操作日志信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    response_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


class SystemLogInfo(BaseModel):
    """系统日志信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    log_level: str
    module: Optional[str] = None
    message: str
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    created_at: Optional[datetime] = None


class CommunicationLogInfo(BaseModel):
    """通讯日志信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: Optional[int] = None
    comm_type: Optional[str] = None
    protocol: Optional[str] = None
    request_data: Optional[str] = None
    response_data: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: Optional[datetime] = None
