"""
告警管理 API - v1
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, and_
import csv
import io

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.alarm import Alarm, AlarmShield
from ...models.point import Point
from ...schemas.alarm import (
    AlarmInfo,
    AlarmAcknowledge,
    AlarmResolve,
    AlarmCount,
    AlarmStatistics,
    AlarmRuleCreate,
    AlarmRuleUpdate,
    AlarmRuleInfo,
    AlarmShieldCreate,
    AlarmShieldInfo,
    AlarmProcess,
    BatchAcknowledgeRequest,
)
from ...schemas.common import PageResponse
from ...services.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PageResponse[AlarmInfo], summary="获取告警列表")
async def get_alarms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="状态: active/acknowledged/resolved"),
    level: Optional[str] = Query(None, description="级别: critical/major/minor/info"),
    point_id: Optional[int] = Query(None, description="点位ID"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    keyword: Optional[str] = Query(None, description="关键词"),
    data_source: Optional[str] = Query(None, description="数据来源过滤: demo/mqtt/bridge"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
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
    if device_type:
        query = query.join(Point, Alarm.point_id == Point.id, isouter=True).where(
            Point.device_type == device_type, Alarm.point_id.isnot(None)
        )
    if start_time:
        query = query.where(Alarm.created_at >= start_time)
    if end_time:
        query = query.where(Alarm.created_at <= end_time)
    if keyword:
        query = query.where(Alarm.alarm_message.contains(keyword))
    if data_source:
        query = query.where(Alarm.data_source == data_source)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Alarm.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    alarms = result.scalars().all()

    # 批量预查询 Point 信息（避免 N+1）
    point_ids = {a.point_id for a in alarms if a.point_id}
    point_map: dict[int, Point] = {}
    if point_ids:
        point_result = await db.execute(select(Point).where(Point.id.in_(point_ids)))
        point_map = {p.id: p for p in point_result.scalars().all()}

    alarm_list = []
    for alarm in alarms:
        alarm_info = AlarmInfo.model_validate(alarm)
        if alarm.point_id and alarm.point_id in point_map:
            point = point_map[alarm.point_id]
            alarm_info.point_code = point.point_code
            alarm_info.point_name = point.point_name
        alarm_list.append(alarm_info)

    return PageResponse(items=alarm_list, total=total, page=page, page_size=page_size)


@router.get("/active", summary="获取活动告警")
async def get_active_alarms(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取所有未解决的告警
    """
    query = (
        select(Alarm)
        .where(Alarm.status.in_(["active", "acknowledged"]))
        .order_by(Alarm.alarm_level.desc(), Alarm.created_at.desc())
    )

    result = await db.execute(query)
    alarms = result.scalars().all()

    # 批量预查询 Point 信息（避免 N+1）
    point_ids = {a.point_id for a in alarms if a.point_id}
    point_map: dict[int, Point] = {}
    if point_ids:
        point_result = await db.execute(select(Point).where(Point.id.in_(point_ids)))
        point_map = {p.id: p for p in point_result.scalars().all()}

    alarm_list = []
    for alarm in alarms:
        alarm_info = AlarmInfo.model_validate(alarm)
        if alarm.point_id and alarm.point_id in point_map:
            point = point_map[alarm.point_id]
            alarm_info.point_code = point.point_code
            alarm_info.point_name = point.point_name
        alarm_list.append(alarm_info)

    return alarm_list


@router.get("/count", response_model=AlarmCount, summary="获取各级别告警数量")
async def get_alarm_count(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取各级别的活动告警数量
    """
    result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id))
        .where(Alarm.status.in_(["active", "acknowledged"]))
        .group_by(Alarm.alarm_level)
    )
    counts = {row[0]: row[1] for row in result.all()}

    return AlarmCount(
        critical=counts.get("critical", 0),
        major=counts.get("major", 0),
        minor=counts.get("minor", 0),
        info=counts.get("info", 0),
        total=sum(counts.values()),
    )


@router.get("/statistics", response_model=AlarmStatistics, summary="获取告警统计")
async def get_alarm_statistics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_type: Optional[str] = Query(None, description="设备类型: TH/UPS/PDU/AC等"),
    alarm_level: Optional[str] = Query(None, description="告警级别: critical/major/minor/info"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取告警统计信息（支持按设备类型和告警级别筛选）
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    # 构建基础条件
    conditions = [Alarm.created_at >= start_time, Alarm.created_at <= end_time]
    if alarm_level:
        conditions.append(Alarm.alarm_level == alarm_level)
    if device_type:
        # 通过子查询获取该设备类型的点位 ID
        point_ids_query = select(Point.id).where(Point.device_type == device_type)
        conditions.append(Alarm.point_id.in_(point_ids_query))

    base_filter = and_(*conditions)

    # 总数
    total_result = await db.execute(select(func.count(Alarm.id)).where(base_filter))
    total = total_result.scalar() or 0

    # 按级别统计
    level_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(base_filter).group_by(Alarm.alarm_level)
    )
    by_level = {row[0]: row[1] for row in level_result.all()}

    # 按状态统计
    status_result = await db.execute(
        select(Alarm.status, func.count(Alarm.id)).where(base_filter).group_by(Alarm.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # 按设备类型统计（JOIN Point 表，排除无 point_id 的数据源告警）
    device_type_result = await db.execute(
        select(Point.device_type, func.count(Alarm.id))
        .join(Point, Alarm.point_id == Point.id)
        .where(base_filter, Alarm.point_id.isnot(None))
        .group_by(Point.device_type)
    )
    by_device_type = {row[0]: row[1] for row in device_type_result.all() if row[0]}

    # 平均处理时间
    avg_conditions = conditions + [Alarm.status == "resolved"]
    avg_duration_result = await db.execute(select(func.avg(Alarm.duration_seconds)).where(and_(*avg_conditions)))
    avg_duration = avg_duration_result.scalar() or 0

    return AlarmStatistics(
        total=total,
        by_level=by_level,
        by_status=by_status,
        by_device_type=by_device_type,
        avg_duration_seconds=int(avg_duration),
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/trend", summary="获取告警趋势")
async def get_alarm_trend(
    days: int = Query(7, ge=1, le=90, description="天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取告警趋势数据（按天统计）
    """
    start_time = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(func.date(Alarm.created_at).label("date"), Alarm.alarm_level, func.count(Alarm.id).label("count"))
        .where(Alarm.created_at >= start_time)
        .group_by(func.date(Alarm.created_at), Alarm.alarm_level)
        .order_by("date")
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
    _: User = Depends(require_viewer),
):
    """
    获取告警最多的点位
    """
    start_time = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(Alarm.point_id, func.count(Alarm.id).label("alarm_count"))
        .where(Alarm.created_at >= start_time, Alarm.point_id.isnot(None))
        .group_by(Alarm.point_id)
        .order_by(func.count(Alarm.id).desc())
        .limit(limit)
    )

    rows = result.all()

    # 批量预查询 Point 信息（避免 N+1）
    point_ids = {row[0] for row in rows if row[0]}
    point_map: dict[int, Point] = {}
    if point_ids:
        point_result = await db.execute(select(Point).where(Point.id.in_(point_ids)))
        point_map = {p.id: p for p in point_result.scalars().all()}

    top_points = []
    for row in rows:
        point = point_map.get(row[0])
        if point:
            top_points.append(
                {
                    "point_id": point.id,
                    "point_code": point.point_code,
                    "point_name": point.point_name,
                    "alarm_count": row[1],
                }
            )

    return top_points


@router.get("/export", summary="导出告警记录")
async def export_alarms(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
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
    writer.writerow(["告警编号", "告警级别", "告警消息", "触发值", "阈值", "状态", "确认时间", "解决时间", "创建时间"])

    for alarm in alarms:
        writer.writerow(
            [
                alarm.alarm_no,
                alarm.alarm_level,
                alarm.alarm_message,
                alarm.trigger_value,
                alarm.threshold_value,
                alarm.status,
                alarm.acknowledged_at,
                alarm.resolved_at,
                alarm.created_at,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alarms.csv"},
    )


@router.put("/batch-acknowledge", summary="批量确认告警")
async def batch_acknowledge(
    data: BatchAcknowledgeRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_operator)
):
    """
    批量确认告警
    """
    now = datetime.now()
    result = await db.execute(
        update(Alarm)
        .where(and_(Alarm.id.in_(data.alarm_ids), Alarm.status == "active"))
        .values(status="acknowledged", acknowledged_by=current_user.id, acknowledged_at=now, ack_remark=data.remark)
    )
    await db.commit()

    actual_count = result.rowcount

    # WebSocket 广播批量确认消息
    await ws_manager.broadcast_alarm(
        {
            "alarm_ids": data.alarm_ids,
            "acknowledged_by": current_user.id,
            "acknowledged_at": now.isoformat(),
            "action": "batch_ack",
        }
    )

    return {"message": f"已确认 {actual_count} 条告警", "count": actual_count}


# ============== 告警规则管理 ==============


@router.get("/rules", response_model=PageResponse[AlarmRuleInfo], summary="获取告警规则列表")
async def get_alarm_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_type: Optional[str] = Query(None, description="规则类型: and/or/sequence"),
    alarm_level: Optional[str] = Query(None, description="告警级别: critical/major/minor/info"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取告警规则列表（分页、筛选）
    """
    from ...models.alarm import AlarmRule

    query = select(AlarmRule)

    if rule_type:
        query = query.where(AlarmRule.rule_type == rule_type)
    if alarm_level:
        query = query.where(AlarmRule.alarm_level == alarm_level)
    if is_enabled is not None:
        query = query.where(AlarmRule.is_enabled == is_enabled)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(AlarmRule.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rules = result.scalars().all()

    return PageResponse(
        items=[AlarmRuleInfo.model_validate(rule) for rule in rules], total=total, page=page, page_size=page_size
    )


@router.post("/rules", response_model=AlarmRuleInfo, summary="创建告警规则")
async def create_alarm_rule(
    data: AlarmRuleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建告警规则
    """
    from ...models.alarm import AlarmRule

    rule = AlarmRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return AlarmRuleInfo.model_validate(rule)


@router.get("/rules/{rule_id}", response_model=AlarmRuleInfo, summary="获取告警规则详情")
async def get_alarm_rule(rule_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取告警规则详情
    """
    from ...models.alarm import AlarmRule

    result = await db.execute(select(AlarmRule).where(AlarmRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")

    return AlarmRuleInfo.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=AlarmRuleInfo, summary="更新告警规则")
async def update_alarm_rule(
    rule_id: int, data: AlarmRuleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    更新告警规则
    """
    from ...models.alarm import AlarmRule

    result = await db.execute(select(AlarmRule).where(AlarmRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")

    # 更新非空字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)

    return AlarmRuleInfo.model_validate(rule)


@router.delete("/rules/{rule_id}", summary="删除告警规则")
async def delete_alarm_rule(rule_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    删除告警规则
    """
    from ...models.alarm import AlarmRule

    result = await db.execute(select(AlarmRule).where(AlarmRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")

    await db.delete(rule)
    await db.commit()

    return {"message": "告警规则已删除"}


@router.put("/rules/{rule_id}/toggle", summary="切换告警规则启用状态")
async def toggle_alarm_rule(rule_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    切换告警规则的启用/禁用状态
    """
    from ...models.alarm import AlarmRule

    result = await db.execute(select(AlarmRule).where(AlarmRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")

    rule.is_enabled = not rule.is_enabled
    await db.commit()
    await db.refresh(rule)

    return {"message": f"告警规则已{'启用' if rule.is_enabled else '禁用'}", "is_enabled": rule.is_enabled}


# ============== 告警屏蔽管理 ==============


@router.get("/shields", response_model=PageResponse[AlarmShieldInfo], summary="获取告警屏蔽列表")
async def get_alarm_shields(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    point_id: Optional[int] = Query(None, description="点位ID"),
    alarm_level: Optional[str] = Query(None, description="告警级别"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """
    获取告警屏蔽列表（分页、筛选）
    """
    query = select(AlarmShield)

    if point_id:
        query = query.where(AlarmShield.point_id == point_id)
    if alarm_level:
        query = query.where(AlarmShield.alarm_level == alarm_level)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(AlarmShield.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    shields = result.scalars().all()

    # 批量预查询 Point 信息（避免 N+1）
    point_ids = {s.point_id for s in shields if s.point_id}
    point_map: dict[int, Point] = {}
    if point_ids:
        point_result = await db.execute(select(Point).where(Point.id.in_(point_ids)))
        point_map = {p.id: p for p in point_result.scalars().all()}

    # 获取关联信息
    shield_list = []
    now = datetime.now()
    for shield in shields:
        shield_info = AlarmShieldInfo.model_validate(shield)

        # 获取点位信息
        if shield.point_id and shield.point_id in point_map:
            point = point_map[shield.point_id]
            shield_info.point_code = point.point_code
            shield_info.point_name = point.point_name

        # 计算状态
        if shield.end_time < now:
            shield_info.status = "expired"
        else:
            shield_info.status = "active"

        shield_list.append(shield_info)

    return PageResponse(items=shield_list, total=total, page=page, page_size=page_size)


@router.post("/shields", response_model=AlarmShieldInfo, summary="创建告警屏蔽")
async def create_alarm_shield(
    data: AlarmShieldCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_operator)
):
    """
    创建告警屏蔽
    """

    shield = AlarmShield(**data.model_dump(), created_by=current_user.id)
    db.add(shield)
    await db.commit()
    await db.refresh(shield)

    # 构建返回信息
    shield_info = AlarmShieldInfo.model_validate(shield)
    shield_info.status = "active" if shield.end_time > datetime.now() else "expired"

    return shield_info


@router.delete("/shields/{shield_id}", summary="删除告警屏蔽")
async def delete_alarm_shield(shield_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    删除告警屏蔽
    """

    result = await db.execute(select(AlarmShield).where(AlarmShield.id == shield_id))
    shield = result.scalar_one_or_none()

    if not shield:
        raise HTTPException(status_code=404, detail="告警屏蔽不存在")

    await db.delete(shield)
    await db.commit()

    return {"message": "告警屏蔽已删除"}


# ============== 单条告警操作（路径参数路由放在最后，避免与 /rules /shields 等静态路径冲突） ==============


@router.get("/{alarm_id}", response_model=AlarmInfo, summary="获取告警详情")
async def get_alarm(alarm_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取告警详情
    """
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm_info = AlarmInfo.model_validate(alarm)
    if alarm.point_id:
        point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
        point = point_result.scalar_one_or_none()
        if point:
            alarm_info.point_code = point.point_code
            alarm_info.point_name = point.point_name

    return alarm_info


@router.put("/{alarm_id}/acknowledge", summary="确认告警")
async def acknowledge_alarm(
    alarm_id: int,
    data: AlarmAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
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

    now = datetime.now()
    await db.execute(
        update(Alarm)
        .where(Alarm.id == alarm_id)
        .values(status="acknowledged", acknowledged_by=current_user.id, acknowledged_at=now, ack_remark=data.remark)
    )
    await db.commit()

    # WebSocket 广播确认消息
    await ws_manager.broadcast_alarm(
        {
            "id": alarm_id,
            "status": "acknowledged",
            "acknowledged_by": current_user.id,
            "acknowledged_at": now.isoformat(),
            "ack_remark": data.remark,
            "action": "ack",
        }
    )

    return {"message": "告警已确认"}


@router.put("/{alarm_id}/resolve", summary="解决告警")
async def resolve_alarm(
    alarm_id: int,
    data: AlarmResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
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

    now = datetime.now()
    duration = max(0, int((now - alarm.created_at).total_seconds())) if alarm.created_at else 0

    await db.execute(
        update(Alarm)
        .where(Alarm.id == alarm_id)
        .values(
            status="resolved",
            resolved_by=current_user.id,
            resolved_at=now,
            resolve_remark=data.remark,
            resolve_type=data.resolve_type or "manual",
            duration_seconds=duration,
        )
    )
    await db.commit()

    # WebSocket 广播解决消息
    await ws_manager.broadcast_alarm(
        {
            "id": alarm_id,
            "status": "resolved",
            "resolved_by": current_user.id,
            "resolved_at": now.isoformat(),
            "resolve_remark": data.remark,
            "resolve_type": data.resolve_type or "manual",
            "duration_seconds": duration,
            "action": "resolve",
        }
    )

    return {"message": "告警已解决"}


@router.put("/{alarm_id}/process", summary="处理告警")
async def process_alarm(
    alarm_id: int,
    data: AlarmProcess,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    记录告警处理过程（不改变状态）
    """
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    if alarm.status not in ("active", "acknowledged"):
        raise HTTPException(status_code=400, detail="告警状态不允许处理")

    now = datetime.now()
    await db.execute(
        update(Alarm)
        .where(Alarm.id == alarm_id)
        .values(process_remark=data.process_remark, processed_by=current_user.id, processed_at=now)
    )
    await db.commit()

    # WebSocket 广播处理消息
    await ws_manager.broadcast_alarm(
        {
            "id": alarm_id,
            "process_remark": data.process_remark,
            "processed_by": current_user.id,
            "processed_at": now.isoformat(),
            "action": "update",
        }
    )

    return {"message": "告警处理记录已保存"}
