"""
系统相关 Schema
"""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class ControlCommandCreate(BaseModel):
    point_id: int
    target_value: float


class ControlCommandResponse(BaseModel):
    id: int
    point_id: int
    target_value: float
    executed_by: int
    status: str
    result_message: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LicenseResponse(BaseModel):
    id: int
    license_key: str
    license_type: str
    max_points: int
    expire_date: Optional[date] = None
    is_active: bool

    class Config:
        from_attributes = True


class LicenseActivate(BaseModel):
    license_key: str


class LicenseUsage(BaseModel):
    license_type: str
    max_points: int
    used_points: int
    remaining_points: int
    expire_date: Optional[date] = None
    is_valid: bool


class OperationLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
