"""
精度监控服务 — 模型精度验证与自动回退

Story 29.5: 模型精度验证与记录
- 回填实际温度（每 5 分钟）
- 连续误差自动回退到 THM
- 每日精度统计与退化预警
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import async_session
from ...models.thermal import TemperaturePredictionLog, ThermalParameter
from ...models.topology_config import CoolingZoneCabinet, CabinetTemperatureSensor
from ...models.asset import Cabinet
from ...models.point import Point
from ...models.history import PointHistory

logger = logging.getLogger(__name__)

# ==================== 精度验证常量 ====================

# MAE 阈值（与架构 V4.2.0 一致）
MAE_EXCELLENT_1H = 1.0    # 1h 预测 MAE ≤ 1.0°C — 优秀
MAE_ACCEPTABLE_3H = 2.0   # 3h 预测 MAE ≤ 2.0°C — 合格
MAX_DEVIATION_SAFE = 3.0   # 最大偏差 ≤ 3.0°C — 安全

# 自动回退阈值
CONSECUTIVE_ERROR_THRESHOLD = 2.0   # 连续误差阈值 °C
CONSECUTIVE_ERROR_COUNT = 3          # 连续误差次数

# 每日精度退化警告阈值
DAILY_MAE_1H_WARNING = 1.5   # mae_1h > 1.5°C 时警告
DAILY_MAE_3H_WARNING = 3.0   # mae_3h > 3.0°C 时警告

# 回填限制
BACKFILL_BATCH_SIZE = 100         # 每次最多处理 100 条
BACKFILL_TIMEOUT_HOURS = 1        # 超时 1 小时标记为数据不可用
SENTINEL_VALUE = -999.0            # 哨兵值: 数据不可用
TEMP_WINDOW_MINUTES = 2.5         # 查询前后 2.5 分钟窗口


async def backfill_actual_temperatures():
    """回填实际温度（定时任务入口 — 每 5 分钟）

    查询待回填的预测记录，对已到期的记录查询实际温度并回填。
    """
    try:
        async with async_session() as session:
            now = datetime.now()

            # 查询待回填记录（actual_temp IS NULL，按创建时间升序）
            query = (
                select(TemperaturePredictionLog)
                .where(TemperaturePredictionLog.actual_temp.is_(None))
                .order_by(TemperaturePredictionLog.created_at.asc())
                .limit(BACKFILL_BATCH_SIZE)
            )
            result = await session.execute(query)
            pending_logs = result.scalars().all()

            if not pending_logs:
                return

            backfilled_count = 0
            sentinel_count = 0
            # 收集需要检查回退的 zone_ids
            zones_to_check = set()

            for log in pending_logs:
                # 计算预测目标时间
                target_time = log.created_at + timedelta(minutes=log.prediction_horizon_min)

                # 如果预测时间窗口尚未到期，跳过
                if now < target_time:
                    continue

                # 查询实际温度
                actual_temp = await _query_actual_temperature(
                    session, log.cooling_zone_id, target_time
                )

                if actual_temp is not None:
                    # 回填实际温度和偏差
                    log.actual_temp = actual_temp
                    log.deviation = actual_temp - log.predicted_temp
                    backfilled_count += 1
                    zones_to_check.add(log.cooling_zone_id)
                elif (now - target_time).total_seconds() > BACKFILL_TIMEOUT_HOURS * 3600:
                    # 超时 1 小时，标记为数据不可用
                    log.actual_temp = SENTINEL_VALUE
                    log.deviation = None
                    sentinel_count += 1

            await session.commit()

            if backfilled_count > 0 or sentinel_count > 0:
                logger.info(
                    f"精度回填完成: 回填 {backfilled_count} 条, "
                    f"标记不可用 {sentinel_count} 条"
                )

            # 对回填过的 zone 检查连续误差
            for zone_id in zones_to_check:
                await _check_consecutive_errors(session, zone_id)

    except Exception as e:
        logger.error(f"精度回填任务失败: {e}", exc_info=True)


async def _query_actual_temperature(
    session: AsyncSession,
    cooling_zone_id: int,
    target_time: datetime,
) -> float | None:
    """查询指定时间点的实际最大进风温度

    链路: CoolingZoneCabinet(zone_id) → Cabinet → CabinetTemperatureSensor(inlet)
          → Point → PointHistory(recorded_at)
    """
    window_delta = timedelta(minutes=TEMP_WINDOW_MINUTES)
    time_start = target_time - window_delta
    time_end = target_time + window_delta

    query = (
        select(func.max(PointHistory.value))
        .select_from(CoolingZoneCabinet)
        .join(Cabinet, Cabinet.id == CoolingZoneCabinet.cabinet_id)
        .join(CabinetTemperatureSensor, CabinetTemperatureSensor.cabinet_id == Cabinet.id)
        .join(Point, Point.id == CabinetTemperatureSensor.point_id)
        .join(PointHistory, PointHistory.point_id == Point.id)
        .where(
            and_(
                CoolingZoneCabinet.zone_id == cooling_zone_id,
                CabinetTemperatureSensor.sensor_location == "inlet",
                PointHistory.recorded_at >= time_start,
                PointHistory.recorded_at <= time_end,
            )
        )
    )
    result = await session.execute(query)
    return result.scalar()


async def _check_consecutive_errors(session: AsyncSession, zone_id: int):
    """检查该 zone 最近连续 3 条有效记录是否全部误差 > 2°C

    如果是，自动回退到 THM 模式（deactivate thermal_parameters）
    """
    # 查询最近 3 条有效预测记录
    query = (
        select(TemperaturePredictionLog.deviation)
        .where(
            and_(
                TemperaturePredictionLog.cooling_zone_id == zone_id,
                TemperaturePredictionLog.actual_temp > 0,
                TemperaturePredictionLog.deviation.isnot(None),
            )
        )
        .order_by(TemperaturePredictionLog.created_at.desc())
        .limit(CONSECUTIVE_ERROR_COUNT)
    )
    result = await session.execute(query)
    deviations = [row[0] for row in result.all()]

    # 不足 3 条记录，不判定
    if len(deviations) < CONSECUTIVE_ERROR_COUNT:
        return

    # 检查是否全部超过阈值
    all_exceed = all(abs(d) > CONSECUTIVE_ERROR_THRESHOLD for d in deviations)
    if not all_exceed:
        return

    # 检查是否已经没有 active 参数（幂等）
    active_query = (
        select(ThermalParameter)
        .where(
            and_(
                ThermalParameter.cooling_zone_id == zone_id,
                ThermalParameter.is_active == True,
            )
        )
    )
    active_result = await session.execute(active_query)
    active_param = active_result.scalar_one_or_none()

    if active_param is None:
        return  # 已经没有 active 参数，幂等

    # 先删除该 zone 已有的 inactive 记录（避免 UniqueConstraint 冲突）
    await session.execute(
        delete(ThermalParameter).where(
            and_(
                ThermalParameter.cooling_zone_id == zone_id,
                ThermalParameter.is_active == False,
            )
        )
    )

    # 将 active 记录设为 inactive
    active_param.is_active = False
    await session.commit()

    logger.warning(
        f"Zone {zone_id} 连续 {CONSECUTIVE_ERROR_COUNT} 次预测误差 > "
        f"{CONSECUTIVE_ERROR_THRESHOLD}°C，已自动回退到 THM 模式"
    )


async def run_daily_accuracy_report():
    """每日精度统计（定时任务入口 — 每日凌晨 1:00）

    计算过去 24 小时各 zone 的预测 MAE，退化时记录告警日志。
    """
    try:
        async with async_session() as session:
            twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

            # 查询过去 24 小时所有有效的预测记录（排除哨兵值）
            query = (
                select(TemperaturePredictionLog)
                .where(
                    and_(
                        TemperaturePredictionLog.created_at >= twenty_four_hours_ago,
                        TemperaturePredictionLog.actual_temp > 0,
                        TemperaturePredictionLog.deviation.isnot(None),
                    )
                )
            )
            result = await session.execute(query)
            logs = result.scalars().all()

            if not logs:
                logger.info("每日精度统计: 过去 24 小时无有效预测记录")
                return

            # 按 zone 分组统计
            zone_logs: dict[int, list] = {}
            for log in logs:
                zone_logs.setdefault(log.cooling_zone_id, []).append(log)

            for zone_id, zone_records in zone_logs.items():
                deviations_1h = []
                deviations_3h = []

                for log in zone_records:
                    abs_dev = abs(log.deviation)
                    if log.prediction_horizon_min <= 60:
                        deviations_1h.append(abs_dev)
                    if log.prediction_horizon_min <= 180:
                        deviations_3h.append(abs_dev)

                mae_1h = (
                    round(sum(deviations_1h) / len(deviations_1h), 3)
                    if deviations_1h else None
                )
                mae_3h = (
                    round(sum(deviations_3h) / len(deviations_3h), 3)
                    if deviations_3h else None
                )

                # 检查退化
                degraded = False
                if mae_1h is not None and mae_1h > DAILY_MAE_1H_WARNING:
                    degraded = True
                if mae_3h is not None and mae_3h > DAILY_MAE_3H_WARNING:
                    degraded = True

                if degraded:
                    logger.error(
                        f"Zone {zone_id} 精度退化: "
                        f"mae_1h={mae_1h}°C, mae_3h={mae_3h}°C，建议重新校准"
                    )
                else:
                    logger.info(
                        f"Zone {zone_id} 精度正常: "
                        f"mae_1h={mae_1h}°C, mae_3h={mae_3h}°C"
                    )

    except Exception as e:
        logger.error(f"每日精度统计任务失败: {e}", exc_info=True)
