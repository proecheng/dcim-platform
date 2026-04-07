"""Redis 缓存服务 — Story 2.6"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisService:
    """Redis 缓存服务 — 优雅降级：Redis 不可用时静默失败"""

    def __init__(self) -> None:
        self._pool = None
        self._enabled = False

    async def connect(self, redis_url: str = "redis://localhost:6379/0") -> None:
        """创建 Redis 连接池"""
        try:
            import redis.asyncio as aioredis

            self._pool = aioredis.from_url(
                redis_url,
                decode_responses=True,
                max_connections=20,
            )
            # 测试连接
            await self._pool.ping()
            self._enabled = True
            logger.info("Redis 已连接: %s", redis_url)
        except Exception as e:
            self._pool = None
            self._enabled = False
            logger.warning("Redis 连接失败，降级为直接查库模式: %s", e)

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._enabled = False
            logger.info("Redis 连接已关闭")

    @property
    def is_available(self) -> bool:
        return self._enabled and self._pool is not None

    async def get(self, key: str) -> Optional[str]:
        """获取值，Redis 不可用时返回 None"""
        if not self.is_available:
            return None
        try:
            return await self._pool.get(key)
        except Exception as e:
            logger.warning("Redis GET 失败 key=%s: %s", key, e)
            return None

    async def set(self, key: str, value: str, ttl: int = 60) -> None:
        """设置值+TTL，Redis 不可用时静默失败"""
        if not self.is_available:
            return
        try:
            await self._pool.set(key, value, ex=ttl)
        except Exception as e:
            logger.warning("Redis SET 失败 key=%s: %s", key, e)

    async def delete(self, key: str) -> None:
        """删除 key，Redis 不可用时静默失败"""
        if not self.is_available:
            return
        try:
            await self._pool.delete(key)
        except Exception as e:
            logger.warning("Redis DELETE 失败 key=%s: %s", key, e)

    async def mget(self, keys: list[str]) -> list[Optional[str]]:
        """批量获取值，Redis 不可用时返回全 None 列表"""
        if not self.is_available or not keys:
            return [None] * len(keys)
        try:
            return await self._pool.mget(keys)
        except Exception as e:
            logger.warning("Redis MGET 失败: %s", e)
            return [None] * len(keys)

    async def get_json(self, key: str) -> Optional[dict]:
        """获取 JSON 值"""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: dict, ttl: int = 60) -> None:
        """设置 JSON 值"""
        await self.set(key, json.dumps(value, ensure_ascii=False), ttl)

    async def sismember(self, key: str, member: str) -> bool:
        """检查 SET 中是否存在成员，Redis 不可用时返回 False"""
        if not self.is_available:
            return False
        try:
            return bool(await self._pool.sismember(key, member))
        except Exception as e:
            logger.warning("Redis SISMEMBER 失败 key=%s: %s", key, e)
            return False

    async def sadd_with_ttl(self, key: str, member: str, ttl: int = 3600) -> None:
        """向 SET 添加成员并设置 TTL，Redis 不可用时静默失败"""
        if not self.is_available:
            return
        try:
            await self._pool.sadd(key, member)
            await self._pool.expire(key, ttl)
        except Exception as e:
            logger.warning("Redis SADD 失败 key=%s: %s", key, e)

    async def incr_with_ttl(self, key: str, ttl: int = 60) -> int:
        """原子递增+TTL，Redis 不可用时返回 -1"""
        if not self.is_available:
            return -1
        try:
            pipe = self._pool.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning("Redis INCR 失败 key=%s: %s", key, e)
            return -1

    async def incrby_with_ttl(self, key: str, amount: int, ttl: int = 60) -> int:
        """原子批量递增+TTL，Redis 不可用时返回 -1"""
        if not self.is_available:
            return -1
        try:
            pipe = self._pool.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning("Redis INCRBY 失败 key=%s: %s", key, e)
            return -1

    def set_with_expiry(self, key: str, value: str, ttl: int) -> bool:
        """同步方式设置值+TTL（用于分布式锁），返回是否成功"""
        if not self.is_available:
            return False
        try:
            import redis

            # 从配置获取 Redis URL
            from app.core.config import get_settings

            settings = get_settings()

            # 使用同步 Redis 客户端进行 SET NX EX 操作
            sync_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            result = sync_client.set(key, value, nx=True, ex=ttl)
            sync_client.close()
            return bool(result)
        except Exception as e:
            logger.warning("Redis SET NX 失败 key=%s: %s", key, e)
            return False

    def delete(self, key: str) -> None:
        """同步方式删除 key（用于释放分布式锁）"""
        if not self.is_available:
            return
        try:
            import redis

            # 从配置获取 Redis URL
            from app.core.config import get_settings

            settings = get_settings()

            sync_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            sync_client.delete(key)
            sync_client.close()
        except Exception as e:
            logger.warning("Redis DELETE 失败 key=%s: %s", key, e)


# 全局单例
redis_service = RedisService()
