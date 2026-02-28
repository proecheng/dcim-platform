"""点位数据处理服务 — Story 2.5 + Story 16.3 断点续传去重

MQTT 网关数据入口。对于已映射到 Point 表的点位，走统一入库管道；
对于未映射的原始网关数据，仅写入 PointDataLatest。
"""

import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.gateway import PointDataLatest
from ..models.point import Point
from .cache_service import cache_point_data
from .dedup_service import is_duplicate, mark_processed
from .ingest_pipeline import IngestPoint, process_payload

logger = logging.getLogger(__name__)


async def handle_point_data(payload: dict, db: AsyncSession, *, site_id: str | None = None) -> int:
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

    # 构建 point_code → Point.id 映射（用于走统一管道）
    point_ids_str = [pt.get("id") for pt in points if pt.get("id")]
    mapping: dict[str, int] = {}
    if point_ids_str:
        result = await db.execute(
            select(Point.id, Point.point_code).where(Point.point_code.in_(point_ids_str))
        )
        mapping = {row[1]: row[0] for row in result.all()}

    # 分离: 已映射的走统一管道，未映射的走原始写入
    pipeline_points: list[IngestPoint] = []
    unmapped_points: list[dict] = []

    for pt in points:
        point_id_str = pt.get("id")
        if not point_id_str:
            continue

        value_raw = pt.get("v", "")
        quality = int(pt.get("q", 0))
        ts_epoch = pt.get("t")
        timestamp = datetime.fromtimestamp(ts_epoch) if ts_epoch else datetime.now()

        if point_id_str in mapping:
            # 已映射 → 走统一管道
            try:
                value_float = float(value_raw)
            except (ValueError, TypeError):
                value_float = 0.0
            pipeline_points.append(IngestPoint(
                point_id=mapping[point_id_str],
                value=value_float,
                quality=quality,
                timestamp=timestamp,
                gateway_id=gw_id,
                point_key=point_id_str,
                source="mqtt",
            ))
        else:
            # 未映射 → 仅写 PointDataLatest
            unmapped_points.append({
                "id": point_id_str,
                "v": str(value_raw),
                "q": quality,
                "ts": timestamp,
            })

    count = 0

    # 统一管道处理已映射点位
    if pipeline_points:
        result = await process_payload(pipeline_points, session=db)
        count += result.written

    # 原始写入未映射点位
    for pt in unmapped_points:
        point_id = pt["id"]
        existing = await db.execute(
            select(PointDataLatest).where(PointDataLatest.point_id == point_id)
        )
        if existing.scalar_one_or_none():
            await db.execute(
                update(PointDataLatest)
                .where(PointDataLatest.point_id == point_id)
                .values(
                    value=pt["v"],
                    quality=pt["q"],
                    timestamp=pt["ts"],
                    gateway_id=gw_id,
                    updated_at=datetime.now(),
                )
            )
        else:
            record = PointDataLatest(
                point_id=point_id,
                value=pt["v"],
                quality=pt["q"],
                timestamp=pt["ts"],
                gateway_id=gw_id,
            )
            db.add(record)
        await cache_point_data(point_id, pt["v"], pt["q"], pt["ts"], gw_id)
        count += 1

    if unmapped_points:
        await db.commit()

    # 标记序列号已处理
    if seq is not None:
        await mark_processed(gw_id, seq)

    logger.debug("点位数据处理: site=%s, gw=%s, %d 条 (管道=%d, 原始=%d)",
                 site_id, gw_id, count, len(pipeline_points), len(unmapped_points))
    return count
