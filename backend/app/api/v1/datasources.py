"""数据源管理 API"""

import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import (
    SiteAccessContext,
    apply_site_scope,
    get_db,
    get_site_access_context,
    get_user_site_ids,
    require_admin,
    require_context_site_access,
    require_operator,
    require_viewer,
)
from ...models.user import User
from ...models.gateway import DataSource, DataSourceStatus
from ...schemas.gateway import DataSourceCreate, DataSourceUpdate, DataSourceResponse, ConnectionTestRequest
from ...services.connection_test import test_datasource_connection
from gateway.adapters.registry import ADAPTER_REGISTRY as _ADAPTER_REGISTRY
from ...schemas.common import PageResponse
import json
from ...models.log import OperationLog

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 已知协议类型白名单（后续 Story 新增协议时扩展此列表）
KNOWN_PROTOCOL_TYPES = {
    "modbus_tcp",
    "modbus_rtu",
    "snmp_v2c",
    "snmp_v3",
    "mqtt",
    "http_rest",
    "bacnet_ip",
    "opc_ua",
}


def _datasource_scope(query, context: SiteAccessContext):
    return apply_site_scope(query, DataSource.site_id, context)


async def _authorized_datasource(db: AsyncSession, datasource_id: int, context: SiteAccessContext) -> DataSource:
    result = await db.execute(_datasource_scope(select(DataSource).where(DataSource.id == datasource_id), context))
    datasource = result.scalar_one_or_none()
    if datasource is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return datasource


@router.put("/{datasource_id}/write-permission", summary="切换数据源写入权限")
async def toggle_write_permission(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    # 查找数据源
    obj = await _authorized_datasource(db, datasource_id, site_context)

    old_value = obj.write_enabled
    new_value = not old_value

    # 更新写入权限
    await db.execute(
        update(DataSource)
        .where(DataSource.id == datasource_id)
        .values(
            write_enabled=new_value,
            updated_at=datetime.now(),
        )
    )

    # 记录操作日志
    log = OperationLog(
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        module="datasource",
        action="update",
        target_type="datasource",
        target_id=datasource_id,
        target_name=obj.name,
        old_value=json.dumps({"write_enabled": old_value}),
        new_value=json.dumps({"write_enabled": new_value}),
        remark=f"{'开启' if new_value else '关闭'}写入权限",
    )
    db.add(log)
    await db.commit()

    return {"write_enabled": new_value, "message": f"写入权限已{'开启' if new_value else '关闭'}"}


@router.get("", response_model=PageResponse[DataSourceResponse], summary="获取数据源列表")
async def list_datasources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    protocol_type: Optional[str] = Query(None, description="协议类型"),
    gateway_id: Optional[int] = Query(None, description="网关 ID"),
    site_id: Optional[int] = Query(None, description="站点ID"),
    status: Optional[str] = Query(None, description="状态"),
    parent_datasource_id: Optional[int] = Query(None, description="父数据源ID（过滤网关下的子设备）"),
    keyword: Optional[str] = Query(None, description="按名称搜索关键字"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    user_site_ids: Optional[list[int]] = Depends(get_user_site_ids),
):
    query = select(DataSource)
    # 站点权限过滤
    if user_site_ids is not None:
        query = query.where(DataSource.site_id.in_(user_site_ids))
    if site_id is not None:
        query = query.where(DataSource.site_id == site_id)
    if protocol_type:
        query = query.where(DataSource.protocol_type == protocol_type)
    if gateway_id is not None:
        query = query.where(DataSource.gateway_id == gateway_id)
    if status:
        query = query.where(DataSource.status == status)
    if parent_datasource_id is not None:
        query = query.where(DataSource.parent_datasource_id == parent_datasource_id)
    if keyword:
        query = query.where(DataSource.name.ilike(f"%{keyword}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(DataSource.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[DataSourceResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DataSourceResponse, summary="创建数据源")
async def create_datasource(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    require_context_site_access(data.site_id, site_context)
    # 校验协议类型
    if data.protocol_type not in KNOWN_PROTOCOL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的协议类型: {data.protocol_type}，支持: {', '.join(sorted(KNOWN_PROTOCOL_TYPES))}",
        )

    obj = DataSource(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return DataSourceResponse.model_validate(obj)


@router.post("/test-connection", summary="测试数据源连接")
async def test_connection(
    req: ConnectionTestRequest,
    _: User = Depends(require_operator),
):
    if req.protocol_type not in _ADAPTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的协议类型: {req.protocol_type}")

    result = await test_datasource_connection(req.protocol_type, req.connection_config)
    return result


@router.get("/export-report", summary="导出对接报告")
async def export_report(
    protocol_type: Optional[str] = Query(None),
    gateway_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    from ...models.gateway import DataSourcePoint
    from ...services.report_export import generate_integration_report

    # 查询数据源
    query = select(DataSource)
    if protocol_type:
        query = query.where(DataSource.protocol_type == protocol_type)
    if gateway_id is not None:
        query = query.where(DataSource.gateway_id == gateway_id)
    if status:
        query = query.where(DataSource.status == status)
    query = query.order_by(DataSource.id)

    result = await db.execute(query)
    ds_list = result.scalars().all()

    datasources = []
    ds_id_to_name = {}
    ds_ids = []
    for ds in ds_list:
        ds_ids.append(ds.id)
        ds_id_to_name[ds.id] = ds.name
        datasources.append(
            {
                "name": ds.name,
                "protocol_type": ds.protocol_type,
                "connection_config": ds.connection_config,
                "status": ds.status,
                "last_communication": ds.last_communication,
                "created_at": ds.created_at,
                "is_enabled": ds.is_enabled,
            }
        )

    points = []
    if ds_ids:
        pt_result = await db.execute(
            select(DataSourcePoint)
            .where(DataSourcePoint.datasource_id.in_(ds_ids))
            .order_by(DataSourcePoint.datasource_id, DataSourcePoint.id)
        )
        for pt in pt_result.scalars().all():
            points.append(
                {
                    "datasource_name": ds_id_to_name.get(pt.datasource_id, ""),
                    "address": pt.address,
                    "data_type": pt.data_type,
                    "scale": pt.scale,
                    "offset": pt.offset,
                    "is_dry_contact": pt.is_dry_contact,
                }
            )

    excel_bytes = generate_integration_report(datasources, points)

    filename = f"integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/communication-status", summary="获取数据源通信状态")
async def get_communication_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    from ...models.gateway import DataSourcePoint
    from ...models.point import Point

    result = await db.execute(
        select(DataSource).where(DataSource.is_enabled == True).order_by(DataSource.name)  # noqa: E712
    )
    datasources = result.scalars().all()

    status_list = []
    for ds in datasources:
        # 统计受影响点位数
        points_result = await db.execute(
            select(func.count(DataSourcePoint.id)).where(DataSourcePoint.datasource_id == ds.id)
        )
        affected_points = points_result.scalar() or 0

        # 统计受影响设备数
        devices_result = await db.execute(
            select(func.count(func.distinct(Point.device_id)))
            .select_from(DataSourcePoint)
            .join(Point, DataSourcePoint.point_id == Point.id)
            .where(
                DataSourcePoint.datasource_id == ds.id,
                DataSourcePoint.point_id.isnot(None),
                Point.device_id.isnot(None),
            )
        )
        affected_devices = devices_result.scalar() or 0

        # 计算中断时长
        interruption_seconds = None
        if ds.status == DataSourceStatus.INTERRUPTED and ds.last_communication:
            interruption_seconds = int((datetime.now() - ds.last_communication).total_seconds())

        status_list.append(
            {
                "id": ds.id,
                "name": ds.name,
                "protocol_type": ds.protocol_type,
                "status": ds.status,
                "last_communication": ds.last_communication.isoformat() if ds.last_communication else None,
                "consecutive_failures": ds.consecutive_failures,
                "retry_max_failures": ds.retry_max_failures,
                "interruption_duration_seconds": interruption_seconds,
                "affected_points": affected_points,
                "affected_devices": affected_devices,
            }
        )

    return status_list


@router.get("/{datasource_id}", response_model=DataSourceResponse, summary="获取数据源详情")
async def get_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    obj = await _authorized_datasource(db, datasource_id, site_context)
    return DataSourceResponse.model_validate(obj)


@router.put("/{datasource_id}", response_model=DataSourceResponse, summary="更新数据源")
async def update_datasource(
    datasource_id: int,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    await _authorized_datasource(db, datasource_id, site_context)

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(DataSource).where(DataSource.id == datasource_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    obj = result.scalar_one()
    return DataSourceResponse.model_validate(obj)


@router.post("/{datasource_id}/test-connection", summary="测试已有数据源连接")
async def test_existing_connection(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    obj = await _authorized_datasource(db, datasource_id, site_context)

    if obj.protocol_type not in _ADAPTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的协议类型: {obj.protocol_type}")

    test_result = await test_datasource_connection(obj.protocol_type, obj.connection_config)
    return test_result


@router.post("/{datasource_id}/points/validate", summary="预校验点位 Excel")
async def validate_points_excel(
    datasource_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    await _authorized_datasource(db, datasource_id, site_context)
    # 文件格式校验
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")

    # 文件大小校验
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB，请分批导入")

    # 数据源存在性校验
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="数据源不存在")

    from ...services.point_import import validate_points

    report = await validate_points(content, datasource_id, db)
    return report


@router.post("/{datasource_id}/points/import", summary="批量导入点位")
async def import_points_excel(
    datasource_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    await _authorized_datasource(db, datasource_id, site_context)
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB，请分批导入")

    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="数据源不存在")

    from ...services.point_import import import_points

    import_result = await import_points(content, datasource_id, db)
    if not import_result["success"]:
        raise HTTPException(status_code=400, detail={"message": "校验失败", "report": import_result["report"]})
    return import_result


@router.delete("/{datasource_id}", summary="删除数据源")
async def delete_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    await _authorized_datasource(db, datasource_id, site_context)

    await db.execute(delete(DataSource).where(DataSource.id == datasource_id))
    await db.commit()
    return {"message": "数据源已删除"}
