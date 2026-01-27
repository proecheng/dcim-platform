"""
可调度资源配置 API - v1
包括：可调度设备、储能系统、光伏系统的配置管理
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...models.energy import (
    DispatchableDevice, StorageSystemConfig, PVSystemConfig,
    DispatchSchedule
)

router = APIRouter()


# ==================== Pydantic 模型 ====================

class DispatchableDeviceBase(BaseModel):
    """可调度设备基础字段"""
    name: str = Field(..., description="设备名称")
    device_type: str = Field(..., description="设备类型: shiftable/curtailable/modulating/generation/storage/rigid")
    rated_power: float = Field(..., description="额定功率 kW")
    min_power: Optional[float] = Field(None, description="最小功率 kW")
    max_power: Optional[float] = Field(None, description="最大功率 kW")

    # 时移型参数
    run_duration: Optional[float] = Field(None, description="单次运行时长 h")
    daily_runs: Optional[int] = Field(None, description="每日运行次数")
    allowed_periods: Optional[List[int]] = Field(None, description="允许时段 [0-23]")
    forbidden_periods: Optional[List[int]] = Field(None, description="禁止时段 [0-23]")

    # 削减型参数
    curtail_ratio: Optional[float] = Field(None, description="可削减比例 %")
    max_curtail_duration: Optional[float] = Field(None, description="最大削减时长 h")
    max_curtail_per_day: Optional[int] = Field(None, description="每日最大削减次数")
    recovery_time: Optional[float] = Field(None, description="恢复时间 h")

    # 调节型参数
    ramp_rate: Optional[float] = Field(None, description="调节速率 kW/min")
    response_delay: Optional[int] = Field(None, description="响应延迟 s")

    # 发电型参数
    generation_cost: Optional[float] = Field(None, description="发电成本 元/kWh")
    is_controllable: bool = Field(False, description="是否可调度")

    # 通用参数
    priority: int = Field(5, description="优先级 1-10")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="设备描述")


class DispatchableDeviceCreate(DispatchableDeviceBase):
    """创建可调度设备"""
    meter_point_id: Optional[int] = None
    power_device_id: Optional[int] = None


class DispatchableDeviceUpdate(BaseModel):
    """更新可调度设备"""
    name: Optional[str] = None
    device_type: Optional[str] = None
    rated_power: Optional[float] = None
    min_power: Optional[float] = None
    max_power: Optional[float] = None
    run_duration: Optional[float] = None
    daily_runs: Optional[int] = None
    allowed_periods: Optional[List[int]] = None
    forbidden_periods: Optional[List[int]] = None
    curtail_ratio: Optional[float] = None
    max_curtail_duration: Optional[float] = None
    max_curtail_per_day: Optional[int] = None
    recovery_time: Optional[float] = None
    ramp_rate: Optional[float] = None
    response_delay: Optional[int] = None
    generation_cost: Optional[float] = None
    is_controllable: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class DispatchableDeviceResponse(DispatchableDeviceBase):
    """可调度设备响应"""
    id: int
    meter_point_id: Optional[int] = None
    power_device_id: Optional[int] = None

    class Config:
        from_attributes = True


class StorageConfigBase(BaseModel):
    """储能配置基础字段"""
    name: str = Field(..., description="储能系统名称")
    capacity: float = Field(..., description="容量 kWh")
    max_charge_power: float = Field(..., description="最大充电功率 kW")
    max_discharge_power: float = Field(..., description="最大放电功率 kW")
    charge_efficiency: float = Field(0.95, description="充电效率")
    discharge_efficiency: float = Field(0.95, description="放电效率")
    min_soc: float = Field(0.10, description="最小SOC")
    max_soc: float = Field(0.90, description="最大SOC")
    cycle_cost: float = Field(0.1, description="循环成本 元/kWh")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = None


class StorageConfigCreate(StorageConfigBase):
    """创建储能配置"""
    meter_point_id: Optional[int] = None


class StorageConfigUpdate(BaseModel):
    """更新储能配置"""
    name: Optional[str] = None
    capacity: Optional[float] = None
    max_charge_power: Optional[float] = None
    max_discharge_power: Optional[float] = None
    charge_efficiency: Optional[float] = None
    discharge_efficiency: Optional[float] = None
    min_soc: Optional[float] = None
    max_soc: Optional[float] = None
    cycle_cost: Optional[float] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class StorageConfigResponse(StorageConfigBase):
    """储能配置响应"""
    id: int
    meter_point_id: Optional[int] = None

    class Config:
        from_attributes = True


class PVConfigBase(BaseModel):
    """光伏配置基础字段"""
    name: str = Field(..., description="光伏系统名称")
    rated_capacity: float = Field(..., description="额定容量 kWp")
    efficiency: float = Field(0.85, description="系统效率")
    is_controllable: bool = Field(False, description="是否可调度")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = None


class PVConfigCreate(PVConfigBase):
    """创建光伏配置"""
    meter_point_id: Optional[int] = None


class PVConfigUpdate(BaseModel):
    """更新光伏配置"""
    name: Optional[str] = None
    rated_capacity: Optional[float] = None
    efficiency: Optional[float] = None
    is_controllable: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class PVConfigResponse(PVConfigBase):
    """光伏配置响应"""
    id: int
    meter_point_id: Optional[int] = None

    class Config:
        from_attributes = True


# ==================== 可调度设备 API ====================

@router.get("/devices", response_model=List[DispatchableDeviceResponse], summary="获取可调度设备列表")
async def get_dispatchable_devices(
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取可调度设备列表"""
    query = select(DispatchableDevice)

    if device_type:
        query = query.where(DispatchableDevice.device_type == device_type)
    if is_active is not None:
        query = query.where(DispatchableDevice.is_active == is_active)

    query = query.order_by(DispatchableDevice.priority, DispatchableDevice.id)
    result = await db.execute(query)
    devices = result.scalars().all()

    return [DispatchableDeviceResponse.model_validate(d) for d in devices]


@router.get("/devices/{device_id}", response_model=DispatchableDeviceResponse, summary="获取单个可调度设备")
async def get_dispatchable_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取单个可调度设备详情"""
    result = await db.execute(
        select(DispatchableDevice).where(DispatchableDevice.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    return DispatchableDeviceResponse.model_validate(device)


@router.post("/devices", response_model=DispatchableDeviceResponse, summary="创建可调度设备")
async def create_dispatchable_device(
    data: DispatchableDeviceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """创建可调度设备"""
    device = DispatchableDevice(**data.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)

    return DispatchableDeviceResponse.model_validate(device)


@router.put("/devices/{device_id}", response_model=DispatchableDeviceResponse, summary="更新可调度设备")
async def update_dispatchable_device(
    device_id: int,
    data: DispatchableDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """更新可调度设备"""
    result = await db.execute(
        select(DispatchableDevice).where(DispatchableDevice.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    await db.commit()
    await db.refresh(device)

    return DispatchableDeviceResponse.model_validate(device)


@router.delete("/devices/{device_id}", summary="删除可调度设备")
async def delete_dispatchable_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """删除可调度设备"""
    result = await db.execute(
        select(DispatchableDevice).where(DispatchableDevice.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    await db.delete(device)
    await db.commit()

    return {"message": "删除成功"}


@router.get("/devices/summary/stats", summary="获取设备统计")
async def get_device_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取可调度设备统计"""
    # 总数
    total_result = await db.execute(select(func.count(DispatchableDevice.id)))
    total = total_result.scalar()

    # 按类型统计
    type_result = await db.execute(
        select(
            DispatchableDevice.device_type,
            func.count(DispatchableDevice.id).label('count'),
            func.sum(DispatchableDevice.rated_power).label('total_power')
        ).group_by(DispatchableDevice.device_type)
    )
    by_type = [
        {"type": row.device_type, "count": row.count, "total_power": float(row.total_power or 0)}
        for row in type_result
    ]

    # 活跃设备
    active_result = await db.execute(
        select(func.count(DispatchableDevice.id)).where(DispatchableDevice.is_active == True)
    )
    active_count = active_result.scalar()

    return {
        "total": total,
        "active_count": active_count,
        "by_type": by_type
    }


# ==================== 储能系统 API ====================

@router.get("/storage", response_model=List[StorageConfigResponse], summary="获取储能系统列表")
async def get_storage_systems(
    is_active: Optional[bool] = Query(None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取储能系统列表"""
    query = select(StorageSystemConfig)

    if is_active is not None:
        query = query.where(StorageSystemConfig.is_active == is_active)

    query = query.order_by(StorageSystemConfig.id)
    result = await db.execute(query)
    systems = result.scalars().all()

    return [StorageConfigResponse.model_validate(s) for s in systems]


@router.get("/storage/{storage_id}", response_model=StorageConfigResponse, summary="获取单个储能系统")
async def get_storage_system(
    storage_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取单个储能系统详情"""
    result = await db.execute(
        select(StorageSystemConfig).where(StorageSystemConfig.id == storage_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="储能系统不存在")

    return StorageConfigResponse.model_validate(system)


@router.post("/storage", response_model=StorageConfigResponse, summary="创建储能系统")
async def create_storage_system(
    data: StorageConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """创建储能系统"""
    system = StorageSystemConfig(**data.model_dump())
    db.add(system)
    await db.commit()
    await db.refresh(system)

    return StorageConfigResponse.model_validate(system)


@router.put("/storage/{storage_id}", response_model=StorageConfigResponse, summary="更新储能系统")
async def update_storage_system(
    storage_id: int,
    data: StorageConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """更新储能系统"""
    result = await db.execute(
        select(StorageSystemConfig).where(StorageSystemConfig.id == storage_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="储能系统不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(system, key, value)

    await db.commit()
    await db.refresh(system)

    return StorageConfigResponse.model_validate(system)


@router.delete("/storage/{storage_id}", summary="删除储能系统")
async def delete_storage_system(
    storage_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """删除储能系统"""
    result = await db.execute(
        select(StorageSystemConfig).where(StorageSystemConfig.id == storage_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="储能系统不存在")

    await db.delete(system)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 光伏系统 API ====================

@router.get("/pv", response_model=List[PVConfigResponse], summary="获取光伏系统列表")
async def get_pv_systems(
    is_active: Optional[bool] = Query(None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取光伏系统列表"""
    query = select(PVSystemConfig)

    if is_active is not None:
        query = query.where(PVSystemConfig.is_active == is_active)

    query = query.order_by(PVSystemConfig.id)
    result = await db.execute(query)
    systems = result.scalars().all()

    return [PVConfigResponse.model_validate(s) for s in systems]


@router.get("/pv/{pv_id}", response_model=PVConfigResponse, summary="获取单个光伏系统")
async def get_pv_system(
    pv_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取单个光伏系统详情"""
    result = await db.execute(
        select(PVSystemConfig).where(PVSystemConfig.id == pv_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="光伏系统不存在")

    return PVConfigResponse.model_validate(system)


@router.post("/pv", response_model=PVConfigResponse, summary="创建光伏系统")
async def create_pv_system(
    data: PVConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """创建光伏系统"""
    system = PVSystemConfig(**data.model_dump())
    db.add(system)
    await db.commit()
    await db.refresh(system)

    return PVConfigResponse.model_validate(system)


@router.put("/pv/{pv_id}", response_model=PVConfigResponse, summary="更新光伏系统")
async def update_pv_system(
    pv_id: int,
    data: PVConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """更新光伏系统"""
    result = await db.execute(
        select(PVSystemConfig).where(PVSystemConfig.id == pv_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="光伏系统不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(system, key, value)

    await db.commit()
    await db.refresh(system)

    return PVConfigResponse.model_validate(system)


@router.delete("/pv/{pv_id}", summary="删除光伏系统")
async def delete_pv_system(
    pv_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """删除光伏系统"""
    result = await db.execute(
        select(PVSystemConfig).where(PVSystemConfig.id == pv_id)
    )
    system = result.scalar_one_or_none()

    if not system:
        raise HTTPException(status_code=404, detail="光伏系统不存在")

    await db.delete(system)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 资源汇总 API ====================

@router.get("/summary", summary="获取所有可调度资源汇总")
async def get_dispatch_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取所有可调度资源汇总信息"""

    # 可调度设备统计
    device_result = await db.execute(
        select(
            func.count(DispatchableDevice.id).label('count'),
            func.sum(DispatchableDevice.rated_power).label('total_power')
        ).where(DispatchableDevice.is_active == True)
    )
    device_row = device_result.first()

    # 储能统计
    storage_result = await db.execute(
        select(
            func.count(StorageSystemConfig.id).label('count'),
            func.sum(StorageSystemConfig.capacity).label('total_capacity'),
            func.sum(StorageSystemConfig.max_charge_power).label('total_charge_power'),
            func.sum(StorageSystemConfig.max_discharge_power).label('total_discharge_power')
        ).where(StorageSystemConfig.is_active == True)
    )
    storage_row = storage_result.first()

    # 光伏统计
    pv_result = await db.execute(
        select(
            func.count(PVSystemConfig.id).label('count'),
            func.sum(PVSystemConfig.rated_capacity).label('total_capacity')
        ).where(PVSystemConfig.is_active == True)
    )
    pv_row = pv_result.first()

    return {
        "dispatchable_devices": {
            "count": device_row.count or 0,
            "total_power": float(device_row.total_power or 0)
        },
        "storage_systems": {
            "count": storage_row.count or 0,
            "total_capacity": float(storage_row.total_capacity or 0),
            "total_charge_power": float(storage_row.total_charge_power or 0),
            "total_discharge_power": float(storage_row.total_discharge_power or 0)
        },
        "pv_systems": {
            "count": pv_row.count or 0,
            "total_capacity": float(pv_row.total_capacity or 0)
        }
    }


# ==================== 演示数据初始化 ====================

@router.post("/init-demo-data", summary="初始化演示数据")
async def init_demo_data(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """初始化可调度资源演示数据"""

    # 检查是否已有数据
    existing = await db.execute(select(func.count(DispatchableDevice.id)))
    if existing.scalar() > 0:
        return {"message": "演示数据已存在", "created": False}

    # 创建可调度设备演示数据
    demo_devices = [
        # 时移型设备
        DispatchableDevice(
            name="空压机系统",
            device_type="shiftable",
            rated_power=150,
            run_duration=4,
            daily_runs=2,
            allowed_periods=[0, 1, 2, 3, 4, 5, 6, 22, 23],
            forbidden_periods=[10, 11, 12, 17, 18, 19],
            priority=3,
            is_active=True,
            description="可在谷时运行的空压机组，提供全天气源储备"
        ),
        DispatchableDevice(
            name="冷冻水蓄冷系统",
            device_type="shiftable",
            rated_power=200,
            run_duration=6,
            daily_runs=1,
            allowed_periods=[0, 1, 2, 3, 4, 5, 6],
            priority=2,
            is_active=True,
            description="夜间蓄冷，白天释放，峰谷套利"
        ),
        DispatchableDevice(
            name="电动叉车充电站",
            device_type="shiftable",
            rated_power=80,
            run_duration=3,
            daily_runs=1,
            allowed_periods=[22, 23, 0, 1, 2, 3, 4, 5, 6, 7],
            priority=5,
            is_active=True,
            description="生产结束后充电，避开峰时"
        ),
        # 削减型设备
        DispatchableDevice(
            name="非关键区域照明",
            device_type="curtailable",
            rated_power=50,
            curtail_ratio=60,
            max_curtail_duration=2,
            max_curtail_per_day=3,
            recovery_time=0.25,
            priority=7,
            is_active=True,
            description="需量超标时可临时降低亮度"
        ),
        DispatchableDevice(
            name="办公区空调",
            device_type="curtailable",
            rated_power=120,
            curtail_ratio=30,
            max_curtail_duration=1,
            max_curtail_per_day=4,
            recovery_time=0.5,
            priority=6,
            is_active=True,
            description="高峰时段提升设定温度2-3度"
        ),
        # 调节型设备
        DispatchableDevice(
            name="冷却塔风机",
            device_type="modulating",
            rated_power=75,
            min_power=20,
            max_power=75,
            ramp_rate=10,
            response_delay=5,
            priority=4,
            is_active=True,
            description="变频调节，可根据需量实时调整"
        ),
        DispatchableDevice(
            name="冷冻水泵",
            device_type="modulating",
            rated_power=55,
            min_power=15,
            max_power=55,
            ramp_rate=8,
            response_delay=3,
            priority=4,
            is_active=True,
            description="变频泵，功率可连续调节"
        ),
        # 刚性负荷（作为参考）
        DispatchableDevice(
            name="生产线主设备",
            device_type="rigid",
            rated_power=500,
            priority=1,
            is_active=True,
            description="核心生产设备，不可调度，仅用于预测"
        ),
    ]

    for device in demo_devices:
        db.add(device)

    # 创建储能系统演示数据
    demo_storage = [
        StorageSystemConfig(
            name="工商业储能系统",
            capacity=500,
            max_charge_power=125,
            max_discharge_power=125,
            charge_efficiency=0.94,
            discharge_efficiency=0.94,
            min_soc=0.10,
            max_soc=0.90,
            cycle_cost=0.08,
            is_active=True,
            description="500kWh/125kW 锂电池储能系统"
        ),
        StorageSystemConfig(
            name="UPS电池组",
            capacity=100,
            max_charge_power=20,
            max_discharge_power=50,
            charge_efficiency=0.90,
            discharge_efficiency=0.88,
            min_soc=0.30,
            max_soc=0.95,
            cycle_cost=0.15,
            is_active=False,
            description="UPS电池可参与削峰（备用，暂未启用）"
        ),
    ]

    for storage in demo_storage:
        db.add(storage)

    # 创建光伏系统演示数据
    demo_pv = [
        PVSystemConfig(
            name="屋顶光伏电站",
            rated_capacity=300,
            efficiency=0.82,
            is_controllable=False,
            is_active=True,
            description="300kWp屋顶分布式光伏"
        ),
        PVSystemConfig(
            name="车棚光伏",
            rated_capacity=50,
            efficiency=0.85,
            is_controllable=False,
            is_active=True,
            description="停车场车棚光伏"
        ),
    ]

    for pv in demo_pv:
        db.add(pv)

    await db.commit()

    return {
        "message": "演示数据初始化成功",
        "created": True,
        "data": {
            "devices": len(demo_devices),
            "storage": len(demo_storage),
            "pv": len(demo_pv)
        }
    }
