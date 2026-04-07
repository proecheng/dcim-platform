"""网关状态监控服务 — Story 2.2 + Story 35.2 双层故障隔离 + Story 35.3 告警"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, distinct

from ..models.gateway import DataSource, DataSourceStatus, GatewayEvent
from .datasource_alarm import (
    create_datasource_alarm,
    resolve_datasource_alarm,
    resolve_datasource_alarms_batch,
)
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


async def _probe_gateway(gw_ds: DataSource, db: AsyncSession) -> list[dict]:
    """探测单个网关可达性，更新 consecutive_failures/status，触发告警。返回待推送消息列表。"""
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
        connected = await asyncio.wait_for(adapter.connect(config), timeout=GATEWAY_PROBE_TIMEOUT)
        if connected:
            result = await asyncio.wait_for(adapter.test_connection(), timeout=GATEWAY_PROBE_TIMEOUT)
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
    pre_probe_status = gw_ds.status  # 在 SQL UPDATE 之前捕获
    broadcasts = []

    if reachable:
        # 探测成功：重置失败计数
        await db.execute(
            update(DataSource)
            .where(DataSource.id == gw_ds.id)
            .values(consecutive_failures=0, status=DataSourceStatus.CONNECTED, updated_at=now)
        )
        # 仅当网关之前是 gateway_offline 时才恢复子设备 + 关闭告警
        if pre_probe_status == DataSourceStatus.GATEWAY_OFFLINE:
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status == DataSourceStatus.GATEWAY_OFFLINE,
                )
                .values(status=DataSourceStatus.DISCONNECTED, updated_at=now)
            )
            # Story 35.3: 关闭网关自身告警
            resolved_count = await resolve_datasource_alarm(db, gw_ds.id, now)
            if resolved_count > 0:
                broadcasts.append(
                    {
                        "action": "resolve",
                        "source": f"datasource:{gw_ds.id}",
                        "status": "resolved",
                    }
                )
            # 批量关闭子设备告警
            child_result = await db.execute(select(DataSource.id).where(DataSource.parent_datasource_id == gw_ds.id))
            child_ids = [r[0] for r in child_result.fetchall()]
            batch_count = await resolve_datasource_alarms_batch(db, child_ids, now)
            if batch_count > 0:
                broadcasts.append(
                    {
                        "action": "resolve_batch",
                        "count": batch_count,
                        "source": f"gateway:{gw_ds.id}:children",
                    }
                )
    else:
        # 探测失败：SQL 级别递增
        await db.execute(
            update(DataSource)
            .where(DataSource.id == gw_ds.id)
            .values(
                consecutive_failures=DataSource.consecutive_failures + 1,
                updated_at=now,
            )
        )
        # flush 确保 SELECT 读到最新值
        await db.flush()
        result = await db.execute(
            select(DataSource.consecutive_failures, DataSource.retry_max_failures).where(DataSource.id == gw_ds.id)
        )
        row = result.one()
        if row.consecutive_failures >= row.retry_max_failures:
            await db.execute(
                update(DataSource)
                .where(DataSource.id == gw_ds.id)
                .values(status=DataSourceStatus.GATEWAY_OFFLINE, updated_at=now)
            )
            # 批量级联子设备
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status != DataSourceStatus.GATEWAY_OFFLINE,
                )
                .values(status=DataSourceStatus.GATEWAY_OFFLINE, updated_at=now)
            )
            # Story 35.3: 查询子设备名称，创建网关离线告警
            child_result = await db.execute(
                select(DataSource.id, DataSource.name).where(DataSource.parent_datasource_id == gw_ds.id)
            )
            children = child_result.fetchall()
            device_names = ", ".join([c.name for c in children[:10]])
            if len(children) > 10:
                device_names += f" 等{len(children)}台"
            alarm = await create_datasource_alarm(
                db,
                gw_ds,
                "mstp_gateway_offline",
                "major",
                f"协议转换网关 {gw_ds.name} 离线，影响 {len(children)} 台 MS/TP 设备：{device_names}",
            )
            if alarm:
                broadcasts.append(
                    {
                        "action": "new",
                        "id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "alarm_level": alarm.alarm_level,
                        "alarm_type": alarm.alarm_type,
                        "alarm_message": alarm.alarm_message,
                        "status": "active",
                    }
                )

    return broadcasts


async def check_mstp_gateway_health(db: AsyncSession) -> None:
    """检查所有 MS/TP 网关 DataSource 的连通性，级联更新子设备状态"""
    # 通过 parent 引用反查网关 ID
    gw_ids_result = await db.execute(
        select(distinct(DataSource.parent_datasource_id)).where(DataSource.parent_datasource_id.isnot(None))
    )
    gateway_ids = [r[0] for r in gw_ids_result.fetchall()]
    if not gateway_ids:
        return  # 无 MS/TP 网关配置

    # 加载网关 DataSource 对象
    gw_result = await db.execute(select(DataSource).where(DataSource.id.in_(gateway_ids)))
    gateway_datasources = gw_result.scalars().all()
    if not gateway_datasources:
        return  # 所有引用的网关均已删除

    # Story 35.3: 收集待推送消息，commit 后推送
    pending_broadcasts = []
    for gw_ds in gateway_datasources:
        try:
            broadcasts = await _probe_gateway(gw_ds, db)
            pending_broadcasts.extend(broadcasts)
        except Exception as e:
            logger.error("网关 %s 探测异常未捕获: %s", gw_ds.id, e)

    await db.commit()

    # commit 成功后 WebSocket 推送
    if pending_broadcasts:
        try:
            from ..services.websocket import ws_manager

            for msg in pending_broadcasts:
                try:
                    await ws_manager.broadcast_alarm(msg)
                except Exception:
                    pass
        except ImportError:
            pass  # WebSocket 模块不可用时静默跳过
