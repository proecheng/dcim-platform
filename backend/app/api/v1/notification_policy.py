"""
Story 34.3: 通知策略配置 — CRUD API 端点
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.notification_policy import NotificationPolicy
from app.schemas.notification_policy import (
    NotificationPolicyCreate,
    NotificationPolicyInfo,
    NotificationPolicyUpdate,
)
from app.services.notification.policy_service import NotificationPolicyService

router = APIRouter()


@router.get("", response_model=list[NotificationPolicyInfo])
async def list_policies(
    site_id: Optional[int] = Query(None),
    alarm_level: Optional[str] = Query(None, pattern="^(critical|major|minor|info)$"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """查询策略列表（支持 site_id, alarm_level 筛选）"""
    query = select(NotificationPolicy)
    if site_id is not None:
        query = query.where(NotificationPolicy.site_id == site_id)
    if alarm_level is not None:
        query = query.where(NotificationPolicy.alarm_level == alarm_level)
    query = query.order_by(NotificationPolicy.id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=NotificationPolicyInfo, status_code=201)
async def create_policy(
    data: NotificationPolicyCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """创建通知策略"""
    # 站点存在性校验
    if data.site_id is not None:
        if not await NotificationPolicyService.validate_site_exists(db, data.site_id):
            raise HTTPException(status_code=422, detail=f"站点 {data.site_id} 不存在")

    # 用户站点权限校验
    if data.notify_user_ids:
        invalid_users = await NotificationPolicyService.validate_user_site_access(
            db, data.site_id, data.notify_user_ids
        )
        if invalid_users:
            raise HTTPException(
                status_code=422,
                detail=f"用户 {invalid_users} 无站点 {data.site_id} 的访问权限",
            )

    # 时段冲突检测
    conflict_id = await NotificationPolicyService.check_time_overlap(
        db, data.site_id, data.alarm_level, data.time_range_start, data.time_range_end
    )
    if conflict_id is not None:
        raise HTTPException(status_code=422, detail=f"与策略 {conflict_id} 时段重叠")

    policy = NotificationPolicy(
        name=data.name,
        site_id=data.site_id,
        alarm_level=data.alarm_level,
        time_range_start=data.time_range_start,
        time_range_end=data.time_range_end,
        channels=data.channels,
        notify_user_ids=data.notify_user_ids,
        channel_escalation_enabled=data.channel_escalation_enabled,
        escalation_timeout_minutes=data.escalation_timeout_minutes,
        escalation_channel_order=data.escalation_channel_order,
        is_enabled=data.is_enabled,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.put("/{policy_id}", response_model=NotificationPolicyInfo)
async def update_policy(
    policy_id: int,
    data: NotificationPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """更新通知策略"""
    result = await db.execute(select(NotificationPolicy).where(NotificationPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")

    provided = data.model_fields_set

    # 合并时段：用 DB 现有值填充未提供的字段
    effective_start = data.time_range_start if "time_range_start" in provided else policy.time_range_start
    effective_end = data.time_range_end if "time_range_end" in provided else policy.time_range_end
    # 合并后校验：必须同时有值或同时为 None
    if (effective_start is None) != (effective_end is None):
        raise HTTPException(
            status_code=422,
            detail="time_range_start 和 time_range_end 必须同时提供或同时为空",
        )
    # 零长度时段
    if effective_start is not None and effective_start == effective_end:
        raise HTTPException(
            status_code=422,
            detail="time_range_start 和 time_range_end 不能相同",
        )

    # 合并 notify_user_ids
    effective_user_ids = data.notify_user_ids if "notify_user_ids" in provided else policy.notify_user_ids
    effective_site_id = policy.site_id  # site_id 不可更新

    # 用户站点权限校验
    if effective_user_ids and "notify_user_ids" in provided:
        invalid_users = await NotificationPolicyService.validate_user_site_access(
            db, effective_site_id, effective_user_ids
        )
        if invalid_users:
            raise HTTPException(
                status_code=422,
                detail=f"用户 {invalid_users} 无站点 {effective_site_id} 的访问权限",
            )

    # 时段冲突检测
    if "time_range_start" in provided or "time_range_end" in provided:
        conflict_id = await NotificationPolicyService.check_time_overlap(
            db,
            effective_site_id,
            policy.alarm_level,
            effective_start,
            effective_end,
            exclude_id=policy_id,
        )
        if conflict_id is not None:
            raise HTTPException(status_code=422, detail=f"与策略 {conflict_id} 时段重叠")

    # escalation 联动校验
    effective_escalation = (
        data.channel_escalation_enabled
        if "channel_escalation_enabled" in provided
        else policy.channel_escalation_enabled
    )
    effective_order = (
        data.escalation_channel_order if "escalation_channel_order" in provided else policy.escalation_channel_order
    )
    if effective_escalation and not effective_order:
        raise HTTPException(
            status_code=422,
            detail="启用渠道升级时必须提供 escalation_channel_order",
        )

    # 应用更新
    for field in provided:
        setattr(policy, field, getattr(data, field))

    await db.flush()
    await db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """删除通知策略（is_default=True 不可删除）"""
    result = await db.execute(select(NotificationPolicy).where(NotificationPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if policy.is_default:
        raise HTTPException(status_code=400, detail="全局默认策略不可删除")
    await db.delete(policy)
    await db.flush()
