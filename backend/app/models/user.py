"""
用户模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint

from ..core.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    real_name = Column(String(50), comment="真实姓名")
    email = Column(String(100), comment="邮箱")
    phone = Column(String(20), comment="手机号")
    role = Column(String(20), default="operator", comment="角色: admin/operator/viewer")
    department = Column(String(100), comment="部门")
    avatar = Column(String(255), comment="头像URL")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_login_at = Column(DateTime, comment="最后登录时间")
    last_login_ip = Column(String(50), comment="最后登录IP")
    login_count = Column(Integer, default=0, comment="登录次数")
    password_changed_at = Column(DateTime, nullable=True, comment="密码最后修改时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class RolePermission(Base):
    """角色权限表"""

    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(20), nullable=False, comment="角色")
    permission = Column(String(100), nullable=False, comment="权限标识")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class UserLoginHistory(Base):
    """用户登录历史"""

    __tablename__ = "user_login_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    login_at = Column(DateTime, default=datetime.now, comment="登录时间")
    login_ip = Column(String(50), comment="登录IP")
    user_agent = Column(String(255), comment="用户代理")
    status = Column(String(20), comment="状态: success/failed")
    fail_reason = Column(String(100), comment="失败原因")


class UserSession(Base):
    """用户会话表 — 并发会话控制"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    token_jti = Column(String(64), unique=True, nullable=False, comment="JWT ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    is_active = Column(Boolean, default=True, comment="是否活跃")


class UserSite(Base):
    """用户-站点关联表"""

    __tablename__ = "user_sites"
    __table_args__ = (UniqueConstraint("user_id", "site_id", name="uq_user_site"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, comment="站点ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class PasswordHistory(Base):
    """密码历史记录表"""

    __tablename__ = "password_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
