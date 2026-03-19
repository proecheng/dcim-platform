"""
告警风暴检测器
Story 34.6 — 告警风暴抑制
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from app.core.redis import redis_service

logger = logging.getLogger(__name__)

# 默认值（SystemConfig 未配置时使用）
DEFAULT_STORM_THRESHOLD = 20
DEFAULT_STORM_WINDOW = 60  # 秒


class StormDetector:
    """告警风暴检测器 — Redis 优先，内存降级"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._counter: dict[int, list[float]] = defaultdict(list)
        self._config_cache: Optional[dict] = None
        self._config_loaded_at: float = 0

    async def get_config(self) -> tuple[int, int]:
        """获取风暴阈值配置（threshold, window），缓存 300 秒"""
        now = time.time()
        if self._config_cache and now - self._config_loaded_at < 300:
            return (
                self._config_cache["threshold"],
                self._config_cache["window"],
            )
        try:
            from app.core.database import async_session
            from app.models.config import SystemConfig
            from sqlalchemy import select

            async with async_session() as session:
                result = await session.execute(
                    select(SystemConfig.config_key, SystemConfig.config_value)
                    .where(
                        SystemConfig.config_group == "notification",
                        SystemConfig.config_key.in_([
                            "storm_threshold", "storm_window"
                        ]),
                    )
                )
                rows = {r[0]: r[1] for r in result.all()}

            threshold = int(rows.get("storm_threshold", DEFAULT_STORM_THRESHOLD))
            window = int(rows.get("storm_window", DEFAULT_STORM_WINDOW))
        except Exception:
            threshold = DEFAULT_STORM_THRESHOLD
            window = DEFAULT_STORM_WINDOW

        self._config_cache = {"threshold": threshold, "window": window}
        self._config_loaded_at = now
        return threshold, window

    async def check_storm(self, site_id: int, count: int = 1) -> bool:
        """
        检测指定站点是否处于告警风暴状态。
        count: 本批次新增告警数量，先递增再判断。
        若递增后总数 >= 阈值则返回 True（本批告警应合并为摘要通知）。
        """
        threshold, window = await self.get_config()

        # Redis 优先
        if redis_service.is_available:
            try:
                if count == 1:
                    total = await redis_service.incr_with_ttl(
                        f"notification:storm:{site_id}", ttl=window
                    )
                else:
                    total = await redis_service.incrby_with_ttl(
                        f"notification:storm:{site_id}", count, ttl=window
                    )
                if total >= 0:
                    return total >= threshold
            except Exception as e:
                logger.warning("风暴检测 Redis 失败，降级内存: %s", e)

        # 内存降级
        return await self._check_storm_memory(site_id, count, threshold, window)

    async def _check_storm_memory(
        self, site_id: int, count: int, threshold: int, window: int
    ) -> bool:
        """内存滑动窗口计数（asyncio.Lock 保护）"""
        async with self._lock:
            now = time.time()
            # 清理过期时间戳
            timestamps = [
                t for t in self._counter[site_id] if now - t < window
            ]
            if not timestamps and count == 0:
                # 无活跃记录且无新增，清理 key 防内存泄漏
                self._counter.pop(site_id, None)
                return False
            # 添加 count 个时间戳
            timestamps.extend([now] * count)
            self._counter[site_id] = timestamps
            return len(timestamps) >= threshold


# 全局单例
storm_detector = StormDetector()
