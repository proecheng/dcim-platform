"""
拓扑编辑API
Topology Editing API

提供拓扑图的可编辑操作接口
Updated: 2025-01-29 - Added point type support
Updated: 2026-01-29 - Added sync endpoint and device points query
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..deps import get_db
from ...services.energy_topology import EnergyTopologyService
from ...services.topology_sync import TopologySyncService
from ...services.point_device_matcher import PointDeviceMatcher
from ...schemas.energy import (
    TopologyNodeCreate, TopologyNodeUpdate, TopologyNodeDelete,
    TopologyBatchOperation, TopologyBatchResult,
    TopologyNodeResponse, TopologyNodeType, TopologyExport, TopologyImport,
    DevicePointConfigCreate, DevicePointConfigUpdate,
    DevicePointConfigResponse
)
from ...models.point import Point, PointRealtime
from ...models.energy import PowerDevice

router = APIRouter()


@router.post("/nodes", summary="创建拓扑节点")
async def create_topology_node(
    data: TopologyNodeCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的拓扑节点（变压器、计量点、配电柜、回路、设备）
    """
    try:
        node_id, node_type = await EnergyTopologyService.create_node(db, data)
        await db.commit()

        # 通知数据模拟器
        sync_service = TopologySyncService(db)
        await sync_service.notify_data_simulator(
            operation="create",
            node_type=node_type,
            node_id=node_id,
            data={"code": data.transformer_code or data.meter_code or data.panel_code or data.circuit_code or data.device_code}
        )

        return {
            "success": True,
            "node_id": node_id,
            "node_type": node_type,
            "message": "节点创建成功"
        }
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put("/nodes", summary="更新拓扑节点")
async def update_topology_node(
    data: TopologyNodeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新拓扑节点信息
    """
    try:
        success = await EnergyTopologyService.update_node(db, data)
        if not success:
            raise HTTPException(status_code=404, detail="节点不存在")

        await db.commit()

        # 通知数据模拟器
        sync_service = TopologySyncService(db)
        await sync_service.notify_data_simulator(
            operation="update",
            node_type=data.node_type.value,
            node_id=data.node_id,
            data={"name": data.name, "code": data.code}
        )

        return {
            "success": True,
            "message": "节点更新成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/nodes", summary="删除拓扑节点")
async def delete_topology_node(
    data: TopologyNodeDelete,
    db: AsyncSession = Depends(get_db)
):
    """
    删除拓扑节点，可选择级联删除子节点
    """
    try:
        # 检查级联影响
        if data.cascade:
            sync_service = TopologySyncService(db)
            impact = await sync_service.cascade_delete_check(data.node_id, data.node_type)
            if impact:
                print(f"级联删除影响: {impact}")

        # 执行删除
        deleted = await EnergyTopologyService.delete_node(db, data, cascade=data.cascade)
        await db.commit()

        # 通知数据模拟器
        sync_service = TopologySyncService(db)
        await sync_service.notify_data_simulator(
            operation="delete",
            node_type=data.node_type.value,
            node_id=data.node_id
        )

        return {
            "success": True,
            "deleted": deleted,
            "message": "节点删除成功"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/batch", summary="批量拓扑操作", response_model=TopologyBatchResult)
async def batch_topology_operation(
    data: TopologyBatchOperation,
    db: AsyncSession = Depends(get_db)
):
    """
    批量执行拓扑操作（创建、更新、删除）
    支持事务，全部成功或全部回滚
    """
    result = await EnergyTopologyService.batch_operation(db, data)

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "批量操作部分失败",
                "errors": result.errors,
                "created_count": result.created_count,
                "updated_count": result.updated_count,
                "deleted_count": result.deleted_count
            }
        )

    return result


@router.get("/export", summary="导出拓扑数据", response_model=TopologyExport)
async def export_topology(
    db: AsyncSession = Depends(get_db)
):
    """
    导出完整拓扑数据（JSON格式）
    """
    return await EnergyTopologyService.export_topology(db)


@router.post("/import", summary="导入拓扑数据", response_model=TopologyBatchResult)
async def import_topology(
    data: TopologyImport,
    db: AsyncSession = Depends(get_db)
):
    """
    导入拓扑数据
    可选择是否清除现有数据
    """
    result = await EnergyTopologyService.import_topology(db, data)

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "导入失败",
                "errors": result.errors
            }
        )

    return result


# ==================== 设备测点管理 ====================

@router.post("/device-points", summary="创建设备测点配置")
async def create_device_points(
    data: DevicePointConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    为设备批量创建测点配置
    测点会自动同步到点位管理模块
    """
    try:
        # 检查设备是否存在
        from ...models.energy import PowerDevice
        from sqlalchemy import select

        result = await db.execute(
            select(PowerDevice).where(PowerDevice.id == data.energy_device_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")

        # 同步测点到点位模块
        sync_service = TopologySyncService(db)
        point_ids = await sync_service.sync_device_points(
            device_id=data.energy_device_id,
            device_code=device.device_code,
            points_config=data.points
        )

        return {
            "success": True,
            "device_id": data.energy_device_id,
            "point_count": len(point_ids),
            "point_ids": point_ids,
            "message": "测点配置创建成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/device-points/{device_id}", summary="获取设备测点配置")
async def get_device_points(
    device_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定设备的所有测点配置
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Point).where(Point.energy_device_id == device_id)
    )
    points = result.scalars().all()

    return {
        "device_id": device_id,
        "points": [
            DevicePointConfigResponse(
                id=p.id,
                energy_device_id=p.energy_device_id,
                point_code=p.point_code,
                point_name=p.point_name,
                point_type=p.point_type,
                data_type=p.data_type,
                unit=p.unit,
                description=p.description,
                device_id=p.device_id,
                register_address=p.register_address,
                function_code=p.function_code,
                scale_factor=p.scale_factor or 1.0,
                offset=p.offset or 0.0,
                alarm_enabled=False,  # 需要从告警阈值表获取
                alarm_high=None,
                alarm_low=None
            )
            for p in points
        ]
    }


@router.put("/device-points/{point_id}", summary="更新设备测点配置")
async def update_device_point(
    point_id: int,
    data: DevicePointConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新设备测点配置
    """
    from sqlalchemy import select
    from datetime import datetime

    try:
        result = await db.execute(
            select(Point).where(Point.id == point_id)
        )
        point = result.scalar_one_or_none()
        if not point:
            raise HTTPException(status_code=404, detail="测点不存在")

        # 更新字段
        if data.point_name is not None:
            point.point_name = data.point_name
        if data.unit is not None:
            point.unit = data.unit
        if data.description is not None:
            point.description = data.description
        if data.device_id is not None:
            point.device_id = data.device_id
        if data.register_address is not None:
            point.register_address = data.register_address
        if data.function_code is not None:
            point.function_code = data.function_code
        if data.scale_factor is not None:
            point.scale_factor = data.scale_factor
        if data.offset is not None:
            point.offset = data.offset

        point.updated_at = datetime.now()
        await db.commit()

        return {
            "success": True,
            "point_id": point_id,
            "message": "测点配置更新成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/device-points/{device_id}", summary="删除设备所有测点")
async def delete_device_points(
    device_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除设备的所有测点配置
    """
    try:
        sync_service = TopologySyncService(db)
        deleted_count = await sync_service.remove_device_points(device_id)

        return {
            "success": True,
            "device_id": device_id,
            "deleted_count": deleted_count,
            "message": "测点删除成功"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/device-points/point/{point_id}", summary="删除单个点位")
async def delete_single_point(
    point_id: int = Path(..., gt=0, description="点位ID，必须大于0"),
    db: AsyncSession = Depends(get_db)
):
    """
    删除单个点位
    """
    from sqlalchemy import delete

    try:
        # 获取点位
        result = await db.execute(select(Point).where(Point.id == point_id))
        point = result.scalar_one_or_none()
        if not point:
            raise HTTPException(status_code=404, detail="点位不存在")

        # 删除实时数据
        await db.execute(delete(PointRealtime).where(PointRealtime.point_id == point_id))

        # 删除点位
        await db.delete(point)
        await db.commit()

        return {
            "success": True,
            "point_id": point_id,
            "message": "点位删除成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ==================== 拓扑连接管理 ====================

@router.post("/connections", summary="创建拓扑连接")
async def create_topology_connection(
    source_id: int = Body(..., description="源节点ID"),
    source_type: TopologyNodeType = Body(..., description="源节点类型"),
    target_id: int = Body(..., description="目标节点ID"),
    target_type: TopologyNodeType = Body(..., description="目标节点类型"),
    db: AsyncSession = Depends(get_db)
):
    """
    创建拓扑节点之间的连接关系
    """
    try:
        sync_service = TopologySyncService(db)

        # 根据节点类型更新层级关系
        if source_type == TopologyNodeType.TRANSFORMER and target_type == TopologyNodeType.METER_POINT:
            success = await sync_service.update_meter_point_hierarchy(target_id, source_id)
        elif source_type == TopologyNodeType.METER_POINT and target_type == TopologyNodeType.PANEL:
            success = await sync_service.update_panel_hierarchy(target_id, source_id)
        elif source_type == TopologyNodeType.PANEL and target_type == TopologyNodeType.CIRCUIT:
            success = await sync_service.update_circuit_hierarchy(target_id, source_id)
        elif source_type == TopologyNodeType.CIRCUIT and target_type == TopologyNodeType.DEVICE:
            success = await sync_service.update_device_hierarchy(target_id, source_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的连接类型: {source_type} -> {target_type}"
            )

        if not success:
            raise HTTPException(status_code=404, detail="节点不存在")

        return {
            "success": True,
            "message": "连接创建成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建连接失败: {str(e)}")


@router.delete("/connections", summary="删除拓扑连接")
async def delete_topology_connection(
    target_id: int = Body(..., description="目标节点ID"),
    target_type: TopologyNodeType = Body(..., description="目标节点类型"),
    db: AsyncSession = Depends(get_db)
):
    """
    删除拓扑节点之间的连接关系（将子节点的父节点设为 NULL）
    """
    try:
        sync_service = TopologySyncService(db)

        # 根据节点类型断开层级关系
        if target_type == TopologyNodeType.METER_POINT:
            success = await sync_service.update_meter_point_hierarchy(target_id, None)
        elif target_type == TopologyNodeType.PANEL:
            success = await sync_service.update_panel_hierarchy(target_id, None)
        elif target_type == TopologyNodeType.CIRCUIT:
            success = await sync_service.update_circuit_hierarchy(target_id, None)
        elif target_type == TopologyNodeType.DEVICE:
            success = await sync_service.update_device_hierarchy(target_id, None)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的节点类型: {target_type}"
            )

        if not success:
            raise HTTPException(status_code=404, detail="节点不存在")

        return {
            "success": True,
            "message": "连接删除成功"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除连接失败: {str(e)}")


# ==================== 设备点位同步 ====================

@router.post("/sync", summary="同步设备与点位关联")
async def sync_device_point_relations(
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发设备与点位的双向同步

    此端点会:
    1. 遍历所有用电设备，查找匹配的点位
    2. 更新设备的 power_point_id, current_point_id, energy_point_id
    3. 同时设置点位的 energy_device_id（双向关联）
    4. 返回同步统计信息
    """
    try:
        result = await PointDeviceMatcher.full_sync(db)
        await db.commit()

        return {
            "success": True,
            "message": "同步完成",
            "updated_devices": result["updated_devices"],
            "updated_points": result["updated_points"],
            "matched_count": result["matched_count"],
            "statistics": result["statistics"]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/sync/status", summary="获取同步状态统计")
async def get_sync_status(
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前设备与点位的关联状态统计

    返回:
    - total_devices: 总设备数
    - linked_devices: 已关联点位的设备数
    - orphan_devices: 孤立设备数（无点位关联）
    - total_points: 总点位数
    - linked_points: 已关联设备的点位数
    - device_link_rate: 设备关联率
    - point_link_rate: 点位关联率
    """
    try:
        stats = await PointDeviceMatcher.get_sync_statistics(db)
        return {
            "success": True,
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/device/{device_id}/points", summary="获取设备关联的所有点位")
async def get_device_linked_points(
    device_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定用电设备关联的所有点位及其实时值

    返回设备的功率点位、电流点位、电能点位以及通过 energy_device_id 反向关联的所有点位
    """
    # 获取设备信息
    device_result = await db.execute(
        select(PowerDevice).where(PowerDevice.id == device_id)
    )
    device = device_result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 收集所有关联的点位ID
    point_ids = set()
    point_roles = {}  # 记录点位的角色

    if device.power_point_id:
        point_ids.add(device.power_point_id)
        point_roles[device.power_point_id] = "power"
    if device.current_point_id:
        point_ids.add(device.current_point_id)
        point_roles[device.current_point_id] = "current"
    if device.energy_point_id:
        point_ids.add(device.energy_point_id)
        point_roles[device.energy_point_id] = "energy"
    if device.voltage_point_id:
        point_ids.add(device.voltage_point_id)
        point_roles[device.voltage_point_id] = "voltage"
    if device.pf_point_id:
        point_ids.add(device.pf_point_id)
        point_roles[device.pf_point_id] = "power_factor"

    # 查找通过 energy_device_id 反向关联的点位
    reverse_linked_result = await db.execute(
        select(Point.id).where(Point.energy_device_id == device_id)
    )
    for (pid,) in reverse_linked_result.all():
        point_ids.add(pid)
        if pid not in point_roles:
            point_roles[pid] = "associated"

    if not point_ids:
        return {
            "device_id": device_id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "points": [],
            "point_count": 0
        }

    # 获取点位详细信息和实时值
    points_result = await db.execute(
        select(Point, PointRealtime)
        .outerjoin(PointRealtime, Point.id == PointRealtime.point_id)
        .where(Point.id.in_(point_ids))
    )

    points_data = []
    for point, realtime in points_result.all():
        points_data.append({
            "id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "point_type": point.point_type,
            "unit": point.unit,
            "role": point_roles.get(point.id, "associated"),
            "realtime": {
                "value": realtime.value if realtime else None,
                "value_text": realtime.value_text if realtime else None,
                "status": realtime.status if realtime else "offline",
                "quality": realtime.quality if realtime else 2,
                "updated_at": realtime.updated_at.isoformat() if realtime and realtime.updated_at else None
            } if realtime else None
        })

    # 按角色排序: power > current > energy > voltage > power_factor > associated
    role_order = {"power": 0, "current": 1, "energy": 2, "voltage": 3, "power_factor": 4, "associated": 5}
    points_data.sort(key=lambda x: (role_order.get(x["role"], 99), x["point_code"]))

    return {
        "device_id": device_id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "rated_power": device.rated_power,
        "points": points_data,
        "point_count": len(points_data)
    }
