"""告警升级规则 API"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.alarm import AlarmEscalation
from ...schemas.alarm import (
    AlarmEscalationCreate, AlarmEscalationUpdate, AlarmEscalationInfo,
)

router = APIRouter()


@router.get("/", summary="获取升级规则列表")
async def list_escalations(
    source_level: Optional[str] = Query(None, description="源告警级别"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    query = select(AlarmEscalation)
    count_query = select(func.count(AlarmEscalation.id))

    if source_level:
        query = query.where(AlarmEscalation.source_level == source_level)
        count_query = count_query.where(AlarmEscalation.source_level == source_level)
    if is_enabled is not None:
        query = query.where(AlarmEscalation.is_enabled == is_enabled)
        count_query = count_query.where(AlarmEscalation.is_enabled == is_enabled)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(AlarmEscalation.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "items": [AlarmEscalationInfo.model_validate(item) for item in items],
        "page": page,
        "page_size": page_size,
    }


@router.post("/", summary="创建升级规则")
async def create_escalation(
    data: AlarmEscalationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    db_data = {
        **data.model_dump(),
        "notify_user_ids": ",".join(str(x) for x in data.notify_user_ids),
    }
    escalation = AlarmEscalation(**db_data)
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)
    return AlarmEscalationInfo.model_validate(escalation)


@router.get("/{escalation_id}", summary="获取升级规则详情")
async def get_escalation(
    escalation_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(
        select(AlarmEscalation).where(AlarmEscalation.id == escalation_id)
    )
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="升级规则不存在")
    return AlarmEscalationInfo.model_validate(escalation)


@router.put("/{escalation_id}", summary="更新升级规则")
async def update_escalation(
    escalation_id: int,
    data: AlarmEscalationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(
        select(AlarmEscalation).where(AlarmEscalation.id == escalation_id)
    )
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="升级规则不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "notify_user_ids" in update_data and update_data["notify_user_ids"] is not None:
        update_data["notify_user_ids"] = ",".join(
            str(x) for x in update_data["notify_user_ids"]
        )
    for key, value in update_data.items():
        setattr(escalation, key, value)

    await db.commit()
    await db.refresh(escalation)
    return AlarmEscalationInfo.model_validate(escalation)


@router.delete("/{escalation_id}", summary="删除升级规则")
async def delete_escalation(
    escalation_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(
        select(AlarmEscalation).where(AlarmEscalation.id == escalation_id)
    )
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="升级规则不存在")

    await db.delete(escalation)
    await db.commit()
    return {"message": "升级规则已删除"}


@router.put("/{escalation_id}/toggle", summary="切换升级规则启用状态")
async def toggle_escalation(
    escalation_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(
        select(AlarmEscalation).where(AlarmEscalation.id == escalation_id)
    )
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="升级规则不存在")

    escalation.is_enabled = not escalation.is_enabled
    await db.commit()
    await db.refresh(escalation)
    return AlarmEscalationInfo.model_validate(escalation)
