"""DataSource 级告警管理（网关/设备离线）— Story 35.3"""

import uuid
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.alarm import Alarm
from ..models.gateway import DataSource

logger = logging.getLogger(__name__)


async def create_datasource_alarm(
    db: AsyncSession,
    ds: DataSource,
    alarm_type: str,
    alarm_level: str,
    alarm_message: str,
) -> Optional[Alarm]:
    """为 DataSource 创建告警，幂等（已有 active 告警则跳过）"""
    source_key = f"datasource:{ds.id}"
    # 幂等检查（按 source + alarm_type 限定作用域）
    existing = await db.execute(
        select(Alarm)
        .where(Alarm.source == source_key, Alarm.alarm_type == alarm_type, Alarm.status == "active")
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
    alarm = Alarm(
        alarm_no=alarm_no,
        point_id=None,
        alarm_level=alarm_level,
        alarm_type=alarm_type,
        alarm_message=alarm_message,
        source=source_key,
        status="active",
        data_source="bridge",
    )
    db.add(alarm)
    await db.flush()
    logger.info("数据源告警创建: %s [%s] %s", alarm_no, alarm_type, ds.name)
    return alarm


async def resolve_datasource_alarm(db: AsyncSession, ds_id: int, now: Optional[datetime] = None) -> int:
    """恢复指定 DataSource 的所有 active 告警，返回关闭数量"""
    if now is None:
        now = datetime.now()
    source_key = f"datasource:{ds_id}"

    result = await db.execute(select(Alarm).where(Alarm.source == source_key, Alarm.status == "active"))
    alarms = result.scalars().all()
    for alarm in alarms:
        alarm.status = "resolved"
        alarm.resolve_type = "auto"
        alarm.resolved_at = now
        if alarm.created_at:
            alarm.duration_seconds = int((now - alarm.created_at).total_seconds())
    return len(alarms)


async def resolve_datasource_alarms_batch(db: AsyncSession, ds_ids: list[int], now: Optional[datetime] = None) -> int:
    """批量恢复多个 DataSource 的 active 告警"""
    if not ds_ids:
        return 0
    if now is None:
        now = datetime.now()
    source_keys = [f"datasource:{did}" for did in ds_ids]

    result = await db.execute(select(Alarm).where(Alarm.source.in_(source_keys), Alarm.status == "active"))
    alarms = result.scalars().all()
    for alarm in alarms:
        alarm.status = "resolved"
        alarm.resolve_type = "auto"
        alarm.resolved_at = now
        if alarm.created_at:
            alarm.duration_seconds = int((now - alarm.created_at).total_seconds())
    return len(alarms)
