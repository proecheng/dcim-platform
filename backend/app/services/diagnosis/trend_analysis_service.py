"""
趋势分析服务
Story 25.7: 趋势分析与多传感器融合
"""

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_lock import get_redis_client
from app.models.diagnosis import TrendWarning
from app.models.history import PointHistory
from app.models.point import Point
from app.models.topology_config import CabinetTemperatureSensor, CoolingZoneCabinet

logger = logging.getLogger(__name__)
_REDIS_UNSET = object()


class TrendAnalysisService:
    """趋势分析服务"""

    def __init__(self, db: AsyncSession, redis: Any = _REDIS_UNSET):
        self.db = db
        self.redis = None if redis is _REDIS_UNSET else redis
        self._load_redis = redis is _REDIS_UNSET

    async def analyze_point_trend(self, point_id: int) -> Optional[TrendWarning]:
        """
        分析点位趋势（改进版：容错、数据质量、动态阈值）

        Args:
            point_id: 点位ID

        Returns:
            TrendWarning 或 None（数据不足或无趋势）
        """
        # 获取点位信息（提前获取以确定视图类型）
        point_info = await self._get_point_info(point_id)
        if not point_info:
            logger.warning(f"Point {point_id} not found")
            return None

        if point_info.unit not in ["℃", "°C"] and "RH" not in point_info.unit and "湿度" not in point_info.unit:
            logger.debug(f"Point {point_id} unit '{point_info.unit}' not supported for trend analysis")
            return None

        # 直接从规范化历史表聚合，兼容 PostgreSQL 与 SQLite 测试环境。
        day = func.date(PointHistory.recorded_at)
        query = (
            select(
                day.label("day"),
                func.avg(PointHistory.value).label("avg_value"),
                func.count(PointHistory.id).label("sample_count"),
            )
            .where(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= datetime.now() - timedelta(days=7),
                or_(PointHistory.quality.is_(None), PointHistory.quality != 2),
            )
            .group_by(day)
            .order_by(day)
        )
        result = await self.db.execute(query)
        daily_avgs = result.fetchall()

        # 2. 检查数据充足性（至少 5 天有效数据）
        valid_days = [row for row in daily_avgs if row.sample_count >= 10]
        if len(valid_days) < 5:
            logger.debug(
                f"Insufficient data for trend analysis on point {point_id} "
                f"({len(valid_days)} valid days available, 5 required)"
            )

            # 连续数据不足检测
            await self._check_continuous_insufficient_data(point_id, len(valid_days))
            return None

        # 3. 检测连续 3 天趋势（允许容差）
        last_3_days = valid_days[-3:]
        values = [float(row.avg_value) for row in last_3_days if row.avg_value is not None]

        # 容差设置
        tolerance = 0.1 if point_info.unit in ["℃", "°C"] else 0.5  # 温度 0.1℃，湿度 0.5%RH

        # 趋势检测（允许容差）
        is_increasing = all(values[i + 1] - values[i] > -tolerance for i in range(len(values) - 1))
        is_decreasing = all(values[i] - values[i + 1] > -tolerance for i in range(len(values) - 1))

        # 整体趋势判断
        overall_change = values[-1] - values[0]
        has_trend = (is_increasing and overall_change > tolerance) or (is_decreasing and overall_change < -tolerance)

        if not has_trend:
            return None

        # 4. 计算 3 天累计变化量
        total_change = abs(overall_change)

        # 5. 从配置读取阈值（按点位单位）
        threshold = await self._get_trend_threshold(point_info.unit)

        # 6. 判断是否触发预警
        if total_change > threshold:
            trend_type = "上升" if overall_change > 0 else "下降"
            message = (
                f"{point_info.point_name} 连续3天呈{trend_type}趋势"
                f"（均值从{values[0]:.1f}→{values[1]:.1f}→{values[2]:.1f}），"
                f"建议检查空调运行状态"
            )

            return TrendWarning(
                point_id=point_id,
                trend_type=trend_type,
                start_value=values[0],
                end_value=values[-1],
                total_change=total_change,
                message=message,
                level="info",  # 明确级别
                detected_at=datetime.now(),
            )

        return None

    async def _check_continuous_insufficient_data(self, point_id: int, available_days: int):
        """检查连续数据不足，生成系统告警"""
        if self._load_redis:
            self._load_redis = False
            try:
                self.redis = await get_redis_client()
            except Exception as exc:
                logger.warning("Redis not available: %s", exc)

        # 检查 Redis 是否可用
        if not self.redis:
            logger.warning("Redis not available, skipping continuous insufficient data check")
            return

        try:
            cache_key = f"insufficient_data:{point_id}"
            count = await self.redis.incr(cache_key)
            await self.redis.expire(cache_key, 3600 * 4)  # 4 小时过期

            if count >= 3:  # 连续 3 次（3 小时）数据不足
                logger.warning(f"Point {point_id} has insufficient data for 3 consecutive hours")
                # 生成系统告警
                await self._create_system_alarm(
                    point_id=point_id,
                    message=f"点位 {point_id} 连续 3 小时数据不足（仅 {available_days} 天），请检查数据采集",
                    level="warning",
                )
                await self.redis.delete(cache_key)  # 重置计数
        except Exception as e:
            logger.error(f"Failed to check continuous insufficient data for point {point_id}: {e}")

    async def _get_point_info(self, point_id: int) -> Optional[Point]:
        """获取点位信息"""
        result = await self.db.execute(select(Point).where(Point.id == point_id))
        return result.scalar_one_or_none()

    async def _get_trend_threshold(self, unit: str) -> float:
        """从配置读取趋势阈值"""
        # 根据点位单位确定配置键
        if unit in ["℃", "°C"]:
            config_key = "trend_threshold_temperature"
            default_value = 0.5
        elif "RH" in unit or "湿度" in unit:
            config_key = "trend_threshold_humidity"
            default_value = 3.0
        else:
            # 默认使用温度阈值
            config_key = "trend_threshold_temperature"
            default_value = 0.5

        # 从 system_configs 表读取
        query = text("""
            SELECT config_value FROM system_configs
            WHERE config_group = 'diagnosis' AND config_key = :config_key
        """)
        result = await self.db.execute(query, {"config_key": config_key})
        row = result.fetchone()

        if row:
            return float(row.config_value)
        return default_value

    async def _create_system_alarm(self, point_id: int, message: str, level: str):
        """创建系统告警"""
        try:
            # 导入放在方法内避免循环依赖
            from app.models.alarm import Alarm

            alarm = Alarm(
                alarm_no=f"SYS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{point_id}",
                point_id=point_id,
                alarm_type="system",
                level=level,
                message=message,
                status="active",
                triggered_at=datetime.now(),
            )
            self.db.add(alarm)
            await self.db.commit()
            logger.info(f"Created system alarm for point {point_id}: {message}")
        except Exception as e:
            logger.error(f"Failed to create system alarm for point {point_id}: {e}")
            await self.db.rollback()

    async def get_recent_warnings(self, zone_id: Optional[int] = None, hours: int = 24) -> List[TrendWarning]:
        """
        获取最近的趋势预警

        Args:
            zone_id: 区域ID（可选）
            hours: 时间范围（小时）

        Returns:
            趋势预警列表
        """
        query = select(TrendWarning).where(TrendWarning.detected_at >= datetime.now() - timedelta(hours=hours))

        if zone_id is not None:
            query = (
                query.join(Point, TrendWarning.point_id == Point.id)
                .join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
                .join(
                    CoolingZoneCabinet,
                    CoolingZoneCabinet.cabinet_id == CabinetTemperatureSensor.cabinet_id,
                )
                .where(CoolingZoneCabinet.zone_id == zone_id)
                .distinct()
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())


# 全局服务实例（依赖注入时使用）
trend_analysis_service: Optional[TrendAnalysisService] = None


def get_trend_analysis_service(db: AsyncSession, redis: Any = _REDIS_UNSET) -> TrendAnalysisService:
    """获取趋势分析服务实例"""
    return TrendAnalysisService(db, redis=redis)
