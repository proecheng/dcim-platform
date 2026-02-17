"""网关状态监控服务 — Story 2.2"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.gateway import GatewayEvent

logger = logging.getLogger(__name__)

RESOURCE_WARNING_THRESHOLD = 90.0  # CPU/内存/磁盘告警阈值 %
RESOURCE_WARNING_COOLDOWN = 300  # 资源告警去重冷却期（秒）


async def record_status_change(
    gateway_id: str,
    old_status: str,
    new_status: str,
    db: AsyncSession,
    detail: dict | None = None,
) -> None:
    """记录网关状态变更事件"""
    event = GatewayEvent(
        gateway_id=gateway_id,
        event_type="status_change",
        old_status=old_status,
        new_status=new_status,
        detail=detail,
    )
    db.add(event)
    await db.flush()
    logger.info("网关状态变更: %s %s → %s", gateway_id, old_status, new_status)


async def check_resource_warnings(
    gateway_id: str,
    payload: dict,
    db: AsyncSession,
) -> None:
    """检查资源使用率是否超阈值（5 分钟内同网关不重复告警）"""
    warnings = {}
    for key, label in [("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘")]:
        value = payload.get(key)
        if value is not None and value > RESOURCE_WARNING_THRESHOLD:
            warnings[key] = value

    if not warnings:
        return

    # 去重：检查冷却期内是否已有 resource_warning
    cooldown_cutoff = datetime.now() - timedelta(seconds=RESOURCE_WARNING_COOLDOWN)
    result = await db.execute(
        select(GatewayEvent).where(
            GatewayEvent.gateway_id == gateway_id,
            GatewayEvent.event_type == "resource_warning",
            GatewayEvent.created_at > cooldown_cutoff,
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return  # 冷却期内已有告警，跳过

    event = GatewayEvent(
        gateway_id=gateway_id,
        event_type="resource_warning",
        detail={"warnings": warnings, "threshold": RESOURCE_WARNING_THRESHOLD},
    )
    db.add(event)
    await db.flush()
    logger.warning("网关资源告警: %s %s", gateway_id, warnings)
