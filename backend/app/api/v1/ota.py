"""OTA 升级 API — Story 15.5"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from ..deps import get_db, require_operator, require_admin
from ...models.user import User
from ...models.gateway import FirmwarePackage, OtaTask, OtaTaskGateway
from ...schemas.ota import (
    FirmwareCreate,
    FirmwareResponse,
    OtaTaskCreate,
    OtaTaskResponse,
    OtaTaskDetailResponse,
    OtaGatewayStatus,
)
from ...schemas.common import PageResponse
from ...services.ota_service import ota_service

router = APIRouter()


# ---- 固件包管理 ----


@router.post("/firmware", response_model=FirmwareResponse, summary="注册固件包")
async def create_firmware(
    data: FirmwareCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """注册新固件包（仅记录元数据，不上传文件）"""
    # 检查版本唯一性
    existing = await db.execute(select(FirmwarePackage).where(FirmwarePackage.version == data.version))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"固件版本已存在: {data.version}")

    obj = FirmwarePackage(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return FirmwareResponse.model_validate(obj)


@router.get("/firmware", response_model=list[FirmwareResponse], summary="固件包列表")
async def list_firmware(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    query = select(FirmwarePackage)
    if is_active is not None:
        query = query.where(FirmwarePackage.is_active == is_active)
    query = query.order_by(FirmwarePackage.id.desc())
    result = await db.execute(query)
    items = result.scalars().all()
    return [FirmwareResponse.model_validate(i) for i in items]


@router.delete("/firmware/{firmware_id}", summary="删除固件包")
async def delete_firmware(
    firmware_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    result = await db.execute(select(FirmwarePackage).where(FirmwarePackage.id == firmware_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "固件包不存在")
    # 检查是否有活跃任务引用该固件
    active_result = await db.execute(
        select(func.count())
        .select_from(OtaTask)
        .where(
            OtaTask.firmware_id == firmware_id,
            OtaTask.status.in_(["pending", "running", "paused"]),
        )
    )
    if active_result.scalar():
        raise HTTPException(400, "该固件包有关联的活跃任务，无法删除")
    await db.execute(delete(FirmwarePackage).where(FirmwarePackage.id == firmware_id))
    await db.commit()
    return {"detail": "已删除"}


# ---- OTA 任务管理 ----


@router.post("/tasks", response_model=OtaTaskResponse, summary="创建升级任务")
async def create_task(
    data: OtaTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
):
    try:
        task = await ota_service.create_task(
            firmware_id=data.firmware_id,
            gateway_ids=data.gateway_ids,
            strategy=data.strategy,
            batch_size=data.batch_size,
            batch_interval=data.batch_interval,
            canary_percent=data.canary_percent,
            created_by=user.username if hasattr(user, "username") else None,
            db=db,
        )
        return OtaTaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/tasks", response_model=PageResponse[OtaTaskResponse], summary="任务列表")
async def list_tasks(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    query = select(OtaTask)
    if status:
        query = query.where(OtaTask.status == status)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(OtaTask.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        total=total,
        items=[OtaTaskResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/{task_id}", response_model=OtaTaskDetailResponse, summary="任务详情")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    result = await db.execute(select(OtaTask).where(OtaTask.task_id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")

    # 获取各网关状态
    gw_result = await db.execute(
        select(OtaTaskGateway)
        .where(OtaTaskGateway.task_id == task_id)
        .order_by(OtaTaskGateway.batch_index, OtaTaskGateway.id)
    )
    gateways = gw_result.scalars().all()

    response = OtaTaskDetailResponse.model_validate(task)
    response.gateways = [OtaGatewayStatus.model_validate(g) for g in gateways]
    return response


@router.post("/tasks/{task_id}/start", summary="启动任务")
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    from ...mqtt import mqtt_service

    try:
        await ota_service.start_task(task_id, mqtt_service.publish, db)
        return {"detail": "任务已启动"}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.post("/tasks/{task_id}/cancel", summary="取消任务")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    from ...mqtt import mqtt_service

    try:
        await ota_service.cancel_task(task_id, mqtt_service.publish, db)
        return {"detail": "任务已取消"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/pause", summary="暂停任务")
async def pause_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    try:
        await ota_service.pause_task(task_id, db)
        return {"detail": "任务已暂停"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/resume", summary="恢复任务")
async def resume_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    from ...mqtt import mqtt_service

    try:
        await ota_service.resume_task(task_id, mqtt_service.publish, db)
        return {"detail": "任务已恢复"}
    except ValueError as e:
        raise HTTPException(400, str(e))
