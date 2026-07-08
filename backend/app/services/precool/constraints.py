"""
约束检查引擎 — ASHRAE 温度硬约束与功率限制

Story 30.1: 提供温度范围、功率上限、温变速率三类约束检查。
集成到 calculate_shiftable_power_for_zone 作为前置安全检查。
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ==================== 默认值（与 datacenter_shift_strategy.py ASHRAE 常量保持一致） ====================
# 因循环导入限制，不从 datacenter_shift_strategy 导入，独立定义默认值
# 运行时从 SystemConfig 读取覆盖

DEFAULT_TEMP_MAX = 27.0  # ASHRAE TC9.9 Class A1 推荐上限 ℃
DEFAULT_TEMP_MIN = 18.0  # ASHRAE TC9.9 Class A1 推荐下限 ℃
DEFAULT_POWER_MULTIPLIER = 1.5  # 制冷功率倍数上限
DEFAULT_RATE_LIMIT = 5.0  # 温变速率限制 °C/h


# ==================== 数据结构 ====================


class ConstraintType(str, Enum):
    """约束类型"""

    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    POWER_OVER_LIMIT = "power_over_limit"
    RATE_OF_CHANGE = "rate_of_change"


@dataclass
class ConstraintViolation:
    """约束违规记录"""

    constraint_type: ConstraintType
    current_value: float
    threshold: float
    zone_id: int
    message: str
    severity: str  # "warning" | "error"

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "type": self.constraint_type.value,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "zone_id": self.zone_id,
            "message": self.message,
            "severity": self.severity,
        }


# ==================== 配置读取 ====================


async def _load_constraint_config(session: AsyncSession) -> Dict[str, float]:
    """
    从 SystemConfig 读取约束参数，若无记录则使用默认值

    Returns:
        Dict: {temp_max, temp_min, power_multiplier, rate_limit}
    """
    defaults = {
        "constraint_temp_max": DEFAULT_TEMP_MAX,
        "constraint_temp_min": DEFAULT_TEMP_MIN,
        "constraint_power_multiplier": DEFAULT_POWER_MULTIPLIER,
        "constraint_rate_limit": DEFAULT_RATE_LIMIT,
    }

    config = {}

    try:
        from app.models.config import SystemConfig
    except ImportError:
        logger.warning("SystemConfig 不可用，使用默认约束参数")
        return {
            "temp_max": DEFAULT_TEMP_MAX,
            "temp_min": DEFAULT_TEMP_MIN,
            "power_multiplier": DEFAULT_POWER_MULTIPLIER,
            "rate_limit": DEFAULT_RATE_LIMIT,
        }

    for key, default_value in defaults.items():
        try:
            result = (
                await session.execute(select(SystemConfig).where(SystemConfig.config_key == key))
            ).scalar_one_or_none()

            if result is None:
                config[key] = default_value
            else:
                config[key] = float(result.config_value)
        except Exception as e:
            logger.error(f"读取约束配置 {key} 失败: {e}，使用默认值 {default_value}")
            config[key] = default_value

    return {
        "temp_max": config["constraint_temp_max"],
        "temp_min": config["constraint_temp_min"],
        "power_multiplier": config["constraint_power_multiplier"],
        "rate_limit": config["constraint_rate_limit"],
    }


# ==================== 温度约束检查 ====================


async def check_temperature_constraints(
    zone_id: int,
    session: AsyncSession,
    config: Optional[Dict[str, float]] = None,
) -> List[ConstraintViolation]:
    """
    ASHRAE 温度范围检查 — 查询最热机柜进风温度

    Returns:
        List[ConstraintViolation]: 违规列表（可能含 warning 和 error）
    """
    if config is None:
        config = await _load_constraint_config(session)

    temp_max = config["temp_max"]
    temp_min = config["temp_min"]
    safety_margin = 2.0  # 接近阈值的安全裕度

    # 查询最热机柜进风温度（最近 5 分钟）
    t_current_max = await _get_max_inlet_temperature(zone_id, session)

    if t_current_max is None:
        # 无温度数据时不产生约束违规（传感器离线由其他机制处理）
        return []

    violations = []

    # 温度超上限
    if t_current_max >= temp_max:
        violations.append(
            ConstraintViolation(
                constraint_type=ConstraintType.TEMPERATURE_HIGH,
                current_value=t_current_max,
                threshold=temp_max,
                zone_id=zone_id,
                message=f"进风温度 {t_current_max:.1f}°C 超过 ASHRAE 上限 {temp_max}°C",
                severity="error",
            )
        )
        logger.error(f"Zone {zone_id}: 温度超上限 {t_current_max:.1f}°C >= {temp_max}°C")
    elif t_current_max >= temp_max - safety_margin:
        violations.append(
            ConstraintViolation(
                constraint_type=ConstraintType.TEMPERATURE_HIGH,
                current_value=t_current_max,
                threshold=temp_max,
                zone_id=zone_id,
                message=f"进风温度 {t_current_max:.1f}°C 接近 ASHRAE 上限 {temp_max}°C",
                severity="warning",
            )
        )
        logger.warning(f"Zone {zone_id}: 温度接近上限 {t_current_max:.1f}°C (阈值 {temp_max}°C)")

    # 温度低于下限
    if t_current_max <= temp_min:
        violations.append(
            ConstraintViolation(
                constraint_type=ConstraintType.TEMPERATURE_LOW,
                current_value=t_current_max,
                threshold=temp_min,
                zone_id=zone_id,
                message=f"进风温度 {t_current_max:.1f}°C 低于 ASHRAE 下限 {temp_min}°C",
                severity="error",
            )
        )
        logger.error(f"Zone {zone_id}: 温度低于下限 {t_current_max:.1f}°C <= {temp_min}°C")

    return violations


async def _get_max_inlet_temperature(zone_id: int, session: AsyncSession) -> Optional[float]:
    """
    获取 zone 内最热机柜的进风温度（最近 5 分钟最大值）

    查询路径: CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(inlet) → Point → PointHistory
    """
    try:
        from app.models.topology_config import CoolingZoneCabinet, CabinetTemperatureSensor
        from app.models.asset import Cabinet
        from app.models.point import Point
        from app.models.history import PointHistory

        now = datetime.now()
        five_min_ago = now - timedelta(minutes=5)

        query = (
            select(func.max(PointHistory.value))
            .join(Point, Point.id == PointHistory.point_id)
            .join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
            .join(Cabinet, Cabinet.id == CabinetTemperatureSensor.cabinet_id)
            .join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == Cabinet.id)
            .where(CoolingZoneCabinet.zone_id == zone_id)
            .where(CabinetTemperatureSensor.sensor_location == 'inlet')
            .where(PointHistory.recorded_at >= five_min_ago)
        )

        result = await session.execute(query)
        return result.scalar()
    except Exception as e:
        logger.error(f"Zone {zone_id}: 查询进风温度失败: {e}")
        return None


# ==================== 功率约束检查 ====================


async def check_power_constraint(
    zone_id: int,
    q_cool: float,
    session: AsyncSession,
    config: Optional[Dict[str, float]] = None,
) -> Optional[ConstraintViolation]:
    """
    检查制冷功率是否超限 — 独立调用，需传入当前/提议的 q_cool 值

    Args:
        zone_id: 制冷区域 ID
        q_cool: 当前或提议的制冷功率 (kW)
        session: 数据库会话
        config: 约束配置（可选，未传入时从 SystemConfig 读取）

    Returns:
        ConstraintViolation 或 None
    """
    if config is None:
        config = await _load_constraint_config(session)

    power_multiplier = config["power_multiplier"]
    q_rated = await _get_zone_rated_power(zone_id, session)
    q_max = q_rated * power_multiplier

    if q_cool > q_max:
        logger.error(
            f"Zone {zone_id}: 制冷功率 {q_cool:.1f}kW 超过上限 {q_max:.1f}kW (额定 {q_rated:.1f}kW × {power_multiplier})"
        )
        return ConstraintViolation(
            constraint_type=ConstraintType.POWER_OVER_LIMIT,
            current_value=q_cool,
            threshold=q_max,
            zone_id=zone_id,
            message=f"制冷功率 {q_cool:.1f}kW 超过上限 {q_max:.1f}kW (额定 {q_rated:.1f}kW × {power_multiplier})",
            severity="error",
        )
    elif q_cool > q_max * 0.9:
        logger.warning(f"Zone {zone_id}: 制冷功率 {q_cool:.1f}kW 接近上限 {q_max:.1f}kW")
        return ConstraintViolation(
            constraint_type=ConstraintType.POWER_OVER_LIMIT,
            current_value=q_cool,
            threshold=q_max,
            zone_id=zone_id,
            message=f"制冷功率 {q_cool:.1f}kW 接近上限 {q_max:.1f}kW",
            severity="warning",
        )

    return None


async def _get_zone_rated_power(zone_id: int, session: AsyncSession) -> float:
    """
    获取 zone 总额定制冷功率

    路径: CoolingZoneUnit(zone_id) → CoolingUnit.cooling_capacity_kw
    回退: CoolingLinkageConfig.max_cooling_power (默认 2000 kW)
    """
    from app.models.topology_config import CoolingZoneUnit
    from app.models.cooling import CoolingUnit

    query = (
        select(func.sum(CoolingUnit.cooling_capacity_kw))
        .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
        .where(CoolingZoneUnit.zone_id == zone_id)
    )

    result = await session.execute(query)
    total_capacity = result.scalar()

    if total_capacity is not None and total_capacity > 0:
        return total_capacity

    # 回退到 CoolingLinkageConfig.max_cooling_power
    try:
        from app.models.load_shift import CoolingLinkageConfig

        config_result = (
            await session.execute(
                select(CoolingLinkageConfig.max_cooling_power).where(CoolingLinkageConfig.cooling_zone_id == zone_id)
            )
        ).scalar_one_or_none()

        if config_result is not None:
            logger.warning(
                f"Zone {zone_id}: 无 CoolingUnit 数据，回退到 CoolingLinkageConfig.max_cooling_power={config_result}kW"
            )
            return config_result
    except Exception as e:
        logger.warning(f"Zone {zone_id}: 读取 CoolingLinkageConfig 失败: {e}")

    # 最终回退
    logger.warning(f"Zone {zone_id}: 无额定功率数据，使用默认值 2000kW")
    return 2000.0


# ==================== 温变速率检查 ====================


async def check_rate_of_change(
    zone_id: int,
    session: AsyncSession,
    config: Optional[Dict[str, float]] = None,
) -> List[ConstraintViolation]:
    """
    温变速率约束检查 — 复用 _calculate_temperature_rise_rate

    Returns:
        List[ConstraintViolation]: 违规列表
    """
    if config is None:
        config = await _load_constraint_config(session)

    rate_limit = config["rate_limit"]

    # lazy import 避免循环导入
    from app.services.datacenter_shift_strategy import _calculate_temperature_rise_rate

    rate = await _calculate_temperature_rise_rate(zone_id, session)
    abs_rate = abs(rate)

    violations = []

    if abs_rate > rate_limit:
        violations.append(
            ConstraintViolation(
                constraint_type=ConstraintType.RATE_OF_CHANGE,
                current_value=abs_rate,
                threshold=rate_limit,
                zone_id=zone_id,
                message=f"温变速率 {abs_rate:.2f}°C/h 超过限制 {rate_limit}°C/h",
                severity="error",
            )
        )
        logger.error(f"Zone {zone_id}: 温变速率超限 |{rate:.2f}|°C/h > {rate_limit}°C/h")
    elif abs_rate > rate_limit * 0.9:
        violations.append(
            ConstraintViolation(
                constraint_type=ConstraintType.RATE_OF_CHANGE,
                current_value=abs_rate,
                threshold=rate_limit,
                zone_id=zone_id,
                message=f"温变速率 {abs_rate:.2f}°C/h 接近限制 {rate_limit}°C/h",
                severity="warning",
            )
        )
        logger.warning(f"Zone {zone_id}: 温变速率接近限制 |{rate:.2f}|°C/h (阈值 {rate_limit}°C/h)")

    return violations


# ==================== 综合检查入口 ====================


async def check_all_constraints(
    zone_id: int,
    session: AsyncSession,
) -> List[ConstraintViolation]:
    """
    综合约束检查入口 — 仅含温度+速率检查（功率检查需单独调用 check_power_constraint）

    用于 calculate_shiftable_power_for_zone 的前置安全检查。

    Returns:
        List[ConstraintViolation]: 所有违规项（含 warning 和 error）
    """
    config = await _load_constraint_config(session)

    violations = []

    try:
        violations.extend(await check_temperature_constraints(zone_id, session, config))
    except Exception as e:
        logger.error(f"Zone {zone_id}: 温度约束检查失败: {e}")

    try:
        violations.extend(await check_rate_of_change(zone_id, session, config))
    except Exception as e:
        logger.error(f"Zone {zone_id}: 温变速率检查失败: {e}")

    return violations
