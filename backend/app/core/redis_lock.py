"""
Redis 分布式锁实现

用于防止电价方案激活时的竞态条件
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from redis import asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()


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
            acquired = await self.redis.set(
                lock_key,
                lock_value,
                nx=True,  # 只在键不存在时设置
                ex=timeout,  # 过期时间
            )

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
            await self.redis.eval(lua_script, 1, lock_key, lock_value)


# 全局 Redis 客户端实例（可选）
_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """获取 Redis 客户端实例"""
    global _redis_client

    if _redis_client is None:
        _redis_client = await aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

    return _redis_client


async def close_redis_client():
    """关闭 Redis 客户端"""
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
