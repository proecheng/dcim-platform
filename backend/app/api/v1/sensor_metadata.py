"""
传感器元数据管理 API
Story 25.5: 传感器元数据与精度加权
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.diagnosis import SensorMetadata
from app.models.user import User
from app.schemas.diagnosis import (
    SensorMetadataCreate,
    SensorMetadataUpdate,
    SensorMetadataResponse,
    SensorMetadataListResponse,
    CalibrationStatusResponse
)
from app.services.diagnosis.sensor_metadata_service import (
    check_calibration_status,
    check_expired_calibrations
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SensorMetadataResponse, status_code=201)
async def create_sensor_metadata(
    data: SensorMetadataCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建传感器元数据

    权限: admin/operator
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="权限不足")

    # 检查点位是否已存在元数据
    result = await db.execute(
        select(SensorMetadata).where(SensorMetadata.point_id == data.point_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"点位 {data.point_id} 已存在元数据")

    # 创建元数据
    metadata = SensorMetadata(**data.model_dump())
    db.add(metadata)
    await db.commit()
    await db.refresh(metadata)

    # 发布 Redis 更新通知
    await _publish_metadata_update(data.point_id)

    logger.info(f"创建传感器元数据: point_id={data.point_id}, accuracy_class={data.accuracy_class}")
    return metadata


@router.get("/", response_model=SensorMetadataListResponse)
async def list_sensor_metadata(
    point_id: Optional[int] = Query(None, description="点位ID过滤"),
    accuracy_class: Optional[float] = Query(None, description="精度等级过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询传感器元数据列表

    权限: 所有登录用户
    """
    # 构建查询
    query = select(SensorMetadata)

    if point_id is not None:
        query = query.where(SensorMetadata.point_id == point_id)
    if accuracy_class is not None:
        query = query.where(SensorMetadata.accuracy_class == accuracy_class)

    # 获取总数
    from sqlalchemy import func
    count_query = select(func.count()).select_from(SensorMetadata)
    if point_id is not None:
        count_query = count_query.where(SensorMetadata.point_id == point_id)
    if accuracy_class is not None:
        count_query = count_query.where(SensorMetadata.accuracy_class == accuracy_class)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页查询
    skip = (page - 1) * page_size
    query = query.offset(skip).limit(page_size)
    result = await db.execute(query)
    metadata_list = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": metadata_list
    }


@router.get("/{metadata_id}", response_model=SensorMetadataResponse)
async def get_sensor_metadata(
    metadata_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取传感器元数据详情

    权限: 所有登录用户
    """
    result = await db.execute(
        select(SensorMetadata).where(SensorMetadata.id == metadata_id)
    )
    metadata = result.scalar_one_or_none()

    if not metadata:
        raise HTTPException(status_code=404, detail="传感器元数据不存在")

    return metadata


@router.put("/{metadata_id}", response_model=SensorMetadataResponse)
async def update_sensor_metadata(
    metadata_id: int,
    data: SensorMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新传感器元数据

    权限: admin/operator
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="权限不足")

    result = await db.execute(
        select(SensorMetadata).where(SensorMetadata.id == metadata_id)
    )
    metadata = result.scalar_one_or_none()

    if not metadata:
        raise HTTPException(status_code=404, detail="传感器元数据不存在")

    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(metadata, key, value)

    await db.commit()
    await db.refresh(metadata)

    # 发布 Redis 更新通知
    await _publish_metadata_update(metadata.point_id)

    logger.info(f"更新传感器元数据: id={metadata_id}, point_id={metadata.point_id}")
    return metadata


@router.delete("/{metadata_id}", status_code=204)
async def delete_sensor_metadata(
    metadata_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除传感器元数据

    权限: admin
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")

    result = await db.execute(
        select(SensorMetadata).where(SensorMetadata.id == metadata_id)
    )
    metadata = result.scalar_one_or_none()

    if not metadata:
        raise HTTPException(status_code=404, detail="传感器元数据不存在")

    point_id = metadata.point_id
    await db.delete(metadata)
    await db.commit()

    # 发布 Redis 更新通知
    await _publish_metadata_update(point_id)

    logger.info(f"删除传感器元数据: id={metadata_id}, point_id={point_id}")


@router.get("/calibration-status/{point_id}", response_model=CalibrationStatusResponse)
async def get_calibration_status(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询传感器校准状态

    权限: 所有登录用户
    """
    status = await check_calibration_status(point_id, db)
    return status


@router.post("/check-expired-calibrations", status_code=202)
async def trigger_expired_calibrations_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    手动触发校准过期检查（创建维护告警）

    权限: admin/operator
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="权限不足")

    await check_expired_calibrations(db)

    logger.info(f"手动触发校准过期检查: user={current_user.username}")
    return {"message": "校准过期检查已触发"}


async def _publish_metadata_update(point_id: int):
    """发布传感器元数据更新通知到 Redis"""
    try:
        import redis.asyncio as redis
        from app.core.config import get_settings
        settings = get_settings()

        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True
        )
        payload = json.dumps({"point_id": point_id})
        await redis_client.publish('sensor:metadata_update', payload)
        await redis_client.close()
    except ImportError:
        logger.warning("Redis 不可用，跳过元数据更新通知")
    except Exception as e:
        logger.error(f"发布元数据更新通知失败: {e}")
