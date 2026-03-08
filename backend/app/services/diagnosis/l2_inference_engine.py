# backend/app/services/diagnosis/l2_inference_engine.py
"""
Story 24.5 + 25.2: L2 故障树推理引擎
支持电气参数的 Sigmoid 连续映射证据收集
"""
import asyncio
import json
import logging
from typing import Optional
import redis.asyncio as redis
from sqlalchemy import select, desc
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.database import async_session
from app.models.fault_tree import FaultTreeNode
from app.models import Point, PointHistory
from app.models.alarm import Alarm
from app.services.diagnosis.evidence_calculator import calc_evidence_probability
from prometheus_client import Counter, REGISTRY

logger = logging.getLogger(__name__)
settings = get_settings()

# Prometheus 监控指标（条件注册）
try:
    electrical_param_evidence_total = Counter(
        'electrical_param_evidence_total',
        'Total electrical parameter evidence calculations',
        ['point_type']
    )
except ValueError:
    electrical_param_evidence_total = REGISTRY._names_to_collectors['electrical_param_evidence_total']

# 电气参数默认配置
ELECTRICAL_PARAM_DEFAULTS = {
    "PHASE_IMBALANCE": {"threshold": 10.0, "threshold_type": "ABOVE"},
    "THD": {"threshold": 5.0, "threshold_type": "ABOVE"},
    "POWER_FACTOR": {"threshold": 0.9, "threshold_type": "BELOW"},
}


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


async def get_point_by_id(point_id: int) -> Optional[Point]:
    """
    查询 Point 模型获取点位元数据

    注意: 此函数使用 READ COMMITTED 隔离级别（SQLAlchemy 默认）
    如需更强的一致性保证，可在调用处使用事务包装

    Args:
        point_id: 点位 ID

    Returns:
        Point 对象或 None（点位不存在）
    """
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Point).where(Point.id == point_id)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"查询点位元数据失败: {e}")
        return None


async def collect_leaf_evidence(node: FaultTreeNode, time_window: int) -> float:
    """
    收集叶节点证据（支持电气参数和传感器精度加权）

    Args:
        node: 故障树叶节点
        time_window: 时间窗口（秒）

    Returns:
        证据概率 [0, 1]
    """
    if node.evidence_point_id is None:
        return node.prior_probability or 0.5

    # 查询点位最新值
    point_value = await get_point_latest_value(node.evidence_point_id, time_window)
    if point_value is None:
        logger.warning(f"点位 {node.evidence_point_id} 无数据，返回先验概率")
        return node.prior_probability or 0.5

    # 获取点位类型
    point = await get_point_by_id(node.evidence_point_id)
    if point is None:
        logger.error(f"点位 {node.evidence_point_id} 不存在，返回先验概率")
        return node.prior_probability or 0.5

    point_type = point.point_type  # e.g., 'PHASE_IMBALANCE', 'THD', 'POWER_FACTOR'

    # 计算原始证据概率
    raw_probability = node.prior_probability or 0.5

    # 检查是否为电气参数类型
    if point_type in ELECTRICAL_PARAM_DEFAULTS:
        # 使用节点配置的阈值，或使用默认值
        threshold = node.threshold_value
        threshold_type = node.threshold_type
        sigmoid_k = node.sigmoid_k or 2.0

        if threshold is None or threshold_type is None:
            # 使用默认配置
            defaults = ELECTRICAL_PARAM_DEFAULTS[point_type]
            threshold = defaults["threshold"]
            threshold_type = defaults["threshold_type"]

        # 计算证据概率（sigmoid 映射）
        raw_probability = calc_evidence_probability(
            value=point_value,
            threshold=threshold,
            threshold_type=threshold_type,
            sigmoid_k=sigmoid_k,
            prior=node.prior_probability or 0.5
        )

        # 记录监控指标
        electrical_param_evidence_total.labels(point_type=point_type).inc()

        logger.info(
            f"电气参数证据: point_id={node.evidence_point_id}, type={point_type}, "
            f"value={point_value}, threshold={threshold}, "
            f"threshold_type={threshold_type}, probability={raw_probability:.3f}"
        )

    else:
        # 非电气参数类型，使用原有逻辑
        # 原有逻辑: 简单阈值判定（二值化）
        # 参考 Story 24.5 实现: backend/app/services/diagnosis/l2_inference_engine.py:collect_leaf_evidence()
        # 如果点位有配置的阈值，使用阈值判定
        if node.threshold_value is not None and node.threshold_type is not None:
            if node.threshold_type == "ABOVE":
                is_abnormal = point_value > node.threshold_value
            else:  # BELOW
                is_abnormal = point_value < node.threshold_value

            raw_probability = 0.9 if is_abnormal else 0.1
        else:
            # 无阈值配置，返回先验概率
            raw_probability = node.prior_probability or 0.5

    # Story 25.4: 检查断路器保护动作（仅针对电流类型点位）
    if point_type in ["CURRENT", "PHASE_CURRENT"]:
        try:
            from app.services.diagnosis.breaker_service import check_breaker_action

            # 查询最近的电流告警
            async with async_session() as db:
                result = await db.execute(
                    select(Alarm)
                    .where(Alarm.point_id == node.evidence_point_id)
                    .where(Alarm.level.in_(["critical", "warning"]))
                    .order_by(desc(Alarm.created_at))
                    .limit(1)
                )
                recent_alarm = result.scalar_one_or_none()

                if recent_alarm:
                    # 检查断路器动作
                    breaker_result = await check_breaker_action(recent_alarm, db)

                    # 根据断路器动作类型调整证据概率
                    if breaker_result.action_type == "保护正常动作":
                        # 断路器正常动作，增强证据可信度
                        raw_probability = min(raw_probability * 1.1, 1.0)
                        logger.info(
                            f"断路器保护正常动作，增强证据: point_id={node.evidence_point_id}, "
                            f"adjusted_prob={raw_probability:.3f}"
                        )
                    elif breaker_result.action_type in ["动作过快，可能误动作", "动作过慢，断路器老化"]:
                        # 断路器动作异常，降低证据可信度
                        raw_probability = raw_probability * 0.8
                        logger.warning(
                            f"断路器动作异常 ({breaker_result.action_type}): point_id={node.evidence_point_id}, "
                            f"adjusted_prob={raw_probability:.3f}"
                        )
                    elif breaker_result.action_type == "断路器故障，未动作":
                        # 断路器故障，显著降低证据可信度
                        raw_probability = raw_probability * 0.5
                        logger.error(
                            f"断路器故障未动作: point_id={node.evidence_point_id}, "
                            f"adjusted_prob={raw_probability:.3f}"
                        )

        except ImportError:
            logger.debug("断路器保护服务不可用，跳过断路器检查")
        except Exception as e:
            logger.warning(f"断路器保护检查失败: {e}，使用原始概率")

    # Story 25.5: 应用传感器精度加权
    try:
        from app.services.diagnosis.sensor_metadata_service import get_sensor_weight, apply_evidence_weight

        sensor_weight = get_sensor_weight(node.evidence_point_id)
        prior = node.prior_probability or 0.5

        # 应用权重收缩公式: P_adj = prior + (P_obs - prior) × weight
        adjusted_probability = apply_evidence_weight(prior, raw_probability, sensor_weight)

        logger.debug(
            f"传感器精度加权: point_id={node.evidence_point_id}, "
            f"raw={raw_probability:.3f}, weight={sensor_weight:.3f}, "
            f"adjusted={adjusted_probability:.3f}"
        )

        return adjusted_probability

    except ImportError:
        logger.warning("传感器元数据服务不可用，使用原始概率")
        return raw_probability
    except Exception as e:
        logger.error(f"应用传感器精度加权失败: {e}，使用原始概率")
        return raw_probability
