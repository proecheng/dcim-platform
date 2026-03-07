"""
环境上下文服务
Story 25.6: 动态告警阈值

提供环境上下文数据（室外温度、IT负载百分比、季节等）
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.point import Point
from app.models.history import PointHistory

logger = logging.getLogger(__name__)


class EnvironmentContextService:
    """环境上下文服务"""

    # 数据源定义（点位名称映射）
    DATA_SOURCE_MAPPING = {
        "outdoor_temp": "室外温度",  # 室外温度传感器点位名称
        "it_load_percent": "IT负载率",  # IT负载百分比点位名称
        "humidity": "室外湿度",  # 室外湿度传感器点位名称
    }

    # 缓存
    _cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()
    _cache_ttl = 60  # 缓存有效期 60 秒（符合 Task 3.3 要求）

    @classmethod
    async def get_context(cls) -> Dict[str, Any]:
        """
        获取环境上下文数据

        Returns:
            Dict[str, Any]: 环境上下文字典，包含:
                - outdoor_temp: 室外温度 (float)
                - it_load_percent: IT负载百分比 (float)
                - season: 季节 (str: spring/summer/autumn/winter)
                - humidity: 室外湿度 (float)
                - timestamp: 数据时间戳 (datetime)
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
        elapsed = (datetime.now() - timestamp).total_seconds()
        return elapsed < cls._cache_ttl

    @classmethod
    async def _load_context(cls) -> Dict[str, Any]:
        """加载环境上下文数据"""
        context = {
            "outdoor_temp": None,
            "it_load_percent": None,
            "season": cls._get_current_season(),
            "humidity": None,
            "timestamp": datetime.now()
        }

        try:
            async with async_session() as session:
                # 加载室外温度
                outdoor_temp = await cls._get_latest_point_value(
                    session, cls.DATA_SOURCE_MAPPING["outdoor_temp"]
                )
                if outdoor_temp is not None:
                    context["outdoor_temp"] = outdoor_temp

                # 加载 IT 负载百分比
                it_load = await cls._get_latest_point_value(
                    session, cls.DATA_SOURCE_MAPPING["it_load_percent"]
                )
                if it_load is not None:
                    context["it_load_percent"] = it_load

                # 加载室外湿度
                humidity = await cls._get_latest_point_value(
                    session, cls.DATA_SOURCE_MAPPING["humidity"]
                )
                if humidity is not None:
                    context["humidity"] = humidity

        except Exception as e:
            logger.error(f"加载环境上下文失败: {e}")

        return context

    @classmethod
    async def _get_latest_point_value(
        cls, session: AsyncSession, point_name: str
    ) -> Optional[float]:
        """
        获取点位最新值

        Args:
            session: 数据库会话
            point_name: 点位名称

        Returns:
            Optional[float]: 点位最新值，不存在返回 None
        """
        try:
            # 查询点位 ID
            result = await session.execute(
                select(Point.id).where(Point.point_name == point_name)
            )
            point = result.scalar_one_or_none()
            if not point:
                return None

            # 查询最新历史记录
            result = await session.execute(
                select(PointHistory.value)
                .where(PointHistory.point_id == point)
                .order_by(PointHistory.timestamp.desc())
                .limit(1)
            )
            value = result.scalar_one_or_none()
            return float(value) if value is not None else None

        except Exception as e:
            logger.error(f"查询点位 {point_name} 最新值失败: {e}")
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
