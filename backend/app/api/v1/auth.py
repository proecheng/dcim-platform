"""
认证 API - v1
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import jwt

from ..deps import get_db, get_current_user
from ...core.config import get_settings
from ...core.security import verify_password, get_password_hash
from ...models.user import User, UserLoginHistory
from ...schemas.user import Token, UserInfo, PasswordChange

router = APIRouter()
settings = get_settings()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


@router.post("/login", response_model=Token, summary="用户登录")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录获取访问令牌
    """
    # 查询用户
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # 获取客户端IP
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # 记录登录历史
    login_history = UserLoginHistory(
        user_id=user.id if user else 0,
        login_ip=client_ip,
        user_agent=user_agent[:255] if user_agent else ""
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    # 登录成功
    login_history.status = "success"
    db.add(login_history)

    # 更新用户登录信息
    await db.execute(
        update(User).where(User.id == user.id).values(
            last_login_at=datetime.now(),
            last_login_ip=client_ip,
            login_count=User.login_count + 1
        )
    )
    await db.commit()

    # 创建令牌
    access_token = create_access_token(data={"sub": user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/logout", summary="用户登出")
async def logout(current_user: User = Depends(get_current_user)):
    """
    用户登出（客户端删除token即可）
    """
    return {"message": "登出成功"}


@router.post("/refresh", response_model=Token, summary="刷新令牌")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """
    刷新访问令牌
    """
    access_token = create_access_token(data={"sub": current_user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


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
        created_at=current_user.created_at
    )


@router.put("/password", summary="修改密码")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    修改当前用户密码
    """
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="两次输入的新密码不一致"
        )

    await db.execute(
        update(User).where(User.id == current_user.id).values(
            password_hash=get_password_hash(data.new_password),
            updated_at=datetime.now()
        )
    )
    await db.commit()

    return {"message": "密码修改成功"}


@router.get("/permissions", summary="获取当前用户权限")
async def get_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的权限列表
    """
    from ...models.user import RolePermission
    result = await db.execute(
        select(RolePermission.permission).where(RolePermission.role == current_user.role)
    )
    permissions = [row[0] for row in result.all()]

    return {
        "role": current_user.role,
        "permissions": permissions
    }
