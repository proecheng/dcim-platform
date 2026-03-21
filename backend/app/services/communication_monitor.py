"""通信中断检测服务"""

from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..engines.alarm_engine import alarm_engine
from ..models.gateway import DataSource, DataSourcePoint
from ..models.point import PointRealtime
from .websocket import ws_manager


async def check_communication_status(session: AsyncSession):
    """检查所有数据源通信状态，标记中断的数据源"""
    result = await session.execute(
        select(DataSource).where(DataSource.is_enabled == True)  # noqa: E712
    )
    datasources = result.scalars().all()

    # Story 35.2: 预加载父 DataSource 状态映射（避免 N+1）
    parent_ids = {ds.parent_datasource_id for ds in datasources if ds.parent_datasource_id is not None}
    parent_status_map = {}
    if parent_ids:
        parent_result = await session.execute(
            select(DataSource.id, DataSource.status).where(DataSource.id.in_(parent_ids))
        )
        parent_status_map = {r.id: r.status for r in parent_result.fetchall()}

    # 收集广播消息，commit 成功后再发送（避免 DB 回滚但前端已收到通知的不一致）
    pending_broadcasts = []

    for ds in datasources:
        # Story 35.2: 子设备双层故障隔离逻辑
        if ds.parent_datasource_id is not None:
            parent_status = parent_status_map.get(ds.parent_datasource_id)
            # 父网关已 gateway_offline → 跳过（由 gateway_health 管理）
            if parent_status == "gateway_offline":
                continue
            # 当前状态为 gateway_offline → 跳过恢复（由 gateway_health 管理）
            if ds.status == "gateway_offline":
                continue

        if ds.consecutive_failures >= ds.retry_max_failures:
            # Story 35.2: 有父网关且父在线 → 用 device_offline
            target_status = "device_offline" if ds.parent_datasource_id is not None else "interrupted"
            if ds.status != target_status and ds.status != "gateway_offline":
                await session.execute(update(DataSource).where(DataSource.id == ds.id).values(status=target_status))
                point_ids = await mark_unreliable_points(session, ds.id, quality=2)
                pending_broadcasts.append(
                    {
                        "type": "data_quality_changed",
                        "datasource_id": ds.id,
                        "quality": 2,
                        "affected_point_ids": point_ids,
                        "affected_count": len(point_ids),
                        "message": f"数据源 {ds.name} 通信中断，{len(point_ids)} 个点位数据标记为不可靠",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
        elif ds.status in ("interrupted", "device_offline") and ds.consecutive_failures == 0:
            await session.execute(update(DataSource).where(DataSource.id == ds.id).values(status="connected"))
            point_ids = await mark_unreliable_points(session, ds.id, quality=0)
            pending_broadcasts.append(
                {
                    "type": "data_quality_changed",
                    "datasource_id": ds.id,
                    "quality": 0,
                    "affected_point_ids": point_ids,
                    "affected_count": len(point_ids),
                    "message": f"数据源 {ds.name} 通信恢复，{len(point_ids)} 个点位数据质量已恢复正常",
                    "timestamp": datetime.now().isoformat(),
                }
            )

    await session.commit()

    # commit 成功后发送 WebSocket 广播
    for payload in pending_broadcasts:
        try:
            await ws_manager.broadcast_system(payload)
        except Exception:
            pass  # WebSocket 失败不影响监控逻辑


async def mark_unreliable_points(session: AsyncSession, datasource_id: int, quality: int) -> List[int]:
    """标记数据源关联点位的数据质量，返回受影响的点位ID列表"""
    result = await session.execute(
        select(DataSourcePoint.point_id).where(
            DataSourcePoint.datasource_id == datasource_id, DataSourcePoint.point_id.isnot(None)
        )
    )
    point_ids = [row[0] for row in result.all()]

    if point_ids:
        status = "offline" if quality == 2 else "normal"
        await session.execute(
            update(PointRealtime).where(PointRealtime.point_id.in_(point_ids)).values(quality=quality, status=status)
        )
        alarm_engine.update_points_quality(point_ids, quality)

    return point_ids
