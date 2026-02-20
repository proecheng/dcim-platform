"""
API 依赖注入模块
"""

import logging
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..core.database import async_session
from ..models.user import User, UserSession, UserSite

logger = logging.getLogger(__name__)
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if username is None:
            raise credentials_exception
    except JWTError:
        # JWT 签名验证失败 — 记录安全告警
        logger.warning("JWT 签名验证失败，可能存在令牌篡改")
        try:
            from ..models.log import OperationLog

            security_log = OperationLog(
                module="auth", action="jwt_tamper_detected", remark="JWT 签名验证失败，可能存在令牌篡改"
            )
            db.add(security_log)
            await db.commit()
        except Exception:
            pass  # 日志写入失败不影响主流程
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    # 检查会话是否有效（jti 存在时才检查，兼容旧 token）
    if jti:
        session_result = await db.execute(
            select(UserSession).where(UserSession.token_jti == jti, UserSession.is_active == True)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已在其他设备登录",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活动用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    return current_user


def require_role(allowed_roles: list[str]):
    """角色权限检查装饰器"""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user

    return role_checker


# 常用权限依赖
require_admin = require_role(["admin"])
require_operator = require_role(["admin", "operator"])
require_viewer = require_role(["admin", "operator", "viewer"])


async def get_user_site_ids(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Optional[list[int]]:
    """获取用户可访问的站点ID列表。admin 返回 None（不过滤）"""
    if current_user.role == "admin":
        return None
    result = await db.execute(select(UserSite.site_id).where(UserSite.user_id == current_user.id))
    return [row[0] for row in result.fetchall()]


async def require_site_access(
    site_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> int:
    """验证用户对指定站点的访问权限。admin 不限制，其他角色检查 UserSite 关联。"""
    if current_user.role == "admin":
        return site_id
    result = await db.execute(select(UserSite).where(UserSite.user_id == current_user.id, UserSite.site_id == site_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该站点")
    return site_id
