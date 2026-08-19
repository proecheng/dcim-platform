"""
Redis 分布式锁实现

用于防止电价方案激活时的竞态条件
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


_RECOVERABLE_REDIS_ERRORS = (RedisError, RuntimeError, OSError, AttributeError)


class RedisLock:
    """Redis 分布式锁"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    @asynccontextmanager
    async def acquire(self, key: str, timeout: int = 10):
        """
        获取分布式锁

        Args:
            key: 锁的键名
            timeout: 超时时间（秒）

        Raises:
            TimeoutError: 获取锁超时
        """
        lock_key = f"lock:{key}"
        lock_value = str(uuid.uuid4())

        # 尝试获取锁（最多等待 timeout 秒）
        acquired = False
        start_time = time.time()

        while time.time() - start_time < timeout:
            # SET NX EX：如果不存在则设置，并设置过期时间
            try:
                acquired = await self.redis.set(
                    lock_key,
                    lock_value,
                    nx=True,  # 只在键不存在时设置
                    ex=timeout,  # 过期时间
                )
            except _RECOVERABLE_REDIS_ERRORS as exc:
                raise RedisError(f"Redis lock unavailable for {key}: {exc}") from exc

            if acquired:
                break

            # 等待 100ms 后重试
            await asyncio.sleep(0.1)

        if not acquired:
            raise TimeoutError(f"Failed to acquire lock: {key}")

        try:
            yield
        finally:
            # 释放锁（只有持有锁的进程才能释放）
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                await self.redis.eval(lua_script, 1, lock_key, lock_value)
            except _RECOVERABLE_REDIS_ERRORS as exc:
                logger.warning("Redis lock release failed key=%s: %s", key, exc)


# 全局 Redis 客户端实例（可选）
_redis_client: Optional[aioredis.Redis] = None
_redis_client_loop: Optional[asyncio.AbstractEventLoop] = None


async def _safe_close_redis_client(client: aioredis.Redis) -> None:
    try:
        await client.aclose()
    except AttributeError:
        try:
            await client.close()
        except _RECOVERABLE_REDIS_ERRORS as exc:
            logger.warning("Redis client close failed: %s", exc)
    except _RECOVERABLE_REDIS_ERRORS as exc:
        logger.warning("Redis client close failed: %s", exc)


async def get_redis_client() -> aioredis.Redis:
    """获取 Redis 客户端实例"""
    global _redis_client, _redis_client_loop

    current_loop = asyncio.get_running_loop()
    if _redis_client is not None and _redis_client_loop is not current_loop:
        await _safe_close_redis_client(_redis_client)
        _redis_client = None
        _redis_client_loop = None

    if _redis_client is None:
        _redis_client = await aioredis.from_url(settings.effective_redis_url, encoding="utf-8", decode_responses=True)
        _redis_client_loop = current_loop

    return _redis_client


async def close_redis_client():
    """关闭 Redis 客户端"""
    global _redis_client, _redis_client_loop

    if _redis_client is not None:
        await _safe_close_redis_client(_redis_client)
        _redis_client = None
        _redis_client_loop = None
