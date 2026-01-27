"""
告警路由
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core import get_db, get_current_user
from ..models import User, Point, Alarm, AlarmThreshold
from ..schemas import (
    AlarmResponse, AlarmAcknowledge, AlarmStats,
    AlarmThresholdCreate, AlarmThresholdUpdate, AlarmThresholdResponse
)

router = APIRouter(prefix="/alarms", tags=["告警管理"])


@router.get("", response_model=List[AlarmResponse])
async def get_alarms(
    status: Optional[str] = Query(None, description="告警状态"),
    level: Optional[str] = Query(None, description="告警级别"),
    point_id: Optional[int] = Query(None, description="点位ID"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取告警列表"""
    query = select(Alarm, Point).join(Point, Alarm.point_id == Point.id)

    if status:
        query = query.where(Alarm.status == status)
    if level:
        query = query.where(Alarm.alarm_level == level)
    if point_id:
        query = query.where(Alarm.point_id == point_id)

    query = query.order_by(Alarm.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return [
        AlarmResponse(
            id=alarm.id,
            point_id=alarm.point_id,
            point_code=point.point_code,
            point_name=point.point_name,
            alarm_level=alarm.alarm_level,
            alarm_message=alarm.alarm_message,
            trigger_value=alarm.trigger_value,
            threshold_value=alarm.threshold_value,
            status=alarm.status,
            acknowledged_by=alarm.acknowledged_by,
            acknowledged_at=alarm.acknowledged_at,
            resolved_at=alarm.resolved_at,
            created_at=alarm.created_at
        )
        for alarm, point in rows
    ]


@router.get("/active", response_model=List[AlarmResponse])
async def get_active_alarms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取活动告警"""
    query = select(Alarm, Point).join(
        Point, Alarm.point_id == Point.id
    ).where(
        Alarm.status == "active"
    ).order_by(Alarm.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    return [
        AlarmResponse(
            id=alarm.id,
            point_id=alarm.point_id,
            point_code=point.point_code,
            point_name=point.point_name,
            alarm_level=alarm.alarm_level,
            alarm_message=alarm.alarm_message,
            trigger_value=alarm.trigger_value,
            threshold_value=alarm.threshold_value,
            status=alarm.status,
            acknowledged_by=alarm.acknowledged_by,
            acknowledged_at=alarm.acknowledged_at,
            resolved_at=alarm.resolved_at,
            created_at=alarm.created_at
        )
        for alarm, point in rows
    ]


@router.get("/count")
async def get_alarm_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取各级别告警数量"""
    query = select(
        Alarm.alarm_level,
        func.count(Alarm.id)
    ).where(Alarm.status == "active").group_by(Alarm.alarm_level)

    result = await db.execute(query)
    counts = {row[0]: row[1] for row in result.all()}

    return {
        "critical": counts.get("critical", 0),
        "major": counts.get("major", 0),
        "minor": counts.get("minor", 0),
        "info": counts.get("info", 0),
        "total": sum(counts.values())
    }


@router.put("/{alarm_id}/acknowledge")
async def acknowledge_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """确认告警"""
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.status = "acknowledged"
    alarm.acknowledged_by = current_user.id
    alarm.acknowledged_at = datetime.utcnow()

    await db.commit()
    return {"message": "确认成功"}


@router.put("/{alarm_id}/resolve")
async def resolve_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """解决告警"""
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.status = "resolved"
    alarm.resolved_at = datetime.utcnow()

    await db.commit()
    return {"message": "解决成功"}


@router.put("/batch-acknowledge")
async def batch_acknowledge(
    data: AlarmAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量确认告警"""
    result = await db.execute(
        select(Alarm).where(Alarm.id.in_(data.alarm_ids))
    )
    alarms = result.scalars().all()

    for alarm in alarms:
        alarm.status = "acknowledged"
        alarm.acknowledged_by = current_user.id
        alarm.acknowledged_at = datetime.utcnow()

    await db.commit()
    return {"message": f"已确认 {len(alarms)} 条告警"}
