"""
环境上下文服务
Story 25.6: 动态告警阈值

提供环境上下文数据（室外温度、IT负载百分比、季节等）
从 Redis 读取数据，支持优雅降级
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import select, and_

from app.core.database import async_session
from app.core.redis import redis_service
from app.models.point import Point
from app.models.device import Device

logger = logging.getLogger(__name__)


class EnvironmentContextService:
    """环境上下文服务 - 从 Redis 读取环境数据"""

    # 缓存
    _cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()
    _cache_ttl = int(os.getenv("ENVIRONMENT_CONTEXT_CACHE_TTL", "60"))  # 缓存有效期（秒），可通过环境变量配置

    # 数据时效性阈值（秒）
    _data_freshness_threshold = int(os.getenv("ENVIRONMENT_DATA_FRESHNESS_THRESHOLD", "600"))  # 10 分钟，可配置

    @classmethod
    async def get_context(cls) -> Dict[str, Any]:
        """
        获取环境上下文数据（从 Redis 读取）

        Returns:
            Dict[str, Any]: 环境上下文字典，包含:
                - outdoor_temp: 室外温度 (float)
                - it_load_percent: IT负载百分比 (float)
                - season: 季节 (str: spring/summer/autumn/winter)
                - timestamp: 数据时间戳 (float, Unix timestamp)
        """
        async with cls._cache_lock:
            # 检查缓存
            if cls._cache and cls._is_cache_valid():
                return cls._cache.copy()

            # 重新加载数据
            context = await cls._load_context()
            cls._cache = context
            return context.copy()

    @classmethod
    def _is_cache_valid(cls) -> bool:
        """检查缓存是否有效"""
        if not cls._cache or "timestamp" not in cls._cache:
            return False

        timestamp = cls._cache["timestamp"]
        elapsed = time.time() - timestamp
        return elapsed < cls._cache_ttl

    @classmethod
    async def _load_context(cls) -> Dict[str, Any]:
        """
        加载环境上下文数据（从 Redis 读取）

        Returns:
            Dict[str, Any]: 环境上下文，包含默认值（Redis 不可用时）
        """
        now = time.time()

        # 默认值（Redis 不可用或数据过期时使用）
        context = {
            "outdoor_temp": 25.0,  # 默认室外温度 25℃
            "it_load_percent": 50.0,  # 默认 IT 负载 50%
            "season": cls._get_current_season(),
            "timestamp": now,
        }

        try:
            # 从 Redis 读取室外温度
            outdoor_temp_value = await redis_service.get("outdoor_temp")
            outdoor_temp_time = await redis_service.get("outdoor_temp:timestamp")

            # 检查数据时效性（10分钟）
            if outdoor_temp_time:
                try:
                    data_age = now - float(outdoor_temp_time)
                except (ValueError, TypeError):
                    data_age = cls._data_freshness_threshold + 1  # 视为过期
                if data_age > cls._data_freshness_threshold:
                    logger.warning(f"室外温度数据过期（{data_age:.0f}秒），使用默认值 {context['outdoor_temp']}℃")
                elif outdoor_temp_value:
                    try:
                        context["outdoor_temp"] = float(outdoor_temp_value)
                    except (ValueError, TypeError):
                        pass
            elif outdoor_temp_value:
                # 有值但无时间戳，直接使用
                try:
                    context["outdoor_temp"] = float(outdoor_temp_value)
                except (ValueError, TypeError):
                    pass

            # 计算 IT 负载百分比
            it_load = await cls._calculate_it_load_percent()
            if it_load is not None:
                context["it_load_percent"] = it_load

        except Exception as e:
            logger.warning(f"加载环境上下文失败: {e}，使用默认值")

        return context

    @classmethod
    async def _calculate_it_load_percent(cls) -> Optional[float]:
        """
        计算 IT 负载百分比

        计算逻辑:
        1. 从 point_realtime 表查询所有 point_type='AI' 且 unit='kW' 的启用点位实时值
        2. 从 devices 表查询所有 device_type='rack' 的启用设备额定功率
        3. 计算: sum(实时功率) / sum(额定功率) × 100%
        4. 结果写入 Redis key "it_load_percent"，TTL 60 秒

        Returns:
            Optional[float]: IT 负载百分比，计算失败返回 None
        """
        try:
            # 先尝试从 Redis 读取缓存
            cached_value = await redis_service.get("it_load_percent")
            if cached_value:
                return float(cached_value)

            # 缓存未命中，重新计算
            async with async_session() as session:
                # 1. 查询所有功率点位的实时值（AI 类型，单位 kW，且点位名称包含 rack 或 cabinet）
                power_points_query = select(Point.id, Point.point_name).where(
                    and_(
                        Point.point_type == "AI",
                        Point.unit.like("%kW%"),
                        Point.is_enabled == True,
                        # 过滤：仅包含机柜相关的功率点位
                        (
                            Point.point_name.like("%rack%")
                            | Point.point_name.like("%cabinet%")
                            | Point.point_name.like("%机柜%")
                        ),
                    )
                )
                power_points_result = await session.execute(power_points_query)
                power_points = power_points_result.all()

                if not power_points:
                    logger.warning(
                        "未找到机柜功率点位（point_type=AI, unit=kW, name contains rack/cabinet），无法计算 IT 负载"
                    )
                    return None

                logger.debug(f"找到 {len(power_points)} 个机柜功率点位")

                # 2. 从 Redis 读取实时功率值并求和
                total_power = 0.0
                valid_count = 0
                for point_id, point_name in power_points:
                    value_str = await redis_service.get(f"point:realtime:{point_id}")
                    if value_str:
                        try:
                            power_value = float(value_str)
                            total_power += power_value
                            valid_count += 1
                        except (ValueError, TypeError):
                            logger.warning(f"点位 {point_name} 实时值格式错误: {value_str}")

                if valid_count == 0:
                    logger.warning("所有功率点位实时值无效，无法计算 IT 负载")
                    return None

                # 3. 查询所有机柜的额定功率
                racks_query = select(Device.rated_power).where(
                    and_(Device.device_type == "rack", Device.enabled == True, Device.rated_power.isnot(None))
                )
                racks_result = await session.execute(racks_query)
                rated_powers = racks_result.scalars().all()

                if not rated_powers:
                    logger.warning("未找到启用的机柜设备（device_type=rack），无法计算 IT 负载")
                    return None

                total_rated_power = sum(rated_powers)

                if total_rated_power == 0:
                    logger.warning("机柜总额定功率为 0，无法计算 IT 负载")
                    return None

                # 4. 计算负载百分比
                it_load_percent = (total_power / total_rated_power) * 100.0

                # 5. 写入 Redis 缓存（TTL 60秒）
                await redis_service.set("it_load_percent", str(it_load_percent), ttl=60)

                logger.debug(
                    f"IT 负载计算完成: {total_power:.2f}kW / {total_rated_power:.2f}kW = {it_load_percent:.2f}% "
                    f"(有效点位: {valid_count}/{len(power_points)})"
                )

                return it_load_percent

        except Exception as e:
            logger.error(f"计算 IT 负载百分比失败: {e}")
            return None

    @classmethod
    def _get_current_season(cls) -> str:
        """
        获取当前季节

        Returns:
            str: 季节名称 (spring/summer/autumn/winter)
        """
        month = datetime.now().month

        if month in (3, 4, 5):
            return "spring"
        elif month in (6, 7, 8):
            return "summer"
        elif month in (9, 10, 11):
            return "autumn"
        else:  # 12, 1, 2
            return "winter"

    @classmethod
    async def clear_cache(cls):
        """清除缓存（用于测试或手动刷新）"""
        async with cls._cache_lock:
            cls._cache = {}
