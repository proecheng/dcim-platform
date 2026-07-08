"""设备模板管理 API"""

import hashlib
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, or_

from pydantic import ValidationError as PydanticValidationError

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.gateway import DeviceTemplate, DataSource, DataSourcePoint
from ...models.point import Point, PointRealtime
from ...schemas.gateway import (
    BuiltinDeviceTemplateResponse,
    DeviceTemplateCreate,
    DeviceTemplateUpdate,
    DeviceTemplateResponse,
    DataSourceCreate,
    DataSourceResponse,
    MstpGatewayExtraConfig,
    CreateMstpDatasourcesRequest,
    CreateMstpDatasourcesResponse,
)
from ...schemas.common import PageResponse
from ...data.protocol_templates import (
    as_device_template_payload,
    get_builtin_protocol_template,
    list_builtin_protocol_templates,
)
from ...services.device_template_binding import bind_template_datasource_to_power_device

router = APIRouter()

_POINT_CODE_MAX_LENGTH = 50


def _sanitize_point_code_fragment(value: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    fragment = re.sub(r"_+", "_", fragment).strip("_")
    return fragment.lower() or "point"


def _make_point_code(datasource_id: int, point_cfg: dict, address: str) -> str:
    raw_id = str(point_cfg.get("point_id") or point_cfg.get("name") or address)
    base = f"ds{datasource_id}_{_sanitize_point_code_fragment(raw_id)}"
    if len(base) <= _POINT_CODE_MAX_LENGTH:
        return base

    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    keep = _POINT_CODE_MAX_LENGTH - len(digest) - 1
    return f"{base[:keep]}_{digest}"


def _infer_point_type(point_cfg: dict) -> str:
    data_type = str(point_cfg.get("data_type") or "").lower()
    category = str(point_cfg.get("category") or "").lower()
    writable = bool(point_cfg.get("writable"))
    if writable and data_type == "bool":
        return "DO"
    if data_type == "bool" or category in {"alarm", "status"}:
        return "DI"
    return "AI"


def _infer_business_data_type(point_cfg: dict) -> str:
    data_type = str(point_cfg.get("data_type") or "").lower()
    if data_type == "bool":
        return "bool"
    if data_type == "string":
        return "string"
    return "float"


def _infer_function_code(address: str) -> Optional[int]:
    reg_type = address.split(":", 1)[0].upper() if ":" in address else "HR"
    return {"CO": 1, "DI": 2, "HR": 3, "IR": 4}.get(reg_type)


def _infer_device_type(template: DeviceTemplate) -> str:
    extra_config = template.extra_config or {}
    configured = extra_config.get("device_type") if isinstance(extra_config, dict) else None
    if configured:
        return str(configured).upper()
    model = (template.model or "").upper()
    name = (template.name or "").upper()
    if "UPS" in model or "UPS" in name:
        return "UPS"
    if "FUSIONCOL" in model or "COOL" in name or "温控" in name:
        return "AC"
    return "OTHER"


def _should_create_business_point(template: DeviceTemplate, point_cfg: dict) -> bool:
    """Only structured templates get automatic business points."""
    if point_cfg.get("point_id") and point_cfg.get("name"):
        return True
    extra_config = template.extra_config or {}
    return bool(isinstance(extra_config, dict) and extra_config.get("builtin_template_key"))


async def _create_business_point_from_template(
    db: AsyncSession,
    *,
    datasource: DataSource,
    template: DeviceTemplate,
    point_cfg: dict,
    address: str,
) -> Point | None:
    if not _should_create_business_point(template, point_cfg):
        return None

    scale = float(point_cfg.get("scale", 1.0))
    offset = float(point_cfg.get("offset", 0.0))
    point = Point(
        point_code=_make_point_code(datasource.id, point_cfg, address),
        point_name=str(point_cfg.get("name") or point_cfg.get("point_id") or address),
        point_type=_infer_point_type(point_cfg),
        device_type=_infer_device_type(template),
        area_code=str((datasource.connection_config or {}).get("area_code") or "A1")[:10],
        unit=point_cfg.get("unit") or None,
        data_type=_infer_business_data_type(point_cfg),
        collect_interval=datasource.collection_interval,
        store_interval=max(datasource.collection_interval, 60),
        register_address=address,
        function_code=_infer_function_code(address),
        scale_factor=scale,
        offset=offset,
        source="bridge",
        description=point_cfg.get("description") or template.name,
    )
    db.add(point)
    await db.flush()
    db.add(PointRealtime(point_id=point.id))
    return point


def _validate_extra_config(extra_config: Optional[dict]) -> None:
    """验证 extra_config：如果 gateway_type 为已知类型则做专项验证，否则透传"""
    if extra_config is None:
        return
    if not isinstance(extra_config, dict):
        return
    gateway_type = extra_config.get("gateway_type")
    if gateway_type == "bacnet_mstp_to_ip":
        try:
            MstpGatewayExtraConfig(**extra_config)
        except PydanticValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))


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
        query = query.where(
            or_(
                DeviceTemplate.name.contains(keyword),
                DeviceTemplate.manufacturer.contains(keyword),
                DeviceTemplate.model.contains(keyword),
            )
        )

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
    _validate_extra_config(data.extra_config)
    obj = DeviceTemplate(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return DeviceTemplateResponse.model_validate(obj)


@router.get("/builtins", response_model=list[BuiltinDeviceTemplateResponse], summary="获取内置协议模板")
async def list_builtin_templates(
    _: User = Depends(require_viewer),
):
    templates = []
    for template in list_builtin_protocol_templates():
        templates.append(
            {
                **template,
                "point_count": len(template.get("point_config", [])),
            }
        )
    return templates


@router.post(
    "/builtins/{template_key}/install",
    response_model=DeviceTemplateResponse,
    summary="安装内置协议模板到设备模板库",
)
async def install_builtin_template(
    template_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    template = get_builtin_protocol_template(template_key)
    if not template:
        raise HTTPException(status_code=404, detail="内置协议模板不存在")

    payload = as_device_template_payload(template)
    extra_config = payload.get("extra_config") or {}
    extra_config["builtin_template_key"] = template_key
    payload["extra_config"] = extra_config
    _validate_extra_config(payload.get("extra_config"))

    result = await db.execute(
        select(DeviceTemplate).where(
            DeviceTemplate.name == payload["name"],
            DeviceTemplate.manufacturer == payload["manufacturer"],
            DeviceTemplate.model == payload["model"],
            DeviceTemplate.protocol_type == payload["protocol_type"],
        )
    )
    obj = result.scalar_one_or_none()
    if obj:
        for key, value in payload.items():
            setattr(obj, key, value)
        obj.updated_at = datetime.now()
    else:
        obj = DeviceTemplate(**payload)
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
    if "extra_config" in update_data:
        _validate_extra_config(update_data["extra_config"])
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
    created_business_points = False
    business_point_bindings = []
    for pt_cfg in template.point_config or []:
        address = str(pt_cfg.get("address", "")).strip()
        if not address:
            continue
        business_point = await _create_business_point_from_template(
            db,
            datasource=ds,
            template=template,
            point_cfg=pt_cfg,
            address=address,
        )
        created_business_points = created_business_points or business_point is not None
        if business_point is not None:
            business_point_bindings.append((pt_cfg, business_point))
        point = DataSourcePoint(
            datasource_id=ds.id,
            point_id=business_point.id if business_point else None,
            address=address,
            data_type=pt_cfg.get("data_type"),
            scale=float(pt_cfg.get("scale", 1.0)),
            offset=float(pt_cfg.get("offset", 0.0)),
            enum_mapping=pt_cfg.get("enum_mapping"),
            is_dry_contact=pt_cfg.get("is_dry_contact", False),
        )
        db.add(point)

    if business_point_bindings:
        await bind_template_datasource_to_power_device(
            db,
            template=template,
            datasource=ds,
            point_bindings=business_point_bindings,
        )

    await db.commit()
    if created_business_points:
        from ...services.ingest_pipeline import invalidate_point_cache

        invalidate_point_cache()
    await db.refresh(ds)
    return DataSourceResponse.model_validate(ds)


@router.post(
    "/{template_id}/create-mstp-datasources",
    response_model=CreateMstpDatasourcesResponse,
    summary="从网关模板批量创建 MS/TP 数据源",
)
async def create_mstp_datasources(
    template_id: int,
    data: CreateMstpDatasourcesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    # 获取模板
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 验证 extra_config
    extra_config = template.extra_config
    if not extra_config or not isinstance(extra_config, dict):
        raise HTTPException(status_code=422, detail="模板缺少 extra_config")
    if extra_config.get("gateway_type") != "bacnet_mstp_to_ip":
        raise HTTPException(status_code=422, detail="模板 gateway_type 不是 bacnet_mstp_to_ip")

    try:
        mstp_cfg = MstpGatewayExtraConfig(**extra_config)
    except PydanticValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not mstp_cfg.downstream_devices:
        raise HTTPException(status_code=422, detail="模板 downstream_devices 为空，请先编辑模板添加下挂设备")

    # 创建网关 DataSource（is_enabled=False，不参与采集）
    gw_ds = DataSource(
        name=f"{template.name}-网关-{data.gateway_ip}",
        protocol_type=template.protocol_type,
        connection_config={
            "host": data.gateway_ip,
            "port": data.port,
            "device_id": mstp_cfg.gateway_device_instance,
            "is_mstp_gateway": True,
        },
        is_enabled=False,
        site_id=data.site_id,
    )
    db.add(gw_ds)
    await db.flush()  # 获取 gw_ds.id 供子设备引用

    device_datasources = []
    for dev in mstp_cfg.downstream_devices:
        # 创建子设备 DataSource
        child_ds = DataSource(
            name=dev.device_name,
            protocol_type=template.protocol_type,
            connection_config={
                "host": data.gateway_ip,
                "port": data.port,
                "device_id": dev.device_instance,
            },
            collection_interval=10,
            is_enabled=True,
            site_id=data.site_id,
            parent_datasource_id=gw_ds.id,
        )
        db.add(child_ds)
        device_datasources.append(child_ds)

    # 统一 flush 获取所有子设备 ID
    await db.flush()

    # 从模板填充点位
    created_business_points = False
    for child_ds in device_datasources:
        for pt_cfg in template.point_config or []:
            address = str(pt_cfg.get("address", "")).strip()
            if not address:
                continue
            business_point = await _create_business_point_from_template(
                db,
                datasource=child_ds,
                template=template,
                point_cfg=pt_cfg,
                address=address,
            )
            created_business_points = created_business_points or business_point is not None
            point = DataSourcePoint(
                datasource_id=child_ds.id,
                point_id=business_point.id if business_point else None,
                address=address,
                data_type=pt_cfg.get("data_type"),
                scale=float(pt_cfg.get("scale", 1.0)),
                offset=float(pt_cfg.get("offset", 0.0)),
                enum_mapping=pt_cfg.get("enum_mapping"),
                is_dry_contact=pt_cfg.get("is_dry_contact", False),
            )
            db.add(point)

    await db.commit()
    if created_business_points:
        from ...services.ingest_pipeline import invalidate_point_cache

        invalidate_point_cache()

    # refresh 所有对象
    await db.refresh(gw_ds)
    for ds in device_datasources:
        await db.refresh(ds)

    return CreateMstpDatasourcesResponse(
        gateway=DataSourceResponse.model_validate(gw_ds),
        devices=[DataSourceResponse.model_validate(ds) for ds in device_datasources],
        total_devices=len(device_datasources),
    )
