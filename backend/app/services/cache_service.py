"""缓存数据服务 — Story 2.6"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.redis import redis_service
from ..models.gateway import PointDataLatest, Gateway

logger = logging.getLogger(__name__)

POINT_CACHE_TTL = 60  # 点位缓存 60s
GATEWAY_CACHE_TTL = 30  # 网关状态缓存 30s


async def cache_point_data(point_id: str, value: str, quality: int, timestamp: datetime, gateway_id: str) -> None:
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
    result = await db.execute(select(PointDataLatest).where(PointDataLatest.point_id == point_id))
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


async def batch_get_point_latest(point_ids: list[str], db: AsyncSession) -> dict[str, Optional[dict]]:
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
        db_result = await db.execute(select(PointDataLatest).where(PointDataLatest.point_id.in_(miss_ids)))
        for record in db_result.scalars().all():
            data = {
                "v": record.value,
                "q": record.quality,
                "t": int(record.timestamp.timestamp()) if record.timestamp else 0,
                "gw": record.gateway_id or "",
            }
            results[record.point_id] = data
            # 回填缓存
            await redis_service.set_json(f"point:{record.point_id}:latest", data, ttl=POINT_CACHE_TTL)

    # 3. 仍然 miss 的设为 None
    for pid in point_ids:
        if pid not in results:
            results[pid] = None

    return results


async def cache_gateway_status(
    gateway_id: str, status: str, cpu: Optional[float] = None, mem: Optional[float] = None, disk: Optional[float] = None
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
    result = await db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id))
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
