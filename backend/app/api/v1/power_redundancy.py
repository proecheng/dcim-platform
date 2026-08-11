"""
冗余配置管理 API - Story 25.4
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..deps import (
    SiteAccessContext,
    apply_device_site_scope,
    get_db,
    get_site_access_context,
    require_admin,
    require_viewer,
)
from ...models.user import User
from ...models.energy import PowerDevice
from ...schemas.diagnosis import RedundancyConfigUpdate, RedundancyConfigResponse

router = APIRouter()


@router.get("/devices/{device_id}/redundancy", response_model=RedundancyConfigResponse, summary="查询设备冗余配置")
async def get_device_redundancy(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """查询配电设备的冗余配置"""
    query = apply_device_site_scope(
        select(PowerDevice).where(PowerDevice.id == device_id), PowerDevice.monitor_device_id, context
    )
    result = await db.execute(query)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"设备 ID {device_id} 不存在")

    return RedundancyConfigResponse(
        device_id=device.id,
        device_code=device.device_code,
        device_name=device.device_name,
        device_type=device.device_type,
        redundancy_type=device.redundancy_type,
        redundancy_group_id=device.redundancy_group_id,
    )


@router.put("/devices/{device_id}/redundancy", response_model=RedundancyConfigResponse, summary="更新设备冗余配置")
async def update_device_redundancy(
    device_id: int,
    config: RedundancyConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """更新配电设备的冗余配置（仅管理员）"""
    query = apply_device_site_scope(
        select(PowerDevice).where(PowerDevice.id == device_id), PowerDevice.monitor_device_id, context
    )
    result = await db.execute(query)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"设备 ID {device_id} 不存在")

    # 更新冗余配置
    if config.redundancy_type is not None:
        device.redundancy_type = config.redundancy_type
    if config.redundancy_group_id is not None:
        device.redundancy_group_id = config.redundancy_group_id

    await db.commit()
    await db.refresh(device)

    return RedundancyConfigResponse(
        device_id=device.id,
        device_code=device.device_code,
        device_name=device.device_name,
        device_type=device.device_type,
        redundancy_type=device.redundancy_type,
        redundancy_group_id=device.redundancy_group_id,
    )
