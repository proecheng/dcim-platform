"""Redis lock degradation tests."""

import pytest
from redis.exceptions import RedisError

from app.core.redis_lock import RedisLock


class _AcquireBrokenRedis:
    async def set(self, *args, **kwargs):
        raise RuntimeError("Event loop is closed")


class _ReleaseBrokenRedis:
    async def set(self, *args, **kwargs):
        return True

    async def eval(self, *args, **kwargs):
        raise RuntimeError("Event loop is closed")


async def test_redis_lock_wraps_closed_loop_acquire_failure():
    lock = RedisLock(_AcquireBrokenRedis())

    with pytest.raises(RedisError, match="Redis lock unavailable"):
        async with lock.acquire("pricing_scheme_activation", timeout=1):
            raise AssertionError("lock body should not run")


async def test_redis_lock_release_failure_does_not_mask_business_error():
    lock = RedisLock(_ReleaseBrokenRedis())

    with pytest.raises(ValueError, match="business failed"):
        async with lock.acquire("pricing_scheme_activation", timeout=1):
            raise ValueError("business failed")
