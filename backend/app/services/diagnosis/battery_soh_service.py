# backend/app/services/diagnosis/battery_soh_service.py
"""
Story 25.3: UPS电池SOH预测服务
"""
import logging
import json
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, desc, func
import redis.asyncio as redis

from app.core.config import get_settings
from app.core.database import async_session
from app.models import Device, SystemConfig
from app.models.diagnosis import BatterySOHRecord
from prometheus_client import Counter, Histogram, REGISTRY

logger = logging.getLogger(__name__)
settings = get_settings()

# Prometheus 监控指标（条件注册，避免测试时重复）
try:
    battery_soh_calculation_duration = Histogram(
        'battery_soh_calculation_duration_seconds',
        'Time spent calculating battery SOH'
    )
except ValueError:
    battery_soh_calculation_duration = REGISTRY._names_to_collectors['battery_soh_calculation_duration_seconds']

try:
    battery_soh_calculation_total = Counter(
        'battery_soh_calculation_total',
        'Total battery SOH calculations'
    )
except ValueError:
    battery_soh_calculation_total = REGISTRY._names_to_collectors['battery_soh_calculation_total']

try:
    battery_soh_calculation_errors = Counter(
        'battery_soh_calculation_errors_total',
        'Total battery SOH calculation errors'
    )
except ValueError:
    battery_soh_calculation_errors = REGISTRY._names_to_collectors['battery_soh_calculation_errors_total']

try:
    battery_soh_alarm_triggered = Counter(
        'battery_soh_alarm_triggered_total',
        'Total battery SOH alarms triggered',
        ['level']
    )
except ValueError:
    battery_soh_alarm_triggered = REGISTRY._names_to_collectors['battery_soh_alarm_triggered_total']


def clip(value: float, min_val: float, max_val: float) -> float:
    """限制值在指定范围内"""
    return max(min_val, min(max_val, value))


async def get_rated_parameters(device_id: int) -> Optional[dict]:
    """
    从 system_configs 读取 UPS 设备额定参数（全局默认值）

    Returns:
        {"rated_resistance_mohm": float, "rated_cycle_count": int} 或 None
    """
    try:
        async with async_session() as db:
            result = await db.execute(
                select(SystemConfig)
                .where(SystemConfig.config_group == "diagnosis")
                .where(SystemConfig.config_key == "ups_rated_params")
            )
            config = result.scalar_one_or_none()

            if not config or not config.config_value:
                logger.warning(f"system_configs 中未找到 ups_rated_params 配置")
                return None

            # 解析 JSON
            params = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value

            rated_resistance = params.get("rated_resistance_mohm")
            rated_cycle_count = params.get("rated_cycle_count")

            if not rated_resistance or not rated_cycle_count:
                logger.warning(
                    f"ups_rated_params 配置不完整: "
                    f"rated_resistance={rated_resistance}, rated_cycle_count={rated_cycle_count}"
                )
                return None

            return {
                "rated_resistance_mohm": float(rated_resistance),
                "rated_cycle_count": int(rated_cycle_count)
            }

    except Exception as e:
        logger.error(f"查询额定参数失败: {e}")
        return None


async def get_soh_weights() -> dict:
    """
    从 system_configs 读取 SOH 权重配置（带初始化逻辑）

    Returns:
        {"w_r": float, "w_c": float, "version": str}
    """
    try:
        async with async_session() as db:
            result = await db.execute(
                select(SystemConfig)
                .where(SystemConfig.config_group == "diagnosis")
                .where(SystemConfig.config_key == "soh_weights")
            )
            config = result.scalar_one_or_none()

            if config and config.config_value:
                # 解析 JSON
                weights = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                return weights

            # 首次运行：初始化默认配置到数据库
            default_weights = {"w_r": 0.6, "w_c": 0.4, "version": "v1.0"}
            new_config = SystemConfig(
                config_group="diagnosis",
                config_key="soh_weights",
                config_value=json.dumps(default_weights),
                value_type="json",
                description="UPS电池SOH计算权重配置",
                is_editable=True
            )
            db.add(new_config)
            await db.commit()
            logger.info("已初始化 SOH 权重配置到 system_configs")

            return default_weights

    except Exception as e:
        logger.error(f"查询 SOH 权重配置失败: {e}")
        return {"w_r": 0.6, "w_c": 0.4, "version": "default"}


async def get_latest_soh(device_id: int) -> Optional[float]:
    """
    查询设备最近一次 SOH 记录（用于降级）

    Returns:
        SOH 百分比 [0, 100] 或 None
    """
    try:
        async with async_session() as db:
            # 只使用最近 7 天内的历史 SOH（超过 7 天视为过期）
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)

            result = await db.execute(
                select(BatterySOHRecord.soh_percent)
                .where(BatterySOHRecord.device_id == device_id)
                .where(BatterySOHRecord.calculated_at >= cutoff_time)
                .order_by(desc(BatterySOHRecord.calculated_at))
                .limit(1)
            )
            soh = result.scalar_one_or_none()
            return soh

    except Exception as e:
        logger.error(f"查询历史 SOH 失败: {e}")
        return None


async def get_latest_soh_record(device_id: int) -> Optional[BatterySOHRecord]:
    """
    查询设备最近一次 SOH 完整记录（用于数据合理性检查）

    Returns:
        BatterySOHRecord 对象或 None
    """
    try:
        async with async_session() as db:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)

            result = await db.execute(
                select(BatterySOHRecord)
                .where(BatterySOHRecord.device_id == device_id)
                .where(BatterySOHRecord.calculated_at >= cutoff_time)
                .order_by(desc(BatterySOHRecord.calculated_at))
                .limit(1)
            )
            record = result.scalar_one_or_none()
            return record

    except Exception as e:
        logger.error(f"查询历史 SOH 记录失败: {e}")
        return None


async def get_point_latest_value(point_id: int, time_window: int) -> Optional[float]:
    """
    查询点位最新值（优先从 Redis，降级到数据库）

    Args:
        point_id: 点位 ID
        time_window: 时间窗口（秒），用于数据库查询

    Returns:
        点位值（float）或 None（无数据）
    """
    redis_client = None
    try:
        # 优先从 Redis 查询
        redis_client = redis.from_url(settings.REDIS_URL)
        value_str = await redis_client.get(f"point:value:{point_id}")
        if value_str:
            return float(value_str)
    except Exception as e:
        logger.warning(f"从 Redis 查询点位值失败: {e}")
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"关闭 Redis 客户端失败: {e}")

    # 降级：从数据库查询
    try:
        from app.models import PointHistory
        async with async_session() as db:
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window)
            result = await db.execute(
                select(PointHistory.value)
                .where(PointHistory.point_id == point_id)
                .where(PointHistory.timestamp >= cutoff_time)
                .order_by(desc(PointHistory.timestamp))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return float(row) if row is not None else None
    except Exception as e:
        logger.error(f"从数据库查询点位值失败: {e}")
        return None


async def _get_point_id_by_type(device_id: int, point_type: str) -> Optional[int]:
    """
    根据设备 ID 和点位类型查询点位 ID

    Args:
        device_id: 设备 ID
        point_type: 点位类型 ('RESISTANCE' 或 'CYCLE_COUNT')

    Returns:
        点位 ID 或 None
    """
    try:
        from app.models import Point
        async with async_session() as db:
            result = await db.execute(
                select(Point.id)
                .where(Point.device_id == device_id)
                .where(Point.point_type == point_type)
            )
            point_id = result.scalar_one_or_none()
            return point_id

    except Exception as e:
        logger.error(f"查询点位 ID 失败: device_id={device_id}, point_type={point_type}, error={e}")
        return None


async def calculate_soh(device_id: int) -> Optional[float]:
    """
    计算单个 UPS 设备的 SOH（带幂等性和数据合理性检查）

    Args:
        device_id: UPS 设备 ID

    Returns:
        SOH 百分比 [0, 100] 或 None（计算失败）
    """
    with battery_soh_calculation_duration.time():
        try:
            # 0. 幂等性检查：今天是否已计算
            async with async_session() as db:
                today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                result = await db.execute(
                    select(BatterySOHRecord)
                    .where(BatterySOHRecord.device_id == device_id)
                    .where(BatterySOHRecord.calculated_at >= today_start)
                )
                existing_record = result.scalar_one_or_none()

                if existing_record:
                    logger.info(f"设备 {device_id} 今日已计算 SOH，返回现有值: {existing_record.soh_percent:.2f}%")
                    return existing_record.soh_percent

            # 1. 获取额定参数
            rated_params = await get_rated_parameters(device_id)
            if not rated_params:
                logger.warning(f"Missing rated parameters for device {device_id}, SOH calculation skipped")
                battery_soh_calculation_errors.inc()
                return None

            rated_resistance = rated_params["rated_resistance_mohm"]
            rated_cycle_count = rated_params["rated_cycle_count"]

            # 2. 查询点位值
            resistance_point_id = await _get_point_id_by_type(device_id, "RESISTANCE")
            cycle_point_id = await _get_point_id_by_type(device_id, "CYCLE_COUNT")

            if not resistance_point_id or not cycle_point_id:
                logger.warning(f"设备 {device_id} 缺少内阻或循环次数点位配置")
                battery_soh_calculation_errors.inc()
                return None

            current_resistance = await get_point_latest_value(resistance_point_id, time_window=3600)
            current_cycle_count = await get_point_latest_value(cycle_point_id, time_window=3600)

            # 3. 降级处理: 点位值为 null 时使用历史 SOH
            if current_resistance is None or current_cycle_count is None:
                logger.warning(
                    f"设备 {device_id} 点位值不可用 "
                    f"(resistance={current_resistance}, cycle={current_cycle_count}), "
                    f"尝试使用历史 SOH"
                )

                # 追踪点位不可用天数
                await track_point_unavailable(device_id)

                latest_soh = await get_latest_soh(device_id)
                if latest_soh is not None:
                    logger.info(f"设备 {device_id} 使用历史 SOH: {latest_soh}%")
                    return latest_soh
                else:
                    logger.warning(f"设备 {device_id} 无历史 SOH 记录，跳过计算")
                    battery_soh_calculation_errors.inc()
                    return None
            else:
                # 点位可用，重置追踪记录
                await reset_point_unavailable_tracking(device_id)

            # 3.5. 数据合理性检查：循环次数变化不应超过 10%
            latest_soh_record = await get_latest_soh_record(device_id)
            if latest_soh_record and latest_soh_record.cycle_count:
                prev_cycle_count = latest_soh_record.cycle_count
                cycle_change_rate = abs(current_cycle_count - prev_cycle_count) / prev_cycle_count
                if cycle_change_rate > 0.1:
                    logger.warning(
                        f"设备 {device_id} 循环次数变化异常: "
                        f"prev={prev_cycle_count}, current={current_cycle_count}, "
                        f"change_rate={cycle_change_rate:.2%}，使用历史 SOH"
                    )
                    return latest_soh_record.soh_percent

            # 4. 获取权重配置
            weights = await get_soh_weights()
            w_r = weights["w_r"]
            w_c = weights["w_c"]
            weights_version = weights.get("version", "unknown")

            # 5. 计算 SOH
            # resistance_factor: 内阻越高，因子越低
            if current_resistance <= rated_resistance:
                resistance_factor = 1.0  # 新电池或正常电池
            else:
                resistance_factor = clip(
                    1.0 - (current_resistance - rated_resistance) / rated_resistance,
                    0.0,
                    1.0
                )

            # cycle_factor: 循环次数越多，因子越低
            cycle_factor = clip(
                1.0 - current_cycle_count / rated_cycle_count,
                0.0,
                1.0
            )

            soh_percent = (resistance_factor * w_r + cycle_factor * w_c) * 100.0
            soh_percent = clip(soh_percent, 0.0, 100.0)

            logger.info(
                f"设备 {device_id} SOH 计算完成: {soh_percent:.2f}% "
                f"(resistance_factor={resistance_factor:.3f}, cycle_factor={cycle_factor:.3f}, "
                f"w_r={w_r}, w_c={w_c})"
            )

            # 6. 写入数据库
            async with async_session() as db:
                record = BatterySOHRecord(
                    device_id=device_id,
                    soh_percent=soh_percent,
                    resistance_mohm=current_resistance,
                    cycle_count=int(current_cycle_count),
                    weights_version=weights_version,
                    calculated_at=datetime.now(timezone.utc)
                )
                db.add(record)
                await db.commit()

            # 7. 记录监控指标（移除 device_id 标签，避免高基数）
            battery_soh_calculation_total.inc()

            return soh_percent

        except Exception as e:
            logger.error(f"设备 {device_id} SOH 计算失败: {e}")
            battery_soh_calculation_errors.inc()
            return None


async def run_daily_soh_calculation():
    """
    每日定时任务: 计算所有 UPS 设备的 SOH

    执行时间: 每日凌晨 3:00
    """
    logger.info("开始执行每日 SOH 计算任务...")
    start_time = datetime.now(timezone.utc)

    try:
        # 查询所有 UPS 设备
        async with async_session() as db:
            result = await db.execute(
                select(Device.id, Device.device_name)
                .where(Device.device_type == "UPS")
            )
            ups_devices = result.all()

        logger.info(f"找到 {len(ups_devices)} 台 UPS 设备")

        # 逐个计算 SOH
        success_count = 0
        error_count = 0

        for device_id, device_name in ups_devices:
            try:
                soh = await calculate_soh(device_id)
                if soh is not None:
                    success_count += 1

                    # 触发告警
                    await trigger_soh_alarm(device_id, device_name, soh)

                    # 反馈到故障树（调整 UPS 相关叶节点先验概率）
                    await update_fault_tree_prior_probability(device_id, soh)

                    # 反馈到设备健康度评估
                    await update_device_health_score(device_id, soh)
                else:
                    error_count += 1

            except Exception as e:
                logger.error(f"设备 {device_id} ({device_name}) SOH 计算异常: {e}")
                error_count += 1

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"每日 SOH 计算任务完成: 成功 {success_count} 台, 失败 {error_count} 台, "
            f"耗时 {elapsed:.2f} 秒"
        )

    except Exception as e:
        logger.error(f"每日 SOH 计算任务异常: {e}")


async def trigger_soh_alarm(device_id: int, device_name: str, soh_percent: float):
    """
    根据 SOH 阈值触发告警

    告警级别映射:
    - SOH < 60%: 预警 (对应 Alarm.level = "major")
    - SOH < 80%: 关注 (对应 Alarm.level = "minor")

    Args:
        device_id: 设备 ID
        device_name: 设备名称
        soh_percent: SOH 百分比 [0, 100]
    """
    try:
        # 检查是否需要触发告警
        alarm_level = None
        if soh_percent < 60:
            alarm_level = "major"  # 预警
        elif soh_percent < 80:
            alarm_level = "minor"  # 关注

        if not alarm_level:
            return

        # 检查最近 24 小时内是否已触发相同告警（避免重复）
        async with async_session() as db:
            from app.models import Alarm

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            result = await db.execute(
                select(Alarm)
                .where(Alarm.device_id == device_id)
                .where(Alarm.alarm_type == "BATTERY_SOH")
                .where(Alarm.level == alarm_level)
                .where(Alarm.created_at >= cutoff_time)
            )
            existing_alarm = result.scalar_one_or_none()

            if existing_alarm:
                logger.info(f"设备 {device_id} 最近 24 小时内已触发 {alarm_level} 级别 SOH 告警，跳过")
                return

            # 创建告警
            alarm = Alarm(
                device_id=device_id,
                alarm_type="BATTERY_SOH",
                level=alarm_level,
                message=f"UPS设备 {device_name} 电池健康度为 {soh_percent:.1f}%，建议检查电池状态",
                created_at=datetime.now(timezone.utc)
            )
            db.add(alarm)
            await db.commit()

            logger.info(f"设备 {device_id} 触发 {alarm_level} 级别 SOH 告警: {soh_percent:.1f}%")

            # 记录监控指标
            battery_soh_alarm_triggered.labels(level=alarm_level).inc()

    except Exception as e:
        logger.error(f"触发 SOH 告警失败: device_id={device_id}, error={e}")


async def update_fault_tree_prior_probability(device_id: int, soh_percent: float):
    """
    根据 SOH 调整故障树中 UPS 相关叶节点的先验概率

    规则: SOH < 60% → 先验概率 × 1.5（上限 0.95）

    Args:
        device_id: 设备 ID
        soh_percent: SOH 百分比 [0, 100]
    """
    try:
        if soh_percent >= 60:
            # SOH 正常，无需调整
            return

        # 查询该设备关联的故障树叶节点
        async with async_session() as db:
            from app.models.diagnosis import FaultTreeNode

            # 查找 UPS 相关的叶节点（通过 device_type 或 device_id 关联）
            result = await db.execute(
                select(FaultTreeNode)
                .where(FaultTreeNode.device_type == "UPS")
                .where(FaultTreeNode.is_leaf == True)
            )
            leaf_nodes = result.scalars().all()

            if not leaf_nodes:
                logger.debug(f"设备 {device_id} 无关联的故障树叶节点")
                return

            # 调整先验概率
            adjustment_factor = 1.5
            for node in leaf_nodes:
                if node.prior_probability is not None:
                    new_prior = min(node.prior_probability * adjustment_factor, 0.95)
                    node.prior_probability = new_prior
                    logger.info(
                        f"故障树节点 {node.id} ({node.name}) 先验概率已调整: "
                        f"{node.prior_probability:.3f} → {new_prior:.3f} (SOH={soh_percent:.1f}%)"
                    )

            await db.commit()
            logger.info(f"设备 {device_id} 故障树先验概率调整完成（共 {len(leaf_nodes)} 个节点）")

    except Exception as e:
        logger.error(f"更新故障树先验概率失败: device_id={device_id}, error={e}")


async def update_device_health_score(device_id: int, soh_percent: float):
    """
    将 SOH 反馈到设备健康度评估（FR75）

    SOH 作为评分因子之一，权重占比 20%

    Args:
        device_id: 设备 ID
        soh_percent: SOH 百分比 [0, 100]
    """
    try:
        async with async_session() as db:
            from app.models.report import DeviceHealthScore

            # 查询或创建设备健康度记录
            result = await db.execute(
                select(DeviceHealthScore)
                .where(DeviceHealthScore.device_id == device_id)
                .order_by(desc(DeviceHealthScore.calculated_at))
                .limit(1)
            )
            health_record = result.scalar_one_or_none()

            if not health_record:
                # 创建新记录
                health_record = DeviceHealthScore(
                    device_id=device_id,
                    total_score=0.0,
                    calculated_at=datetime.now(timezone.utc)
                )
                db.add(health_record)

            # 更新 SOH 评分因子（权重 20%）
            # 假设 health_record.score_factors 是 JSON 字段: {"soh": 85.0, "uptime": 95.0, ...}
            if health_record.score_factors is None:
                health_record.score_factors = {}

            health_record.score_factors["soh"] = soh_percent

            # 重新计算总分（简化版：各因子加权平均）
            # 实际项目中应调用完整的健康度评估服务
            factors = health_record.score_factors
            weights = {
                "soh": 0.20,
                "uptime": 0.25,
                "alarm_rate": 0.20,
                "maintenance": 0.15,
                "performance": 0.20
            }

            total_score = 0.0
            total_weight = 0.0
            for factor_name, weight in weights.items():
                if factor_name in factors:
                    total_score += factors[factor_name] * weight
                    total_weight += weight

            if total_weight > 0:
                health_record.total_score = total_score / total_weight

            health_record.calculated_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                f"设备 {device_id} 健康度评分已更新: "
                f"SOH={soh_percent:.1f}%, 总分={health_record.total_score:.1f}"
            )

    except Exception as e:
        logger.error(f"更新设备健康度评分失败: device_id={device_id}, error={e}")


async def track_point_unavailable(device_id: int):
    """
    追踪点位不可用天数，连续 7 天触发告警

    Args:
        device_id: 设备 ID
    """
    try:
        async with async_session() as db:
            from app.models.diagnosis import SOHPointUnavailableTracking
            from app.models import Alarm

            today = datetime.now(timezone.utc).date()

            # 查询或创建追踪记录
            result = await db.execute(
                select(SOHPointUnavailableTracking)
                .where(SOHPointUnavailableTracking.device_id == device_id)
            )
            tracking = result.scalar_one_or_none()

            if not tracking:
                # 首次不可用
                tracking = SOHPointUnavailableTracking(
                    device_id=device_id,
                    consecutive_days=1,
                    last_unavailable_date=today,
                    alarm_triggered=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(tracking)
                logger.info(f"设备 {device_id} 点位首次不可用，开始追踪")
            else:
                # 检查是否连续
                last_date = tracking.last_unavailable_date
                if isinstance(last_date, datetime):
                    last_date = last_date.date()

                if (today - last_date).days == 1:
                    # 连续不可用
                    tracking.consecutive_days += 1
                    tracking.last_unavailable_date = today
                    tracking.updated_at = datetime.now(timezone.utc)
                    logger.info(f"设备 {device_id} 点位连续不可用 {tracking.consecutive_days} 天")
                elif (today - last_date).days > 1:
                    # 中断后重新开始
                    tracking.consecutive_days = 1
                    tracking.last_unavailable_date = today
                    tracking.alarm_triggered = False
                    tracking.updated_at = datetime.now(timezone.utc)
                    logger.info(f"设备 {device_id} 点位不可用追踪已重置")

            # 检查是否达到 7 天阈值
            if tracking.consecutive_days >= 7 and not tracking.alarm_triggered:
                # 触发告警
                alarm = Alarm(
                    device_id=device_id,
                    alarm_type="SOH_POINT_UNAVAILABLE",
                    level="major",  # WARNING 级别
                    message=f"UPS设备点位连续 {tracking.consecutive_days} 天不可用，无法计算 SOH",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(alarm)
                tracking.alarm_triggered = True
                logger.warning(f"设备 {device_id} 触发点位长期不可用告警（连续 {tracking.consecutive_days} 天）")

            await db.commit()

    except Exception as e:
        logger.error(f"追踪点位不可用失败: device_id={device_id}, error={e}")


async def reset_point_unavailable_tracking(device_id: int):
    """
    重置点位不可用追踪（点位恢复可用时调用）

    Args:
        device_id: 设备 ID
    """
    try:
        async with async_session() as db:
            from app.models.diagnosis import SOHPointUnavailableTracking

            result = await db.execute(
                select(SOHPointUnavailableTracking)
                .where(SOHPointUnavailableTracking.device_id == device_id)
            )
            tracking = result.scalar_one_or_none()

            if tracking and tracking.consecutive_days > 0:
                logger.info(f"设备 {device_id} 点位已恢复，重置追踪记录（之前连续不可用 {tracking.consecutive_days} 天）")
                await db.delete(tracking)
                await db.commit()

    except Exception as e:
        logger.error(f"重置点位不可用追踪失败: device_id={device_id}, error={e}")
