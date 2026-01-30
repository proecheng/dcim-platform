"""
点位管理 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload
import csv
import io

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.point import Point, PointRealtime, PointGroup, PointGroupMember
from ...models.energy import PowerDevice
from ...schemas.point import (
    PointCreate, PointUpdate, PointInfo, PointTypesSummary,
    PointGroupCreate, PointGroupInfo
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[PointInfo], summary="获取点位列表")
async def get_points(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    point_type: Optional[str] = Query(None, description="点位类型: AI/DI/AO/DO"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    area_code: Optional[str] = Query(None, description="区域代码"),
    is_enabled: Optional[bool] = Query(None, description="启用状态"),
    energy_device_id: Optional[int] = Query(None, description="关联用能设备ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取点位列表（支持多条件筛选、分页）
    返回数据包含关联的用能设备名称
    """
    query = select(Point)

    if keyword:
        query = query.where(
            (Point.point_code.contains(keyword)) |
            (Point.point_name.contains(keyword))
        )
    if point_type:
        query = query.where(Point.point_type == point_type)
    if device_type:
        query = query.where(Point.device_type == device_type)
    if area_code:
        query = query.where(Point.area_code == area_code)
    if is_enabled is not None:
        query = query.where(Point.is_enabled == is_enabled)
    if energy_device_id is not None:
        query = query.where(Point.energy_device_id == energy_device_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Point.area_code, Point.point_code)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    points = result.scalars().all()

    # 获取关联的用能设备名称
    energy_device_ids = [p.energy_device_id for p in points if p.energy_device_id]
    energy_device_map = {}
    if energy_device_ids:
        device_result = await db.execute(
            select(PowerDevice.id, PowerDevice.device_name, PowerDevice.device_code)
            .where(PowerDevice.id.in_(energy_device_ids))
        )
        for device_id, device_name, device_code in device_result.all():
            energy_device_map[device_id] = {"name": device_name, "code": device_code}

    # 构建返回数据，附加 energy_device_name
    items = []
    for p in points:
        point_dict = PointInfo.model_validate(p).model_dump()
        if p.energy_device_id and p.energy_device_id in energy_device_map:
            point_dict["energy_device_name"] = energy_device_map[p.energy_device_id]["name"]
            point_dict["energy_device_code"] = energy_device_map[p.energy_device_id]["code"]
        else:
            point_dict["energy_device_name"] = None
            point_dict["energy_device_code"] = None
        items.append(point_dict)

    return PageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/types-summary", response_model=PointTypesSummary, summary="获取点位类型统计")
async def get_types_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取点位按类型的统计信息
    """
    # 总数统计
    total_result = await db.execute(select(func.count(Point.id)))
    total = total_result.scalar()

    enabled_result = await db.execute(
        select(func.count(Point.id)).where(Point.is_enabled == True)
    )
    enabled = enabled_result.scalar()

    # 按类型统计
    type_result = await db.execute(
        select(Point.point_type, func.count(Point.id)).group_by(Point.point_type)
    )
    type_counts = {row[0]: row[1] for row in type_result.all()}

    # 按设备类型统计
    device_type_result = await db.execute(
        select(Point.device_type, func.count(Point.id)).group_by(Point.device_type)
    )
    device_type_counts = {row[0]: row[1] for row in device_type_result.all()}

    return PointTypesSummary(
        total=total,
        enabled=enabled,
        ai=type_counts.get("AI", 0),
        di=type_counts.get("DI", 0),
        ao=type_counts.get("AO", 0),
        do=type_counts.get("DO", 0),
        by_device_type=device_type_counts
    )


@router.get("/groups", summary="获取点位分组")
async def get_groups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取点位分组列表
    """
    result = await db.execute(
        select(PointGroup).order_by(PointGroup.sort_order)
    )
    groups = result.scalars().all()
    return [PointGroupInfo.model_validate(g) for g in groups]


@router.post("/groups", response_model=PointGroupInfo, summary="创建点位分组")
async def create_group(
    data: PointGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建点位分组
    """
    group = PointGroup(**data.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return PointGroupInfo.model_validate(group)


@router.get("/export", summary="导出点位配置")
async def export_points(
    point_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    导出点位配置为CSV文件
    """
    query = select(Point)
    if point_type:
        query = query.where(Point.point_type == point_type)

    result = await db.execute(query.order_by(Point.point_code))
    points = result.scalars().all()

    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "点位编码", "点位名称", "点位类型", "设备类型", "区域",
        "单位", "量程下限", "量程上限", "精度", "采集周期", "启用"
    ])
    for p in points:
        writer.writerow([
            p.point_code, p.point_name, p.point_type, p.device_type, p.area_code,
            p.unit, p.min_range, p.max_range, p.precision, p.collect_interval,
            "是" if p.is_enabled else "否"
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=points.csv"}
    )


@router.post("/batch-import", summary="批量导入点位")
async def batch_import_points(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    从CSV文件批量导入点位
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传CSV文件")

    content = await file.read()
    try:
        content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = content.decode("gbk")

    reader = csv.DictReader(io.StringIO(content))
    success_count = 0
    error_list = []

    for row in reader:
        try:
            point = Point(
                point_code=row.get("点位编码", ""),
                point_name=row.get("点位名称", ""),
                point_type=row.get("点位类型", "AI"),
                device_type=row.get("设备类型", ""),
                area_code=row.get("区域", "A1"),
                unit=row.get("单位", ""),
                min_range=float(row.get("量程下限", 0)) if row.get("量程下限") else None,
                max_range=float(row.get("量程上限", 100)) if row.get("量程上限") else None,
                precision=int(row.get("精度", 2)) if row.get("精度") else 2,
                collect_interval=int(row.get("采集周期", 10)) if row.get("采集周期") else 10,
                is_enabled=row.get("启用", "是") == "是"
            )
            db.add(point)
            success_count += 1
        except Exception as e:
            error_list.append(f"行 {success_count + len(error_list) + 2}: {str(e)}")

    await db.commit()

    return {
        "success_count": success_count,
        "error_count": len(error_list),
        "errors": error_list[:10]  # 只返回前10个错误
    }


@router.get("/{point_id}", response_model=PointInfo, summary="获取点位详情")
async def get_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取点位详情
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")
    return PointInfo.model_validate(point)


@router.post("", response_model=PointInfo, summary="创建点位")
async def create_point(
    data: PointCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建新点位
    """
    # 检查点位编码唯一性
    result = await db.execute(select(Point).where(Point.point_code == data.point_code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="点位编码已存在")

    point = Point(**data.model_dump())
    db.add(point)
    await db.commit()
    await db.refresh(point)

    # 创建实时值记录
    realtime = PointRealtime(point_id=point.id)
    db.add(realtime)
    await db.commit()

    return PointInfo.model_validate(point)


@router.put("/{point_id}", response_model=PointInfo, summary="更新点位")
async def update_point(
    point_id: int,
    data: PointUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新点位信息
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(update(Point).where(Point.id == point_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one()

    return PointInfo.model_validate(point)


@router.delete("/{point_id}", summary="删除点位")
async def delete_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    删除点位
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    # 删除关联的实时值
    await db.execute(delete(PointRealtime).where(PointRealtime.point_id == point_id))
    # 删除点位
    await db.execute(delete(Point).where(Point.id == point_id))
    await db.commit()

    return {"message": "点位已删除"}


@router.put("/{point_id}/enable", summary="启用点位")
async def enable_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    启用点位
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="点位不存在")

    await db.execute(
        update(Point).where(Point.id == point_id).values(
            is_enabled=True, updated_at=datetime.now()
        )
    )
    await db.commit()
    return {"message": "点位已启用"}


@router.put("/{point_id}/disable", summary="禁用点位")
async def disable_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    禁用点位
    """
    result = await db.execute(select(Point).where(Point.id == point_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="点位不存在")

    await db.execute(
        update(Point).where(Point.id == point_id).values(
            is_enabled=False, updated_at=datetime.now()
        )
    )
    await db.commit()
    return {"message": "点位已禁用"}


@router.put("/{point_id}/link-device", summary="关联点位到用能设备")
async def link_point_to_device(
    point_id: int,
    energy_device_id: int = Query(..., description="用能设备ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    将点位关联到用能设备

    1. 验证点位和设备存在
    2. 设置点位的 energy_device_id
    3. 根据点位名称识别用途，设置设备的相应点位字段
    """
    from ...services.point_device_matcher import PointDeviceMatcher

    # 验证点位存在
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    # 验证设备存在
    result = await db.execute(select(PowerDevice).where(PowerDevice.id == energy_device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="用能设备不存在")

    # 设置点位的关联
    point.energy_device_id = energy_device_id
    point.updated_at = datetime.now()

    # 识别点位用途并设置设备的相应字段
    usage = PointDeviceMatcher.identify_point_usage(point.point_name)
    if usage == "power":
        device.power_point_id = point_id
    elif usage == "current":
        device.current_point_id = point_id
    elif usage == "energy":
        device.energy_point_id = point_id
    elif usage == "voltage":
        device.voltage_point_id = point_id
    elif usage == "power_factor":
        device.pf_point_id = point_id

    await db.commit()

    return {
        "message": "关联成功",
        "point_id": point_id,
        "energy_device_id": energy_device_id,
        "detected_usage": usage
    }


@router.delete("/{point_id}/link-device", summary="取消点位与用能设备的关联")
async def unlink_point_from_device(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    取消点位与用能设备的关联

    1. 清除点位的 energy_device_id
    2. 清除设备中指向该点位的字段
    """
    # 获取点位
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    original_device_id = point.energy_device_id

    if not original_device_id:
        return {"message": "点位未关联任何设备"}

    # 清除点位的关联
    point.energy_device_id = None
    point.updated_at = datetime.now()

    # 清除设备中指向该点位的字段
    result = await db.execute(select(PowerDevice).where(PowerDevice.id == original_device_id))
    device = result.scalar_one_or_none()
    if device:
        if device.power_point_id == point_id:
            device.power_point_id = None
        if device.current_point_id == point_id:
            device.current_point_id = None
        if device.energy_point_id == point_id:
            device.energy_point_id = None
        if hasattr(device, 'voltage_point_id') and device.voltage_point_id == point_id:
            device.voltage_point_id = None
        if hasattr(device, 'pf_point_id') and device.pf_point_id == point_id:
            device.pf_point_id = None

    await db.commit()

    return {
        "message": "取消关联成功",
        "point_id": point_id,
        "removed_from_device_id": original_device_id
    }
