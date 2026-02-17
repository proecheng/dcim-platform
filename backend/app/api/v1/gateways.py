"""网关管理 API"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.gateway import Gateway, DataSource, DataSourcePoint, GatewayEvent, ConfigPushRecord
from ...schemas.gateway import (
    GatewayCreate, GatewayUpdate, GatewayResponse,
    GatewayStatusSummary, GatewayDetailResponse, GatewayEventResponse,
    ConfigPushResponse, ConfigPushRecordResponse,
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[GatewayResponse], summary="获取网关列表")
async def list_gateways(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="状态"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    keyword: Optional[str] = Query(None, description="名称/IP 模糊搜索"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    query = select(Gateway)
    if status:
        query = query.where(Gateway.status == status)
    if is_enabled is not None:
        query = query.where(Gateway.is_enabled == is_enabled)
    if keyword:
        query = query.where(
            (Gateway.name.contains(keyword)) | (Gateway.ip_address.contains(keyword))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Gateway.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[GatewayResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=GatewayResponse, summary="创建网关")
async def create_gateway(
    data: GatewayCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    # 检查 gateway_id 唯一性
    result = await db.execute(select(Gateway).where(Gateway.gateway_id == data.gateway_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="网关标识已存在")

    obj = Gateway(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return GatewayResponse.model_validate(obj)


@router.get("/summary", response_model=GatewayStatusSummary, summary="网关状态汇总")
async def gateway_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    total_result = await db.execute(select(func.count()).select_from(Gateway))
    total = total_result.scalar() or 0

    online_result = await db.execute(
        select(func.count()).select_from(Gateway).where(Gateway.status == "online")
    )
    online = online_result.scalar() or 0

    return GatewayStatusSummary(total=total, online=online, offline=total - online)


@router.get("/{gateway_id}", response_model=GatewayDetailResponse, summary="获取网关详情")
async def get_gateway(
    gateway_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="网关不存在")

    # 查询关联数据源数量
    ds_count_result = await db.execute(
        select(func.count()).select_from(DataSource).where(DataSource.gateway_id == obj.id)
    )
    datasource_count = ds_count_result.scalar() or 0

    # 查询关联点位数量
    point_count = 0
    if datasource_count > 0:
        ds_ids_result = await db.execute(
            select(DataSource.id).where(DataSource.gateway_id == obj.id)
        )
        ds_ids = [row[0] for row in ds_ids_result.all()]
        if ds_ids:
            pt_count_result = await db.execute(
                select(func.count()).select_from(DataSourcePoint).where(
                    DataSourcePoint.datasource_id.in_(ds_ids)
                )
            )
            point_count = pt_count_result.scalar() or 0

    response_data = GatewayDetailResponse.model_validate(obj)
    response_data.datasource_count = datasource_count
    response_data.point_count = point_count
    return response_data


@router.get("/{gateway_id}/events", response_model=PageResponse[GatewayEventResponse], summary="网关事件历史")
async def gateway_events(
    gateway_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None, description="事件类型筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    # 先查 Gateway 获取 gateway_id 字符串
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gw = gw_result.scalar_one_or_none()
    if not gw:
        raise HTTPException(status_code=404, detail="网关不存在")

    query = select(GatewayEvent).where(GatewayEvent.gateway_id == gw.gateway_id)
    if event_type:
        query = query.where(GatewayEvent.event_type == event_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(GatewayEvent.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[GatewayEventResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{gateway_id}/push-config", response_model=ConfigPushResponse, summary="下发配置到网关")
async def push_config(
    gateway_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """构建并下发采集配置到指定网关"""
    # 验证网关存在
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    if not gw_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="网关不存在")

    from ...mqtt import mqtt_service
    from ...services.config_push import push_config_to_gateway

    # 预检 MQTT 连接状态
    if mqtt_service._client is None:
        raise HTTPException(status_code=503, detail="MQTT 未连接")

    try:
        record = await push_config_to_gateway(gateway_id, mqtt_service.publish, db)
    except RuntimeError as e:
        # MQTT 未连接
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ConfigPushResponse.model_validate(record)


@router.get("/{gateway_id}/config-history", response_model=PageResponse[ConfigPushRecordResponse], summary="配置下发历史")
async def config_history(
    gateway_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """查询网关配置下发历史"""
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gw = gw_result.scalar_one_or_none()
    if not gw:
        raise HTTPException(status_code=404, detail="网关不存在")

    query = select(ConfigPushRecord).where(ConfigPushRecord.gateway_id == gw.gateway_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(ConfigPushRecord.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[ConfigPushRecordResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{gateway_id}", response_model=GatewayResponse, summary="更新网关")
async def update_gateway(
    gateway_id: int,
    data: GatewayUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="网关不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(Gateway).where(Gateway.id == gateway_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    obj = result.scalar_one()
    return GatewayResponse.model_validate(obj)


@router.delete("/{gateway_id}", summary="删除网关")
async def delete_gateway(
    gateway_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="网关不存在")

    await db.execute(delete(Gateway).where(Gateway.id == gateway_id))
    await db.commit()
    return {"message": "网关已删除"}
