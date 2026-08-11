"""
传感器数据漂移检测服务
Story 9-7: 传感器数据漂移检测
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.drift import DriftDetectionResult
from ..models.point import Point, PointRealtime
from ..models.history import PointHistory

logger = logging.getLogger(__name__)

# 最小样本数（48 小时 / 5 秒采集 ≈ 34560，但存储周期 60 秒 ≈ 2880）
MIN_SAMPLES = 100
# 3σ 阈值
DRIFT_THRESHOLD_SIGMA = 3.0
# 恢复阈值（低于此值认为恢复正常）
RESOLVE_THRESHOLD_SIGMA = 2.0
# 历史数据窗口（小时）
HISTORY_WINDOW_HOURS = 48


def _generate_diagnosis(deviation_sigma: float, cross_result: Optional[str]) -> str:
    """根据偏差和交叉验证结果生成诊断建议"""
    sigma_str = f"{deviation_sigma:.1f}"
    if deviation_sigma > 5.0:
        return f"该点位读数严重偏离（{sigma_str}σ），数据可信度极低。建议立即现场检查。"
    if cross_result == "fail":
        return f"该点位读数持续偏离（{sigma_str}σ），同区域交叉验证失败。建议现场校验或更换传感器。"
    if cross_result == "pass":
        return f"该点位读数偏离历史均值 {sigma_str}σ，但同区域传感器正常。建议观察 24 小时。"
    # skipped（无法交叉验证）
    return f"该点位读数偏离历史均值 {sigma_str}σ，同区域无可比较传感器。建议现场校验。"


async def run_drift_detection(db: AsyncSession, allowed_point_ids=None) -> dict:
    """
    执行漂移检测。返回检测统计。
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=HISTORY_WINDOW_HOURS)

    # Step 1: 获取所有启用的 AI 类型点位
    point_query = select(Point).where(
        Point.point_type.in_(["AI", "measurement"]),
        Point.is_enabled == True,  # noqa: E712
    )
    if allowed_point_ids is not None:
        point_query = point_query.where(Point.id.in_(allowed_point_ids))
    point_result = await db.execute(point_query)
    points = point_result.scalars().all()

    total_checked = 0
    skipped = 0
    new_suspected = 0
    new_confirmed = 0
    auto_resolved = 0

    for point in points:
        # Step 2: 查询最近 48 小时历史数据
        hist_result = await db.execute(
            select(PointHistory.value).where(
                PointHistory.point_id == point.id,
                PointHistory.recorded_at >= cutoff,
            )
        )
        values = [row[0] for row in hist_result.all() if row[0] is not None]

        if len(values) < MIN_SAMPLES:
            skipped += 1
            continue

        total_checked += 1

        # Step 3: 计算均值和标准差
        mean_val = statistics.mean(values)
        try:
            std_val = statistics.stdev(values)
        except statistics.StatisticsError:
            std_val = 0.0

        # Step 4: 获取当前值
        rt_result = await db.execute(select(PointRealtime).where(PointRealtime.point_id == point.id))
        realtime = rt_result.scalar_one_or_none()
        if not realtime or realtime.value is None:
            skipped += 1
            continue

        current_val = float(realtime.value)

        # Step 5: 计算偏差 σ 倍数（处理 std=0 的情况）
        if std_val == 0:
            deviation = 0.0 if current_val == mean_val else 999.0
        else:
            deviation = abs(current_val - mean_val) / std_val

        # 检查是否有未解除的漂移记录
        existing_result = await db.execute(
            select(DriftDetectionResult).where(
                DriftDetectionResult.point_id == point.id,
                DriftDetectionResult.status.in_(["suspected", "confirmed"]),
            )
        )
        existing = existing_result.scalar_one_or_none()

        if deviation <= RESOLVE_THRESHOLD_SIGMA:
            # Step 8: 恢复正常 → 解除漂移标记
            if existing:
                existing.status = "resolved"
                existing.resolved_at = now
                existing.current_value = current_val
                existing.deviation_sigma = deviation
                # 恢复 PointRealtime.quality
                realtime.quality = 0
                auto_resolved += 1
            continue

        if deviation <= DRIFT_THRESHOLD_SIGMA:
            # 在 2σ ~ 3σ 之间，不触发新漂移，但也不解除
            continue

        # Step 6-7: 超过 3σ → 执行交叉验证
        cross_result = await _cross_validate(
            db,
            point.id,
            point.area_code,
            point.device_type,
            mean_val,
            std_val,
            allowed_point_ids=allowed_point_ids,
        )

        if cross_result == "fail":
            status = "confirmed"
            quality = 2  # 不可靠
            new_confirmed += 1
        else:
            status = "suspected"
            quality = 1  # 不确定
            new_suspected += 1

        diagnosis = _generate_diagnosis(deviation, cross_result)

        if existing:
            # 更新已有记录
            existing.status = status
            existing.mean_value = mean_val
            existing.std_value = std_val
            existing.current_value = current_val
            existing.deviation_sigma = deviation
            existing.cross_validation_result = cross_result
            existing.diagnosis = diagnosis
            existing.detected_at = now
        else:
            # 创建新记录
            new_record = DriftDetectionResult(
                point_id=point.id,
                point_code=point.point_code,
                point_name=point.point_name,
                area_code=point.area_code,
                status=status,
                mean_value=mean_val,
                std_value=std_val,
                current_value=current_val,
                deviation_sigma=deviation,
                cross_validation_result=cross_result,
                diagnosis=diagnosis,
                detected_at=now,
            )
            db.add(new_record)

        # 更新 PointRealtime.quality
        realtime.quality = quality

    await db.commit()

    logger.info(
        f"漂移检测完成: checked={total_checked}, suspected={new_suspected}, "
        f"confirmed={new_confirmed}, resolved={auto_resolved}, skipped={skipped}"
    )

    return {
        "total_checked": total_checked,
        "new_suspected": new_suspected,
        "new_confirmed": new_confirmed,
        "auto_resolved": auto_resolved,
        "skipped": skipped,
    }


async def _cross_validate(
    db: AsyncSession,
    point_id: int,
    area_code: Optional[str],
    device_type: Optional[str],
    target_mean: float,
    target_std: float,
    allowed_point_ids=None,
) -> str:
    """
    交叉验证：比较同区域同类型其他传感器的均值。
    返回 "pass" / "fail" / "skipped"
    """
    if not area_code or not device_type:
        return "skipped"

    # 查询同区域同类型的其他点位当前值
    neighbor_query = (
        select(PointRealtime.value)
        .join(Point, Point.id == PointRealtime.point_id)
        .where(
            Point.area_code == area_code,
            Point.device_type == device_type,
            Point.id != point_id,
            Point.is_enabled == True,  # noqa: E712
            PointRealtime.value.isnot(None),
        )
    )
    if allowed_point_ids is not None:
        neighbor_query = neighbor_query.where(Point.id.in_(allowed_point_ids))
    neighbor_result = await db.execute(neighbor_query)
    neighbor_values = [row[0] for row in neighbor_result.all() if row[0] is not None]

    if len(neighbor_values) < 2:
        return "skipped"

    # 计算邻居均值
    neighbor_mean = statistics.mean(neighbor_values)

    # 如果目标点位的均值偏离邻居均值也超过 3σ → fail
    if target_std == 0:
        return "fail" if target_mean != neighbor_mean else "pass"

    neighbor_deviation = abs(target_mean - neighbor_mean) / target_std
    if neighbor_deviation > DRIFT_THRESHOLD_SIGMA:
        return "fail"

    return "pass"


async def resolve_drift(db: AsyncSession, result_id: int) -> Optional[DriftDetectionResult]:
    """手动解除漂移标记"""
    result = await db.execute(select(DriftDetectionResult).where(DriftDetectionResult.id == result_id))
    record = result.scalar_one_or_none()
    if not record:
        return None

    if record.status == "resolved":
        raise ValueError("该漂移记录已解除")

    record.status = "resolved"
    record.resolved_at = datetime.now()

    # 恢复 PointRealtime.quality
    await db.execute(update(PointRealtime).where(PointRealtime.point_id == record.point_id).values(quality=0))

    await db.commit()
    return record
