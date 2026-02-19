"""网关自动注册服务 — Story 2.1 + Story 16.3 多站点网关接入"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_

from ..models.gateway import Gateway
from ..models.spatial import Site
from .gateway_monitor import record_status_change, check_resource_warnings
from .cache_service import cache_gateway_status

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_SECONDS = 90


async def _resolve_site_id(site_id_str: str | None, db: AsyncSession) -> int | None:
    """解析并验证 topic 中的 site_id，返回有效的整数 site_id 或 None"""
    if site_id_str is None:
        return None
    try:
        site_id = int(site_id_str)
    except (ValueError, TypeError):
        logger.warning("topic 中 site_id=%s 无法解析为整数", site_id_str)
        return None
    result = await db.execute(select(Site.id).where(Site.id == site_id))
    if result.scalar_one_or_none() is None:
        logger.warning("topic 中 site_id=%s 对应站点不存在", site_id_str)
        return None
    return site_id


async def handle_gateway_status(
    payload: dict, db: AsyncSession, *, site_id: str | None = None
) -> None:
    """处理网关心跳消息 — 自动注册或更新，支持 site_id 绑定"""
    gw_id = payload.get("gw_id")
    if not gw_id:
        logger.warning("心跳消息缺少 gw_id: %s", payload)
        return

    result = await db.execute(select(Gateway).where(Gateway.gateway_id == gw_id))
    existing = result.scalar_one_or_none()

    now = datetime.now()
    resolved_site_id = await _resolve_site_id(site_id, db)

    if existing is None:
        # 自动注册 — 设置 site_id
        gateway = Gateway(
            gateway_id=gw_id,
            name=payload.get("name", f"gateway-{gw_id}"),
            ip_address=payload.get("ip"),
            version=payload.get("version"),
            capabilities=payload.get("capabilities"),
            status="online",
            cpu_usage=payload.get("cpu"),
            memory_usage=payload.get("mem"),
            disk_usage=payload.get("disk"),
            last_heartbeat=now,
            site_id=resolved_site_id,
        )
        db.add(gateway)
        await record_status_change(gw_id, "none", "online", db)
        await check_resource_warnings(gw_id, payload, db)
        await db.commit()
        await cache_gateway_status(
            gw_id, "online",
            cpu=payload.get("cpu"),
            mem=payload.get("mem"),
            disk=payload.get("disk"),
        )
        logger.info("网关自动注册: %s (ip=%s, site_id=%s)", gw_id, payload.get("ip"), resolved_site_id)
    else:
        # 更新心跳
        old_status = existing.status
        update_values: dict = dict(
            status="online",
            name=payload.get("name", existing.name),
            ip_address=payload.get("ip", existing.ip_address),
            version=payload.get("version", existing.version),
            capabilities=payload.get("capabilities", existing.capabilities),
            cpu_usage=payload.get("cpu"),
            memory_usage=payload.get("mem"),
            disk_usage=payload.get("disk"),
            last_heartbeat=now,
            updated_at=now,
        )
        # 如果网关无 site_id 且 topic 有，则补充设置
        if resolved_site_id is not None and existing.site_id is None:
            update_values["site_id"] = resolved_site_id
            logger.info("网关 %s 补充绑定站点: site_id=%s", gw_id, resolved_site_id)
        elif resolved_site_id is not None and existing.site_id != resolved_site_id:
            logger.warning(
                "网关 %s site_id 不一致: DB=%s, topic=%s（不覆盖）",
                gw_id, existing.site_id, resolved_site_id,
            )

        await db.execute(
            update(Gateway).where(Gateway.gateway_id == gw_id).values(**update_values)
        )
        # 状态变更记录
        if old_status != "online":
            await record_status_change(gw_id, old_status, "online", db)
        # 检查资源告警
        await check_resource_warnings(gw_id, payload, db)
        await db.commit()
        await cache_gateway_status(
            gw_id, "online",
            cpu=payload.get("cpu"),
            mem=payload.get("mem"),
            disk=payload.get("disk"),
        )
        logger.debug("网关心跳更新: %s", gw_id)


async def check_gateway_heartbeats(db: AsyncSession) -> int:
    """检查网关心跳超时，返回标记为 offline 的数量"""
    cutoff = datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    result = await db.execute(
        select(Gateway).where(
            Gateway.status == "online",
            or_(
                Gateway.last_heartbeat < cutoff,
                Gateway.last_heartbeat.is_(None),
            ),
        )
    )
    stale_gateways = result.scalars().all()

    if not stale_gateways:
        return 0

    stale_ids = [gw.gateway_id for gw in stale_gateways]
    await db.execute(
        update(Gateway).where(
            Gateway.gateway_id.in_(stale_ids)
        ).values(status="offline", updated_at=datetime.now())
    )

    for gw_id in stale_ids:
        await record_status_change(gw_id, "online", "offline", db)

    await db.commit()

    return len(stale_ids)
