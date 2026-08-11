"""
用户管理 API - v1
"""

from datetime import datetime
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_admin
from ...core.security import get_password_hash
from ...models.user import User, UserLoginHistory, UserSite
from ...models.spatial import Site
from ...schemas.user import UserCreate, UserUpdate, UserInfo, UserLoginHistoryResponse, UserSiteUpdate, UserSiteInfo
from ...schemas.common import PageResponse
from ...services.websocket import ws_manager

router = APIRouter()
logger = logging.getLogger(__name__)


async def _invalidate_user_after_commit(user_id: int) -> None:
    try:
        await ws_manager.invalidate_user(user_id)
    except Exception as exc:
        logger.error(
            "WebSocket revocation failed: event=user_authorization_changed user_id=%s error=%s",
            user_id,
            exc,
            extra={"security_event": "user_authorization_revocation_failed", "user_id": user_id},
        )


@router.get("", response_model=PageResponse[UserInfo], summary="获取用户列表")
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    role: Optional[str] = Query(None, description="角色筛选"),
    is_active: Optional[bool] = Query(None, description="启用状态"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取用户列表（分页）
    """
    query = select(User)

    # 筛选条件
    if keyword:
        query = query.where(
            (User.username.contains(keyword)) | (User.real_name.contains(keyword)) | (User.email.contains(keyword))
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

    return PageResponse(items=[UserInfo.model_validate(u) for u in users], total=total, page=page, page_size=page_size)


@router.get("/sites/{site_id}/users", response_model=List[UserInfo], summary="获取站点下的用户列表")
async def get_site_users(site_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    获取站点下关联的用户列表
    """
    result = await db.execute(select(Site).where(Site.id == site_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="站点不存在")

    stmt = select(User).join(UserSite, User.id == UserSite.user_id).where(UserSite.site_id == site_id).order_by(User.id)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserInfo.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserInfo, summary="获取用户详情")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    获取用户详情
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserInfo.model_validate(user)


@router.post("", response_model=UserInfo, summary="创建用户")
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
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
        department=data.department,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserInfo.model_validate(user)


@router.put("/{user_id}", response_model=UserInfo, summary="更新用户")
async def update_user(
    user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
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
    await _invalidate_user_after_commit(user_id)

    # 重新查询
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    return UserInfo.model_validate(user)


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
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
    await _invalidate_user_after_commit(user_id)

    return {"message": "用户已删除"}


@router.post("/batch-delete", summary="批量删除用户")
async def batch_delete_users(
    user_ids: List[int], db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    """
    批量删除用户（不能删除自己）
    """
    if current_user.id in user_ids:
        raise HTTPException(status_code=400, detail="不能删除自己")

    result = await db.execute(select(func.count(User.id)).where(User.id.in_(user_ids)))
    found = result.scalar()
    if found == 0:
        raise HTTPException(status_code=404, detail="未找到要删除的用户")

    await db.execute(delete(User).where(User.id.in_(user_ids)))
    await db.commit()
    for user_id in user_ids:
        await _invalidate_user_after_commit(user_id)

    return {"message": f"已删除 {found} 个用户", "deleted_count": found}


@router.put("/{user_id}/status", summary="启用/禁用用户")
async def toggle_user_status(
    user_id: int, is_active: bool, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
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

    await db.execute(update(User).where(User.id == user_id).values(is_active=is_active, updated_at=datetime.now()))
    await db.commit()
    await _invalidate_user_after_commit(user_id)

    return {"message": f"用户已{'启用' if is_active else '禁用'}"}


@router.put("/{user_id}/reset-password", summary="重置密码")
async def reset_password(
    user_id: int,
    new_password: str = Query(..., min_length=8, description="新密码（必填，至少8位）"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    重置用户密码（必须提供新密码）
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(password_hash=get_password_hash(new_password), updated_at=datetime.now())
    )
    await db.commit()
    await _invalidate_user_after_commit(user_id)

    return {"message": "密码已重置"}


@router.get("/{user_id}/login-history", summary="获取登录历史")
async def get_login_history(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
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
        "page_size": page_size,
    }


# ==================== 用户站点管理 ====================


@router.get("/{user_id}/sites", response_model=List[UserSiteInfo], summary="获取用户站点列表")
async def get_user_sites(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    获取用户关联的站点列表
    """
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="用户不存在")

    stmt = (
        select(UserSite.site_id, Site.site_code, Site.site_name)
        .join(Site, UserSite.site_id == Site.id)
        .where(UserSite.user_id == user_id)
        .order_by(Site.id)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [UserSiteInfo(site_id=r[0], site_code=r[1], site_name=r[2]) for r in rows]


@router.put("/{user_id}/sites", summary="设置用户站点权限")
async def update_user_sites(
    user_id: int, data: UserSiteUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    """
    设置用户的站点权限（全量替换）
    """
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="用户不存在")

    # 验证站点存在
    if data.site_ids:
        site_count = await db.execute(select(func.count(Site.id)).where(Site.id.in_(data.site_ids)))
        if site_count.scalar() != len(data.site_ids):
            raise HTTPException(status_code=400, detail="部分站点不存在")

    # 删除旧关联
    await db.execute(delete(UserSite).where(UserSite.user_id == user_id))

    # 创建新关联
    for site_id in data.site_ids:
        db.add(UserSite(user_id=user_id, site_id=site_id))

    await db.commit()
    await _invalidate_user_after_commit(user_id)
    return {"message": f"已为用户分配 {len(data.site_ids)} 个站点"}
