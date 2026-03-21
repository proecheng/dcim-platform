"""网关状态监控服务 — Story 2.2 + Story 35.2 双层故障隔离"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, distinct

from ..models.gateway import DataSource, GatewayEvent
from gateway.adapters.bacnet_ip import BacnetIpAdapter
from gateway.adapters.base import DataSourceConfig

logger = logging.getLogger(__name__)

RESOURCE_WARNING_THRESHOLD = 90.0  # CPU/内存/磁盘告警阈值 %
RESOURCE_WARNING_COOLDOWN = 300  # 资源告警去重冷却期（秒）
GATEWAY_PROBE_TIMEOUT = 10  # 网关探测超时（秒）— Story 35.2


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
        select(GatewayEvent)
        .where(
            GatewayEvent.gateway_id == gateway_id,
            GatewayEvent.event_type == "resource_warning",
            GatewayEvent.created_at > cooldown_cutoff,
        )
        .limit(1)
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


# ─── Story 35.2: 双层故障隔离 ───────────────────────────────────


async def _probe_gateway(gw_ds: DataSource, db: AsyncSession) -> None:
    """探测单个网关可达性，更新 consecutive_failures 和 status"""
    adapter = BacnetIpAdapter()
    config = DataSourceConfig(
        datasource_id=str(gw_ds.id),
        protocol_type="bacnet_ip",
        connection_params=gw_ds.connection_config,
        points=[],
        collection_interval=30,
    )
    reachable = False
    try:
        connected = await asyncio.wait_for(
            adapter.connect(config), timeout=GATEWAY_PROBE_TIMEOUT
        )
        if connected:
            result = await asyncio.wait_for(
                adapter.test_connection(), timeout=GATEWAY_PROBE_TIMEOUT
            )
            reachable = result.success
    except asyncio.TimeoutError:
        logger.warning("网关 %s 探测超时 (%ds)", gw_ds.id, GATEWAY_PROBE_TIMEOUT)
        reachable = False
    except Exception as e:
        logger.warning("网关 %s 探测异常: %s", gw_ds.id, e)
        reachable = False
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    now = datetime.now()
    pre_probe_status = gw_ds.status  # 在 SQL UPDATE 之前捕获（ORM identity map 会被 synchronize_session 同步）
    if reachable:
        # 探测成功：重置失败计数
        await db.execute(
            update(DataSource).where(DataSource.id == gw_ds.id)
            .values(consecutive_failures=0, status="connected", updated_at=now)
        )
        # 仅当网关之前是 gateway_offline 时才恢复子设备
        if pre_probe_status == "gateway_offline":
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status == "gateway_offline",
                )
                .values(status="disconnected", updated_at=now)
            )
    else:
        # 探测失败：SQL 级别递增
        await db.execute(
            update(DataSource).where(DataSource.id == gw_ds.id)
            .values(
                consecutive_failures=DataSource.consecutive_failures + 1,
                updated_at=now,
            )
        )
        # flush 确保 SELECT 读到最新值
        await db.flush()
        result = await db.execute(
            select(DataSource.consecutive_failures, DataSource.retry_max_failures)
            .where(DataSource.id == gw_ds.id)
        )
        row = result.one()
        if row.consecutive_failures >= row.retry_max_failures:
            await db.execute(
                update(DataSource).where(DataSource.id == gw_ds.id)
                .values(status="gateway_offline", updated_at=now)
            )
            # 批量级联子设备
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status != "gateway_offline",
                )
                .values(status="gateway_offline", updated_at=now)
            )


async def check_mstp_gateway_health(db: AsyncSession) -> None:
    """检查所有 MS/TP 网关 DataSource 的连通性，级联更新子设备状态"""
    # 通过 parent 引用反查网关 ID
    gw_ids_result = await db.execute(
        select(distinct(DataSource.parent_datasource_id))
        .where(DataSource.parent_datasource_id.isnot(None))
    )
    gateway_ids = [r[0] for r in gw_ids_result.fetchall()]
    if not gateway_ids:
        return  # 无 MS/TP 网关配置

    # 加载网关 DataSource 对象
    gw_result = await db.execute(
        select(DataSource).where(DataSource.id.in_(gateway_ids))
    )
    gateway_datasources = gw_result.scalars().all()
    if not gateway_datasources:
        return  # 所有引用的网关均已删除

    for gw_ds in gateway_datasources:
        try:
            await _probe_gateway(gw_ds, db)
        except Exception as e:
            logger.error("网关 %s 探测异常未捕获: %s", gw_ds.id, e)

    await db.commit()
