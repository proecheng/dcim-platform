"""
统计分析 API - v1
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ..deps import (
    SiteAccessContext,
    apply_device_site_scope,
    apply_point_site_scope,
    apply_site_scope,
    get_db,
    get_site_access_context,
    require_viewer,
)
from ...models.user import User
from ...models.point import Point, PointRealtime
from ...models.device import Device
from ...models.alarm import Alarm
from ...models.history import PointHistory
from ...core.cache_headers import set_cache_headers, CACHE_SHORT, CACHE_MEDIUM

router = APIRouter()


def _scope_point_query(query, context: SiteAccessContext):
    """通过 Point -> Device -> Site 约束点位查询。"""
    return apply_device_site_scope(query, Point.device_id, context)


def _scope_alarm_query(query, context: SiteAccessContext):
    """通过 Alarm -> Point -> Device -> Site 约束告警查询。"""
    return apply_point_site_scope(query, Alarm.point_id, context)


@router.get("/overview", summary="获取系统概览统计")
async def get_overview(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取系统概览统计信息
    """
    # 点位统计
    point_total = (await db.execute(_scope_point_query(select(func.count(Point.id)), context))).scalar()
    point_enabled = (
        await db.execute(_scope_point_query(select(func.count(Point.id)).where(Point.is_enabled == True), context))
    ).scalar()

    # 设备统计
    device_total = (await db.execute(apply_site_scope(select(func.count(Device.id)), Device.site_id, context))).scalar()
    device_online = (
        await db.execute(
            apply_site_scope(select(func.count(Device.id)).where(Device.status == "online"), Device.site_id, context)
        )
    ).scalar()

    # 活动告警
    alarm_active_query = _scope_alarm_query(
        select(func.count(Alarm.id)).where(Alarm.status.in_(["active", "acknowledged"])), context
    )
    alarm_active = (await db.execute(alarm_active_query)).scalar()

    # 今日告警
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    alarm_today_query = _scope_alarm_query(
        select(func.count(Alarm.id)).where(Alarm.created_at >= today_start), context
    )
    alarm_today = (await db.execute(alarm_today_query)).scalar()

    # 实时数据状态
    realtime_query = apply_point_site_scope(
        select(PointRealtime.status, func.count(PointRealtime.point_id)).group_by(PointRealtime.status),
        PointRealtime.point_id,
        context,
    )
    realtime_result = await db.execute(realtime_query)
    realtime_status = {row[0]: row[1] for row in realtime_result.all()}

    set_cache_headers(response, CACHE_SHORT)
    return {
        "points": {"total": point_total, "enabled": point_enabled, "disabled": point_total - point_enabled},
        "devices": {"total": device_total, "online": device_online, "offline": device_total - device_online},
        "alarms": {"active": alarm_active, "today": alarm_today},
        "realtime": realtime_status,
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/points", summary="获取点位统计")
async def get_points_statistics(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取点位统计信息
    """
    # 按类型统计
    type_result = await db.execute(
        _scope_point_query(select(Point.point_type, func.count(Point.id)).group_by(Point.point_type), context)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}

    # 按设备类型统计
    device_type_result = await db.execute(
        _scope_point_query(select(Point.device_type, func.count(Point.id)).group_by(Point.device_type), context)
    )
    by_device_type = {row[0]: row[1] for row in device_type_result.all()}

    # 按区域统计
    area_result = await db.execute(
        _scope_point_query(select(Point.area_code, func.count(Point.id)).group_by(Point.area_code), context)
    )
    by_area = {row[0]: row[1] for row in area_result.all()}

    # 按状态统计
    status_query = apply_point_site_scope(
        select(PointRealtime.status, func.count(PointRealtime.point_id)).group_by(PointRealtime.status),
        PointRealtime.point_id,
        context,
    )
    status_result = await db.execute(status_query)
    by_status = {row[0]: row[1] for row in status_result.all()}

    set_cache_headers(response, CACHE_MEDIUM)
    return {"by_type": by_type, "by_device_type": by_device_type, "by_area": by_area, "by_status": by_status}


@router.get("/alarms", summary="获取告警统计")
async def get_alarms_statistics(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取告警统计信息
    """
    start_time = datetime.now() - timedelta(days=days)

    # 按级别统计
    level_query = _scope_alarm_query(
        select(Alarm.alarm_level, func.count(Alarm.id))
        .where(Alarm.created_at >= start_time)
        .group_by(Alarm.alarm_level),
        context,
    )
    level_result = await db.execute(level_query)
    by_level = {row[0]: row[1] for row in level_result.all()}

    # 按状态统计
    status_query = _scope_alarm_query(
        select(Alarm.status, func.count(Alarm.id)).where(Alarm.created_at >= start_time).group_by(Alarm.status),
        context,
    )
    status_result = await db.execute(status_query)
    by_status = {row[0]: row[1] for row in status_result.all()}

    # 按天统计趋势
    daily_query = _scope_alarm_query(
        select(func.date(Alarm.created_at).label("date"), func.count(Alarm.id).label("count"))
        .where(Alarm.created_at >= start_time)
        .group_by(func.date(Alarm.created_at))
        .order_by("date"),
        context,
    )
    daily_result = await db.execute(daily_query)
    daily_trend = [{"date": str(row[0]), "count": row[1]} for row in daily_result.all()]

    # 高频告警点位 TOP 10
    top_points_query = _scope_alarm_query(
        select(Alarm.point_id, func.count(Alarm.id).label("count"))
        .where(Alarm.created_at >= start_time)
        .group_by(Alarm.point_id)
        .order_by(func.count(Alarm.id).desc())
        .limit(10),
        context,
    )
    top_points_result = await db.execute(top_points_query)

    top_points = []
    for row in top_points_result.all():
        point_result = await db.execute(select(Point).where(Point.id == row[0]))
        point = point_result.scalar_one_or_none()
        if point:
            top_points.append(
                {
                    "point_id": point.id,
                    "point_code": point.point_code,
                    "point_name": point.point_name,
                    "alarm_count": row[1],
                }
            )

    # 平均处理时间
    avg_duration_query = _scope_alarm_query(
        select(func.avg(Alarm.duration_seconds)).where(
            and_(Alarm.created_at >= start_time, Alarm.status == "resolved")
        ),
        context,
    )
    avg_duration_result = await db.execute(avg_duration_query)
    avg_duration = avg_duration_result.scalar() or 0

    return {
        "period_days": days,
        "by_level": by_level,
        "by_status": by_status,
        "daily_trend": daily_trend,
        "top_alarm_points": top_points,
        "avg_resolve_duration_seconds": int(avg_duration),
    }


@router.get("/energy", summary="获取能耗统计")
async def get_energy_statistics(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取能耗统计信息
    """
    start_time = datetime.now() - timedelta(days=days)

    # 查找功率相关点位
    power_points_query = _scope_point_query(
        select(Point).where(
            and_(Point.device_type == "PDU", Point.point_type == "AI", Point.point_name.contains("功率"))
        ),
        context,
    )
    power_points_result = await db.execute(power_points_query)
    power_points = power_points_result.scalars().all()

    energy_data = []
    for point in power_points:
        # 获取每日平均功率
        daily_result = await db.execute(
            select(func.date(PointHistory.recorded_at).label("date"), func.avg(PointHistory.value).label("avg_power"))
            .where(and_(PointHistory.point_id == point.id, PointHistory.recorded_at >= start_time))
            .group_by(func.date(PointHistory.recorded_at))
            .order_by("date")
        )

        daily_data = [
            {"date": str(row[0]), "avg_power": round(row[1], 2) if row[1] else 0} for row in daily_result.all()
        ]

        energy_data.append(
            {
                "point_code": point.point_code,
                "point_name": point.point_name,
                "unit": point.unit,
                "daily_data": daily_data,
            }
        )

    return {"period_days": days, "power_points": energy_data}


@router.get("/availability", summary="获取可用性统计")
async def get_availability_statistics(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取系统可用性统计
    """
    start_time = datetime.now() - timedelta(days=days)
    total_seconds = days * 24 * 3600

    # 计算告警时长
    alarm_duration_query = _scope_alarm_query(
        select(func.sum(Alarm.duration_seconds)).where(
            and_(
                Alarm.created_at >= start_time, Alarm.status == "resolved", Alarm.alarm_level.in_(["critical", "major"])
            )
        ),
        context,
    )
    alarm_duration_result = await db.execute(alarm_duration_query)
    alarm_duration = alarm_duration_result.scalar() or 0

    # 可用率
    availability = (total_seconds - alarm_duration) / total_seconds * 100 if total_seconds > 0 else 100

    # 按设备类型统计可用性
    device_types = ["UPS", "AC", "PDU"]
    device_availability = {}

    for dtype in device_types:
        # 获取该类型的告警时长
        type_duration_query = _scope_alarm_query(
            select(func.sum(Alarm.duration_seconds))
            .join(Point)
            .where(and_(Alarm.created_at >= start_time, Alarm.status == "resolved", Point.device_type == dtype)),
            context,
        )
        type_duration_result = await db.execute(type_duration_query)
        type_duration = type_duration_result.scalar() or 0
        type_availability = (total_seconds - type_duration) / total_seconds * 100 if total_seconds > 0 else 100
        device_availability[dtype] = round(type_availability, 2)

    return {
        "period_days": days,
        "overall_availability": round(availability, 2),
        "total_alarm_duration_seconds": alarm_duration,
        "by_device_type": device_availability,
    }


@router.get("/comparison", summary="获取同比/环比数据")
async def get_comparison_data(
    metric: str = Query("alarm", description="指标: alarm/energy"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取同比环比数据
    """
    now = datetime.now()

    # 本周
    this_week_start = now - timedelta(days=now.weekday())
    this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # 上周
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start

    # 本月
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 上月
    if now.month == 1:
        last_month_start = datetime(now.year - 1, 12, 1)
    else:
        last_month_start = datetime(now.year, now.month - 1, 1)
    last_month_end = this_month_start

    if metric == "alarm":
        # 本周告警数
        this_week_result = await db.execute(
            _scope_alarm_query(select(func.count(Alarm.id)).where(Alarm.created_at >= this_week_start), context)
        )
        this_week_count = this_week_result.scalar()

        # 上周告警数
        last_week_query = _scope_alarm_query(
            select(func.count(Alarm.id)).where(
                and_(Alarm.created_at >= last_week_start, Alarm.created_at < last_week_end)
            ),
            context,
        )
        last_week_result = await db.execute(last_week_query)
        last_week_count = last_week_result.scalar()

        # 本月告警数
        this_month_result = await db.execute(
            _scope_alarm_query(select(func.count(Alarm.id)).where(Alarm.created_at >= this_month_start), context)
        )
        this_month_count = this_month_result.scalar()

        # 上月告警数
        last_month_query = _scope_alarm_query(
            select(func.count(Alarm.id)).where(
                and_(Alarm.created_at >= last_month_start, Alarm.created_at < last_month_end)
            ),
            context,
        )
        last_month_result = await db.execute(last_month_query)
        last_month_count = last_month_result.scalar()

        # 计算环比
        week_change = ((this_week_count - last_week_count) / last_week_count * 100) if last_week_count > 0 else 0
        month_change = ((this_month_count - last_month_count) / last_month_count * 100) if last_month_count > 0 else 0

        return {
            "metric": "alarm",
            "this_week": this_week_count,
            "last_week": last_week_count,
            "week_change_percent": round(week_change, 1),
            "this_month": this_month_count,
            "last_month": last_month_count,
            "month_change_percent": round(month_change, 1),
        }

    else:
        # 能耗对比（简化版）
        return {"metric": "energy", "message": "能耗对比功能需要配置功率点位"}
