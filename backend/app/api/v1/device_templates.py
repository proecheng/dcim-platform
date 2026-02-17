"""设备模板管理 API"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, or_

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.gateway import DeviceTemplate, DataSource, DataSourcePoint
from ...schemas.gateway import (
    DeviceTemplateCreate, DeviceTemplateUpdate, DeviceTemplateResponse,
    DataSourceCreate, DataSourceResponse,
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[DeviceTemplateResponse], summary="获取设备模板列表")
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manufacturer: Optional[str] = Query(None, description="厂商"),
    model_name: Optional[str] = Query(None, description="型号"),
    protocol_type: Optional[str] = Query(None, description="协议类型"),
    keyword: Optional[str] = Query(None, description="关键词"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    query = select(DeviceTemplate)
    if manufacturer:
        query = query.where(DeviceTemplate.manufacturer == manufacturer)
    if model_name:
        query = query.where(DeviceTemplate.model == model_name)
    if protocol_type:
        query = query.where(DeviceTemplate.protocol_type == protocol_type)
    if keyword:
        query = query.where(or_(
            DeviceTemplate.name.contains(keyword),
            DeviceTemplate.manufacturer.contains(keyword),
            DeviceTemplate.model.contains(keyword),
        ))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(DeviceTemplate.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[DeviceTemplateResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DeviceTemplateResponse, summary="创建设备模板")
async def create_template(
    data: DeviceTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    obj = DeviceTemplate(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return DeviceTemplateResponse.model_validate(obj)


@router.get("/{template_id}", response_model=DeviceTemplateResponse, summary="获取模板详情")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")
    return DeviceTemplateResponse.model_validate(obj)


@router.put("/{template_id}", response_model=DeviceTemplateResponse, summary="更新模板")
async def update_template(
    template_id: int,
    data: DeviceTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(DeviceTemplate).where(DeviceTemplate.id == template_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one()
    return DeviceTemplateResponse.model_validate(obj)


@router.delete("/{template_id}", summary="删除模板")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="模板不存在")

    await db.execute(delete(DeviceTemplate).where(DeviceTemplate.id == template_id))
    await db.commit()
    return {"message": "模板已删除"}


@router.post("/{template_id}/create-datasource", response_model=DataSourceResponse, summary="从模板创建数据源")
async def create_datasource_from_template(
    template_id: int,
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    # 获取模板
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 创建数据源
    ds = DataSource(**data.model_dump())
    db.add(ds)
    await db.flush()  # 获取 ds.id

    # 从模板填充点位
    for pt_cfg in (template.point_config or []):
        point = DataSourcePoint(
            datasource_id=ds.id,
            address=str(pt_cfg.get("address", "")),
            data_type=pt_cfg.get("data_type"),
            scale=float(pt_cfg.get("scale", 1.0)),
            offset=float(pt_cfg.get("offset", 0.0)),
            enum_mapping=pt_cfg.get("enum_mapping"),
            is_dry_contact=pt_cfg.get("is_dry_contact", False),
        )
        db.add(point)

    await db.commit()
    await db.refresh(ds)
    return DataSourceResponse.model_validate(ds)
