"""Redis 缓存策略测试 — Story 2.6

12 个测试覆盖 RedisService、cache_service、集成和降级。
所有测试使用 unittest.mock.AsyncMock mock redis.asyncio，不需要真实 Redis。
"""

import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.redis import RedisService, redis_service
from app.models.gateway import PointDataLatest, Gateway
from app.services.cache_service import (
    cache_point_data,
    get_point_latest,
    batch_get_point_latest,
    cache_gateway_status,
    get_gateway_status,
    POINT_CACHE_TTL,
    GATEWAY_CACHE_TTL,
)


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_pool():
    """创建 mock Redis 连接池"""
    pool = AsyncMock()
    pool.ping = AsyncMock()
    pool.get = AsyncMock(return_value=None)
    pool.set = AsyncMock()
    pool.delete = AsyncMock()
    pool.mget = AsyncMock(return_value=[])
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def redis_svc(mock_pool):
    """创建已连接的 RedisService 实例"""
    svc = RedisService()
    svc._pool = mock_pool
    svc._enabled = True
    return svc


# ============================================================
# 1. RedisService set/get 正常读写
# ============================================================

async def test_redis_service_set_get(redis_svc, mock_pool):
    """测试 RedisService.set/get — 正常读写"""
    mock_pool.get.return_value = "hello"

    await redis_svc.set("key1", "hello", ttl=60)
    mock_pool.set.assert_called_once_with("key1", "hello", ex=60)

    result = await redis_svc.get("key1")
    assert result == "hello"
    mock_pool.get.assert_called_once_with("key1")


# ============================================================
# 2. RedisService set — TTL 正确设置
# ============================================================

async def test_redis_service_ttl(redis_svc, mock_pool):
    """测试 RedisService.set — TTL 正确设置"""
    await redis_svc.set("k", "v", ttl=120)
    mock_pool.set.assert_called_once_with("k", "v", ex=120)

    mock_pool.set.reset_mock()
    await redis_svc.set("k2", "v2", ttl=30)
    mock_pool.set.assert_called_once_with("k2", "v2", ex=30)


# ============================================================
# 3. RedisService — Redis 不可用时静默降级
# ============================================================

async def test_redis_service_graceful_degradation():
    """测试 RedisService — Redis 不可用时静默降级（不抛异常）"""
    svc = RedisService()
    # 未连接状态
    assert svc.is_available is False

    # 所有操作应静默返回，不抛异常
    result = await svc.get("any_key")
    assert result is None

    await svc.set("any_key", "value")  # 不抛异常

    await svc.delete("any_key")  # 不抛异常

    mget_result = await svc.mget(["k1", "k2"])
    assert mget_result == [None, None]

    json_result = await svc.get_json("any_key")
    assert json_result is None

    await svc.set_json("any_key", {"a": 1})  # 不抛异常


# ============================================================
# 4. cache_point_data — 正确写入 Redis key 和 JSON 值
# ============================================================

async def test_cache_point_data(redis_svc):
    """测试 cache_point_data — 正确写入 Redis key 和 JSON 值"""
    ts = datetime(2024, 1, 15, 12, 0, 0)

    with patch("app.services.cache_service.redis_service", redis_svc):
        await cache_point_data("p001", "25.6", 0, ts, "gw-001")

    # 验证 set 被调用
    call_args = redis_svc._pool.set.call_args
    assert call_args is not None
    key = call_args[0][0]
    value_str = call_args[0][1]
    ttl = call_args[1]["ex"]

    assert key == "point:p001:latest"
    assert ttl == POINT_CACHE_TTL

    data = json.loads(value_str)
    assert data["v"] == "25.6"
    assert data["q"] == 0
    assert data["t"] == int(ts.timestamp())
    assert data["gw"] == "gw-001"


# ============================================================
# 5. get_point_latest — Redis hit 时直接返回（不查 DB）
# ============================================================

async def test_get_point_latest_redis_hit(redis_svc, db_session):
    """测试 get_point_latest — Redis hit 时直接返回（不查 DB）"""
    cached_data = {"v": "25.6", "q": 0, "t": 1705305600, "gw": "gw-001"}
    redis_svc._pool.get.return_value = json.dumps(cached_data)

    with patch("app.services.cache_service.redis_service", redis_svc):
        result = await get_point_latest("p001", db_session)

    assert result == cached_data
    # 验证 Redis get 被调用
    redis_svc._pool.get.assert_called_once_with("point:p001:latest")


# ============================================================
# 6. get_point_latest — Redis miss 时查 DB 并回填缓存
# ============================================================

async def test_get_point_latest_redis_miss_db_hit(redis_svc, db_session):
    """测试 get_point_latest — Redis miss 时查 DB 并回填缓存"""
    redis_svc._pool.get.return_value = None  # Redis miss

    # 在 DB 中插入数据
    ts = datetime(2024, 1, 15, 12, 0, 0)
    record = PointDataLatest(
        point_id="p002", value="30.5", quality=0,
        timestamp=ts, gateway_id="gw-002",
    )
    db_session.add(record)
    await db_session.commit()

    with patch("app.services.cache_service.redis_service", redis_svc):
        result = await get_point_latest("p002", db_session)

    assert result is not None
    assert result["v"] == "30.5"
    assert result["q"] == 0
    assert result["gw"] == "gw-002"

    # 验证回填缓存（set 被调用）
    assert redis_svc._pool.set.called


# ============================================================
# 7. cache_gateway_status — 正确写入 Redis key 和 JSON 值
# ============================================================

async def test_cache_gateway_status(redis_svc):
    """测试 cache_gateway_status — 正确写入 Redis key 和 JSON 值"""
    with patch("app.services.cache_service.redis_service", redis_svc):
        await cache_gateway_status("gw-001", "online", cpu=45.2, mem=60.1, disk=30.5)

    call_args = redis_svc._pool.set.call_args
    assert call_args is not None
    key = call_args[0][0]
    value_str = call_args[0][1]
    ttl = call_args[1]["ex"]

    assert key == "gateway:gw-001:status"
    assert ttl == GATEWAY_CACHE_TTL

    data = json.loads(value_str)
    assert data["status"] == "online"
    assert data["cpu"] == 45.2
    assert data["mem"] == 60.1
    assert data["disk"] == 30.5
    assert "ts" in data


# ============================================================
# 8. get_gateway_status — Redis hit / miss 两种路径
# ============================================================

async def test_get_gateway_status_hit_and_miss(redis_svc, db_session):
    """测试 get_gateway_status — Redis hit / miss 两种路径"""
    # --- hit 路径 ---
    cached_data = {"status": "online", "cpu": 45.2, "mem": 60.1, "disk": 30.5, "ts": 1705305600}
    redis_svc._pool.get.return_value = json.dumps(cached_data)

    with patch("app.services.cache_service.redis_service", redis_svc):
        result = await get_gateway_status("gw-001", db_session)
    assert result == cached_data

    # --- miss 路径 ---
    redis_svc._pool.get.return_value = None
    redis_svc._pool.set.reset_mock()

    gw = Gateway(
        gateway_id="gw-002", name="测试网关", status="online",
        cpu_usage=50.0, memory_usage=70.0, disk_usage=40.0,
        last_heartbeat=datetime(2024, 1, 15, 12, 0, 0),
    )
    db_session.add(gw)
    await db_session.commit()

    with patch("app.services.cache_service.redis_service", redis_svc):
        result = await get_gateway_status("gw-002", db_session)

    assert result is not None
    assert result["status"] == "online"
    assert result["cpu"] == 50.0
    assert result["mem"] == 70.0
    assert result["disk"] == 40.0
    # 验证回填
    assert redis_svc._pool.set.called


# ============================================================
# 9. handle_point_data 集成 — 写入 DB 后同步写入缓存
# ============================================================

async def test_handle_point_data_calls_cache(db_session):
    """测试 handle_point_data 集成 — 写入 DB 后同步写入缓存"""
    from app.services.point_data import handle_point_data

    payload = {
        "gw_id": "gw-001",
        "points": [
            {"id": "p001", "v": 25.6, "q": 0, "t": int(time.time())},
        ],
    }

    with patch("app.services.point_data.cache_point_data", new_callable=AsyncMock) as mock_cache:
        count = await handle_point_data(payload, db_session)

    assert count == 1
    mock_cache.assert_called_once()
    call_args = mock_cache.call_args
    assert call_args[0][0] == "p001"  # point_id
    assert call_args[0][4] == "gw-001"  # gateway_id


# ============================================================
# 10. handle_gateway_status 集成 — 写入 DB 后同步写入缓存
# ============================================================

async def test_handle_gateway_status_calls_cache(db_session):
    """测试 handle_gateway_status 集成 — 写入 DB 后同步写入缓存"""
    from app.services.gateway_registration import handle_gateway_status

    payload = {
        "gw_id": "gw-cache-001",
        "name": "缓存测试网关",
        "ip": "192.168.1.100",
        "cpu": 45.0,
        "mem": 60.0,
        "disk": 30.0,
    }

    with patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock) as mock_cache:
        await handle_gateway_status(payload, db_session)

    mock_cache.assert_called_once()
    call_args = mock_cache.call_args
    assert call_args[0][0] == "gw-cache-001"  # gateway_id
    assert call_args[0][1] == "online"  # status
    assert call_args[1]["cpu"] == 45.0
    assert call_args[1]["mem"] == 60.0
    assert call_args[1]["disk"] == 30.0


# ============================================================
# 11. Redis 降级 — Redis 断开时 handle_point_data 仍正常写入 DB
# ============================================================

async def test_handle_point_data_degradation(db_session):
    """测试 Redis 降级 — Redis 断开时 handle_point_data 仍正常写入 DB"""
    from app.services.point_data import handle_point_data

    payload = {
        "gw_id": "gw-001",
        "points": [
            {"id": "p-degrade-001", "v": 99.9, "q": 0, "t": int(time.time())},
        ],
    }

    # redis_service 未连接（默认状态），cache_point_data 内部会静默失败
    # 确保 redis_service 处于不可用状态
    original_enabled = redis_service._enabled
    original_pool = redis_service._pool
    redis_service._enabled = False
    redis_service._pool = None

    try:
        count = await handle_point_data(payload, db_session)
    finally:
        redis_service._enabled = original_enabled
        redis_service._pool = original_pool

    # DB 写入应正常
    assert count == 1
    result = await db_session.execute(
        select(PointDataLatest).where(PointDataLatest.point_id == "p-degrade-001")
    )
    record = result.scalar_one()
    assert record.value == "99.9"


# ============================================================
# 12. batch_get_point_latest — 批量获取，部分 hit 部分 miss
# ============================================================

async def test_batch_get_point_latest(redis_svc, db_session):
    """测试 batch_get_point_latest — 批量获取，部分 hit 部分 miss"""
    # p001 在 Redis 中有缓存，p002 miss 但在 DB 中，p003 完全不存在
    cached_p001 = json.dumps({"v": "25.6", "q": 0, "t": 1705305600, "gw": "gw-001"})
    redis_svc._pool.mget.return_value = [cached_p001, None, None]

    # p002 在 DB 中
    ts = datetime(2024, 1, 15, 12, 0, 0)
    record = PointDataLatest(
        point_id="p002", value="30.5", quality=0,
        timestamp=ts, gateway_id="gw-002",
    )
    db_session.add(record)
    await db_session.commit()

    with patch("app.services.cache_service.redis_service", redis_svc):
        results = await batch_get_point_latest(["p001", "p002", "p003"], db_session)

    # p001: Redis hit
    assert results["p001"] is not None
    assert results["p001"]["v"] == "25.6"

    # p002: DB hit + 回填
    assert results["p002"] is not None
    assert results["p002"]["v"] == "30.5"

    # p003: 完全不存在
    assert results["p003"] is None

    # 验证 mget 被调用
    redis_svc._pool.mget.assert_called_once()
