"""数据源桥接服务 — 将 DataSourcePoint 采集数据同步到 Point/PointRealtime — Story 4.1"""

import json
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.point import Point, PointRealtime
from ..models.gateway import DataSourcePoint
from ..core.redis import redis_service


async def sync_point_data(
    session: AsyncSession,
    point_id: int,
    value: float,
    quality: int = 0,
    status: str = "normal",
    alarm_level: Optional[str] = None,
) -> None:
    """将采集数据通过统一入库管道同步到所有表

    Args:
        session: 数据库会话
        point_id: Point 表的 ID
        value: 采集值
        quality: 数据质量 (0=好, 1=不确定, 2=坏)
        status: 状态 (normal/alarm/offline)
        alarm_level: 告警级别
    """
    from .ingest_pipeline import IngestPoint, process_payload

    pt = IngestPoint(
        point_id=point_id,
        value=value,
        quality=quality,
        status=status,
        source="bridge",
    )
    await process_payload([pt], session=session)


async def link_datasource_to_point(
    session: AsyncSession,
    datasource_point_id: int,
    point_id: int,
) -> bool:
    """建立 DataSourcePoint 到 Point 的映射关系

    通过在 Point 表的 register_address 字段存储 datasource_point_id 实现映射。

    Returns:
        True if link was created successfully
    """
    # 验证 DataSourcePoint 存在
    ds_result = await session.execute(select(DataSourcePoint).where(DataSourcePoint.id == datasource_point_id))
    ds_point = ds_result.scalar_one_or_none()
    if not ds_point:
        return False

    # 验证 Point 存在
    pt_result = await session.execute(select(Point).where(Point.id == point_id))
    point = pt_result.scalar_one_or_none()
    if not point:
        return False

    # 存储映射关系
    await session.execute(
        update(Point)
        .where(Point.id == point_id)
        .values(
            energy_device_id=datasource_point_id,  # 复用此字段存储映射
            updated_at=datetime.now(),
        )
    )
    await session.commit()
    return True
