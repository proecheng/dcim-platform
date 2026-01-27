"""
告警管理 API - v1
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, and_
import csv
import io

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.alarm import Alarm, AlarmThreshold, AlarmShield
from ...models.point import Point
from ...schemas.alarm import (
    AlarmInfo, AlarmAcknowledge, AlarmResolve, AlarmCount,
    AlarmStatistics, AlarmTrend
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[AlarmInfo], summary="获取告警列表")
async def get_alarms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="状态: active/acknowledged/resolved"),
    level: Optional[str] = Query(None, description="级别: critical/major/minor/info"),
    point_id: Optional[int] = Query(None, description="点位ID"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    keyword: Optional[str] = Query(None, description="关键词"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取告警列表（多条件筛选、分页）
    """
    query = select(Alarm)

    if status:
        query = query.where(Alarm.status == status)
    if level:
        query = query.where(Alarm.alarm_level == level)
    if point_id:
        query = query.where(Alarm.point_id == point_id)
    if start_time:
        query = query.where(Alarm.created_at >= start_time)
    if end_time:
        query = query.where(Alarm.created_at <= end_time)
    if keyword:
        query = query.where(Alarm.alarm_message.contains(keyword))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Alarm.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    alarms = result.scalars().all()

    # 获取点位信息
    alarm_list = []
    for alarm in alarms:
        point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
        point = point_result.scalar_one_or_none()
        alarm_info = AlarmInfo.model_validate(alarm)
        if point:
            alarm_info.point_code = point.point_code
            alarm_info.point_name = point.point_name
        alarm_list.append(alarm_info)

    return PageResponse(
        items=alarm_list,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/active", summary="获取活动告警")
async def get_active_alarms(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取所有未解决的告警
    """
    query = select(Alarm).where(
        Alarm.status.in_(["active", "acknowledged"])
    ).order_by(
        Alarm.alarm_level.desc(), Alarm.created_at.desc()
    )

    result = await db.execute(query)
    alarms = result.scalars().all()

    alarm_list = []
    for alarm in alarms:
        point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
        point = point_result.scalar_one_or_none()
        alarm_info = AlarmInfo.model_validate(alarm)
        if point:
            alarm_info.point_code = point.point_code
            alarm_info.point_name = point.point_name
        alarm_list.append(alarm_info)

    return alarm_list


@router.get("/count", response_model=AlarmCount, summary="获取各级别告警数量")
async def get_alarm_count(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取各级别的活动告警数量
    """
    result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            Alarm.status.in_(["active", "acknowledged"])
        ).group_by(Alarm.alarm_level)
    )
    counts = {row[0]: row[1] for row in result.all()}

    return AlarmCount(
        critical=counts.get("critical", 0),
        major=counts.get("major", 0),
        minor=counts.get("minor", 0),
        info=counts.get("info", 0),
        total=sum(counts.values())
    )


@router.get("/statistics", response_model=AlarmStatistics, summary="获取告警统计")
async def get_alarm_statistics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取告警统计信息
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    base_query = select(Alarm).where(
        and_(Alarm.created_at >= start_time, Alarm.created_at <= end_time)
    )

    # 总数
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = total_result.scalar()

    # 按级别统计
    level_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at <= end_time)
        ).group_by(Alarm.alarm_level)
    )
    by_level = {row[0]: row[1] for row in level_result.all()}

    # 按状态统计
    status_result = await db.execute(
        select(Alarm.status, func.count(Alarm.id)).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at <= end_time)
        ).group_by(Alarm.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # 平均处理时间
    avg_duration_result = await db.execute(
        select(func.avg(Alarm.duration_seconds)).where(
            and_(
                Alarm.created_at >= start_time,
                Alarm.created_at <= end_time,
                Alarm.status == "resolved"
            )
        )
    )
    avg_duration = avg_duration_result.scalar() or 0

    return AlarmStatistics(
        total=total,
        by_level=by_level,
        by_status=by_status,
        avg_duration_seconds=int(avg_duration),
        start_time=start_time,
        end_time=end_time
    )


@router.get("/trend", summary="获取告警趋势")
async def get_alarm_trend(
    days: int = Query(7, ge=1, le=90, description="天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取告警趋势数据（按天统计）
    """
    start_time = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(Alarm.created_at).label("date"),
            Alarm.alarm_level,
            func.count(Alarm.id).label("count")
        ).where(
            Alarm.created_at >= start_time
        ).group_by(
            func.date(Alarm.created_at), Alarm.alarm_level
        ).order_by("date")
    )

    # 整理数据
    trend_data = {}
    for row in result.all():
        date_str = str(row[0])
        if date_str not in trend_data:
            trend_data[date_str] = {"date": date_str, "critical": 0, "major": 0, "minor": 0, "info": 0}
        trend_data[date_str][row[1]] = row[2]

    return list(trend_data.values())


@router.get("/top-points", summary="获取高频告警点位")
async def get_top_alarm_points(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取告警最多的点位
    """
    start_time = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(
            Alarm.point_id,
            func.count(Alarm.id).label("alarm_count")
        ).where(
            Alarm.created_at >= start_time
        ).group_by(
            Alarm.point_id
        ).order_by(
            func.count(Alarm.id).desc()
        ).limit(limit)
    )

    top_points = []
    for row in result.all():
        point_result = await db.execute(select(Point).where(Point.id == row[0]))
        point = point_result.scalar_one_or_none()
        if point:
            top_points.append({
                "point_id": point.id,
                "point_code": point.point_code,
                "point_name": point.point_name,
                "alarm_count": row[1]
            })

    return top_points


@router.get("/export", summary="导出告警记录")
async def export_alarms(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    导出告警记录为CSV
    """
    query = select(Alarm)

    if start_time:
        query = query.where(Alarm.created_at >= start_time)
    if end_time:
        query = query.where(Alarm.created_at <= end_time)
    if status:
        query = query.where(Alarm.status == status)

    result = await db.execute(query.order_by(Alarm.created_at.desc()))
    alarms = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "告警编号", "告警级别", "告警消息", "触发值", "阈值",
        "状态", "确认时间", "解决时间", "创建时间"
    ])

    for alarm in alarms:
        writer.writerow([
            alarm.alarm_no, alarm.alarm_level, alarm.alarm_message,
            alarm.trigger_value, alarm.threshold_value, alarm.status,
            alarm.acknowledged_at, alarm.resolved_at, alarm.created_at
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alarms.csv"}
    )


@router.get("/{alarm_id}", response_model=AlarmInfo, summary="获取告警详情")
async def get_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取告警详情
    """
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
    point = point_result.scalar_one_or_none()

    alarm_info = AlarmInfo.model_validate(alarm)
    if point:
        alarm_info.point_code = point.point_code
        alarm_info.point_name = point.point_name

    return alarm_info


@router.put("/{alarm_id}/acknowledge", summary="确认告警")
async def acknowledge_alarm(
    alarm_id: int,
    data: AlarmAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    确认告警
    """
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    if alarm.status != "active":
        raise HTTPException(status_code=400, detail="告警状态不允许确认")

    await db.execute(
        update(Alarm).where(Alarm.id == alarm_id).values(
            status="acknowledged",
            acknowledged_by=current_user.id,
            acknowledged_at=datetime.now(),
            ack_remark=data.remark
        )
    )
    await db.commit()

    return {"message": "告警已确认"}


@router.put("/{alarm_id}/resolve", summary="解决告警")
async def resolve_alarm(
    alarm_id: int,
    data: AlarmResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    解决告警
    """
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    if alarm.status == "resolved":
        raise HTTPException(status_code=400, detail="告警已解决")

    duration = int((datetime.now() - alarm.created_at).total_seconds())

    await db.execute(
        update(Alarm).where(Alarm.id == alarm_id).values(
            status="resolved",
            resolved_by=current_user.id,
            resolved_at=datetime.now(),
            resolve_remark=data.remark,
            resolve_type=data.resolve_type or "manual",
            duration_seconds=duration
        )
    )
    await db.commit()

    return {"message": "告警已解决"}


@router.put("/batch-acknowledge", summary="批量确认告警")
async def batch_acknowledge(
    alarm_ids: List[int],
    remark: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    批量确认告警
    """
    await db.execute(
        update(Alarm).where(
            and_(Alarm.id.in_(alarm_ids), Alarm.status == "active")
        ).values(
            status="acknowledged",
            acknowledged_by=current_user.id,
            acknowledged_at=datetime.now(),
            ack_remark=remark
        )
    )
    await db.commit()

    return {"message": f"已确认 {len(alarm_ids)} 条告警"}
