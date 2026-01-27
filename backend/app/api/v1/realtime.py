"""
实时数据 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.point import Point, PointRealtime
from ...schemas.realtime import RealtimeData, RealtimeSummary, ControlCommand

router = APIRouter()


@router.get("", summary="获取所有点位实时数据")
async def get_all_realtime(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取所有启用点位的实时数据
    """
    query = select(Point, PointRealtime).join(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.is_enabled == True)

    result = await db.execute(query)
    rows = result.all()

    data = []
    for point, realtime in rows:
        data.append(RealtimeData(
            point_id=point.id,
            point_code=point.point_code,
            point_name=point.point_name,
            point_type=point.point_type,
            device_type=point.device_type,
            area_code=point.area_code,
            value=realtime.value,
            value_text=realtime.value_text,
            unit=point.unit,
            quality=realtime.quality,
            status=realtime.status,
            alarm_level=realtime.alarm_level,
            updated_at=realtime.updated_at
        ))

    return data


@router.get("/summary", response_model=RealtimeSummary, summary="获取实时数据汇总")
async def get_realtime_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取实时数据汇总信息
    """
    from sqlalchemy import func

    # 点位统计
    total_result = await db.execute(
        select(func.count(Point.id)).where(Point.is_enabled == True)
    )
    total_points = total_result.scalar()

    # 状态统计
    status_result = await db.execute(
        select(PointRealtime.status, func.count(PointRealtime.point_id)).group_by(PointRealtime.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    # 告警级别统计
    alarm_result = await db.execute(
        select(PointRealtime.alarm_level, func.count(PointRealtime.point_id)).where(
            PointRealtime.alarm_level.isnot(None)
        ).group_by(PointRealtime.alarm_level)
    )
    alarm_counts = {row[0]: row[1] for row in alarm_result.all()}

    # 关键指标（温湿度、电力）
    key_points = {}
    key_point_codes = ["A1_TH_AI_001", "A1_TH_AI_002", "A1_PDU_AI_005", "A1_UPS_AI_001"]
    for code in key_point_codes:
        point_result = await db.execute(
            select(Point, PointRealtime).join(
                PointRealtime, Point.id == PointRealtime.point_id
            ).where(Point.point_code == code)
        )
        row = point_result.first()
        if row:
            point, realtime = row
            key_points[code] = {
                "name": point.point_name,
                "value": realtime.value,
                "unit": point.unit,
                "status": realtime.status
            }

    return RealtimeSummary(
        total_points=total_points,
        normal_count=status_counts.get("normal", 0),
        alarm_count=status_counts.get("alarm", 0),
        offline_count=status_counts.get("offline", 0),
        critical_count=alarm_counts.get("critical", 0),
        major_count=alarm_counts.get("major", 0),
        minor_count=alarm_counts.get("minor", 0),
        key_points=key_points
    )


@router.get("/dashboard", summary="获取仪表盘数据")
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取仪表盘显示所需的数据
    """
    from sqlalchemy import func
    from ...models.alarm import Alarm

    # 概览卡片数据
    overview = {
        "temperature": None,
        "humidity": None,
        "power": None,
        "ups_load": None,
        "ac_running": 0,
        "alarm_count": 0
    }

    # 获取温度
    temp_result = await db.execute(
        select(PointRealtime.value).join(Point).where(
            Point.point_code == "A1_TH_AI_001"
        )
    )
    temp = temp_result.scalar()
    if temp:
        overview["temperature"] = round(temp, 1)

    # 获取湿度
    hum_result = await db.execute(
        select(PointRealtime.value).join(Point).where(
            Point.point_code == "A1_TH_AI_002"
        )
    )
    hum = hum_result.scalar()
    if hum:
        overview["humidity"] = round(hum, 1)

    # 获取功率
    power_result = await db.execute(
        select(PointRealtime.value).join(Point).where(
            Point.point_code == "A1_PDU_AI_005"
        )
    )
    power = power_result.scalar()
    if power:
        overview["power"] = round(power, 1)

    # 获取UPS负载
    ups_result = await db.execute(
        select(PointRealtime.value).join(Point).where(
            Point.point_code == "A1_UPS_AI_003"
        )
    )
    ups = ups_result.scalar()
    if ups:
        overview["ups_load"] = round(ups, 1)

    # 空调运行数量
    ac_result = await db.execute(
        select(func.count(PointRealtime.point_id)).join(Point).where(
            Point.device_type == "AC",
            Point.point_type == "DI",
            PointRealtime.value == 1
        )
    )
    overview["ac_running"] = ac_result.scalar() or 0

    # 活动告警数量
    alarm_result = await db.execute(
        select(func.count(Alarm.id)).where(Alarm.status == "active")
    )
    overview["alarm_count"] = alarm_result.scalar() or 0

    # 设备状态分布
    from ...models.device import Device
    device_status_result = await db.execute(
        select(Device.status, func.count(Device.id)).group_by(Device.status)
    )
    device_status = {row[0]: row[1] for row in device_status_result.all()}

    return {
        "overview": overview,
        "device_status": device_status,
        "updated_at": datetime.now().isoformat()
    }


@router.get("/{point_id}", response_model=RealtimeData, summary="获取单个点位实时数据")
async def get_point_realtime(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取单个点位的实时数据
    """
    result = await db.execute(
        select(Point, PointRealtime).join(
            PointRealtime, Point.id == PointRealtime.point_id
        ).where(Point.id == point_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="点位不存在")

    point, realtime = row
    return RealtimeData(
        point_id=point.id,
        point_code=point.point_code,
        point_name=point.point_name,
        point_type=point.point_type,
        device_type=point.device_type,
        area_code=point.area_code,
        value=realtime.value,
        value_text=realtime.value_text,
        unit=point.unit,
        quality=realtime.quality,
        status=realtime.status,
        alarm_level=realtime.alarm_level,
        updated_at=realtime.updated_at
    )


@router.get("/by-type/{point_type}", summary="按类型获取实时数据")
async def get_realtime_by_type(
    point_type: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    按点位类型获取实时数据
    """
    if point_type not in ["AI", "DI", "AO", "DO"]:
        raise HTTPException(status_code=400, detail="无效的点位类型")

    query = select(Point, PointRealtime).join(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.is_enabled == True, Point.point_type == point_type)

    result = await db.execute(query)
    rows = result.all()

    return [
        RealtimeData(
            point_id=point.id,
            point_code=point.point_code,
            point_name=point.point_name,
            point_type=point.point_type,
            device_type=point.device_type,
            area_code=point.area_code,
            value=realtime.value,
            value_text=realtime.value_text,
            unit=point.unit,
            quality=realtime.quality,
            status=realtime.status,
            alarm_level=realtime.alarm_level,
            updated_at=realtime.updated_at
        ) for point, realtime in rows
    ]


@router.get("/by-area/{area_code}", summary="按区域获取实时数据")
async def get_realtime_by_area(
    area_code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    按区域获取实时数据
    """
    query = select(Point, PointRealtime).join(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.is_enabled == True, Point.area_code == area_code)

    result = await db.execute(query)
    rows = result.all()

    return [
        RealtimeData(
            point_id=point.id,
            point_code=point.point_code,
            point_name=point.point_name,
            point_type=point.point_type,
            device_type=point.device_type,
            area_code=point.area_code,
            value=realtime.value,
            value_text=realtime.value_text,
            unit=point.unit,
            quality=realtime.quality,
            status=realtime.status,
            alarm_level=realtime.alarm_level,
            updated_at=realtime.updated_at
        ) for point, realtime in rows
    ]


@router.post("/control/{point_id}", summary="下发控制指令")
async def send_control_command(
    point_id: int,
    command: ControlCommand,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    向AO/DO点位下发控制指令
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()

    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    if point.point_type not in ["AO", "DO"]:
        raise HTTPException(status_code=400, detail="该点位不支持控制操作")

    if not point.is_enabled:
        raise HTTPException(status_code=400, detail="点位已禁用")

    # 记录操作日志
    from ...models.log import OperationLog
    log = OperationLog(
        user_id=current_user.id,
        username=current_user.username,
        module="realtime",
        action="control",
        target_type="point",
        target_id=point_id,
        target_name=point.point_name,
        new_value=str(command.value),
        remark=command.remark
    )
    db.add(log)

    # 更新实时值（模拟控制）
    await db.execute(
        update(PointRealtime).where(PointRealtime.point_id == point_id).values(
            value=command.value,
            updated_at=datetime.now()
        )
    )
    await db.commit()

    return {
        "message": "控制指令已下发",
        "point_code": point.point_code,
        "value": command.value
    }


# ==================== V2.3 能源仪表盘 ====================

@router.get("/energy-dashboard", summary="获取能源仪表盘数据")
async def get_energy_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取V2.3增强版能源仪表盘数据

    包含：实时能耗、效率指标、需量状态、成本分析、节能建议
    """
    from sqlalchemy import func
    from ...models.energy import (
        PUEHistory, EnergyDaily, MeterPoint, EnergySuggestion, PowerDevice
    )

    # 1. 实时能耗数据
    realtime = {
        "total_power": 0,
        "it_power": 0,
        "cooling_power": 0,
        "other_power": 0,
        "today_energy": 0,
        "month_energy": 0
    }

    # 获取最新PUE记录
    pue_result = await db.execute(
        select(PUEHistory).order_by(PUEHistory.record_time.desc()).limit(1)
    )
    pue_record = pue_result.scalar_one_or_none()
    if pue_record:
        realtime["total_power"] = pue_record.total_power or 0
        realtime["it_power"] = pue_record.it_power or 0
        realtime["cooling_power"] = pue_record.cooling_power or 0
        realtime["other_power"] = pue_record.other_power or 0

    # 获取今日用电量
    today = datetime.now().date()
    today_result = await db.execute(
        select(func.sum(EnergyDaily.total_energy)).where(
            EnergyDaily.date == today
        )
    )
    realtime["today_energy"] = today_result.scalar() or 0

    # 获取本月用电量
    month_start = today.replace(day=1)
    month_result = await db.execute(
        select(func.sum(EnergyDaily.total_energy)).where(
            EnergyDaily.date >= month_start
        )
    )
    realtime["month_energy"] = month_result.scalar() or 0

    # 2. 效率指标
    efficiency = {
        "pue": 1.5,
        "pue_target": 1.4,
        "pue_trend": "stable",
        "cooling_ratio": 0,
        "it_ratio": 0
    }

    if pue_record:
        efficiency["pue"] = round(pue_record.pue, 2)
        if pue_record.total_power > 0:
            efficiency["cooling_ratio"] = round(
                (pue_record.cooling_power or 0) / pue_record.total_power * 100, 1
            )
            efficiency["it_ratio"] = round(
                (pue_record.it_power or 0) / pue_record.total_power * 100, 1
            )

    # PUE趋势（对比昨天）
    yesterday = today - timedelta(days=1)
    yesterday_pue_result = await db.execute(
        select(func.avg(PUEHistory.pue)).where(
            func.date(PUEHistory.record_time) == yesterday
        )
    )
    yesterday_pue = yesterday_pue_result.scalar()
    if yesterday_pue and pue_record:
        if pue_record.pue < yesterday_pue - 0.02:
            efficiency["pue_trend"] = "down"
        elif pue_record.pue > yesterday_pue + 0.02:
            efficiency["pue_trend"] = "up"

    # 3. 需量状态
    demand = {
        "current_demand": 0,
        "declared_demand": 100,
        "utilization_rate": 0,
        "max_today": 0,
        "over_declared_risk": False
    }

    # 获取计量点信息
    meter_result = await db.execute(
        select(MeterPoint).where(MeterPoint.is_enabled == True).limit(1)
    )
    meter = meter_result.scalar_one_or_none()
    if meter:
        demand["declared_demand"] = meter.declared_demand or 100

    # 当前需量（使用总功率）
    if pue_record:
        demand["current_demand"] = pue_record.total_power or 0
        demand["utilization_rate"] = round(
            demand["current_demand"] / demand["declared_demand"] * 100, 1
        ) if demand["declared_demand"] > 0 else 0
        demand["over_declared_risk"] = demand["utilization_rate"] > 90

    # 今日最大需量
    today_max_result = await db.execute(
        select(func.max(PUEHistory.total_power)).where(
            func.date(PUEHistory.record_time) == today
        )
    )
    demand["max_today"] = today_max_result.scalar() or 0

    # 4. 成本分析
    cost = {
        "today_cost": 0,
        "month_cost": 0,
        "peak_ratio": 0,
        "valley_ratio": 0,
        "avg_price": 0.8
    }

    # 简化计算：用电量 * 平均电价
    cost["today_cost"] = round(realtime["today_energy"] * 0.8, 2)
    cost["month_cost"] = round(realtime["month_energy"] * 0.8, 2)

    # 峰谷比例（模拟数据）
    cost["peak_ratio"] = 45
    cost["valley_ratio"] = 25

    # 5. 节能建议汇总
    suggestions = {
        "pending_count": 0,
        "high_priority_count": 0,
        "potential_saving_kwh": 0,
        "potential_saving_cost": 0
    }

    # 统计待处理建议
    pending_result = await db.execute(
        select(func.count(EnergySuggestion.id)).where(
            EnergySuggestion.status == "pending"
        )
    )
    suggestions["pending_count"] = pending_result.scalar() or 0

    # 统计高优先级建议
    high_result = await db.execute(
        select(func.count(EnergySuggestion.id)).where(
            EnergySuggestion.status == "pending",
            EnergySuggestion.priority.in_(["high", "urgent"])
        )
    )
    suggestions["high_priority_count"] = high_result.scalar() or 0

    # 统计潜在节能量
    saving_result = await db.execute(
        select(
            func.sum(EnergySuggestion.potential_saving),
            func.sum(EnergySuggestion.potential_cost_saving)
        ).where(EnergySuggestion.status == "pending")
    )
    saving_row = saving_result.first()
    if saving_row:
        suggestions["potential_saving_kwh"] = saving_row[0] or 0
        suggestions["potential_saving_cost"] = saving_row[1] or 0

    # 6. 趋势数据 (用于迷你图表)
    trends = {
        "power_1h": [],
        "pue_24h": [],
        "demand_24h": []
    }

    # 获取近1小时功率趋势
    one_hour_ago = datetime.now() - timedelta(hours=1)
    try:
        power_trend_result = await db.execute(
            select(PUEHistory.total_power, PUEHistory.record_time)
            .where(PUEHistory.record_time >= one_hour_ago)
            .order_by(PUEHistory.record_time)
        )
        power_trend_rows = power_trend_result.all()
        trends["power_1h"] = [row[0] or 0 for row in power_trend_rows]
    except Exception:
        pass

    # 获取近24小时PUE趋势 (简化版本，不使用date_trunc)
    one_day_ago = datetime.now() - timedelta(hours=24)
    try:
        pue_trend_result = await db.execute(
            select(PUEHistory.pue, PUEHistory.record_time)
            .where(PUEHistory.record_time >= one_day_ago)
            .order_by(PUEHistory.record_time)
        )
        pue_trend_rows = pue_trend_result.all()
        # 取最后24个点作为趋势
        pue_values = [round(row[0], 2) if row[0] else 0 for row in pue_trend_rows]
        trends["pue_24h"] = pue_values[-24:] if len(pue_values) > 24 else pue_values
    except Exception:
        pass

    # 获取近24小时需量趋势 (使用功率数据)
    trends["demand_24h"] = trends["power_1h"][-24:] if len(trends["power_1h"]) >= 24 else trends["power_1h"]

    return {
        "realtime": realtime,
        "efficiency": efficiency,
        "demand": demand,
        "cost": cost,
        "suggestions": suggestions,
        "trends": trends,
        "update_time": datetime.now().isoformat()
    }
