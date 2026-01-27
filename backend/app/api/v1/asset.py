"""
资产管理 API - v1
"""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.asset import (
    Asset, Cabinet, AssetLifecycle, MaintenanceRecord,
    AssetInventory, AssetInventoryItem, AssetStatus, AssetType
)
from ...schemas.asset import (
    CabinetCreate, CabinetUpdate, CabinetResponse,
    AssetCreate, AssetUpdate, AssetResponse,
    LifecycleResponse,
    MaintenanceCreate, MaintenanceResponse,
    InventoryCreate, InventoryItemUpdate, InventoryResponse, InventoryItemResponse,
    AssetStatistics
)
from ...schemas.common import PageResponse

router = APIRouter(prefix="/asset", tags=["资产管理"])


# ==================== 机柜管理 ====================

@router.get("/cabinets", response_model=List[CabinetResponse], summary="获取机柜列表")
async def get_cabinets(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取机柜列表（分页）
    """
    query = select(Cabinet).offset(skip).limit(limit)
    result = await db.execute(query)
    cabinets = result.scalars().all()

    # 计算每个机柜的已使用U数和可用U数
    cabinet_list = []
    for cabinet in cabinets:
        # 获取该机柜中所有资产占用的U数
        used_u_result = await db.execute(
            select(func.sum(Asset.u_height)).where(
                Asset.cabinet_id == cabinet.id,
                Asset.u_height.isnot(None)
            )
        )
        used_u = used_u_result.scalar() or 0

        cabinet_data = CabinetResponse.model_validate(cabinet)
        cabinet_data.used_u = used_u
        cabinet_data.available_u = (cabinet.total_u or 42) - used_u
        cabinet_list.append(cabinet_data)

    return cabinet_list


@router.get("/cabinets/{cabinet_id}", response_model=CabinetResponse, summary="获取机柜详情")
async def get_cabinet(
    cabinet_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取机柜详情
    """
    result = await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")

    # 计算已使用U数
    used_u_result = await db.execute(
        select(func.sum(Asset.u_height)).where(
            Asset.cabinet_id == cabinet_id,
            Asset.u_height.isnot(None)
        )
    )
    used_u = used_u_result.scalar() or 0

    cabinet_data = CabinetResponse.model_validate(cabinet)
    cabinet_data.used_u = used_u
    cabinet_data.available_u = (cabinet.total_u or 42) - used_u

    return cabinet_data


@router.get("/cabinets/{cabinet_id}/usage", summary="获取机柜U位使用情况")
async def get_cabinet_usage(
    cabinet_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
) -> Dict[str, Any]:
    """
    获取机柜U位使用情况，包含U位映射表
    """
    result = await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")

    total_u = cabinet.total_u or 42

    # 获取该机柜中所有资产
    assets_result = await db.execute(
        select(Asset).where(
            Asset.cabinet_id == cabinet_id,
            Asset.u_position.isnot(None),
            Asset.u_height.isnot(None)
        )
    )
    assets = assets_result.scalars().all()

    # 构建U位映射表
    u_map = {}
    used_u = 0

    for asset in assets:
        if asset.u_position and asset.u_height:
            for u in range(asset.u_position, asset.u_position + asset.u_height):
                if u <= total_u:
                    u_map[str(u)] = {
                        "asset_id": asset.id,
                        "asset_code": asset.asset_code,
                        "asset_name": asset.asset_name,
                        "asset_type": asset.asset_type.value if asset.asset_type else None
                    }
            used_u += asset.u_height

    available_u = total_u - used_u
    usage_rate = round((used_u / total_u * 100), 2) if total_u > 0 else 0

    return {
        "cabinet_id": cabinet_id,
        "cabinet_name": cabinet.cabinet_name,
        "total_u": total_u,
        "used_u": used_u,
        "available_u": available_u,
        "usage_rate": usage_rate,
        "u_map": u_map
    }


@router.post("/cabinets", response_model=CabinetResponse, summary="创建机柜")
async def create_cabinet(
    data: CabinetCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建新机柜
    """
    # 检查编码是否已存在
    existing = await db.execute(
        select(Cabinet).where(Cabinet.cabinet_code == data.cabinet_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="机柜编码已存在")

    cabinet = Cabinet(**data.model_dump())
    db.add(cabinet)
    await db.commit()
    await db.refresh(cabinet)

    cabinet_data = CabinetResponse.model_validate(cabinet)
    cabinet_data.used_u = 0
    cabinet_data.available_u = cabinet.total_u or 42

    return cabinet_data


@router.put("/cabinets/{cabinet_id}", response_model=CabinetResponse, summary="更新机柜")
async def update_cabinet(
    cabinet_id: int,
    data: CabinetUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新机柜信息
    """
    result = await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")

    # 如果更新编码，检查是否已存在
    update_data = data.model_dump(exclude_unset=True)
    if "cabinet_code" in update_data and update_data["cabinet_code"] != cabinet.cabinet_code:
        existing = await db.execute(
            select(Cabinet).where(Cabinet.cabinet_code == update_data["cabinet_code"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="机柜编码已存在")

    for key, value in update_data.items():
        if value is not None:
            setattr(cabinet, key, value)

    cabinet.updated_at = datetime.now()
    await db.commit()
    await db.refresh(cabinet)

    # 计算已使用U数
    used_u_result = await db.execute(
        select(func.sum(Asset.u_height)).where(
            Asset.cabinet_id == cabinet_id,
            Asset.u_height.isnot(None)
        )
    )
    used_u = used_u_result.scalar() or 0

    cabinet_data = CabinetResponse.model_validate(cabinet)
    cabinet_data.used_u = used_u
    cabinet_data.available_u = (cabinet.total_u or 42) - used_u

    return cabinet_data


@router.delete("/cabinets/{cabinet_id}", summary="删除机柜")
async def delete_cabinet(
    cabinet_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除机柜（如果有关联资产则不允许删除）
    """
    result = await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")

    # 检查是否有关联资产
    asset_count_result = await db.execute(
        select(func.count(Asset.id)).where(Asset.cabinet_id == cabinet_id)
    )
    asset_count = asset_count_result.scalar()

    if asset_count > 0:
        raise HTTPException(status_code=400, detail="机柜下存在关联资产，无法删除")

    await db.delete(cabinet)
    await db.commit()

    return {"message": "机柜删除成功"}


# ==================== 资产管理 ====================

@router.get("/assets", response_model=List[AssetResponse], summary="获取资产列表")
async def get_assets(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    asset_type: Optional[AssetType] = Query(None, description="资产类型"),
    status: Optional[AssetStatus] = Query(None, description="资产状态"),
    cabinet_id: Optional[int] = Query(None, description="机柜ID"),
    keyword: Optional[str] = Query(None, description="关键词(资产编码、名称、品牌、型号)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取资产列表（多条件筛选、分页）
    """
    query = select(Asset)

    conditions = []
    if asset_type:
        conditions.append(Asset.asset_type == asset_type)
    if status:
        conditions.append(Asset.status == status)
    if cabinet_id:
        conditions.append(Asset.cabinet_id == cabinet_id)
    if keyword:
        keyword_filter = or_(
            Asset.asset_code.contains(keyword),
            Asset.asset_name.contains(keyword),
            Asset.brand.contains(keyword),
            Asset.model.contains(keyword)
        )
        conditions.append(keyword_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Asset.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    assets = result.scalars().all()

    # 填充机柜名称和保修状态
    asset_list = []
    for asset in assets:
        asset_data = AssetResponse.model_validate(asset)

        # 获取机柜名称
        if asset.cabinet_id:
            cabinet_result = await db.execute(
                select(Cabinet).where(Cabinet.id == asset.cabinet_id)
            )
            cabinet = cabinet_result.scalar_one_or_none()
            if cabinet:
                asset_data.cabinet_name = cabinet.cabinet_name

        # 计算保修状态
        asset_data.warranty_status = _calculate_warranty_status(asset.warranty_end)
        asset_list.append(asset_data)

    return asset_list


@router.get("/assets/{asset_id}", response_model=AssetResponse, summary="获取资产详情")
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取资产详情
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    asset_data = AssetResponse.model_validate(asset)

    # 获取机柜名称
    if asset.cabinet_id:
        cabinet_result = await db.execute(
            select(Cabinet).where(Cabinet.id == asset.cabinet_id)
        )
        cabinet = cabinet_result.scalar_one_or_none()
        if cabinet:
            asset_data.cabinet_name = cabinet.cabinet_name

    # 计算保修状态
    asset_data.warranty_status = _calculate_warranty_status(asset.warranty_end)

    return asset_data


@router.post("/assets", response_model=AssetResponse, summary="创建资产")
async def create_asset(
    data: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    创建新资产
    """
    # 检查编码是否已存在
    existing = await db.execute(
        select(Asset).where(Asset.asset_code == data.asset_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="资产编码已存在")

    # 如果指定了机柜，检查机柜是否存在
    cabinet_name = None
    if data.cabinet_id:
        cabinet_result = await db.execute(
            select(Cabinet).where(Cabinet.id == data.cabinet_id)
        )
        cabinet = cabinet_result.scalar_one_or_none()
        if not cabinet:
            raise HTTPException(status_code=400, detail="指定的机柜不存在")
        cabinet_name = cabinet.cabinet_name

    asset = Asset(**data.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    # 添加生命周期记录
    to_location = None
    if cabinet_name:
        to_location = f"{cabinet_name} U{asset.u_position}" if asset.u_position else cabinet_name

    lifecycle = AssetLifecycle(
        asset_id=asset.id,
        action="purchase",
        action_date=datetime.now(),
        operator=current_user.username,
        from_location=None,
        to_location=to_location,
        remark="资产创建入库"
    )
    db.add(lifecycle)
    await db.commit()

    asset_data = AssetResponse.model_validate(asset)
    asset_data.cabinet_name = cabinet_name
    asset_data.warranty_status = _calculate_warranty_status(asset.warranty_end)

    return asset_data


@router.put("/assets/{asset_id}", response_model=AssetResponse, summary="更新资产")
async def update_asset(
    asset_id: int,
    data: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    更新资产信息
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 如果更新编码，检查是否已存在
    if "asset_code" in update_data and update_data["asset_code"] != asset.asset_code:
        existing = await db.execute(
            select(Asset).where(Asset.asset_code == update_data["asset_code"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="资产编码已存在")

    # 记录位置变更
    old_cabinet_id = asset.cabinet_id
    old_u_position = asset.u_position
    new_cabinet_id = update_data.get("cabinet_id", old_cabinet_id)
    new_u_position = update_data.get("u_position", old_u_position)
    location_changed = (old_cabinet_id != new_cabinet_id) or (old_u_position != new_u_position)

    # 记录状态变更
    old_status = asset.status
    new_status = update_data.get("status", old_status)
    status_changed = old_status != new_status

    # 更新资产属性
    for key, value in update_data.items():
        if value is not None:
            setattr(asset, key, value)

    asset.updated_at = datetime.now()
    await db.commit()
    await db.refresh(asset)

    # 添加位置变更生命周期记录
    if location_changed:
        from_location = None
        to_location = None

        if old_cabinet_id:
            old_cab_result = await db.execute(
                select(Cabinet).where(Cabinet.id == old_cabinet_id)
            )
            old_cabinet = old_cab_result.scalar_one_or_none()
            if old_cabinet:
                from_location = f"{old_cabinet.cabinet_name} U{old_u_position}" if old_u_position else old_cabinet.cabinet_name

        if new_cabinet_id:
            new_cab_result = await db.execute(
                select(Cabinet).where(Cabinet.id == new_cabinet_id)
            )
            new_cabinet = new_cab_result.scalar_one_or_none()
            if new_cabinet:
                to_location = f"{new_cabinet.cabinet_name} U{new_u_position}" if new_u_position else new_cabinet.cabinet_name

        lifecycle = AssetLifecycle(
            asset_id=asset_id,
            action="move",
            action_date=datetime.now(),
            operator=current_user.username,
            from_location=from_location,
            to_location=to_location,
            remark="资产位置变更"
        )
        db.add(lifecycle)
        await db.commit()

    # 添加状态变更生命周期记录
    if status_changed:
        action = "status_change"
        remark = f"状态变更: {old_status.value if old_status else 'None'} -> {new_status.value if new_status else 'None'}"

        if new_status == AssetStatus.scrapped:
            action = "scrap"
            remark = "资产报废"
        elif new_status == AssetStatus.maintenance:
            action = "maintain"
            remark = "资产送修"
        elif new_status == AssetStatus.in_use:
            action = "deploy"
            remark = "资产部署上线"

        lifecycle = AssetLifecycle(
            asset_id=asset_id,
            action=action,
            action_date=datetime.now(),
            operator=current_user.username,
            from_location=None,
            to_location=None,
            remark=remark
        )
        db.add(lifecycle)
        await db.commit()

    # 获取机柜名称
    cabinet_name = None
    if asset.cabinet_id:
        cabinet_result = await db.execute(
            select(Cabinet).where(Cabinet.id == asset.cabinet_id)
        )
        cabinet = cabinet_result.scalar_one_or_none()
        if cabinet:
            cabinet_name = cabinet.cabinet_name

    asset_data = AssetResponse.model_validate(asset)
    asset_data.cabinet_name = cabinet_name
    asset_data.warranty_status = _calculate_warranty_status(asset.warranty_end)

    return asset_data


@router.delete("/assets/{asset_id}", summary="删除资产")
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除资产及其关联记录
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # 删除关联的生命周期记录
    await db.execute(
        select(AssetLifecycle).where(AssetLifecycle.asset_id == asset_id)
    )
    await db.execute(
        AssetLifecycle.__table__.delete().where(AssetLifecycle.asset_id == asset_id)
    )

    # 删除关联的维护记录
    await db.execute(
        MaintenanceRecord.__table__.delete().where(MaintenanceRecord.asset_id == asset_id)
    )

    # 删除关联的盘点明细
    await db.execute(
        AssetInventoryItem.__table__.delete().where(AssetInventoryItem.asset_id == asset_id)
    )

    await db.delete(asset)
    await db.commit()

    return {"message": "资产删除成功"}


@router.get("/assets/{asset_id}/lifecycle", response_model=List[LifecycleResponse], summary="获取资产生命周期记录")
async def get_asset_lifecycle(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取指定资产的生命周期记录
    """
    # 检查资产是否存在
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="资产不存在")

    result = await db.execute(
        select(AssetLifecycle).where(
            AssetLifecycle.asset_id == asset_id
        ).order_by(AssetLifecycle.action_date.desc())
    )
    records = result.scalars().all()

    return [LifecycleResponse.model_validate(r) for r in records]


# ==================== 维护管理 ====================

@router.post("/maintenance", response_model=MaintenanceResponse, summary="创建维护记录")
async def create_maintenance(
    data: MaintenanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    创建维护记录并更新资产状态
    """
    # 检查资产是否存在
    asset_result = await db.execute(select(Asset).where(Asset.id == data.asset_id))
    asset = asset_result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # 创建维护记录
    record = MaintenanceRecord(**data.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # 更新资产状态为维护中
    asset.status = AssetStatus.maintenance
    asset.updated_at = datetime.now()
    await db.commit()

    # 添加生命周期记录
    lifecycle = AssetLifecycle(
        asset_id=asset.id,
        action="maintain",
        action_date=datetime.now(),
        operator=data.technician or current_user.username,
        from_location=None,
        to_location=None,
        remark=f"开始维护: {data.maintenance_type} - {data.description or ''}"
    )
    db.add(lifecycle)
    await db.commit()

    return MaintenanceResponse.model_validate(record)


@router.put("/maintenance/{record_id}/complete", response_model=MaintenanceResponse, summary="完成维护")
async def complete_maintenance(
    record_id: int,
    result: Optional[str] = Query(None, description="维护结果"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    完成维护并恢复资产状态
    """
    record_result = await db.execute(
        select(MaintenanceRecord).where(MaintenanceRecord.id == record_id)
    )
    record = record_result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="维护记录不存在")

    # 更新维护记录
    record.end_time = datetime.now()
    if result:
        record.result = result
    await db.commit()
    await db.refresh(record)

    # 恢复资产状态为使用中
    asset_result = await db.execute(select(Asset).where(Asset.id == record.asset_id))
    asset = asset_result.scalar_one_or_none()

    if asset:
        asset.status = AssetStatus.in_use
        asset.updated_at = datetime.now()
        await db.commit()

        # 添加生命周期记录
        lifecycle = AssetLifecycle(
            asset_id=asset.id,
            action="deploy",
            action_date=datetime.now(),
            operator=record.technician,
            from_location=None,
            to_location=None,
            remark=f"维护完成: {result or '正常'}"
        )
        db.add(lifecycle)
        await db.commit()

    return MaintenanceResponse.model_validate(record)


@router.get("/maintenance", response_model=List[MaintenanceResponse], summary="获取维护记录列表")
async def get_maintenance_records(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    asset_id: Optional[int] = Query(None, description="资产ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取维护记录列表（可按资产ID筛选）
    """
    query = select(MaintenanceRecord)

    if asset_id:
        query = query.where(MaintenanceRecord.asset_id == asset_id)

    query = query.order_by(MaintenanceRecord.start_time.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()

    return [MaintenanceResponse.model_validate(r) for r in records]


# ==================== 盘点管理 ====================

@router.post("/inventory", response_model=InventoryResponse, summary="创建资产盘点")
async def create_inventory(
    data: InventoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建资产盘点任务，自动生成盘点明细
    """
    # 检查盘点编码是否已存在
    existing = await db.execute(
        select(AssetInventory).where(AssetInventory.inventory_code == data.inventory_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="盘点编码已存在")

    # 创建盘点主记录
    inventory = AssetInventory(**data.model_dump())
    inventory.status = "pending"
    db.add(inventory)
    await db.commit()
    await db.refresh(inventory)

    # 获取所有在用和借出的资产，创建盘点明细
    assets_result = await db.execute(
        select(Asset).where(
            Asset.status.in_([AssetStatus.in_use, AssetStatus.borrowed])
        )
    )
    assets = assets_result.scalars().all()

    for asset in assets:
        expected_location = None
        if asset.cabinet_id:
            cabinet_result = await db.execute(
                select(Cabinet).where(Cabinet.id == asset.cabinet_id)
            )
            cabinet = cabinet_result.scalar_one_or_none()
            if cabinet:
                expected_location = f"{cabinet.cabinet_name} U{asset.u_position}" if asset.u_position else cabinet.cabinet_name

        item = AssetInventoryItem(
            inventory_id=inventory.id,
            asset_id=asset.id,
            expected_location=expected_location,
            is_matched=False
        )
        db.add(item)

    await db.commit()

    # 更新统计信息
    await _update_inventory_stats(db, inventory.id)
    await db.refresh(inventory)

    return InventoryResponse.model_validate(inventory)


@router.get("/inventory", response_model=List[InventoryResponse], summary="获取盘点列表")
async def get_inventory_list(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取资产盘点列表
    """
    query = select(AssetInventory).order_by(
        AssetInventory.created_at.desc()
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    inventories = result.scalars().all()

    return [InventoryResponse.model_validate(inv) for inv in inventories]


@router.get("/inventory/{inventory_id}/items", response_model=List[InventoryItemResponse], summary="获取盘点明细")
async def get_inventory_items(
    inventory_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取指定盘点任务的明细列表
    """
    # 检查盘点是否存在
    inventory_result = await db.execute(
        select(AssetInventory).where(AssetInventory.id == inventory_id)
    )
    if not inventory_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="盘点任务不存在")

    result = await db.execute(
        select(AssetInventoryItem).where(
            AssetInventoryItem.inventory_id == inventory_id
        )
    )
    items = result.scalars().all()

    return [InventoryItemResponse.model_validate(item) for item in items]


@router.put("/inventory/items/{item_id}", response_model=InventoryItemResponse, summary="更新盘点明细")
async def update_inventory_item(
    item_id: int,
    data: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新盘点明细（录入盘点结果）
    """
    result = await db.execute(
        select(AssetInventoryItem).where(AssetInventoryItem.id == item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="盘点明细不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(item, key, value)

    if not item.check_time:
        item.check_time = datetime.now()

    await db.commit()
    await db.refresh(item)

    # 更新盘点统计信息
    await _update_inventory_stats(db, item.inventory_id)

    return InventoryItemResponse.model_validate(item)


# ==================== 统计分析 ====================

@router.get("/statistics", response_model=AssetStatistics, summary="获取资产统计信息")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取资产统计信息
    """
    # 资产总数
    total_result = await db.execute(select(func.count(Asset.id)))
    total_count = total_result.scalar() or 0

    # 按状态统计
    status_result = await db.execute(
        select(Asset.status, func.count(Asset.id)).group_by(Asset.status)
    )
    by_status = {
        status.value if status else "unknown": count
        for status, count in status_result.all()
    }

    # 按类型统计
    type_result = await db.execute(
        select(Asset.asset_type, func.count(Asset.id)).group_by(Asset.asset_type)
    )
    by_type = {
        asset_type.value if asset_type else "unknown": count
        for asset_type, count in type_result.all()
    }

    # 按部门统计
    dept_result = await db.execute(
        select(Asset.department, func.count(Asset.id)).where(
            Asset.department.isnot(None)
        ).group_by(Asset.department)
    )
    by_department = {
        dept or "未分配": count
        for dept, count in dept_result.all()
    }

    # 资产总价值
    value_result = await db.execute(select(func.sum(Asset.purchase_price)))
    total_value = value_result.scalar() or 0

    # 保修即将到期数量（30天内）
    expiring_date = date.today() + timedelta(days=30)
    expiring_result = await db.execute(
        select(func.count(Asset.id)).where(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= expiring_date,
            Asset.warranty_end >= date.today(),
            Asset.status != AssetStatus.scrapped
        )
    )
    warranty_expiring_count = expiring_result.scalar() or 0

    return AssetStatistics(
        total_count=total_count,
        by_status=by_status,
        by_type=by_type,
        by_department=by_department,
        total_value=float(total_value),
        warranty_expiring_count=warranty_expiring_count
    )


@router.get("/warranty-expiring", response_model=List[AssetResponse], summary="获取即将过保资产")
async def get_warranty_expiring_assets(
    days: int = Query(30, ge=1, le=365, description="天数范围"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取保修即将到期的资产
    """
    expiring_date = date.today() + timedelta(days=days)

    result = await db.execute(
        select(Asset).where(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= expiring_date,
            Asset.warranty_end >= date.today(),
            Asset.status != AssetStatus.scrapped
        ).order_by(Asset.warranty_end.asc())
    )
    assets = result.scalars().all()

    asset_list = []
    for asset in assets:
        asset_data = AssetResponse.model_validate(asset)

        # 获取机柜名称
        if asset.cabinet_id:
            cabinet_result = await db.execute(
                select(Cabinet).where(Cabinet.id == asset.cabinet_id)
            )
            cabinet = cabinet_result.scalar_one_or_none()
            if cabinet:
                asset_data.cabinet_name = cabinet.cabinet_name

        asset_data.warranty_status = _calculate_warranty_status(asset.warranty_end)
        asset_list.append(asset_data)

    return asset_list


# ==================== 辅助函数 ====================

def _calculate_warranty_status(warranty_end: Optional[date]) -> str:
    """
    计算保修状态

    Args:
        warranty_end: 保修结束日期

    Returns:
        保修状态: valid/expiring/expired/unknown
    """
    if not warranty_end:
        return "unknown"

    today = date.today()
    if warranty_end < today:
        return "expired"
    elif warranty_end <= today + timedelta(days=30):
        return "expiring"
    else:
        return "valid"


async def _update_inventory_stats(db: AsyncSession, inventory_id: int) -> None:
    """
    更新盘点统计信息

    Args:
        db: 数据库会话
        inventory_id: 盘点ID
    """
    inventory_result = await db.execute(
        select(AssetInventory).where(AssetInventory.id == inventory_id)
    )
    inventory = inventory_result.scalar_one_or_none()

    if not inventory:
        return

    items_result = await db.execute(
        select(AssetInventoryItem).where(
            AssetInventoryItem.inventory_id == inventory_id
        )
    )
    items = items_result.scalars().all()

    total_count = len(items)
    checked_count = sum(1 for item in items if item.check_time is not None)
    matched_count = sum(1 for item in items if item.is_matched)
    unmatched_count = sum(1 for item in items if item.check_time is not None and not item.is_matched)

    inventory.total_count = total_count
    inventory.checked_count = checked_count
    inventory.matched_count = matched_count
    inventory.unmatched_count = unmatched_count

    # 更新盘点状态
    if checked_count == 0:
        inventory.status = "pending"
    elif checked_count < total_count:
        inventory.status = "in_progress"
    else:
        inventory.status = "completed"
        inventory.completed_at = datetime.now()

    await db.commit()
