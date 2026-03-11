"""
预冷系统 API 路由

Story 29.4: 温度预测 API 端点
提供温度预测、热参数查询、模型验证报告、预冷仪表盘等 4 个端点
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_db, require_role
from ...schemas.precool import (
    PredictRequest,
    PredictResponse,
    ThermalParameterOut,
    ValidationReport,
    DashboardZone,
    DashboardResponse,
)

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
            if error_type in ("numerical_instability", "invalid_parameters", "invalid_q_cool_schedule", "temperature_out_of_bounds"):
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
        count_query = (
            select(func.count(ThermalParameter.id))
            .where(ThermalParameter.cooling_zone_id == zone_id)
        )
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

        items_out = [
            ThermalParameterOut.model_validate(item).model_dump()
            for item in items
        ]

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
        query = (
            select(TemperaturePredictionLog)
            .where(
                and_(
                    TemperaturePredictionLog.cooling_zone_id == zone_id,
                    TemperaturePredictionLog.created_at >= seven_days_ago,
                    TemperaturePredictionLog.actual_temp > 0,
                    TemperaturePredictionLog.deviation.isnot(None),
                )
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
            select(ThermalParameter.cooling_zone_id)
            .where(ThermalParameter.is_active == True)
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
