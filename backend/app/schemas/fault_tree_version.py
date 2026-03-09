"""
故障树版本 Schema - Story 24.4
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class FaultTreeVersionCreate(BaseModel):
    """创建版本请求"""
    pass  # 所有参数从路径和当前用户获取


class FaultTreeVersionResponse(BaseModel):
    """版本响应"""
    id: int
    tree_id: int
    version_number: int
    status: str
    snapshot: str
    hmac_signature: Optional[str] = None
    created_by: int
    created_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FaultTreeVersionListResponse(BaseModel):
    """版本列表响应"""
    id: int
    version_number: int
    status: str
    created_by: int
    created_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
