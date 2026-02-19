"""
用户相关 Schema
"""
import re
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


def validate_password_complexity(password: str, min_length: int = 8, min_categories: int = 3) -> str:
    """验证密码复杂度：至少 min_length 位，包含至少 min_categories 类字符"""
    if len(password) < min_length:
        raise ValueError(f'密码长度至少{min_length}个字符')

    categories = 0
    if re.search(r'[A-Z]', password):
        categories += 1
    if re.search(r'[a-z]', password):
        categories += 1
    if re.search(r'\d', password):
        categories += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        categories += 1

    if categories < min_categories:
        raise ValueError(f'密码必须包含大写字母、小写字母、数字、特殊字符中至少{min_categories}类')
    return password


class Token(BaseModel):
    """访问令牌"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    password_expired_warning: Optional[str] = None


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    real_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str = "operator"
    department: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserUpdate(BaseModel):
    """更新用户"""
    real_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class UserInfo(BaseModel):
    """用户信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    department: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    """用户列表响应"""
    items: List[UserInfo]
    total: int
    page: int
    page_size: int


class UserLoginHistoryResponse(BaseModel):
    """登录历史"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    login_at: datetime
    login_ip: Optional[str] = None
    user_agent: Optional[str] = None
    status: Optional[str] = None
    fail_reason: Optional[str] = None


# 保持向后兼容
UserResponse = UserInfo
UserBase = UserCreate


class UserSiteUpdate(BaseModel):
    """更新用户站点权限"""
    site_ids: List[int]


class UserSiteInfo(BaseModel):
    """用户站点信息"""
    model_config = ConfigDict(from_attributes=True)

    site_id: int
    site_code: str
    site_name: str


class PasswordPolicyConfig(BaseModel):
    """密码策略配置"""
    min_length: int = 8
    min_categories: int = 3
    history_count: int = 5
    expire_days: int = 90
