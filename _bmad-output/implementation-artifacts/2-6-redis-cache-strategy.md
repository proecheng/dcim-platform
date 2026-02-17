# Story 2.6: Redis 缓存策略实现

Status: done

## Story

As a 开发者,
I want 实现 Redis 缓存策略,
So that 实时数据可以通过缓存快速访问，支撑 WebSocket 推送和仪表盘展示。

## Acceptance Criteria (验收标准)

1. **AC-1: Redis 服务封装** — 创建 `RedisService` 类，封装 redis.asyncio 连接池，提供 `get/set/delete/exists` 等基础操作，支持连接池管理和优雅关闭
2. **AC-2: 点位数据缓存** — Key 模式 `point:{id}:latest`，TTL 60s，存储最新点位值（JSON: `{"v": "25.6", "q": 0, "t": 1708000000, "gw": "gw-001"}`）
3. **AC-3: 网关状态缓存** — Key 模式 `gateway:{id}:status`，TTL 30s，存储网关心跳状态（JSON: `{"status": "online", "cpu": 45.2, "mem": 60.1, "disk": 30.5, "ts": 1708000000}`）
4. **AC-4: Write-through 策略** — 在 `handle_point_data` 和 `handle_gateway_status` 中，数据写入 DB 的同时写入 Redis 缓存
5. **AC-5: Read-through 策略** — 提供 `get_point_latest` 和 `get_gateway_status` 方法，优先从 Redis 读取，miss 时从 DB 读取并回填缓存
6. **AC-6: 优雅降级** — Redis 连接断开时，所有缓存操作静默失败（仅 log warning），系统降级为直接查库模式，不影响核心业务
7. **AC-7: 配置集成** — Settings 新增 `redis_enabled`, `redis_url` 配置项，默认 `redis://localhost:6379/0`
8. **AC-8: 缓存失效** — 数据更新时同步更新缓存（write-through），TTL 到期自动失效

## Tasks / Subtasks (任务分解)

- [ ] Task 1: Settings 配置 (AC: #7)
  - [ ] 1.1 在 `backend/app/core/config.py` 的 Settings 中新增 `redis_enabled: bool = True`, `redis_url: str = "redis://localhost:6379/0"`

- [ ] Task 2: Redis 服务封装 (AC: #1, #6)
  - [ ] 2.1 创建 `backend/app/core/redis.py` — `RedisService` 类
  - [ ] 2.2 `connect()` 方法：创建 redis.asyncio 连接池
  - [ ] 2.3 `close()` 方法：关闭连接池
  - [ ] 2.4 `get(key)` 方法：获取值，Redis 不可用时返回 None
  - [ ] 2.5 `set(key, value, ttl)` 方法：设置值+TTL，Redis 不可用时静默失败
  - [ ] 2.6 `delete(key)` 方法：删除 key，Redis 不可用时静默失败
  - [ ] 2.7 `mget(keys)` 方法：批量获取值，Redis 不可用时返回全 None 列表
  - [ ] 2.8 全局单例 `redis_service` 实例

- [ ] Task 3: 缓存数据服务 (AC: #2, #3, #4, #5, #8)
  - [ ] 3.1 创建 `backend/app/services/cache_service.py`
  - [ ] 3.2 `cache_point_data(point_id, value, quality, timestamp, gateway_id)` — 写入 `point:{id}:latest`，TTL 60s
  - [ ] 3.3 `get_point_latest(point_id, db)` — 先查 Redis，miss 则查 DB 并回填
  - [ ] 3.4 `batch_get_point_latest(point_ids, db)` — 批量获取点位最新值
  - [ ] 3.5 `cache_gateway_status(gateway_id, status, cpu, mem, disk)` — 写入 `gateway:{id}:status`，TTL 30s
  - [ ] 3.6 `get_gateway_status(gateway_id, db)` — 先查 Redis，miss 则查 DB 并回填

- [ ] Task 4: 集成到现有服务 (AC: #4)
  - [ ] 4.1 修改 `backend/app/services/point_data.py` — `handle_point_data` 写入 DB 后调用 `cache_point_data`
  - [ ] 4.2 修改 `backend/app/services/gateway_registration.py` — `handle_gateway_status` 写入 DB 后调用 `cache_gateway_status`

- [ ] Task 5: 应用生命周期集成 (AC: #1)
  - [ ] 5.1 修改 `backend/app/main.py` — startup 时调用 `redis_service.connect()`，shutdown 时调用 `redis_service.close()`

- [ ] Task 6: 单元测试 (AC: 全部)
  - [ ] 6.1 测试 RedisService.set/get — 正常读写（mock redis.asyncio）
  - [ ] 6.2 测试 RedisService.set — TTL 正确设置
  - [ ] 6.3 测试 RedisService — Redis 不可用时静默降级（不抛异常）
  - [ ] 6.4 测试 cache_point_data — 正确写入 Redis key 和 JSON 值
  - [ ] 6.5 测试 get_point_latest — Redis hit 时直接返回（不查 DB）
  - [ ] 6.6 测试 get_point_latest — Redis miss 时查 DB 并回填缓存
  - [ ] 6.7 测试 cache_gateway_status — 正确写入 Redis key 和 JSON 值
  - [ ] 6.8 测试 get_gateway_status — Redis hit / miss 两种路径
  - [ ] 6.9 测试 handle_point_data 集成 — 写入 DB 后同步写入缓存
  - [ ] 6.10 测试 handle_gateway_status 集成 — 写入 DB 后同步写入缓存
  - [ ] 6.11 测试 Redis 降级 — Redis 断开时 handle_point_data 仍正常写入 DB
  - [ ] 6.12 测试 batch_get_point_latest — 批量获取，部分 hit 部分 miss

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/core/config.py                 # 修改 — 新增 redis_enabled, redis_url
backend/app/core/redis.py                  # 新建 — RedisService
backend/app/services/cache_service.py      # 新建 — 缓存数据服务
backend/app/services/point_data.py         # 修改 — 集成缓存写入
backend/app/services/gateway_registration.py # 修改 — 集成缓存写入
backend/app/main.py                        # 修改 — 生命周期集成
backend/tests/test_redis_cache.py          # 新建 — 单元测试
```

### 2. RedisService 实现

```python
# backend/app/core/redis.py

import json
import logging
from typing import Any, Optional

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


# 全局单例
redis_service = RedisService()
```

### 3. 缓存数据服务

```python
# backend/app/services/cache_service.py

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.redis import redis_service
from ..models.gateway import PointDataLatest, Gateway

logger = logging.getLogger(__name__)

POINT_CACHE_TTL = 60   # 点位缓存 60s
GATEWAY_CACHE_TTL = 30  # 网关状态缓存 30s


async def cache_point_data(
    point_id: str, value: str, quality: int, timestamp: datetime, gateway_id: str
) -> None:
    """写入点位数据到 Redis 缓存"""
    key = f"point:{point_id}:latest"
    data = {
        "v": value,
        "q": quality,
        "t": int(timestamp.timestamp()),
        "gw": gateway_id,
    }
    await redis_service.set_json(key, data, ttl=POINT_CACHE_TTL)


async def get_point_latest(point_id: str, db: AsyncSession) -> Optional[dict]:
    """获取点位最新值 — 先查 Redis，miss 则查 DB 并回填"""
    key = f"point:{point_id}:latest"

    # 1. 尝试 Redis
    cached = await redis_service.get_json(key)
    if cached is not None:
        return cached

    # 2. 查 DB
    result = await db.execute(
        select(PointDataLatest).where(PointDataLatest.point_id == point_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    # 3. 回填缓存
    data = {
        "v": record.value,
        "q": record.quality,
        "t": int(record.timestamp.timestamp()) if record.timestamp else 0,
        "gw": record.gateway_id or "",
    }
    await redis_service.set_json(key, data, ttl=POINT_CACHE_TTL)
    return data


async def batch_get_point_latest(
    point_ids: list[str], db: AsyncSession
) -> dict[str, Optional[dict]]:
    """批量获取点位最新值"""
    results: dict[str, Optional[dict]] = {}
    miss_ids: list[str] = []

    # 1. 批量查 Redis（使用 MGET）
    keys = [f"point:{pid}:latest" for pid in point_ids]
    cached_values = await redis_service.mget(keys)
    for pid, raw in zip(point_ids, cached_values):
        if raw is not None:
            try:
                results[pid] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                miss_ids.append(pid)
        else:
            miss_ids.append(pid)

    # 2. miss 的查 DB
    if miss_ids:
        db_result = await db.execute(
            select(PointDataLatest).where(PointDataLatest.point_id.in_(miss_ids))
        )
        for record in db_result.scalars().all():
            data = {
                "v": record.value,
                "q": record.quality,
                "t": int(record.timestamp.timestamp()) if record.timestamp else 0,
                "gw": record.gateway_id or "",
            }
            results[record.point_id] = data
            # 回填缓存
            await redis_service.set_json(
                f"point:{record.point_id}:latest", data, ttl=POINT_CACHE_TTL
            )

    # 3. 仍然 miss 的设为 None
    for pid in point_ids:
        if pid not in results:
            results[pid] = None

    return results


async def cache_gateway_status(
    gateway_id: str, status: str,
    cpu: Optional[float] = None, mem: Optional[float] = None, disk: Optional[float] = None
) -> None:
    """写入网关状态到 Redis 缓存"""
    key = f"gateway:{gateway_id}:status"
    data = {
        "status": status,
        "cpu": cpu,
        "mem": mem,
        "disk": disk,
        "ts": int(datetime.now().timestamp()),
    }
    await redis_service.set_json(key, data, ttl=GATEWAY_CACHE_TTL)


async def get_gateway_status(gateway_id: str, db: AsyncSession) -> Optional[dict]:
    """获取网关状态 — 先查 Redis，miss 则查 DB 并回填"""
    key = f"gateway:{gateway_id}:status"

    # 1. 尝试 Redis
    cached = await redis_service.get_json(key)
    if cached is not None:
        return cached

    # 2. 查 DB
    result = await db.execute(
        select(Gateway).where(Gateway.gateway_id == gateway_id)
    )
    gw = result.scalar_one_or_none()
    if gw is None:
        return None

    # 3. 回填缓存
    data = {
        "status": gw.status or "unknown",
        "cpu": gw.cpu_usage,
        "mem": gw.memory_usage,
        "disk": gw.disk_usage,
        "ts": int(gw.last_heartbeat.timestamp()) if gw.last_heartbeat else 0,
    }
    await redis_service.set_json(key, data, ttl=GATEWAY_CACHE_TTL)
    return data
```

### 4. 集成到 handle_point_data

在 `backend/app/services/point_data.py` 的 `handle_point_data` 中，每个点位写入 DB 后调用：

```python
from .cache_service import cache_point_data

# 在 UPSERT 之后
await cache_point_data(point_id, value, quality, timestamp, gw_id)
```

### 5. 集成到 handle_gateway_status

在 `backend/app/services/gateway_registration.py` 的 `handle_gateway_status` 中，写入 DB 后调用：

```python
from .cache_service import cache_gateway_status

# 在 db.commit() 之后
await cache_gateway_status(
    gw_id, "online",
    cpu=payload.get("cpu"),
    mem=payload.get("mem"),
    disk=payload.get("disk"),
)
```

### 6. main.py 生命周期集成

```python
# 在 startup 事件中
from app.core.redis import redis_service
from app.core.config import get_settings

settings = get_settings()
if settings.redis_enabled:
    await redis_service.connect(settings.redis_url)

# 在 shutdown 事件中
await redis_service.close()
```

### 7. 关键约束

- **mock 测试**: 使用 `unittest.mock.AsyncMock` mock `redis.asyncio`，不需要真实 Redis
- **优雅降级**: 所有 Redis 操作用 try/except 包裹，异常时仅 log warning，不影响业务
- **TTL**: 点位 60s，网关 30s，与架构文档一致
- **JSON 存储**: 缓存值用 JSON 字符串存储，方便序列化/反序列化
- **write-through**: 数据写入 DB 的同时写入 Redis，保证缓存一致性
- **read-through**: 读取时先查 Redis，miss 则查 DB 并回填缓存
- **全局单例**: `redis_service` 在模块级别创建，通过 `connect/close` 管理生命周期
- **不修改现有测试**: 现有 test_point_data.py 和 test_gateway_registration.py 不需要修改（cache_service 内部降级）

### Project Structure Notes

- `backend/app/core/redis.py` — 新建（RedisService）
- `backend/app/services/cache_service.py` — 新建（缓存数据服务）
- `backend/app/core/config.py` — 修改（新增 redis_enabled, redis_url）
- `backend/app/services/point_data.py` — 修改（集成缓存写入）
- `backend/app/services/gateway_registration.py` — 修改（集成缓存写入）
- `backend/app/main.py` — 修改（生命周期集成）
- 测试文件放在 `backend/tests/test_redis_cache.py`

### References

- [Source: architecture.md#3.6] Redis 缓存策略 — Key 模式和 TTL
- [Source: epics.md#Story 2.6] Acceptance Criteria
- [Source: point_data.py] handle_point_data 现有实现
- [Source: gateway_registration.py] handle_gateway_status 现有实现

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

