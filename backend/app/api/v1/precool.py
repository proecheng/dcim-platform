"""
预冷系统 API 路由

Story 29.4: 温度预测 API 端点
Story 30.3: 回退保护 API
Story 31.3: 预冷计划 API 端点
Story 31.4: 预冷配置管理端点
Story 32.3: 热参数管理 API（手动校准、校准历史、部署阶段）
Story 33.1: VPP 可调容量查询端点
"""

import json
import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal, Optional

from ...api.deps import get_db, require_role
from ...schemas.precool import (
    PredictRequest,
    PredictResponse,
    ThermalParameterOut,
    ValidationReport,
    DashboardZone,
    DashboardResponse,
    RollbackTriggerInfo,
    RollbackStatusResponse,
    RollbackEventOut,
    RollbackOverviewResponse,
    ScheduleCreateRequest,
    ScheduleListItem,
    ScheduleDetailOut,
    ScheduleAbortRequest,
    ScheduleAbortResponse,
    PrecoolConfigOut,
    PrecoolConfigUpdate,
    DeploymentPhaseUpdate,
)
from ...services.precool.rollback_manager import rollback_manager
from ...models.rollback import RollbackEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/zones/{zone_id}/predict", summary="温度轨迹预测")
async def predict_temperature(
    zone_id: int,
    request: PredictRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """
    预测制冷区域温度变化

    - 如果 RC 参数已校准，使用 TCL 模型预测
    - 如果 RC 参数未校准，自动回退到 THM 兜底
    """
    try:
        from ...services.precool.thermal_model import ThermalModel

        model = ThermalModel()
        result = await model.predict_temperature(
            zone_id=zone_id,
            hours=request.hours,
            q_cool_schedule=request.q_cool_schedule,
        )

        # 如果 ThermalModel 返回 error
        if "error" in result:
            error_type = result["error"]

            # 404: zone 不存在
            if error_type == "zone_not_found":
                return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

            # THM 兜底: RC 参数未校准
            if error_type == "parameters_not_calibrated":
                return await _thm_fallback(zone_id, db)

            # 503: 数据不可用
            if error_type in ("insufficient_data", "sensor_offline", "data_fetch_failed", "insufficient_history"):
                return {"code": 503, "message": f"数据不可用: {result.get('details', error_type)}", "data": None}

            # 422: 参数/计算错误
            if error_type in (
                "numerical_instability",
                "invalid_parameters",
                "invalid_q_cool_schedule",
                "temperature_out_of_bounds",
            ):
                return {"code": 422, "message": f"参数错误: {result.get('details', error_type)}", "data": None}

            # 500: 其他错误
            return {"code": 500, "message": f"预测失败: {error_type}", "data": None}

        # 成功
        return {
            "code": 200,
            "message": "success",
            "data": PredictResponse(
                zone_id=result["zone_id"],
                predicted_temp=result["predicted_temp"],
                prediction_horizon_min=result["prediction_horizon_min"],
                temperature_trajectory=result["temperature_trajectory"],
                time_steps=result["time_steps"],
                model_version=result["model_version"],
                data_quality=result.get("data_quality"),
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"温度预测异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


async def _thm_fallback(zone_id: int, db: AsyncSession) -> dict:
    """THM 兜底: RC 参数未校准时使用温度裕度法"""
    try:
        from ...services.datacenter_shift_strategy import calculate_shiftable_power_for_zone

        thm_result = await calculate_shiftable_power_for_zone(zone_id, db)

        if "error" in thm_result:
            return {
                "code": 503,
                "message": f"THM 兜底失败: {thm_result.get('details', thm_result['error'])}",
                "data": None,
            }

        t_current_max = thm_result.get("T_current_max", 25.0)

        return {
            "code": 200,
            "message": "success",
            "data": PredictResponse(
                zone_id=zone_id,
                predicted_temp=t_current_max,
                prediction_horizon_min=60,
                temperature_trajectory=[],
                time_steps=[],
                model_version="THM-fallback",
                data_quality=None,
                thm_result=thm_result,
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"THM 兜底异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "THM 兜底异常", "data": None}


@router.get("/zones/{zone_id}/parameters", summary="查询 R/C 标定参数历史")
async def get_thermal_parameters(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """返回指定制冷区域的热参数标定历史"""
    try:
        from ...models.thermal import ThermalParameter

        # 查询总数
        count_query = select(func.count(ThermalParameter.id)).where(ThermalParameter.cooling_zone_id == zone_id)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 查询分页数据
        data_query = (
            select(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone_id)
            .order_by(ThermalParameter.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(data_query)
        items = result.scalars().all()

        items_out = [ThermalParameterOut.model_validate(item).model_dump() for item in items]

        return {
            "code": 200,
            "message": "success",
            "data": {"items": items_out, "total": total},
        }

    except Exception as e:
        logger.error(f"查询热参数异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/zones/{zone_id}/validation", summary="模型验证报告")
async def get_validation_report(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """返回模型验证报告（最近 7 天）"""
    try:
        from ...models.thermal import TemperaturePredictionLog

        seven_days_ago = datetime.now() - timedelta(days=7)

        # 查询最近 7 天已回填的有效预测记录
        # 排除哨兵值 -999.0（数据不可用），仅使用 deviation IS NOT NULL 的记录
        query = select(TemperaturePredictionLog).where(
            and_(
                TemperaturePredictionLog.cooling_zone_id == zone_id,
                TemperaturePredictionLog.created_at >= seven_days_ago,
                TemperaturePredictionLog.actual_temp > 0,
                TemperaturePredictionLog.deviation.isnot(None),
            )
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        if not logs:
            return {
                "code": 200,
                "message": "success",
                "data": ValidationReport(
                    zone_id=zone_id,
                    mae_1h=None,
                    mae_3h=None,
                    max_deviation=None,
                    sample_count=0,
                ).model_dump(),
            }

        # 计算 MAE（使用存储的 deviation 字段）
        deviations_1h = []
        deviations_3h = []
        all_deviations = []

        for log in logs:
            dev = abs(log.deviation)
            all_deviations.append(dev)

            if log.prediction_horizon_min <= 60:
                deviations_1h.append(dev)
            if log.prediction_horizon_min <= 180:
                deviations_3h.append(dev)

        mae_1h = sum(deviations_1h) / len(deviations_1h) if deviations_1h else None
        mae_3h = sum(deviations_3h) / len(deviations_3h) if deviations_3h else None
        max_deviation = max(all_deviations) if all_deviations else None

        return {
            "code": 200,
            "message": "success",
            "data": ValidationReport(
                zone_id=zone_id,
                mae_1h=round(mae_1h, 3) if mae_1h is not None else None,
                mae_3h=round(mae_3h, 3) if mae_3h is not None else None,
                max_deviation=round(max_deviation, 3) if max_deviation is not None else None,
                sample_count=len(logs),
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"查询验证报告异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/dashboard", summary="预冷仪表盘聚合数据")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """返回预冷仪表盘聚合数据"""
    try:
        from ...models.topology_config import (
            CoolingZone,
            CoolingZoneCabinet,
            CabinetTemperatureSensor,
        )
        from ...models.thermal import ThermalParameter
        from ...models.asset import Cabinet
        from ...models.point import Point
        from ...models.history import PointHistory
        from ...services.datacenter_shift_strategy import calculate_shiftable_power_for_zone

        # 1. 查询所有 CoolingZone
        zones_result = await db.execute(select(CoolingZone))
        zones = zones_result.scalars().all()

        # 2. 批量查询所有 zone 的 active thermal_parameters
        active_params_result = await db.execute(
            select(ThermalParameter.cooling_zone_id).where(ThermalParameter.is_active == True)
        )
        calibrated_zone_ids = set(row[0] for row in active_params_result.all())

        # 3. 查询最近 5 分钟的温度数据（批量）
        now = datetime.now()
        five_min_ago = now - timedelta(minutes=5)

        temp_query = (
            select(
                CoolingZoneCabinet.zone_id,
                func.max(PointHistory.value).label("max_temp"),
            )
            .join(Cabinet, Cabinet.id == CoolingZoneCabinet.cabinet_id)
            .join(CabinetTemperatureSensor, CabinetTemperatureSensor.cabinet_id == Cabinet.id)
            .join(Point, Point.id == CabinetTemperatureSensor.point_id)
            .join(PointHistory, PointHistory.point_id == Point.id)
            .where(
                and_(
                    CabinetTemperatureSensor.sensor_location == "inlet",
                    PointHistory.recorded_at >= five_min_ago,
                )
            )
            .group_by(CoolingZoneCabinet.zone_id)
        )
        temp_result = await db.execute(temp_query)
        zone_temps = {row[0]: row[1] for row in temp_result.all()}

        # 4. 逐个 zone 计算 shiftable_ratio
        dashboard_zones = []
        thm_count = 0
        tcl_count = 0
        offline_count = 0

        for zone in zones:
            current_temp = zone_temps.get(zone.id)
            is_calibrated = zone.id in calibrated_zone_ids
            model_mode = "TCL" if is_calibrated else "THM"

            if is_calibrated:
                tcl_count += 1
            else:
                thm_count += 1

            if current_temp is None:
                offline_count += 1
                headroom = None
            else:
                headroom = round(27.0 - current_temp, 2)

            # 计算 shiftable_ratio
            shiftable_ratio = None
            try:
                shift_result = await calculate_shiftable_power_for_zone(zone.id, db)
                if "error" not in shift_result:
                    shiftable_ratio = shift_result.get("shiftable_ratio")
            except Exception as e:
                logger.warning(f"Zone {zone.id} shiftable_ratio 计算失败: {e}")

            dashboard_zones.append(
                DashboardZone(
                    zone_id=zone.id,
                    zone_name=zone.zone_name,
                    current_temp=round(current_temp, 2) if current_temp is not None else None,
                    headroom=headroom,
                    model_mode=model_mode,
                    shiftable_ratio=round(shiftable_ratio, 3) if shiftable_ratio is not None else None,
                ).model_dump()
            )

        status_summary = {
            "total_zones": len(zones),
            "thm_zones": thm_count,
            "tcl_zones": tcl_count,
            "offline_zones": offline_count,
        }

        return {
            "code": 200,
            "message": "success",
            "data": DashboardResponse(
                zones=dashboard_zones,
                status_summary=status_summary,
                today_savings=0.0,
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"查询仪表盘异常: {e}")
        return {"code": 500, "message": "内部错误", "data": None}


# ==================== Story 30.3: 回退保护 API ====================


@router.get("/zones/{zone_id}/rollback-status", summary="查询 zone 回退保护状态")
async def get_rollback_status(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回指定 zone 的实时回退保护状态"""
    try:
        from ...models.topology_config import CoolingZone

        # 校验 zone_id 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()

        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        status = rollback_manager.get_zone_rollback_status(zone_id)

        return {
            "code": 200,
            "message": "success",
            "data": RollbackStatusResponse(
                zone_id=status["zone_id"],
                has_active_rollback=status["has_active_rollback"],
                active_triggers=[RollbackTriggerInfo(**t) for t in status["active_triggers"]],
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"查询回退状态异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/zones/{zone_id}/rollback-history", summary="查询回退历史事件")
async def get_rollback_history(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[Literal["active", "resolved"]] = Query(
        default=None, description="筛选: active/resolved，不传返回全部"
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """查询指定 zone 的历史回退事件，支持分页和 status 筛选"""
    try:
        from ...models.topology_config import CoolingZone

        # 校验 zone_id 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()

        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 构建查询
        query = select(RollbackEvent).where(RollbackEvent.zone_id == zone_id)

        if status is not None:
            query = query.where(RollbackEvent.status == status)

        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页查询
        query = query.order_by(RollbackEvent.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        items_out = [RollbackEventOut.model_validate(item).model_dump() for item in items]

        return {
            "code": 200,
            "message": "success",
            "data": {"items": items_out, "total": total},
        }

    except Exception as e:
        logger.error(f"查询回退历史异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/rollback-overview", summary="全局回退状态概览")
async def get_rollback_overview(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回所有 zone 的回退状态汇总"""
    try:
        from ...models.topology_config import CoolingZone

        # 查询所有 CoolingZone
        zones_result = await db.execute(select(CoolingZone.id))
        zone_ids = zones_result.scalars().all()
        total_zones = len(zone_ids)

        # 逐个查询回退状态（从内存）
        zone_statuses = []
        zones_with_active = 0
        total_triggers = 0
        trigger_counts: dict = {}

        for zid in zone_ids:
            status = rollback_manager.get_zone_rollback_status(zid)
            zone_statuses.append(
                RollbackStatusResponse(
                    zone_id=status["zone_id"],
                    has_active_rollback=status["has_active_rollback"],
                    active_triggers=[RollbackTriggerInfo(**t) for t in status["active_triggers"]],
                )
            )

            if status["has_active_rollback"]:
                zones_with_active += 1
                for t in status["active_triggers"]:
                    total_triggers += 1
                    tt = t["trigger_type"]
                    trigger_counts[tt] = trigger_counts.get(tt, 0) + 1

        # 查询最近 24h 事件数
        now = datetime.now()
        day_ago = now - timedelta(hours=24)
        recent_count = (
            await db.execute(select(func.count(RollbackEvent.id)).where(RollbackEvent.created_at >= day_ago))
        ).scalar() or 0

        return {
            "code": 200,
            "message": "success",
            "data": RollbackOverviewResponse(
                total_zones=total_zones,
                zones_with_active_rollback=zones_with_active,
                total_active_triggers=total_triggers,
                trigger_type_counts=trigger_counts,
                recent_events_24h=recent_count,
                zone_statuses=[s.model_dump() for s in zone_statuses],
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"查询回退概览异常: {e}")
        return {"code": 500, "message": "内部错误", "data": None}


# ==================== Story 31.3: 预冷计划 API ====================


def _schedule_to_list_item(plan) -> dict:
    """将 PrecoolSchedule ORM 转为 ScheduleListItem dict"""
    return ScheduleListItem(
        id=plan.id,
        cooling_zone_id=plan.cooling_zone_id,
        schedule_date=str(plan.schedule_date),
        precool_start_time=str(plan.precool_start_time),
        precool_end_time=str(plan.precool_end_time),
        target_temp=plan.target_temp,
        peak_start_time=str(plan.peak_start_time),
        peak_end_time=str(plan.peak_end_time),
        planned_savings_kwh=plan.planned_savings_kwh,
        actual_savings_kwh=plan.actual_savings_kwh,
        status=plan.status,
        abort_reason=plan.abort_reason,
        is_validated=plan.is_validated or False,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    ).model_dump()


def _schedule_to_detail(plan) -> dict:
    """将 PrecoolSchedule ORM 转为 ScheduleDetailOut dict"""
    return ScheduleDetailOut(
        id=plan.id,
        cooling_zone_id=plan.cooling_zone_id,
        schedule_date=str(plan.schedule_date),
        precool_start_time=str(plan.precool_start_time),
        precool_end_time=str(plan.precool_end_time),
        target_temp=plan.target_temp,
        peak_start_time=str(plan.peak_start_time),
        peak_end_time=str(plan.peak_end_time),
        planned_savings_kwh=plan.planned_savings_kwh,
        actual_savings_kwh=plan.actual_savings_kwh,
        status=plan.status,
        abort_reason=plan.abort_reason,
        temperature_trajectory=plan.temperature_trajectory,
        is_validated=plan.is_validated or False,
        validated_at=plan.validated_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    ).model_dump()


@router.post("/zones/{zone_id}/schedule", summary="生成预冷计划")
async def create_schedule(
    zone_id: int,
    request: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """生成日前预冷计划（调用贪心优化算法）"""
    try:
        from ...models.topology_config import CoolingZone
        from ...services.precool.scheduler import (
            PrecoolScheduler,
            PrecoolPlanError,
            load_time_slots_from_db,
        )

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 解析日期
        if request.schedule_date:
            try:
                schedule_date = date.fromisoformat(request.schedule_date)
            except ValueError:
                return {"code": 422, "message": "日期格式错误，需 YYYY-MM-DD", "data": None}
        else:
            schedule_date = date.today() + timedelta(days=1)

        # 加载电价时段
        time_slots = await load_time_slots_from_db(db)

        # 生成计划
        try:
            scheduler = PrecoolScheduler()
            result = await scheduler.generate_precool_plan(
                zone_id=zone_id,
                schedule_date=schedule_date,
                session=db,
                time_slots=time_slots,
            )
        except PrecoolPlanError as e:
            return {
                "code": 422,
                "message": e.reason,
                "data": {
                    "error": e.error,
                    "reason": e.reason,
                    "suggestions": e.suggestions,
                },
            }

        if result.schedule is None:
            return {"code": 422, "message": "计划生成失败", "data": None}

        # 保存到数据库（API 层控制事务）
        plan = result.schedule
        db.add(plan)
        try:
            await db.commit()
            await db.refresh(plan)
        except IntegrityError:
            await db.rollback()
            return {
                "code": 409,
                "message": f"zone {zone_id} 日期 {schedule_date} 已有预冷计划",
                "data": None,
            }

        logger.info(
            "预冷计划已创建: zone=%d, date=%s, saving=%.2f kWh",
            zone_id,
            schedule_date,
            plan.planned_savings_kwh or 0,
        )

        return {"code": 200, "message": "success", "data": _schedule_to_detail(plan)}

    except Exception as e:
        logger.error(f"创建预冷计划异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/zones/{zone_id}/schedule", summary="查询预冷计划列表")
async def list_schedules(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[Literal["pending", "executing", "completed", "aborted"]] = Query(
        default=None, description="状态筛选"
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """查询指定 zone 的预冷计划列表（不含 trajectory）"""
    try:
        from ...models.topology_config import CoolingZone
        from ...models.thermal import PrecoolSchedule

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 构建查询
        query = select(PrecoolSchedule).where(PrecoolSchedule.cooling_zone_id == zone_id)
        if status is not None:
            query = query.where(PrecoolSchedule.status == status)

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页
        query = query.order_by(PrecoolSchedule.schedule_date.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        items_out = [_schedule_to_list_item(item) for item in items]

        return {
            "code": 200,
            "message": "success",
            "data": {"items": items_out, "total": total},
        }

    except Exception as e:
        logger.error(f"查询预冷计划列表异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/schedules/{schedule_id}", summary="查询预冷计划详情")
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """查询单个预冷计划详情（含完整 trajectory）"""
    try:
        from ...models.thermal import PrecoolSchedule

        plan = (await db.execute(select(PrecoolSchedule).where(PrecoolSchedule.id == schedule_id))).scalar_one_or_none()

        if plan is None:
            return {"code": 404, "message": f"预冷计划 {schedule_id} 不存在", "data": None}

        return {"code": 200, "message": "success", "data": _schedule_to_detail(plan)}

    except Exception as e:
        logger.error(f"查询预冷计划详情异常: schedule_id={schedule_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.post("/schedules/{schedule_id}/abort", summary="中止预冷计划")
async def abort_schedule(
    schedule_id: int,
    request: ScheduleAbortRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """中止执行中的预冷计划"""
    try:
        from ...models.thermal import PrecoolSchedule
        from ...services.precool.executor import precool_executor

        plan = (await db.execute(select(PrecoolSchedule).where(PrecoolSchedule.id == schedule_id))).scalar_one_or_none()

        if plan is None:
            return {"code": 404, "message": f"预冷计划 {schedule_id} 不存在", "data": None}

        if plan.status != "executing":
            return {
                "code": 400,
                "message": f"计划状态为 {plan.status}，只能中止 executing 状态的计划",
                "data": None,
            }

        reason = request.reason or "manual_abort"
        await precool_executor.abort_plan_by_api(plan, reason, db)
        await db.commit()

        return {
            "code": 200,
            "message": "success",
            "data": ScheduleAbortResponse(
                status=plan.status,
                abort_reason=plan.abort_reason,
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"中止预冷计划异常: schedule_id={schedule_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


# ==================== Story 31.4: 预冷配置管理 API ====================


@router.get("/zones/{zone_id}/config", summary="查询预冷配置")
async def get_precool_config(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """查询指定 zone 的预冷配置（precool_enabled, precool_target_temp）"""
    try:
        from ...models.topology_config import CoolingZone
        from ...models.load_shift import CoolingLinkageConfig

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 查询配置
        config = (
            await db.execute(select(CoolingLinkageConfig).where(CoolingLinkageConfig.cooling_zone_id == zone_id))
        ).scalar_one_or_none()

        if config is None:
            # 返回默认值
            return {
                "code": 200,
                "message": "success",
                "data": PrecoolConfigOut(
                    zone_id=zone_id,
                    precool_enabled=False,
                    precool_target_temp=18.0,
                ).model_dump(),
            }

        return {
            "code": 200,
            "message": "success",
            "data": PrecoolConfigOut(
                zone_id=zone_id,
                precool_enabled=config.precool_enabled or False,
                precool_target_temp=config.precool_target_temp or 18.0,
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"查询预冷配置异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.put("/zones/{zone_id}/config", summary="更新预冷配置")
async def update_precool_config(
    zone_id: int,
    request: PrecoolConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """更新指定 zone 的预冷配置（admin only）"""
    try:
        from ...models.topology_config import CoolingZone
        from ...models.load_shift import CoolingLinkageConfig
        from ...models.log import OperationLog

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 查询或创建配置
        config = (
            await db.execute(select(CoolingLinkageConfig).where(CoolingLinkageConfig.cooling_zone_id == zone_id))
        ).scalar_one_or_none()

        is_new = config is None
        if is_new:
            config = CoolingLinkageConfig(cooling_zone_id=zone_id)
            db.add(config)
            await db.flush()

        # 记录旧值
        old_values = {
            "precool_enabled": config.precool_enabled or False,
            "precool_target_temp": config.precool_target_temp or 18.0,
        }

        # 更新字段
        if request.precool_enabled is not None:
            config.precool_enabled = request.precool_enabled
        if request.precool_target_temp is not None:
            config.precool_target_temp = request.precool_target_temp

        new_values = {
            "precool_enabled": config.precool_enabled or False,
            "precool_target_temp": config.precool_target_temp or 18.0,
        }

        # 审计日志
        log = OperationLog(
            user_id=current_user.id,
            username=current_user.username,
            module="precool",
            action="create" if is_new else "update",
            target_type="cooling_linkage_config",
            target_id=config.id,
            target_name=f"zone_{zone_id}_precool_config",
            old_value=json.dumps(old_values),
            new_value=json.dumps(new_values),
        )
        db.add(log)

        await db.commit()

        logger.info(
            "预冷配置已更新: zone=%d, enabled=%s, target_temp=%.1f",
            zone_id,
            config.precool_enabled,
            config.precool_target_temp or 18.0,
        )

        return {
            "code": 200,
            "message": "success",
            "data": PrecoolConfigOut(
                zone_id=zone_id,
                precool_enabled=config.precool_enabled or False,
                precool_target_temp=config.precool_target_temp or 18.0,
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"更新预冷配置异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


# ==================== Story 32.3: 热参数管理 API ====================


@router.post("/zones/{zone_id}/calibrate", summary="触发手动 RC 校准")
async def trigger_calibration(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """手动触发指定区域的 RC 参数校准"""
    try:
        from ...models.topology_config import CoolingZone

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 调用校准服务（self-managing session）
        from ...services.precool.calibrator import rc_calibrator

        result = await rc_calibrator.calibrate(zone_id)

        if "error" in result:
            error = result["error"]
            if error == "scipy_not_installed":
                return {"code": 503, "message": "scipy 未安装，校准功能不可用", "data": None}
            return {"code": 422, "message": f"校准失败: {error}", "data": result}

        return {"code": 200, "message": "success", "data": result}

    except Exception as e:
        logger.error(f"手动校准异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/zones/{zone_id}/calibration-history", summary="查询校准历史")
async def get_calibration_history(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回指定区域的校准历史记录（仅非 demo 记录）"""
    try:
        from ...models.topology_config import CoolingZone
        from ...models.thermal import ThermalParameter

        # 校验 zone 存在
        zone = (await db.execute(select(CoolingZone).where(CoolingZone.id == zone_id))).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 查询总数
        total_result = await db.execute(
            select(func.count())
            .select_from(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone_id)
            .where(ThermalParameter.is_demo == False)  # noqa: E712
        )
        total = total_result.scalar() or 0

        # 分页查询
        result = await db.execute(
            select(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone_id)
            .where(ThermalParameter.is_demo == False)  # noqa: E712
            .order_by(ThermalParameter.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        records = result.scalars().all()

        items = [ThermalParameterOut.model_validate(r).model_dump() for r in records]

        return {
            "code": 200,
            "message": "success",
            "data": {"total": total, "items": items},
        }

    except Exception as e:
        logger.error(f"查询校准历史异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.get("/deployment-phase", summary="查询当前部署阶段")
async def get_deployment_phase(
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回当前预冷功能部署阶段"""
    try:
        from ...services.precool.deployment_phase import deployment_phase_service

        result = await deployment_phase_service.get_current_phase()
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询部署阶段异常: {e}")
        return {"code": 500, "message": "内部错误", "data": None}


@router.put("/deployment-phase", summary="切换部署阶段")
async def update_deployment_phase(
    request: DeploymentPhaseUpdate,
    current_user=Depends(require_role(["admin"])),
):
    """切换预冷功能部署阶段（仅 admin）"""
    try:
        from ...services.precool.deployment_phase import deployment_phase_service

        result = await deployment_phase_service.update_phase(
            new_phase=request.phase,
            force=request.force,
            user_id=current_user.id,
            username=current_user.username,
        )
        if "error" in result:
            if result["error"] == "precondition_failed":
                return {"code": 422, "message": "前置条件不满足", "data": result}
            return {"code": 400, "message": result.get("details", result["error"]), "data": result}
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"切换部署阶段异常: {e}")
        return {"code": 500, "message": "内部错误", "data": None}


# ==================== Story 33.1: VPP 可调容量查询 ====================


@router.get("/vpp/capacity", summary="查询 VPP 可调容量")
async def get_vpp_capacity(
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """
    查询各区域聚合的分向可调容量（仅部署阶段 4 可用）

    - down_adjustable_kw: 向下可调电功率（削峰）
    - up_adjustable_kw: 向上可调电功率（填谷）
    """
    try:
        # 1. 检查部署阶段
        from ...services.precool.deployment_phase import deployment_phase_service

        phase_info = await deployment_phase_service.get_current_phase()
        if phase_info["current_phase"] != 4:
            return {"code": 403, "message": "VPP 接口仅在部署阶段 4 可用", "data": None}
    except Exception as e:
        logger.error(f"VPP 容量查询 - 部署阶段检查失败: {e}", exc_info=True)
        return {"code": 500, "message": f"部署阶段检查失败: {e}", "data": None}

    try:
        from ...services.precool.vpp_capacity import vpp_capacity_service

        # 2. 尝试读取 Redis 缓存
        cached = await vpp_capacity_service.get_cached_capacity()
        if cached is not None:
            return {"code": 200, "message": "success", "data": cached}

        # 3. 缓存未命中，实时计算
        result = await vpp_capacity_service.calculate_capacity()
        return {"code": 200, "message": "success", "data": result}

    except Exception as e:
        logger.error(f"VPP 容量查询失败: {e}", exc_info=True)
        return {"code": 500, "message": f"VPP 容量查询失败: {e}", "data": None}


# ==================== Story 33.2: VPP 调控指令接收 ====================


async def verify_vpp_api_key(x_vpp_api_key: str = Header(None)):
    """VPP 独立 API Key 认证（与 JWT 分离）"""
    from ...core.config import get_settings

    settings = get_settings()
    if not x_vpp_api_key or x_vpp_api_key != settings.VPP_API_KEY:
        return None
    return x_vpp_api_key


@router.post("/vpp/dispatch", summary="接收 VPP 调控指令")
async def receive_vpp_dispatch(
    request: dict,
    api_key: str = Depends(verify_vpp_api_key),
):
    """
    接收 VPP 平台下发的负荷调控指令（仅部署阶段 4 可用）

    - command_type: down_adjust（削峰）/ up_adjust（填谷）
    - target_power_kw: 目标调控功率 (kW_e)
    - duration_minutes: 持续时间（分钟）
    - priority: 优先级（1=普通, 2=紧急）

    认证方式: X-VPP-API-Key header（与 JWT 分离）
    """
    # 1. API Key 认证
    if api_key is None:
        return {"code": 401, "message": "VPP 认证失败", "data": None}

    # 2. 请求格式校验
    command_type = request.get("command_type")
    if command_type not in ("down_adjust", "up_adjust"):
        return {
            "code": 400,
            "message": "command_type 必须为 down_adjust 或 up_adjust",
            "data": None,
        }
    for field in ("target_power_kw", "duration_minutes"):
        if field not in request:
            return {
                "code": 400,
                "message": f"缺少必填字段: {field}",
                "data": None,
            }

    # 3. 部署阶段检查
    try:
        from ...services.precool.deployment_phase import deployment_phase_service

        phase_info = await deployment_phase_service.get_current_phase()
        if phase_info["current_phase"] != 4:
            return {
                "code": 403,
                "message": "VPP 接口仅在部署阶段 4 可用",
                "data": None,
            }
    except Exception as e:
        logger.error(f"VPP 调控 - 部署阶段检查失败: {e}", exc_info=True)
        return {"code": 500, "message": f"部署阶段检查失败: {e}", "data": None}

    # 4. 速率限制
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service

        rate_ok = await vpp_dispatch_service.check_rate_limit()
        if not rate_ok:
            return {
                "code": 429,
                "message": "超出速率限制（每小时最多 12 条）",
                "data": None,
            }
    except Exception as e:
        logger.error(f"VPP 调控 - 速率限制检查失败: {e}", exc_info=True)
        # 速率限制失败不阻塞

    # 5. 调用 dispatch 服务
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service

        result = await vpp_dispatch_service.validate_and_execute(request)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"VPP 调控指令处理失败: {e}", exc_info=True)
        return {"code": 500, "message": f"VPP 调控指令处理失败: {e}", "data": None}


# ==================== VPP 监控查询端点 (Story 33.3) ====================


@router.get("/vpp/dispatches", summary="查询 VPP 调控指令列表")
async def list_vpp_dispatches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    _=Depends(require_role(["admin", "operator"])),
):
    """
    查询 VPP 调控指令历史（JWT 认证，admin/operator 可访问）

    - **page**: 页码（默认 1）
    - **page_size**: 每页条数（默认 20，最大 100）
    - **status**: 可选状态过滤（accepted/rejected/received）
    """
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service

        result = await vpp_dispatch_service.list_dispatches(page, page_size, status)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询 VPP 调控指令列表失败: {e}", exc_info=True)
        return {"code": 500, "message": f"查询失败: {e}", "data": None}


@router.get("/vpp/statistics", summary="查询 VPP 需求响应统计")
async def get_vpp_statistics(
    _=Depends(require_role(["admin", "operator"])),
):
    """查询 VPP 需求响应统计（日/月汇总，JWT 认证）"""
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service

        result = await vpp_dispatch_service.get_statistics()
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询 VPP 统计失败: {e}", exc_info=True)
        return {"code": 500, "message": f"查询失败: {e}", "data": None}
