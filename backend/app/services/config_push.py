"""配置构建与下发服务 — Story 2.3"""

import json
import logging
from typing import Callable, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.gateway import Gateway, DataSource, DataSourcePoint, ConfigPushRecord

logger = logging.getLogger(__name__)


async def build_gateway_config(gateway_id: int, db: AsyncSession) -> dict:
    """构建网关采集配置 JSON"""
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gateway = gw_result.scalar_one_or_none()
    if not gateway:
        raise ValueError("网关不存在: %s" % gateway_id)

    ds_result = await db.execute(
        select(DataSource).where(
            DataSource.gateway_id == gateway_id,
            DataSource.is_enabled == True,
        )
    )
    datasources = ds_result.scalars().all()

    ds_configs = []
    for ds in datasources:
        pt_result = await db.execute(select(DataSourcePoint).where(DataSourcePoint.datasource_id == ds.id))
        points = pt_result.scalars().all()

        ds_config = {
            "datasource_id": str(ds.id),
            "protocol_type": ds.protocol_type,
            "connection_params": ds.connection_config,
            "collection_interval": ds.collection_interval,
            "write_enabled": ds.write_enabled,
            "points": [
                {
                    "point_id": str(pt.point_id or pt.id),
                    "address": pt.address,
                    "data_type": pt.data_type,
                    "scale": pt.scale,
                    "offset": pt.offset,
                    "enum_mapping": pt.enum_mapping,
                    "is_dry_contact": pt.is_dry_contact,
                }
                for pt in points
            ],
        }
        ds_configs.append(ds_config)

    return {
        "gateway_id": gateway.gateway_id,
        "datasources": ds_configs,
    }


async def push_config_to_gateway(
    gateway_id: int,
    mqtt_publish_fn: Callable[..., Coroutine],
    db: AsyncSession,
) -> ConfigPushRecord:
    """构建配置并通过 MQTT 下发到网关"""
    config = await build_gateway_config(gateway_id, db)

    record = ConfigPushRecord(
        gateway_id=config["gateway_id"],
        config_snapshot=config,
        status="pending",
    )
    db.add(record)
    await db.flush()

    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gateway = gw_result.scalar_one()
    topic = f"dcim/{gateway.site_id}/gw/{gateway.gateway_id}/config"

    try:
        await mqtt_publish_fn(topic, json.dumps(config), qos=2)
        record.status = "delivered"
        logger.info("配置下发成功: %s → %s", gateway.gateway_id, topic)
    except Exception as e:
        record.status = "failed"
        record.error_message = str(e)[:500]
        logger.error("配置下发失败: %s — %s", gateway.gateway_id, e)

    await db.commit()
    return record
