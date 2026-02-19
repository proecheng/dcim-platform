"""断点续传消息去重服务 — Story 16.3"""
import logging

from ..core.redis import redis_service

logger = logging.getLogger(__name__)

# 序列号缓存 TTL: 1小时（覆盖网关离线缓存的最大时间窗口）
SEQ_CACHE_TTL = 3600


async def is_duplicate(gw_id: str, seq: int) -> bool:
    """检查消息序列号是否重复（断点续传去重）

    使用 Redis SET 存储已处理的序列号。
    Redis 不可用时返回 False（允许处理，宁可重复不可丢失）。
    """
    key = f"gw:{gw_id}:seqs"
    return await redis_service.sismember(key, str(seq))


async def mark_processed(gw_id: str, seq: int) -> None:
    """标记序列号已处理"""
    key = f"gw:{gw_id}:seqs"
    await redis_service.sadd_with_ttl(key, str(seq), ttl=SEQ_CACHE_TTL)
