"""
演示数据API
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .service import demo_data_service
from ..api.deps import get_db, require_admin
from ..models.user import User
from ..models.energy import DispatchableDevice, StorageSystemConfig, PVSystemConfig

router = APIRouter(prefix="/demo", tags=["演示数据"])


class LoadDemoDataRequest(BaseModel):
    days: int = 30


class DemoDataResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


@router.get("/status")
async def get_demo_status():
    """获取演示数据状态"""
    status = await demo_data_service.check_demo_data_status()
    return {"code": 0, "data": status}


@router.post("/load")
async def load_demo_data(request: LoadDemoDataRequest, background_tasks: BackgroundTasks):
    """加载演示数据（后台任务）"""
    if demo_data_service.loading:
        return {
            "code": 1,
            "message": "正在加载中，请稍候",
            "data": {"progress": demo_data_service.progress, "progress_message": demo_data_service.progress_message},
        }

    # 启动后台任务
    background_tasks.add_task(demo_data_service.load_demo_data, request.days)

    return {"code": 0, "message": "开始加载演示数据", "data": {"days": request.days}}


@router.get("/progress")
async def get_load_progress():
    """获取加载进度"""
    return {
        "code": 0,
        "data": {
            "loading": demo_data_service.loading,
            "progress": demo_data_service.progress,
            "progress_message": demo_data_service.progress_message,
            "is_loaded": demo_data_service.is_loaded,
        },
    }


@router.post("/unload")
async def unload_demo_data():
    """卸载演示数据"""
    result = await demo_data_service.unload_demo_data()
    return {"code": 0 if result["success"] else 1, **result}


@router.post("/refresh-dates")
async def refresh_dates(background_tasks: BackgroundTasks):
    """刷新历史数据日期到最近30天（后台任务）"""
    if demo_data_service.loading:
        return {
            "code": 1,
            "message": "正在操作中，请稍候",
            "data": {"progress": demo_data_service.progress, "progress_message": demo_data_service.progress_message},
        }

    # 启动后台任务
    background_tasks.add_task(demo_data_service.refresh_dates)

    return {"code": 0, "message": "开始刷新日期"}


@router.post("/init-dispatch-data", summary="初始化可调度资源演示数据")
async def init_dispatch_demo_data(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """初始化可调度资源演示数据"""

    existing = await db.execute(select(func.count(DispatchableDevice.id)))
    if existing.scalar() > 0:
        return {"message": "演示数据已存在", "created": False}

    demo_devices = [
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
            description="可在谷时运行的空压机组，提供全天气源储备",
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
            description="夜间蓄冷，白天释放，峰谷套利",
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
            description="生产结束后充电，避开峰时",
        ),
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
            description="需量超标时可临时降低亮度",
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
            description="高峰时段提升设定温度2-3度",
        ),
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
            description="变频调节，可根据需量实时调整",
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
            description="变频泵，功率可连续调节",
        ),
        DispatchableDevice(
            name="生产线主设备",
            device_type="rigid",
            rated_power=500,
            priority=1,
            is_active=True,
            description="核心生产设备，不可调度，仅用于预测",
        ),
    ]

    for device in demo_devices:
        db.add(device)

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
            description="500kWh/125kW 锂电池储能系统",
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
            description="UPS电池可参与调峰（实验），暂未启用",
        ),
    ]

    for storage in demo_storage:
        db.add(storage)

    demo_pv = [
        PVSystemConfig(
            name="屋顶光伏电站",
            rated_capacity=300,
            efficiency=0.82,
            is_controllable=False,
            is_active=True,
            description="300kWp屋顶分布式光伏",
        ),
        PVSystemConfig(
            name="车棚光伏",
            rated_capacity=50,
            efficiency=0.85,
            is_controllable=False,
            is_active=True,
            description="停车场光伏车棚",
        ),
    ]

    for pv in demo_pv:
        db.add(pv)

    await db.commit()

    return {
        "message": "演示数据初始化成功",
        "created": True,
        "data": {"devices": len(demo_devices), "storage": len(demo_storage), "pv": len(demo_pv)},
    }
