"""
传感器元数据服务
Story 25.5: 传感器元数据与精度加权

本模块实现传感器元数据的缓存管理、权重计算和校准状态检查。
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import SensorMetadata, CalibrationStatus
from app.core.database import async_session

logger = logging.getLogger(__name__)


class SensorMetadataCache:
    """传感器元数据内存缓存"""

    _cache: Dict[int, SensorMetadata] = {}
    _lock = asyncio.Lock()
    _listener_task: Optional[asyncio.Task] = None

    @classmethod
    async def load_all(cls, session: AsyncSession) -> None:
        """全量加载传感器元数据到内存缓存"""
        try:
            async with cls._lock:
                result = await session.execute(select(SensorMetadata))
                metadata_list = result.scalars().all()

                cls._cache.clear()
                for metadata in metadata_list:
                    cls._cache[metadata.point_id] = metadata

                logger.info(f"Loaded {len(cls._cache)} sensor metadata records into cache")
        except Exception as e:
            logger.error(f"Failed to load sensor metadata cache: {e}")
            # 缓存加载失败不阻止应用启动，使用默认权重

    @classmethod
    async def reload_point(cls, point_id: int) -> None:
        """重新加载指定点位的元数据"""
        try:
            async with async_session() as session:
                result = await session.execute(select(SensorMetadata).where(SensorMetadata.point_id == point_id))
                metadata = result.scalar_one_or_none()

                async with cls._lock:
                    if metadata:
                        cls._cache[point_id] = metadata
                        logger.debug(f"Reloaded metadata for point {point_id}")
                    elif point_id in cls._cache:
                        del cls._cache[point_id]
                        logger.debug(f"Removed metadata for point {point_id}")
        except Exception as e:
            logger.error(f"Failed to reload metadata for point {point_id}: {e}")

    @classmethod
    def get(cls, point_id: int) -> Optional[SensorMetadata]:
        """从缓存获取传感器元数据（同步方法，用于推理时快速查询）"""
        return cls._cache.get(point_id)

    @classmethod
    async def start_listener(cls) -> asyncio.Task:
        """启动 Redis Pub/Sub 监听器"""

        async def listener_loop():
            """监听器循环"""
            try:
                import redis.asyncio as redis
                from app.core.config import get_settings

                settings = get_settings()

                redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
                pubsub = redis_client.pubsub()
                await pubsub.subscribe("sensor:metadata_update")

                logger.info("Started Redis listener for sensor metadata updates")

                while True:
                    try:
                        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if message and message["type"] == "message":
                            payload = json.loads(message["data"])
                            point_id = payload.get("point_id")
                            if point_id:
                                await cls.reload_point(point_id)
                    except asyncio.CancelledError:
                        logger.info("Redis listener cancelled, shutting down gracefully")
                        await pubsub.unsubscribe("sensor:metadata_update")
                        await redis_client.close()
                        break
                    except Exception as e:
                        logger.error(f"Error in Redis listener: {e}")
                        await asyncio.sleep(5)  # 重连延迟
            except ImportError:
                logger.warning("Redis not available, sensor metadata cache will not auto-update")
            except Exception as e:
                logger.error(f"Failed to start Redis listener: {e}")

        task = asyncio.create_task(listener_loop())
        cls._listener_task = task
        return task

    @classmethod
    async def stop_listener(cls) -> None:
        """停止 Redis 监听器"""
        if cls._listener_task:
            cls._listener_task.cancel()
            try:
                await cls._listener_task
            except asyncio.CancelledError:
                pass
            cls._listener_task = None
            logger.info("Stopped Redis listener for sensor metadata updates")


def get_sensor_weight(point_id: int) -> float:
    """
    获取传感器权重

    Args:
        point_id: 点位ID

    Returns:
        传感器权重 (0-1)，默认 0.85

    权重计算规则:
    - 无元数据: 0.85
    - 0.2级精度: 1.0
    - 0.5级精度: 0.9
    - 1.0级精度: 0.8
    - 校准过期: 基础权重 × 0.6
    - 未校准(calibration_date=NULL): 使用基础权重
    """
    metadata = SensorMetadataCache.get(point_id)

    if not metadata:
        return 0.85  # 默认权重

    # 计算基础权重
    base_weight_map = {0.2: 1.0, 0.5: 0.9, 1.0: 0.8}
    base_weight = base_weight_map.get(metadata.accuracy_class, 0.85)

    # 检查校准过期
    if metadata.calibration_date is not None:
        days_since_calibration = (date.today() - metadata.calibration_date).days
        if days_since_calibration > metadata.calibration_interval_days:
            # 校准过期，权重降级
            return base_weight * 0.6

    return base_weight


def apply_evidence_weight(prior: float, observed: float, weight: float) -> float:
    """
    使用收缩公式调整证据概率

    Args:
        prior: 先验概率
        observed: 观测概率（原始证据概率）
        weight: 传感器权重 (0-1)

    Returns:
        调整后的概率

    公式: P_adj = prior + (observed - prior) × weight

    解释:
    - weight=1.0: P_adj = observed（完全信任观测值）
    - weight=0.0: P_adj = prior（完全不信任观测值，回归先验）
    - weight=0.5: P_adj = (prior + observed) / 2（折中）

    避免系统性压低: 权重影响的是观测值向先验的回归程度，
    而不是直接乘以观测值，因此不会系统性压低所有概率。
    """
    adjusted = prior + (observed - prior) * weight
    return max(0.0, min(1.0, adjusted))  # 确保在 [0, 1] 范围内


async def check_calibration_status(point_id: int, session: AsyncSession) -> Dict:
    """
    检查传感器校准状态

    Args:
        point_id: 点位ID
        session: 数据库会话

    Returns:
        校准状态信息字典
    """
    result = await session.execute(select(SensorMetadata).where(SensorMetadata.point_id == point_id))
    metadata = result.scalar_one_or_none()

    if not metadata:
        return {
            "point_id": point_id,
            "status": CalibrationStatus.NO_METADATA.value,
            "expired_days": None,
            "calibration_date": None,
            "next_calibration_date": None,
        }

    if metadata.calibration_date is None:
        return {
            "point_id": point_id,
            "status": CalibrationStatus.NOT_CALIBRATED.value,
            "expired_days": None,
            "calibration_date": None,
            "next_calibration_date": None,
        }

    days_since_calibration = (date.today() - metadata.calibration_date).days
    next_calibration = metadata.calibration_date + timedelta(days=metadata.calibration_interval_days)

    if days_since_calibration > metadata.calibration_interval_days:
        expired_days = days_since_calibration - metadata.calibration_interval_days
        return {
            "point_id": point_id,
            "status": CalibrationStatus.EXPIRED.value,
            "expired_days": expired_days,
            "calibration_date": metadata.calibration_date,
            "next_calibration_date": next_calibration,
        }

    return {
        "point_id": point_id,
        "status": CalibrationStatus.VALID.value,
        "expired_days": None,
        "calibration_date": metadata.calibration_date,
        "next_calibration_date": next_calibration,
    }


async def check_expired_calibrations(session: AsyncSession) -> None:
    """
    检查所有传感器的校准过期状态，创建维护告警

    Args:
        session: 数据库会话
    """
    try:
        # 查询所有有校准日期的传感器元数据
        result = await session.execute(select(SensorMetadata).where(SensorMetadata.calibration_date.isnot(None)))
        metadata_list = result.scalars().all()

        from app.models.alarm import Alarm
        from app.models.point import Point

        expired_count = 0
        for metadata in metadata_list:
            days_since_calibration = (date.today() - metadata.calibration_date).days
            if days_since_calibration > metadata.calibration_interval_days:
                expired_days = days_since_calibration - metadata.calibration_interval_days

                # 检查是否已存在未处理的同类告警
                existing_alarm = await session.execute(
                    select(Alarm).where(
                        Alarm.point_id == metadata.point_id,
                        Alarm.alarm_type == "maintenance",
                        Alarm.status == "active",
                        Alarm.additional_info.contains('"alarm_source": "sensor_calibration"'),
                    )
                )
                if existing_alarm.scalar_one_or_none():
                    continue  # 已存在告警，跳过

                # 获取点位名称
                point_result = await session.execute(select(Point).where(Point.id == metadata.point_id))
                point = point_result.scalar_one_or_none()
                point_name = point.point_name if point else f"Point {metadata.point_id}"

                # 创建维护告警
                suggested_date = date.today() + timedelta(days=7)
                alarm = Alarm(
                    point_id=metadata.point_id,
                    alarm_type="maintenance",
                    alarm_level="info",
                    alarm_message=f"传感器需校准: {point_name} (已过期 {expired_days} 天)",
                    status="active",
                    additional_info={
                        "alarm_source": "sensor_calibration",
                        "point_id": metadata.point_id,
                        "expired_days": expired_days,
                        "suggested_calibration_date": suggested_date.isoformat(),
                    },
                    created_at=datetime.now(),
                )
                session.add(alarm)
                expired_count += 1

        if expired_count > 0:
            await session.commit()
            logger.info(f"Created {expired_count} calibration maintenance alarms")
        else:
            logger.debug("No expired calibrations found")

    except Exception as e:
        logger.error(f"Failed to check expired calibrations: {e}")
        await session.rollback()
