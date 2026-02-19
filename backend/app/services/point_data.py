"""点位数据处理服务 — Story 2.5 + Story 16.3 断点续传去重"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.gateway import PointDataLatest
from .cache_service import cache_point_data
from .dedup_service import is_duplicate, mark_processed

logger = logging.getLogger(__name__)


async def handle_point_data(
    payload: dict, db: AsyncSession, *, site_id: str | None = None
) -> int:
    """处理网关上报的点位数据，返回处理条数。支持断点续传去重。"""
    gw_id = payload.get("gw_id")
    points = payload.get("points")
    if not gw_id or not points:
        logger.warning("数据消息格式无效: 缺少 gw_id 或 points")
        return 0

    # 断点续传去重: 如果 payload 包含 seq，检查是否已处理
    seq = payload.get("seq")
    if seq is not None:
        if await is_duplicate(gw_id, seq):
            logger.debug("重复消息跳过: gw=%s, seq=%s", gw_id, seq)
            return 0

    count = 0
    for pt in points:
        point_id = pt.get("id")
        if not point_id:
            continue

        value = str(pt.get("v", ""))
        quality = int(pt.get("q", 0))
        ts_epoch = pt.get("t")
        timestamp = datetime.fromtimestamp(ts_epoch) if ts_epoch else datetime.now()

        # UPSERT: 存在则更新，不存在则插入
        result = await db.execute(
            select(PointDataLatest).where(PointDataLatest.point_id == point_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.execute(
                update(PointDataLatest).where(PointDataLatest.point_id == point_id).values(
                    value=value,
                    quality=quality,
                    timestamp=timestamp,
                    gateway_id=gw_id,
                    updated_at=datetime.now(),
                )
            )
        else:
            record = PointDataLatest(
                point_id=point_id,
                value=value,
                quality=quality,
                timestamp=timestamp,
                gateway_id=gw_id,
            )
            db.add(record)

        await cache_point_data(point_id, value, quality, timestamp, gw_id)
        count += 1

    await db.commit()

    # 标记序列号已处理
    if seq is not None:
        await mark_processed(gw_id, seq)

    logger.debug("点位数据处理: site=%s, gw=%s, %d 条", site_id, gw_id, count)
    return count
