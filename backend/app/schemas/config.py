"""
配置相关 Schema
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class SystemConfigInfo(BaseModel):
    """系统配置信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_group: str
    config_key: str
    config_value: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None
    is_editable: bool = True
    updated_at: Optional[datetime] = None


class SystemConfigUpdate(BaseModel):
    """更新系统配置"""
    config_group: str
    config_key: str
    config_value: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None


class DictionaryInfo(BaseModel):
    """数据字典信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    dict_type: str
    dict_code: str
    dict_name: str
    dict_value: Optional[str] = None
    sort_order: int = 0
    is_enabled: bool = True


class LicenseInfo(BaseModel):
    """授权信息"""
    id: int
    license_key: str
    license_type: str
    max_points: int
    features: List[str] = []
    issue_date: Optional[date] = None
    expire_date: Optional[date] = None
    is_active: bool = True
    activated_at: Optional[datetime] = None
    status: str = "active"


class LicenseActivate(BaseModel):
    """激活授权"""
    license_key: str
    hardware_id: Optional[str] = None
