"""
电费监控 API - v1
实时需量监控、预警、月度统计

数据来源策略:
1. 优先从数据库获取真实数据
2. 若无真实数据且 SIMULATION_ENABLED=True，使用 demo_provider 提供的模拟数据
3. 若无真实数据且 SIMULATION_ENABLED=False，返回空数据或默认值
"""
from typing import Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from ..deps import get_db, require_viewer
from ...models.user import User
from ...models.energy import (
    RealtimeMonitoring, MonthlyStatistics, PricingConfig,
    Demand15MinData, MeterPoint
)
from ...services.demo_data_provider import demo_provider
from ...core.config import get_settings

router = APIRouter()


# ==================== Pydantic 模型 ====================

class DemandStatus(BaseModel):
    """需量状态"""
    current_power: float = Field(..., description="当前功率 kW")
    window_avg_power: float = Field(..., description="15分钟窗口平均功率 kW")
    demand_target: float = Field(..., description="需量目标 kW")
    declared_demand: float = Field(..., description="申报需量 kW")
    utilization_ratio: float = Field(..., description="需量利用率 %")
    remaining_capacity: float = Field(..., description="剩余容量 kW")
    alert_level: str = Field(..., description="预警级别: normal/warning/critical")
    month_max_demand: float = Field(..., description="本月最大需量 kW")
    month_max_time: Optional[str] = Field(None, description="本月最大需量时间")
    trend: str = Field(..., description="趋势: up/down/stable")
    timestamp: str = Field(..., description="数据时间")
    is_demo_data: bool = Field(False, description="是否为演示数据")


class DemandAlert(BaseModel):
    """需量预警"""
    level: str = Field(..., description="预警级别")
    message: str = Field(..., description="预警信息")
    current_value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    suggestion: str = Field(..., description="建议措施")


class MonthlyBillSummary(BaseModel):
    """月度电费汇总"""
    year_month: str
    total_energy: float = Field(0, description="总用电量 kWh")
    max_demand: float = Field(0, description="最大需量 kW")
    demand_target: float = Field(0, description="需量目标 kW")
    energy_cost: float = Field(0, description="电量电费 元")
    demand_cost: float = Field(0, description="需量电费 元")
    power_factor_adjustment: float = Field(0, description="力调电费 元")
    total_cost: float = Field(0, description="总电费 元")
    optimized_saving: float = Field(0, description="优化节省 元")
    cost_breakdown: dict = Field(default_factory=dict)
    is_demo_data: bool = Field(False, description="是否为演示数据")


class RealtimeDataPoint(BaseModel):
    """实时数据点"""
    timestamp: str
    power: float
    demand_target: float
    alert_level: str


# ==================== 辅助函数 ====================

async def _get_declared_demand(db: AsyncSession) -> tuple[float, float]:
    """获取申报需量和需量单价配置

    Returns:
        (declared_demand, demand_price) 元组
    """
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()

    declared_demand = float(config.declared_demand) if config and config.declared_demand else 1000.0
    demand_price = float(config.demand_price) if config and config.demand_price else 38.0

    return declared_demand, demand_price


async def _get_latest_realtime_data(db: AsyncSession) -> Optional[RealtimeMonitoring]:
    """从数据库获取最新的实时监控数据"""
    result = await db.execute(
        select(RealtimeMonitoring).order_by(desc(RealtimeMonitoring.timestamp)).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_month_max_demand(db: AsyncSession, year_month: str) -> tuple[Optional[float], Optional[str]]:
    """获取指定月份的最大需量

    Returns:
        (max_demand, max_demand_time) 元组
    """
    start_date = datetime.strptime(year_month + "-01", "%Y-%m-%d")
    if start_date.month == 12:
        end_date = start_date.replace(year=start_date.year + 1, month=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1)

    # 从 15 分钟需量数据表查询
    result = await db.execute(
        select(Demand15MinData)
        .where(
            Demand15MinData.timestamp >= start_date,
            Demand15MinData.timestamp < end_date
        )
        .order_by(desc(Demand15MinData.average_power))
        .limit(1)
    )
    max_record = result.scalar_one_or_none()

    if max_record:
        return (
            float(max_record.average_power) if max_record.average_power else None,
            max_record.timestamp.strftime("%Y-%m-%d %H:%M") if max_record.timestamp else None
        )
    return None, None


# ==================== 实时监控 API ====================

@router.get("/realtime/status", response_model=DemandStatus, summary="获取实时需量状态")
async def get_realtime_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当前实时需量状态，包括预警级别

    数据来源:
    - 优先从 realtime_monitoring 表获取最新数据
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    settings = get_settings()
    now = datetime.now()
    year_month = now.strftime("%Y-%m")

    # 获取配置
    declared_demand, _ = await _get_declared_demand(db)
    demand_target = declared_demand

    # 尝试从数据库获取真实数据
    latest_data = await _get_latest_realtime_data(db)

    # 检查数据是否过期（超过 5 分钟视为过期）
    data_is_fresh = (
        latest_data is not None and
        latest_data.timestamp is not None and
        (now - latest_data.timestamp).total_seconds() < 300
    )

    if data_is_fresh and latest_data:
        # 使用真实数据
        current_power = float(latest_data.current_power) if latest_data.current_power else 0
        window_avg_power = float(latest_data.window_avg_power) if latest_data.window_avg_power else current_power
        utilization_ratio = float(latest_data.utilization_ratio) if latest_data.utilization_ratio else (
            (window_avg_power / demand_target) * 100 if demand_target > 0 else 0
        )
        alert_level = latest_data.alert_level or "normal"

        # 获取本月最大需量
        month_max_demand, month_max_time = await _get_month_max_demand(db, year_month)
        if month_max_demand is None:
            month_max_demand = window_avg_power
            month_max_time = now.strftime("%Y-%m-%d %H:%M")

        # 趋势判断（基于实际数据）
        if current_power > window_avg_power * 1.05:
            trend = "up"
        elif current_power < window_avg_power * 0.95:
            trend = "down"
        else:
            trend = "stable"

        return DemandStatus(
            current_power=round(current_power, 1),
            window_avg_power=round(window_avg_power, 1),
            demand_target=round(demand_target, 1),
            declared_demand=round(declared_demand, 1),
            utilization_ratio=round(utilization_ratio, 1),
            remaining_capacity=round(max(0, demand_target - window_avg_power), 1),
            alert_level=alert_level,
            month_max_demand=round(month_max_demand, 1),
            month_max_time=month_max_time,
            trend=trend,
            timestamp=latest_data.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            is_demo_data=False
        )

    # 无真实数据，检查是否启用模拟模式
    if settings.simulation_enabled:
        # 使用 demo_provider 获取模拟数据
        demo_data = demo_provider.get_demo_demand_status(declared_demand, now)
        return DemandStatus(**demo_data)
    else:
        # 返回默认值（非模拟模式下无数据）
        return DemandStatus(
            current_power=0,
            window_avg_power=0,
            demand_target=round(demand_target, 1),
            declared_demand=round(declared_demand, 1),
            utilization_ratio=0,
            remaining_capacity=round(demand_target, 1),
            alert_level="normal",
            month_max_demand=0,
            month_max_time=None,
            trend="stable",
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
            is_demo_data=False
        )


@router.get("/realtime/alerts", response_model=List[DemandAlert], summary="获取当前预警列表")
async def get_realtime_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当前所有活跃的需量预警"""

    # 获取实时状态（自动使用真实数据或模拟数据）
    status = await get_realtime_status(db, _)

    alerts = []

    if status.alert_level == "critical":
        alerts.append(DemandAlert(
            level="critical",
            message=f"需量超标！当前15分钟平均功率 {status.window_avg_power}kW 已超过目标值 {status.demand_target}kW",
            current_value=status.window_avg_power,
            threshold=status.demand_target,
            suggestion="立即启动削减措施：1)降低非关键空调负荷 2)暂停可延迟设备 3)启用储能放电"
        ))
    elif status.alert_level == "warning":
        alerts.append(DemandAlert(
            level="warning",
            message=f"需量接近上限！当前利用率 {status.utilization_ratio:.1f}%，剩余容量仅 {status.remaining_capacity}kW",
            current_value=status.window_avg_power,
            threshold=status.demand_target * 0.9,
            suggestion="建议预防性措施：1)检查可削减负荷 2)准备储能系统 3)通知相关部门"
        ))

    # 检查趋势预警
    if status.trend == "up" and status.utilization_ratio > 80:
        alerts.append(DemandAlert(
            level="warning",
            message=f"功率上升趋势，预计可能突破目标值",
            current_value=status.current_power,
            threshold=status.demand_target,
            suggestion="持续关注，做好削峰准备"
        ))

    return alerts


@router.get("/realtime/curve", summary="获取实时功率曲线数据")
async def get_realtime_curve(
    hours: int = Query(4, description="获取最近几小时数据", ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取最近N小时的功率曲线数据（用于实时图表）

    数据来源:
    - 优先从 demand_15min_data 表获取历史数据
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    settings = get_settings()
    now = datetime.now()
    start_time = now - timedelta(hours=hours)

    # 获取配置
    declared_demand, _ = await _get_declared_demand(db)

    # 尝试从数据库获取真实数据
    result = await db.execute(
        select(Demand15MinData)
        .where(Demand15MinData.timestamp >= start_time)
        .order_by(Demand15MinData.timestamp)
    )
    records = result.scalars().all()

    if records:
        # 使用真实数据
        data_points = []
        for record in records:
            power = float(record.average_power) if record.average_power else 0
            utilization = (power / declared_demand * 100) if declared_demand > 0 else 0

            if utilization >= 100:
                alert = "critical"
            elif utilization >= 90:
                alert = "warning"
            else:
                alert = "normal"

            data_points.append({
                "timestamp": record.timestamp.strftime("%H:%M"),
                "full_timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "power": round(power, 1),
                "demand_target": declared_demand,
                "utilization": round(utilization, 1),
                "alert_level": alert,
                "is_demo_data": False
            })

        return {
            "data": data_points,
            "demand_target": declared_demand,
            "time_range": f"最近{hours}小时",
            "is_demo_data": False
        }

    # 无真实数据，检查是否启用模拟模式
    if settings.simulation_enabled:
        data_points = demo_provider.get_demo_realtime_curve(declared_demand, hours, now)
        return {
            "data": data_points,
            "demand_target": declared_demand,
            "time_range": f"最近{hours}小时",
            "is_demo_data": True
        }
    else:
        # 返回空数据
        return {
            "data": [],
            "demand_target": declared_demand,
            "time_range": f"最近{hours}小时",
            "is_demo_data": False
        }


# ==================== 月度统计 API ====================

@router.get("/monthly/current", response_model=MonthlyBillSummary, summary="获取当月电费汇总")
async def get_current_month_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当月电费汇总统计

    数据来源:
    - 优先从 monthly_statistics 表获取数据
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    settings = get_settings()
    now = datetime.now()
    year_month = now.strftime("%Y-%m")

    # 获取配置
    declared_demand, demand_price = await _get_declared_demand(db)

    # 尝试从数据库获取真实数据
    result = await db.execute(
        select(MonthlyStatistics).where(MonthlyStatistics.year_month == year_month)
    )
    stats = result.scalar_one_or_none()

    if stats:
        # 使用真实数据
        return MonthlyBillSummary(
            year_month=year_month,
            total_energy=float(stats.total_energy) if stats.total_energy else 0,
            max_demand=float(stats.max_demand) if stats.max_demand else 0,
            demand_target=float(stats.demand_target) if stats.demand_target else declared_demand,
            energy_cost=float(stats.energy_cost) if stats.energy_cost else 0,
            demand_cost=float(stats.demand_cost) if stats.demand_cost else 0,
            power_factor_adjustment=float(stats.power_factor_adjustment) if stats.power_factor_adjustment else 0,
            total_cost=float(stats.total_cost) if stats.total_cost else 0,
            optimized_saving=float(stats.optimized_saving) if stats.optimized_saving else 0,
            cost_breakdown={},
            is_demo_data=False
        )

    # 无真实数据，检查是否启用模拟模式
    if settings.simulation_enabled:
        demo_data = demo_provider.get_demo_monthly_summary(declared_demand, demand_price, now)
        return MonthlyBillSummary(**demo_data)
    else:
        # 返回默认值
        return MonthlyBillSummary(
            year_month=year_month,
            total_energy=0,
            max_demand=0,
            demand_target=declared_demand,
            energy_cost=0,
            demand_cost=0,
            power_factor_adjustment=0,
            total_cost=0,
            optimized_saving=0,
            cost_breakdown={},
            is_demo_data=False
        )


@router.get("/monthly/history", summary="获取历史月度电费")
async def get_monthly_history(
    months: int = Query(12, description="获取最近几个月", ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取历史月度电费统计

    数据来源:
    - 优先从 monthly_statistics 表获取数据
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    settings = get_settings()
    now = datetime.now()

    # 获取配置
    declared_demand, _ = await _get_declared_demand(db)

    # 尝试从数据库获取真实数据
    result = await db.execute(
        select(MonthlyStatistics).order_by(desc(MonthlyStatistics.year_month)).limit(months)
    )
    records = result.scalars().all()

    if records:
        # 使用真实数据
        history = []
        for record in records:
            history.append({
                "year_month": record.year_month,
                "total_energy": float(record.total_energy) if record.total_energy else 0,
                "total_cost": float(record.total_cost) if record.total_cost else 0,
                "energy_cost": float(record.energy_cost) if record.energy_cost else 0,
                "demand_cost": float(record.demand_cost) if record.demand_cost else 0,
                "other_cost": float(record.power_factor_adjustment) if record.power_factor_adjustment else 0,
                "max_demand": float(record.max_demand) if record.max_demand else 0,
                "is_demo_data": False
            })

        return {
            "data": history,
            "months": len(history),
            "is_demo_data": False
        }

    # 无真实数据，检查是否启用模拟模式
    if settings.simulation_enabled:
        history = demo_provider.get_demo_monthly_history(declared_demand, months, now)
        return {
            "data": history,
            "months": months,
            "is_demo_data": True
        }
    else:
        return {
            "data": [],
            "months": 0,
            "is_demo_data": False
        }


# ==================== 需量趋势分析 ====================

@router.get("/demand/daily-trend", summary="获取日需量趋势")
async def get_daily_demand_trend(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取指定日期的24小时需量趋势

    数据来源:
    - 优先从 demand_15min_data 表获取数据
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    settings = get_settings()

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    # 获取配置
    declared_demand, _ = await _get_declared_demand(db)

    # 尝试从数据库获取真实数据
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(Demand15MinData)
        .where(
            Demand15MinData.timestamp >= day_start,
            Demand15MinData.timestamp < day_end
        )
        .order_by(Demand15MinData.timestamp)
    )
    records = result.scalars().all()

    if records:
        # 使用真实数据
        data_points = []
        max_demand = 0
        max_demand_time = None

        for record in records:
            demand = float(record.average_power) if record.average_power else 0
            time_str = record.timestamp.strftime("%H:%M")

            if demand > max_demand:
                max_demand = demand
                max_demand_time = time_str

            data_points.append({
                "time": time_str,
                "demand": round(demand, 1),
                "period": record.time_period or "flat"
            })

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "declared_demand": declared_demand,
            "max_demand": round(max_demand, 1),
            "max_demand_time": max_demand_time,
            "avg_demand": round(sum(p["demand"] for p in data_points) / len(data_points), 1) if data_points else 0,
            "data": data_points,
            "is_demo_data": False
        }

    # 无真实数据，检查是否启用模拟模式
    if settings.simulation_enabled:
        demo_data = demo_provider.get_demo_daily_demand_trend(declared_demand, target_date)
        return demo_data
    else:
        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "declared_demand": declared_demand,
            "max_demand": 0,
            "max_demand_time": None,
            "avg_demand": 0,
            "data": [],
            "is_demo_data": False
        }


# ==================== 实时调度控制 API ====================

class DispatchCommandRequest(BaseModel):
    """调度指令请求"""
    action: str = Field(..., description="动作: curtail/discharge/shift/restore")
    device_id: Optional[int] = Field(None, description="设备ID")
    device_name: str = Field(..., description="设备名称")
    power_change: float = Field(..., description="功率变化量 kW")
    duration: int = Field(600, description="持续时间 秒")
    reason: str = Field("手动调整", description="原因")


class DispatchStatus(BaseModel):
    """调度状态"""
    demand_target: float
    current_power: float
    predicted_power: float
    utilization_ratio: float
    alert_level: str
    time_remaining: int
    trend: str
    risk_score: float
    active_commands: List[dict]
    storage_available: float
    storage_soc: float


@router.get("/dispatch/status", summary="获取实时调度状态")
async def get_dispatch_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取实时调度控制器状态

    包括：
    - 当前功率和预测
    - 预警级别
    - 活跃的调度指令
    - 储能状态

    数据来源:
    - 优先从实时监控数据获取当前功率
    - 若无数据且启用模拟模式，使用 demo_provider 提供的模拟数据
    """
    from app.services.realtime_dispatch import get_dispatch_controller

    settings = get_settings()

    # 获取配置
    declared_demand, _ = await _get_declared_demand(db)
    demand_target = declared_demand

    controller = get_dispatch_controller(demand_target)

    # 获取实时状态（自动使用真实数据或模拟数据）
    status = await get_realtime_status(db, _)

    # 使用实时状态数据
    current_power = status.current_power
    prediction = controller.add_power_reading(current_power)

    ctrl_status = controller.get_status()

    return {
        "code": 0,
        "message": "success",
        "data": {
            "demand_target": demand_target,
            "current_power": round(current_power, 1),
            "predicted_power": prediction.predicted_window_avg,
            "utilization_ratio": prediction.utilization_ratio,
            "alert_level": prediction.alert_level.value,
            "time_remaining": prediction.time_remaining,
            "trend": prediction.trend,
            "risk_score": prediction.risk_score,
            "active_commands": ctrl_status["active_commands"],
            "storage_available": ctrl_status["storage_available"],
            "storage_soc": ctrl_status["storage_soc"],
            "curtailable_devices_count": ctrl_status["curtailable_devices_count"],
            "is_demo_data": status.is_demo_data
        }
    }


@router.post("/dispatch/command", summary="发送调度指令")
async def send_dispatch_command(
    request: DispatchCommandRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    发送手动调度指令

    支持的动作：
    - curtail: 削减负荷
    - discharge: 储能放电
    - shift: 延迟启动
    - restore: 恢复运行
    """
    from app.services.realtime_dispatch import (
        get_dispatch_controller,
        AdjustmentAction
    )

    controller = get_dispatch_controller()

    # 转换动作类型
    action_map = {
        'curtail': AdjustmentAction.CURTAIL,
        'discharge': AdjustmentAction.DISCHARGE,
        'shift': AdjustmentAction.SHIFT,
        'restore': AdjustmentAction.RESTORE,
    }

    action = action_map.get(request.action)
    if not action:
        return {
            "code": 400,
            "message": f"无效的动作类型: {request.action}",
            "data": None
        }

    cmd = controller.create_manual_command(
        action=action,
        device_id=request.device_id,
        device_name=request.device_name,
        power_change=request.power_change,
        duration=request.duration,
        reason=request.reason
    )

    return {
        "code": 0,
        "message": "success",
        "data": {
            "command_id": cmd.id,
            "action": cmd.action.value,
            "device_name": cmd.device_name,
            "power_change": cmd.power_change,
            "duration": cmd.duration,
            "status": cmd.status,
            "created_at": cmd.created_at.isoformat()
        }
    }


@router.put("/dispatch/command/{command_id}/complete", summary="完成调度指令")
async def complete_dispatch_command(
    command_id: str,
    success: bool = Query(True, description="是否成功"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """标记调度指令为已完成"""
    from app.services.realtime_dispatch import get_dispatch_controller

    controller = get_dispatch_controller()
    controller.complete_command(command_id, success)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "command_id": command_id,
            "status": "completed" if success else "failed"
        }
    }


@router.get("/dispatch/simulation", summary="模拟实时监控")
async def simulate_monitoring(
    minutes: int = Query(5, description="模拟分钟数", ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    运行实时监控模拟

    用于演示和测试实时调度功能
    注意：此 API 仅用于演示目的，始终使用模拟数据
    """
    from app.services.realtime_dispatch import simulate_realtime_monitoring

    results = simulate_realtime_monitoring(minutes)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "duration_minutes": minutes,
            "data_points": len(results),
            "results": results,
            "is_demo_data": True  # 此 API 始终使用模拟数据
        }
    }
