"""
用户相关 Schema
"""
import re
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


def validate_password_complexity(password: str) -> str:
    """验证密码复杂度"""
    if len(password) < 8:
        raise ValueError('密码长度至少8个字符')
    if not re.search(r'[A-Z]', password):
        raise ValueError('密码必须包含大写字母')
    if not re.search(r'[a-z]', password):
        raise ValueError('密码必须包含小写字母')
    if not re.search(r'\d', password):
        raise ValueError('密码必须包含数字')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError('密码必须包含特殊字符')
    return password


class Token(BaseModel):
    """访问令牌"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


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
