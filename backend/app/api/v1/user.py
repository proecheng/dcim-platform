"""
用户管理 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, get_current_user, require_admin
from ...core.security import get_password_hash
from ...models.user import User, UserLoginHistory
from ...schemas.user import (
    UserCreate, UserUpdate, UserInfo, UserListResponse,
    UserLoginHistoryResponse
)
from ...schemas.common import PageParams, PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[UserInfo], summary="获取用户列表")
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    role: Optional[str] = Query(None, description="角色筛选"),
    is_active: Optional[bool] = Query(None, description="启用状态"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取用户列表（分页）
    """
    query = select(User)

    # 筛选条件
    if keyword:
        query = query.where(
            (User.username.contains(keyword)) |
            (User.real_name.contains(keyword)) |
            (User.email.contains(keyword))
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页查询
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    return PageResponse(
        items=[UserInfo.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{user_id}", response_model=UserInfo, summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取用户详情
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserInfo.model_validate(user)


@router.post("", response_model=UserInfo, summary="创建用户")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    创建新用户
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否已存在
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="邮箱已被使用")

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        real_name=data.real_name,
        email=data.email,
        phone=data.phone,
        role=data.role,
        department=data.department
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserInfo.model_validate(user)


@router.put("/{user_id}", response_model=UserInfo, summary="更新用户")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    更新用户信息
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(update(User).where(User.id == user_id).values(**update_data))
    await db.commit()

    # 重新查询
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    return UserInfo.model_validate(user)


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除用户
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    return {"message": "用户已删除"}


@router.put("/{user_id}/status", summary="启用/禁用用户")
async def toggle_user_status(
    user_id: int,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    启用或禁用用户
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await db.execute(
        update(User).where(User.id == user_id).values(
            is_active=is_active,
            updated_at=datetime.now()
        )
    )
    await db.commit()

    return {"message": f"用户已{'启用' if is_active else '禁用'}"}


@router.put("/{user_id}/reset-password", summary="重置密码")
async def reset_password(
    user_id: int,
    new_password: str = Query(..., min_length=8, description="新密码（必填，至少8位）"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    重置用户密码（必须提供新密码）
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await db.execute(
        update(User).where(User.id == user_id).values(
            password_hash=get_password_hash(new_password),
            updated_at=datetime.now()
        )
    )
    await db.commit()

    return {"message": "密码已重置"}


@router.get("/{user_id}/login-history", summary="获取登录历史")
async def get_login_history(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取用户登录历史
    """
    query = select(UserLoginHistory).where(UserLoginHistory.user_id == user_id)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页查询
    query = query.order_by(UserLoginHistory.login_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    history = result.scalars().all()

    return {
        "items": [UserLoginHistoryResponse.model_validate(h) for h in history],
        "total": total,
        "page": page,
        "page_size": page_size
    }
