"""
电费监控 API - v1
实时需量监控、预警、月度统计
"""
from typing import Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
import random
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


class RealtimeDataPoint(BaseModel):
    """实时数据点"""
    timestamp: str
    power: float
    demand_target: float
    alert_level: str


# ==================== 实时监控 API ====================

@router.get("/realtime/status", response_model=DemandStatus, summary="获取实时需量状态")
async def get_realtime_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当前实时需量状态，包括预警级别"""

    # 获取配置（申报需量）
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()

    declared_demand = float(config.declared_demand) if config and config.declared_demand else 1000.0
    demand_target = declared_demand  # 目标值通常等于申报值

    # 模拟实时数据（实际应从实时数据源获取）
    now = datetime.now()
    hour = now.hour

    # 根据时间段模拟不同负荷水平
    if 10 <= hour <= 12 or 17 <= hour <= 19:  # 尖峰时段
        base_load = declared_demand * random.uniform(0.75, 0.95)
    elif 8 <= hour <= 22:  # 一般工作时间
        base_load = declared_demand * random.uniform(0.55, 0.75)
    else:  # 夜间
        base_load = declared_demand * random.uniform(0.25, 0.45)

    # 添加随机波动
    current_power = base_load + random.uniform(-50, 50)
    window_avg_power = base_load + random.uniform(-30, 30)

    # 计算利用率
    utilization_ratio = (window_avg_power / demand_target) * 100
    remaining_capacity = demand_target - window_avg_power

    # 判断预警级别
    if utilization_ratio >= 100:
        alert_level = "critical"
    elif utilization_ratio >= 90:
        alert_level = "warning"
    else:
        alert_level = "normal"

    # 模拟本月最大需量
    month_max_demand = declared_demand * random.uniform(0.85, 0.98)
    month_max_time = (now - timedelta(days=random.randint(1, 15))).strftime("%Y-%m-%d %H:%M")

    # 趋势判断（简化逻辑）
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
        remaining_capacity=round(max(0, remaining_capacity), 1),
        alert_level=alert_level,
        month_max_demand=round(month_max_demand, 1),
        month_max_time=month_max_time,
        trend=trend,
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S")
    )


@router.get("/realtime/alerts", response_model=List[DemandAlert], summary="获取当前预警列表")
async def get_realtime_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当前所有活跃的需量预警"""

    # 获取实时状态
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
    """获取最近N小时的功率曲线数据（用于实时图表）"""

    # 获取配置
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()
    declared_demand = float(config.declared_demand) if config and config.declared_demand else 1000.0

    now = datetime.now()
    data_points = []

    # 生成模拟数据（每5分钟一个点）
    for i in range(hours * 12):  # 每小时12个点
        ts = now - timedelta(minutes=i * 5)
        hour = ts.hour

        # 根据时间段模拟负荷
        if 10 <= hour <= 12 or 17 <= hour <= 19:
            base = declared_demand * random.uniform(0.75, 0.92)
        elif 8 <= hour <= 22:
            base = declared_demand * random.uniform(0.55, 0.75)
        else:
            base = declared_demand * random.uniform(0.25, 0.45)

        power = base + random.uniform(-30, 30)
        utilization = power / declared_demand * 100

        if utilization >= 100:
            alert = "critical"
        elif utilization >= 90:
            alert = "warning"
        else:
            alert = "normal"

        data_points.append({
            "timestamp": ts.strftime("%H:%M"),
            "full_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "power": round(power, 1),
            "demand_target": declared_demand,
            "utilization": round(utilization, 1),
            "alert_level": alert
        })

    # 按时间正序排列
    data_points.reverse()

    return {
        "data": data_points,
        "demand_target": declared_demand,
        "time_range": f"最近{hours}小时"
    }


# ==================== 月度统计 API ====================

@router.get("/monthly/current", response_model=MonthlyBillSummary, summary="获取当月电费汇总")
async def get_current_month_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当月电费汇总统计"""

    now = datetime.now()
    year_month = now.strftime("%Y-%m")

    # 获取配置
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()

    # 模拟月度数据
    days_in_month = now.day

    # 基础参数
    declared_demand = float(config.declared_demand) if config and config.declared_demand else 1000.0
    demand_price = float(config.demand_price) if config and config.demand_price else 38.0

    # 模拟用电量和需量
    daily_energy = random.uniform(15000, 20000)  # 日均用电量
    total_energy = daily_energy * days_in_month
    max_demand = declared_demand * random.uniform(0.85, 0.98)

    # 分时电量分布（模拟）
    sharp_ratio = 0.08
    peak_ratio = 0.30
    flat_ratio = 0.35
    valley_ratio = 0.20
    deep_valley_ratio = 0.07

    # 电价（模拟）
    prices = {
        "sharp": 1.20,
        "peak": 0.95,
        "flat": 0.65,
        "valley": 0.35,
        "deep_valley": 0.20
    }

    # 计算电量电费
    energy_cost = (
        total_energy * sharp_ratio * prices["sharp"] +
        total_energy * peak_ratio * prices["peak"] +
        total_energy * flat_ratio * prices["flat"] +
        total_energy * valley_ratio * prices["valley"] +
        total_energy * deep_valley_ratio * prices["deep_valley"]
    )

    # 计算需量电费
    # 如果最大需量 < 申报需量的40%，按40%计
    billable_demand = max(max_demand, declared_demand * 0.4)
    # 如果超过申报需量，超出部分按2倍计
    if max_demand > declared_demand:
        demand_cost = declared_demand * demand_price + (max_demand - declared_demand) * demand_price * 2
    else:
        demand_cost = billable_demand * demand_price

    # 力调电费（简化，假设功率因数0.92，减免0.5%）
    base_cost = energy_cost + demand_cost
    power_factor_adjustment = -base_cost * 0.005

    total_cost = energy_cost + demand_cost + power_factor_adjustment

    # 模拟优化节省
    optimized_saving = total_cost * random.uniform(0.03, 0.08)

    return MonthlyBillSummary(
        year_month=year_month,
        total_energy=round(total_energy, 1),
        max_demand=round(max_demand, 1),
        demand_target=round(declared_demand, 1),
        energy_cost=round(energy_cost, 2),
        demand_cost=round(demand_cost, 2),
        power_factor_adjustment=round(power_factor_adjustment, 2),
        total_cost=round(total_cost, 2),
        optimized_saving=round(optimized_saving, 2),
        cost_breakdown={
            "energy_by_period": {
                "sharp": round(total_energy * sharp_ratio, 1),
                "peak": round(total_energy * peak_ratio, 1),
                "flat": round(total_energy * flat_ratio, 1),
                "valley": round(total_energy * valley_ratio, 1),
                "deep_valley": round(total_energy * deep_valley_ratio, 1)
            },
            "cost_by_period": {
                "sharp": round(total_energy * sharp_ratio * prices["sharp"], 2),
                "peak": round(total_energy * peak_ratio * prices["peak"], 2),
                "flat": round(total_energy * flat_ratio * prices["flat"], 2),
                "valley": round(total_energy * valley_ratio * prices["valley"], 2),
                "deep_valley": round(total_energy * deep_valley_ratio * prices["deep_valley"], 2)
            }
        }
    )


@router.get("/monthly/history", summary="获取历史月度电费")
async def get_monthly_history(
    months: int = Query(12, description="获取最近几个月", ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取历史月度电费统计"""

    now = datetime.now()
    history = []

    for i in range(months):
        target_date = now - timedelta(days=30 * i)
        year_month = target_date.strftime("%Y-%m")

        # 模拟历史数据
        base_energy = 500000 + random.uniform(-50000, 50000)
        base_cost = 350000 + random.uniform(-30000, 30000)

        # 季节性波动
        month = target_date.month
        if month in [7, 8]:  # 夏季高峰
            factor = 1.3
        elif month in [1, 2, 12]:  # 冬季
            factor = 1.1
        else:
            factor = 1.0

        history.append({
            "year_month": year_month,
            "total_energy": round(base_energy * factor, 1),
            "total_cost": round(base_cost * factor, 2),
            "energy_cost": round(base_cost * factor * 0.65, 2),
            "demand_cost": round(base_cost * factor * 0.30, 2),
            "other_cost": round(base_cost * factor * 0.05, 2),
            "max_demand": round(1000 * random.uniform(0.85, 0.98), 1)
        })

    return {
        "data": history,
        "months": months
    }


# ==================== 需量趋势分析 ====================

@router.get("/demand/daily-trend", summary="获取日需量趋势")
async def get_daily_demand_trend(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取指定日期的24小时需量趋势"""

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    # 获取配置
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()
    declared_demand = float(config.declared_demand) if config and config.declared_demand else 1000.0

    # 生成24小时 * 4 (15分钟间隔) 的数据
    data_points = []
    max_demand = 0
    max_demand_time = None

    for hour in range(24):
        for quarter in range(4):
            time_str = f"{hour:02d}:{quarter*15:02d}"

            # 根据时段模拟负荷
            if 10 <= hour <= 12 or 17 <= hour <= 19:
                base = declared_demand * random.uniform(0.78, 0.95)
            elif 8 <= hour <= 22:
                base = declared_demand * random.uniform(0.55, 0.75)
            else:
                base = declared_demand * random.uniform(0.25, 0.45)

            demand = base + random.uniform(-20, 20)

            if demand > max_demand:
                max_demand = demand
                max_demand_time = time_str

            # 时段类型
            if hour in [11, 18]:
                period = "sharp"
            elif hour in [9, 10, 12, 13, 17, 19, 20]:
                period = "peak"
            elif hour in [8, 14, 15, 16, 21]:
                period = "flat"
            elif hour in [22, 23, 4, 5, 6, 7]:
                period = "valley"
            else:
                period = "deep_valley"

            data_points.append({
                "time": time_str,
                "demand": round(demand, 1),
                "period": period
            })

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "declared_demand": declared_demand,
        "max_demand": round(max_demand, 1),
        "max_demand_time": max_demand_time,
        "avg_demand": round(sum(p["demand"] for p in data_points) / len(data_points), 1),
        "data": data_points
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
    """
    from app.services.realtime_dispatch import get_dispatch_controller

    # 获取配置
    config_result = await db.execute(
        select(PricingConfig).where(PricingConfig.is_enabled == True).order_by(desc(PricingConfig.id))
    )
    config = config_result.scalar_one_or_none()
    demand_target = float(config.declared_demand) if config and config.declared_demand else 800.0

    controller = get_dispatch_controller(demand_target)

    # 模拟一个当前功率读数
    import random
    current_power = demand_target * random.uniform(0.75, 0.95)
    prediction = controller.add_power_reading(current_power)

    status = controller.get_status()

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
            "active_commands": status["active_commands"],
            "storage_available": status["storage_available"],
            "storage_soc": status["storage_soc"],
            "curtailable_devices_count": status["curtailable_devices_count"],
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
    """
    from app.services.realtime_dispatch import simulate_realtime_monitoring

    results = simulate_realtime_monitoring(minutes)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "duration_minutes": minutes,
            "data_points": len(results),
            "results": results
        }
    }
