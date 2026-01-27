"""
用户相关 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


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
    new_password: str = Field(..., min_length=6)
    confirm_password: str


class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    real_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str = "operator"
    department: Optional[str] = None


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
