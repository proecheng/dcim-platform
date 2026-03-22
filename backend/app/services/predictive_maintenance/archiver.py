"""Hourly 归档任务 — Story 36.1

聚合 PointHistory 上一小时数据写入 PointHistoryArchive（archive_type='hourly'）
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ...models.history import PointHistory, PointHistoryArchive
from .config import VALID_QUALITY_THRESHOLD

logger = logging.getLogger(__name__)


async def archive_hourly(db: AsyncSession) -> int:
    """聚合上一小时 PointHistory 写入 PointHistoryArchive

    幂等：依赖 UNIQUE(point_id, archive_type, recorded_at) 约束，
    INSERT 前检查已存在记录，跳过已归档的点位。

    Returns: 新增归档记录数
    """
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hour_end = hour_start + timedelta(hours=1)

    # 单条 SQL GROUP BY point_id 聚合所有点位
    stmt = (
        select(
            PointHistory.point_id,
            func.min(PointHistory.value).label("value_min"),
            func.max(PointHistory.value).label("value_max"),
            func.avg(PointHistory.value).label("value_avg"),
            func.sum(PointHistory.value).label("value_sum"),
            func.count(PointHistory.id).label("sample_count"),
        )
        .where(
            and_(
                PointHistory.recorded_at >= hour_start,
                PointHistory.recorded_at < hour_end,
                PointHistory.quality < VALID_QUALITY_THRESHOLD,  # 过滤坏数据
            )
        )
        .group_by(PointHistory.point_id)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    if not rows:
        logger.debug("归档: %s 无需聚合的数据", hour_start.strftime("%Y-%m-%d %H:00"))
        return 0

    # 查询已归档的 point_id（幂等检查）
    point_ids = [r.point_id for r in rows]
    existing_result = await db.execute(
        select(PointHistoryArchive.point_id).where(
            PointHistoryArchive.point_id.in_(point_ids),
            PointHistoryArchive.archive_type == "hourly",
            PointHistoryArchive.recorded_at == hour_start,
        )
    )
    existing_point_ids = {r[0] for r in existing_result.fetchall()}

    created = 0
    for row in rows:
        if row.point_id in existing_point_ids:
            continue  # 已归档，跳过

        archive = PointHistoryArchive(
            point_id=row.point_id,
            archive_type="hourly",
            value_min=row.value_min,
            value_max=row.value_max,
            value_avg=row.value_avg,
            value_sum=row.value_sum,
            sample_count=row.sample_count,
            recorded_at=hour_start,
        )
        db.add(archive)
        created += 1

    if created > 0:
        try:
            await db.flush()
        except IntegrityError:
            # 并发写入时可能触发 UNIQUE 约束冲突
            # 不调用 rollback，由外层 context manager 负责事务语义
            logger.warning("归档 %s: 并发写入冲突，部分记录可能重复",
                           hour_start.strftime("%Y-%m-%d %H:00"))
            return 0

    logger.info("归档 %s: 新增 %d 条，跳过 %d 条（已存在）",
                hour_start.strftime("%Y-%m-%d %H:00"), created, len(existing_point_ids))
    return created
