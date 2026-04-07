"""
认证 API - v1
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import jwt

from ..deps import get_db, get_current_user, oauth2_scheme
from ...core.config import get_settings
from ...core.security import verify_password, get_password_hash
from ...models.user import User, UserLoginHistory, UserSession, PasswordHistory
from ...models.config import SystemConfig
from ...schemas.user import Token, UserInfo, PasswordChange, PasswordPolicyConfig

router = APIRouter()
settings = get_settings()

# 默认密码策略
DEFAULT_PASSWORD_POLICY = {
    "min_length": 8,
    "min_categories": 3,
    "history_count": 5,
    "expire_days": 90,
}


async def _get_password_policy(db: AsyncSession) -> dict:
    """从 SystemConfig 获取密码策略，不存在则返回默认值"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_group == "password_policy"))
    configs = result.scalars().all()
    policy = DEFAULT_PASSWORD_POLICY.copy()
    for c in configs:
        if c.config_key in policy:
            policy[c.config_key] = int(c.config_value)
    return policy


# 简单的内存速率限制器
class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        # 清除过期的尝试记录
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        # 检查是否超过限制
        if len(self.attempts[key]) >= self.max_attempts:
            return False
        self.attempts[key].append(now)
        return True

    def get_remaining_time(self, key: str) -> int:
        if not self.attempts[key]:
            return 0
        oldest = min(self.attempts[key])
        remaining = self.window_seconds - (time.time() - oldest)
        return max(0, int(remaining))


# 登录速率限制：每分钟最多5次尝试
login_limiter = RateLimiter(max_attempts=5, window_seconds=60)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, str]:
    """创建访问令牌，返回 (token, jti)"""
    to_encode = data.copy()
    jti = uuid.uuid4().hex
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire, "jti": jti})
    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return token, jti


@router.post("/login", response_model=Token, summary="用户登录")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    用户登录获取访问令牌
    """
    # 获取客户端IP用于速率限制
    client_ip = request.client.host if request.client else "unknown"

    # 检查速率限制
    if not login_limiter.is_allowed(client_ip):
        remaining = login_limiter.get_remaining_time(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录尝试过于频繁，请在{remaining}秒后重试",
            headers={"Retry-After": str(remaining)},
        )

    # 查询用户
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # 获取客户端IP
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # 记录登录历史
    login_history = UserLoginHistory(
        user_id=user.id if user else 0, login_ip=client_ip, user_agent=user_agent[:255] if user_agent else ""
    )

    if not user or not verify_password(form_data.password, user.password_hash):
        login_history.status = "failed"
        login_history.fail_reason = "用户名或密码错误"
        if user:
            login_history.user_id = user.id
            db.add(login_history)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        login_history.status = "failed"
        login_history.fail_reason = "用户已被禁用"
        db.add(login_history)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    # 登录成功
    login_history.status = "success"
    db.add(login_history)

    # 更新用户登录信息
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(), last_login_ip=client_ip, login_count=User.login_count + 1)
    )

    # 创建令牌（含 jti）
    access_token, jti = create_access_token(data={"sub": user.username})

    # P0-3 修复: 先查询现有活跃会话，再创建新会话
    MAX_SESSIONS = 3
    active_sessions_result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active == True)
        .order_by(UserSession.created_at.asc())
    )
    active_sessions = active_sessions_result.scalars().all()

    # 如果已达到限制，踢出最早的会话
    if len(active_sessions) >= MAX_SESSIONS:
        sessions_to_kick = active_sessions[: len(active_sessions) - MAX_SESSIONS + 1]
        for s in sessions_to_kick:
            s.is_active = False

    # 创建新会话记录
    session_record = UserSession(user_id=user.id, token_jti=jti)
    db.add(session_record)

    await db.commit()

    # 检查密码是否过期
    password_warning = None
    policy = await _get_password_policy(db)
    expire_days = policy["expire_days"]
    if expire_days > 0:
        pwd_changed = user.password_changed_at or user.created_at
        if pwd_changed:
            days_since = (datetime.now() - pwd_changed).days
            if days_since >= expire_days:
                password_warning = f"您的密码已超过{expire_days}天未更换，建议尽快修改密码"

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        password_expired_warning=password_warning,
    )


@router.post("/logout", summary="用户登出")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    用户登出（失效当前会话）
    """
    # P0-2 修复: 解析 token 获取 jti 并失效会话
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")

        if jti:
            # 失效当前会话
            await db.execute(update(UserSession).where(UserSession.token_jti == jti).values(is_active=False))
            await db.commit()
    except Exception:
        pass  # 即使失败也返回成功，避免泄露信息

    return {"message": "登出成功"}


@router.post("/refresh", response_model=Token, summary="刷新令牌")
async def refresh_token(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    刷新访问令牌
    """
    access_token, jti = create_access_token(data={"sub": current_user.username})

    # P0-1 修复: 创建新会话记录
    session_record = UserSession(user_id=current_user.id, token_jti=jti)
    db.add(session_record)
    await db.commit()

    return Token(access_token=access_token, token_type="bearer", expires_in=settings.access_token_expire_minutes * 60)


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    """
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        real_name=current_user.real_name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        department=current_user.department,
        avatar=current_user.avatar,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )


@router.put("/password", summary="修改密码")
async def change_password(
    data: PasswordChange, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    修改当前用户密码（含密码历史检查）
    """
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")

    # 获取密码策略
    policy = await _get_password_policy(db)
    history_count = policy["history_count"]

    # 检查密码历史：不能与最近 N 次相同
    if history_count > 0:
        history_result = await db.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == current_user.id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(history_count)
        )
        history_records = history_result.scalars().all()
        for record in history_records:
            if verify_password(data.new_password, record.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"新密码不能与最近{history_count}次使用的密码相同"
                )

    # 保存旧密码到历史
    db.add(PasswordHistory(user_id=current_user.id, password_hash=current_user.password_hash))

    # 更新密码
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(
            password_hash=get_password_hash(data.new_password),
            password_changed_at=datetime.now(),
            updated_at=datetime.now(),
        )
    )
    await db.commit()

    return {"message": "密码修改成功"}


@router.get("/permissions", summary="获取当前用户权限")
async def get_permissions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    获取当前用户的权限列表
    """
    from ...models.user import RolePermission

    result = await db.execute(select(RolePermission.permission).where(RolePermission.role == current_user.role))
    permissions = [row[0] for row in result.all()]

    return {"role": current_user.role, "permissions": permissions}


@router.get("/password-policy", response_model=PasswordPolicyConfig, summary="获取密码策略")
async def get_password_policy(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """
    获取当前密码策略配置
    """
    policy = await _get_password_policy(db)
    return PasswordPolicyConfig(**policy)


@router.put("/password-policy", response_model=PasswordPolicyConfig, summary="更新密码策略")
async def update_password_policy(
    data: PasswordPolicyConfig, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    更新密码策略配置（仅管理员）
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可修改密码策略")

    policy_items = {
        "min_length": str(data.min_length),
        "min_categories": str(data.min_categories),
        "history_count": str(data.history_count),
        "expire_days": str(data.expire_days),
    }

    for key, value in policy_items.items():
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_group == "password_policy", SystemConfig.config_key == key)
        )
        config = result.scalar_one_or_none()
        if config:
            config.config_value = value
            config.updated_at = datetime.now()
        else:
            db.add(
                SystemConfig(
                    config_group="password_policy",
                    config_key=key,
                    config_value=value,
                    value_type="int",
                    description=f"密码策略-{key}",
                    is_editable=True,
                )
            )

    await db.commit()
    return data
