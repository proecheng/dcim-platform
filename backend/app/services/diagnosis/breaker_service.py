"""
断路器保护动作判定服务
Story 25.4: N+X冗余拓扑与断路器保护逻辑
"""

import time
import logging
from typing import Tuple, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter, Histogram, REGISTRY

from app.models.alarm import Alarm
from app.models.diagnosis import BreakerProfile
from app.models.energy import PowerDevice

logger = logging.getLogger(__name__)

# 断路器动作时间阈值倍数
BREAKER_FAILURE_THRESHOLD_MULTIPLIER = 2.0

# Prometheus 监控指标（条件注册，避免重复）
try:
    diagnosis_breaker_check_duration_seconds = Histogram(
        'diagnosis_breaker_check_duration_seconds',
        'Duration of breaker action check operations in seconds',
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
except ValueError:
    diagnosis_breaker_check_duration_seconds = REGISTRY._names_to_collectors['diagnosis_breaker_check_duration_seconds']

try:
    diagnosis_breaker_action_total = Counter(
        'diagnosis_breaker_action_total',
        'Total number of breaker action checks',
        ['action_type']
    )
except ValueError:
    diagnosis_breaker_action_total = REGISTRY._names_to_collectors['diagnosis_breaker_action_total']


# 断路器脱扣曲线常量
BREAKER_CURVES = {
    'B': [(3, 3, 45), (5, 0.04, 0.1)],      # (倍数, 最小时间s, 最大时间s)
    'C': [(5, 1.3, 15), (10, 0.04, 0.1)],
    'D': [(10, 1, 8), (50, 0.04, 0.1)]
}


class BreakerActionResult(BaseModel):
    """断路器动作判定结果"""
    action_type: str
    confidence: float
    explanation: str
    overload_ratio: float
    expected_time_range: Tuple[float, float]
    actual_time: float
    error: Optional[str] = None


def interpolate_trip_time(curve_type: str, overload_ratio: float) -> Tuple[float, float]:
    """
    使用线性插值计算过载倍数对应的脱扣时间范围

    Args:
        curve_type: 曲线类型 (B/C/D)
        overload_ratio: 过载倍数

    Returns:
        (min_time, max_time): 预期时间范围（秒）
    """
    if curve_type not in BREAKER_CURVES:
        raise ValueError(f"不支持的曲线类型: {curve_type}")

    points = BREAKER_CURVES[curve_type]

    # 处理边界情况：小于最小倍数
    if overload_ratio <= points[0][0]:
        return (points[0][1], points[0][2])

    # 处理边界情况：大于最大倍数
    if overload_ratio >= points[-1][0]:
        return (points[-1][1], points[-1][2])

    # 找到 overload_ratio 所在的区间
    for i in range(len(points) - 1):
        ratio1, min1, max1 = points[i]
        ratio2, min2, max2 = points[i + 1]

        if ratio1 <= overload_ratio <= ratio2:
            # 线性插值
            t = (overload_ratio - ratio1) / (ratio2 - ratio1)
            min_time = min1 + t * (min2 - min1)
            max_time = max1 + t * (max2 - max1)
            return (min_time, max_time)

    # 理论上不应该到达这里
    return (points[-1][1], points[-1][2])


async def check_breaker_action(alarm: Alarm, session: AsyncSession) -> BreakerActionResult:
    """
    检查断路器保护动作是否正常

    Args:
        alarm: 告警对象
        session: 数据库会话

    Returns:
        BreakerActionResult: 断路器动作判定结果
    """
    start_time = time.time()
    action_type = "error"

    try:
        # 从告警对象获取 point_id，查询点位关联的 power_device_id
        # 通过 power_devices.current_point_id 反向查询
        result = await session.execute(
            select(PowerDevice).where(PowerDevice.current_point_id == alarm.point_id)
        )
        power_device = result.scalar_one_or_none()

        if not power_device:
            action_type = "no_breaker_config"
            result = BreakerActionResult(
                action_type=action_type,
                confidence=0.0,
                explanation="点位未关联到配电设备",
                overload_ratio=0.0,
                expected_time_range=(0, 0),
                actual_time=0.0
            )
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return result

        # 从 breaker_profiles 表查询断路器特性
        result = await session.execute(
            select(BreakerProfile).where(BreakerProfile.breaker_device_id == power_device.id)
        )
        breaker_profile = result.scalar_one_or_none()

        if not breaker_profile:
            action_type = "no_breaker_config"
            result = BreakerActionResult(
                action_type=action_type,
                confidence=0.0,
                explanation="设备未配置断路器特性",
                overload_ratio=0.0,
                expected_time_range=(0, 0),
                actual_time=0.0
            )
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return result

        # 从告警的 trigger_value 获取实际电流
        actual_current = alarm.trigger_value
        if not actual_current or actual_current <= 0:
            action_type = "error"
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return BreakerActionResult(
                action_type=action_type,
                confidence=0.0,
                explanation="告警触发值无效",
                overload_ratio=0.0,
                expected_time_range=(0, 0),
                actual_time=0.0,
                error="Invalid trigger_value"
            )

        # 计算过载倍数
        overload_ratio = actual_current / breaker_profile.rated_current

        # 调用 interpolate_trip_time 获取预期时间范围
        min_time, max_time = interpolate_trip_time(breaker_profile.trip_curve_type, overload_ratio)

        # 计算动作时间 = (当前时间 - alarm.created_at).total_seconds()
        actual_time = (datetime.now() - alarm.created_at).total_seconds()

        # 判定动作是否正常
        if min_time <= actual_time <= max_time:
            # 动作时间在预期范围内 → "保护正常动作"
            action_type = "保护正常动作"
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return BreakerActionResult(
                action_type=action_type,
                confidence=0.95,
                explanation=f"断路器在预期时间范围内动作（{min_time:.2f}s - {max_time:.2f}s），实际动作时间 {actual_time:.2f}s",
                overload_ratio=overload_ratio,
                expected_time_range=(min_time, max_time),
                actual_time=actual_time
            )
        elif actual_time < min_time:
            # 动作时间 < min_time → "动作过快，可能误动作"
            action_type = "动作过快，可能误动作"
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return BreakerActionResult(
                action_type=action_type,
                confidence=0.7,
                explanation=f"断路器动作过快（预期 ≥{min_time:.2f}s，实际 {actual_time:.2f}s），可能存在误动作",
                overload_ratio=overload_ratio,
                expected_time_range=(min_time, max_time),
                actual_time=actual_time
            )
        elif actual_time > max_time and actual_time <= max_time * BREAKER_FAILURE_THRESHOLD_MULTIPLIER:
            # 动作时间 > max_time 且 < max_time × 2 → "动作过慢，断路器老化"
            action_type = "动作过慢，断路器老化"
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return BreakerActionResult(
                action_type=action_type,
                confidence=0.8,
                explanation=f"断路器动作过慢（预期 ≤{max_time:.2f}s，实际 {actual_time:.2f}s），可能存在老化",
                overload_ratio=overload_ratio,
                expected_time_range=(min_time, max_time),
                actual_time=actual_time
            )
        else:
            # 动作时间 > max_time × 2 → "断路器故障，未动作"
            action_type = "断路器故障，未动作"
            diagnosis_breaker_action_total.labels(action_type=action_type).inc()
            return BreakerActionResult(
                action_type=action_type,
                confidence=0.9,
                explanation=f"断路器未在预期时间内动作（预期 ≤{max_time:.2f}s，实际 {actual_time:.2f}s），可能存在故障",
                overload_ratio=overload_ratio,
                expected_time_range=(min_time, max_time),
                actual_time=actual_time
            )

    except Exception as e:
        # 数据库查询失败或计算异常时记录错误日志
        action_type = "error"
        logger.error(f"断路器判定失败 alarm_id={alarm.id}: {str(e)}")
        diagnosis_breaker_action_total.labels(action_type=action_type).inc()

        return BreakerActionResult(
            action_type=action_type,
            confidence=0.0,
            explanation="断路器判定过程发生错误",
            overload_ratio=0.0,
            expected_time_range=(0, 0),
            actual_time=0.0,
            error=str(e)
        )

    finally:
        # 记录耗时
        duration = time.time() - start_time
        diagnosis_breaker_check_duration_seconds.observe(duration)
