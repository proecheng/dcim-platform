"""
需量板块嵌入式 API
提供精简数据接口，供节能中心详情页嵌入组件调用

[V2.9] 使用统一的 DemandAnalysisService 确保数据一致性
"""
from typing import Optional, List
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from decimal import Decimal

from ..deps import get_db, require_viewer
from ...models.user import User
from ...models.energy import (
    DemandHistory, MeterPoint, PowerCurveData,
    ElectricityPricing, PricingConfig
)
from ...schemas.common import ResponseModel
from ...services.demand_analysis_service import DemandAnalysisService, subtract_months  # [V2.9] 统一服务

router = APIRouter(prefix="/demand", tags=["需量嵌入式API"])


# ==================== Schema 定义 ====================

from pydantic import BaseModel


class DemandComparisonData(BaseModel):
    """需量配置对比数据"""
    meter_point_id: Optional[int] = None
    meter_point_name: str = "全站"
    current_declared: float  # 当前申报需量
    max_demand_12m: float    # 12月最大需量
    avg_demand_12m: float    # 12月平均需量
    utilization_rate: float  # 利用率
    over_declared: float     # 超申报量
    recommendation: dict     # 推荐建议


class DemandCurvePoint(BaseModel):
    """需量曲线数据点"""
    month: str
    max_demand: float
    avg_demand: Optional[float] = None
    declared_demand: Optional[float] = None


class DemandCurveMiniData(BaseModel):
    """迷你需量曲线数据"""
    data: List[DemandCurvePoint]
    max_value: float
    max_month: str
    declared_demand: Optional[float] = None


class HourlyLoadPoint(BaseModel):
    """小时负荷数据点"""
    hour: int
    power: float
    period: str  # peak/valley/flat/sharp


class PeriodSummary(BaseModel):
    """时段汇总"""
    total_kwh: float
    avg_power: float
    hours: int


class LoadPeriodData(BaseModel):
    """负荷时段分布数据"""
    date: str
    hourly_data: List[HourlyLoadPoint]
    period_summary: dict  # {peak: PeriodSummary, valley: PeriodSummary, ...}
    shiftable_power: float  # 可转移功率


# ==================== API 端点 ====================


@router.get("/comparison", response_model=ResponseModel[DemandComparisonData], summary="需量配置对比数据")
async def get_demand_comparison(
    meter_point_id: Optional[int] = Query(None, description="计量点ID，不传则返回全站数据"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    获取需量配置对比数据，供嵌入式组件使用

    返回：
    - 当前申报需量 vs 实际最大需量对比
    - 利用率和调整建议

    注: 使用统一的 DemandAnalysisService 确保数据源和计算逻辑一致
    """
    from ...services.demand_analysis_service import DemandAnalysisService

    # 使用统一的需量分析服务
    service = DemandAnalysisService(db)
    data = await service.get_comparison_data(meter_point_id)

    return ResponseModel(
        code=0,
        message="success",
        data=DemandComparisonData(
            meter_point_id=data["meter_point_id"],
            meter_point_name=data["meter_point_name"],
            current_declared=data["current_declared"],
            max_demand_12m=data["max_demand_12m"],
            avg_demand_12m=data["avg_demand_12m"],
            utilization_rate=data["utilization_rate"],
            over_declared=data["over_declared"],
            recommendation=data["recommendation"]
        )
    )


@router.get("/curve-mini", response_model=ResponseModel[DemandCurveMiniData], summary="迷你需量曲线")
async def get_demand_curve_mini(
    meter_point_id: Optional[int] = Query(None, description="计量点ID"),
    months: int = Query(12, description="月数", ge=3, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    获取迷你需量曲线数据（月度最大需量趋势）

    用于嵌入式图表展示，数据量精简

    [V2.9] 使用统一的模拟数据生成方法
    """
    end_date = datetime.now()
    # [V2.9-FIX] 使用精确的月份计算
    start_date = subtract_months(end_date, months)

    query = select(DemandHistory).where(
        and_(
            DemandHistory.stat_year * 100 + DemandHistory.stat_month >=
                start_date.year * 100 + start_date.month,
            DemandHistory.stat_year * 100 + DemandHistory.stat_month <=
                end_date.year * 100 + end_date.month
        )
    ).order_by(DemandHistory.stat_year, DemandHistory.stat_month)

    if meter_point_id:
        query = query.where(DemandHistory.meter_point_id == meter_point_id)

    result = await db.execute(query)
    records = result.scalars().all()

    if not records:
        # [V2.9] 使用统一的模拟数据生成方法
        mock_data = DemandAnalysisService.generate_mock_demand_curve(
            meter_point_id=meter_point_id,
            months=months,
            base_demand=650.0,
            declared_demand=DemandAnalysisService.DEFAULT_DECLARED_DEMAND
        )

        data = [DemandCurvePoint(
            month=d["month"],
            max_demand=d["max_demand"],
            avg_demand=d["avg_demand"],
            declared_demand=d["declared_demand"]
        ) for d in mock_data]

        max_value = max(d["max_demand"] for d in mock_data)
        max_month = next(d["month"] for d in mock_data if d["max_demand"] == max_value)

        return ResponseModel(
            code=0,
            message="success",
            data=DemandCurveMiniData(
                data=data,
                max_value=max_value,
                max_month=max_month,
                declared_demand=DemandAnalysisService.DEFAULT_DECLARED_DEMAND
            )
        )

    # 处理真实数据
    data = []
    max_value = 0
    max_month = ""
    declared_demand = records[0].declared_demand if records else DemandAnalysisService.DEFAULT_DECLARED_DEMAND

    for r in records:
        month_str = f"{r.stat_year}-{r.stat_month:02d}"
        demand = r.max_demand or 0
        data.append(DemandCurvePoint(
            month=month_str,
            max_demand=demand,
            avg_demand=r.avg_demand,
            declared_demand=r.declared_demand
        ))
        if demand > max_value:
            max_value = demand
            max_month = month_str

    return ResponseModel(
        code=0,
        message="success",
        data=DemandCurveMiniData(
            data=data,
            max_value=max_value,
            max_month=max_month,
            declared_demand=declared_demand
        )
    )


@router.get("/load-period", response_model=ResponseModel[LoadPeriodData], summary="负荷时段分布")
async def get_load_period_distribution(
    meter_point_id: Optional[int] = Query(None, description="计量点ID"),
    target_date: Optional[date] = Query(None, description="目标日期，默认昨天"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    获取24小时负荷时段分布数据

    用于峰谷套利分析的嵌入式图表

    [V2.9] 使用统一的模拟数据生成方法
    """
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).date()

    # 获取电价时段配置
    pricing_result = await db.execute(
        select(ElectricityPricing).where(ElectricityPricing.is_active == True)
    )
    pricing_records = pricing_result.scalars().all()

    # 构建时段映射 (简化版)
    period_map = {}
    for p in pricing_records:
        if hasattr(p, 'start_hour') and hasattr(p, 'end_hour'):
            for h in range(p.start_hour, p.end_hour):
                period_map[h] = p.period_type

    # 默认5时段配置（如果没有电价配置）
    # 尖峰(sharp), 峰时(peak), 平时(flat), 谷时(valley), 深谷(deep_valley)
    if not period_map:
        period_map = {
            0: 'deep_valley', 1: 'deep_valley', 2: 'deep_valley', 3: 'deep_valley',
            4: 'valley', 5: 'valley', 6: 'valley', 7: 'valley',
            8: 'flat', 9: 'peak', 10: 'peak', 11: 'sharp',
            12: 'peak', 13: 'flat', 14: 'flat', 15: 'flat',
            16: 'flat', 17: 'peak', 18: 'sharp', 19: 'peak',
            20: 'peak', 21: 'flat', 22: 'valley', 23: 'valley'
        }

    # 查询功率曲线数据
    start_time = datetime.combine(target_date, datetime.min.time())
    end_time = datetime.combine(target_date, datetime.max.time())

    query = select(PowerCurveData).where(
        and_(
            PowerCurveData.record_time >= start_time,
            PowerCurveData.record_time <= end_time
        )
    )

    if meter_point_id:
        query = query.where(PowerCurveData.meter_point_id == meter_point_id)

    result = await db.execute(query)
    records = result.scalars().all()

    # 按小时聚合（5时段）
    hourly_data = []
    period_stats = {
        'sharp': {'kwh': 0, 'hours': 0, 'power_sum': 0},
        'peak': {'kwh': 0, 'hours': 0, 'power_sum': 0},
        'flat': {'kwh': 0, 'hours': 0, 'power_sum': 0},
        'valley': {'kwh': 0, 'hours': 0, 'power_sum': 0},
        'deep_valley': {'kwh': 0, 'hours': 0, 'power_sum': 0}
    }

    if records:
        # 按小时分组
        hour_powers = {}
        for r in records:
            hour = r.record_time.hour
            if hour not in hour_powers:
                hour_powers[hour] = []
            hour_powers[hour].append(r.power or 0)

        for hour in range(24):
            period = period_map.get(hour, 'flat')
            power = sum(hour_powers.get(hour, [500])) / max(len(hour_powers.get(hour, [1])), 1)

            hourly_data.append(HourlyLoadPoint(
                hour=hour,
                power=round(power, 1),
                period=period
            ))

            period_stats[period]['kwh'] += power
            period_stats[period]['hours'] += 1
            period_stats[period]['power_sum'] += power
    else:
        # [V2.9] 使用统一的模拟数据生成方法
        mock_data = DemandAnalysisService.generate_mock_hourly_load(
            meter_point_id=meter_point_id,
            target_date=target_date,
            period_map=period_map
        )

        for d in mock_data:
            hourly_data.append(HourlyLoadPoint(
                hour=d["hour"],
                power=d["power"],
                period=d["period"]
            ))

            period = d["period"]
            period_stats[period]['kwh'] += d["power"]
            period_stats[period]['hours'] += 1
            period_stats[period]['power_sum'] += d["power"]

    # 计算时段汇总
    period_summary = {}
    for period, stats in period_stats.items():
        if stats['hours'] > 0:
            period_summary[period] = {
                'total_kwh': round(stats['kwh'], 1),
                'avg_power': round(stats['power_sum'] / stats['hours'], 1),
                'hours': stats['hours']
            }

    # 估算可转移功率（高价时段与低价时段的差异）
    # 高价时段：尖峰 + 峰时，低价时段：深谷 + 谷时
    sharp_avg = period_summary.get('sharp', {}).get('avg_power', 0)
    peak_avg = period_summary.get('peak', {}).get('avg_power', 0)
    valley_avg = period_summary.get('valley', {}).get('avg_power', 0)
    deep_valley_avg = period_summary.get('deep_valley', {}).get('avg_power', 0)

    high_price_avg = (sharp_avg + peak_avg) / 2 if (sharp_avg or peak_avg) else 0
    low_price_avg = (deep_valley_avg + valley_avg) / 2 if (deep_valley_avg or valley_avg) else 0

    shiftable_power = max(0, (high_price_avg - low_price_avg) * 0.5)

    return ResponseModel(
        code=0,
        message="success",
        data=LoadPeriodData(
            date=str(target_date),
            hourly_data=hourly_data,
            period_summary=period_summary,
            shiftable_power=round(shiftable_power, 1)
        )
    )


@router.get("/power-factor-trend", response_model=ResponseModel, summary="功率因数趋势")
async def get_power_factor_trend(
    meter_point_id: Optional[int] = Query(None, description="计量点ID"),
    days: int = Query(30, description="天数", ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    获取功率因数趋势数据

    用于力调电费优化的嵌入式图表

    [V2.9-FIX] 先尝试查询真实数据，无数据时使用统一模拟数据
    """
    baseline = 0.90  # 基准功率因数

    # [V2.9] 尝试从 PowerCurveData 获取真实功率因数数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 查询功率因数数据（假设 PowerCurveData 有 power_factor 字段）
    query = select(
        func.date(PowerCurveData.record_time).label('date'),
        func.avg(PowerCurveData.power_factor).label('avg_pf'),
        func.min(PowerCurveData.power_factor).label('min_pf'),
        func.max(PowerCurveData.power_factor).label('max_pf')
    ).where(
        and_(
            PowerCurveData.record_time >= start_date,
            PowerCurveData.record_time <= end_date,
            PowerCurveData.power_factor.isnot(None),
            PowerCurveData.power_factor > 0
        )
    ).group_by(func.date(PowerCurveData.record_time))

    if meter_point_id:
        query = query.where(PowerCurveData.meter_point_id == meter_point_id)

    result = await db.execute(query)
    records = result.all()

    data = []
    if records and len(records) >= 3:
        # 使用真实数据
        for r in records:
            pf = float(r.avg_pf) if r.avg_pf else 0
            data.append({
                "date": str(r.date),
                "power_factor": round(pf, 3),
                "status": "good" if pf >= baseline else ("warning" if pf >= 0.85 else "bad")
            })
    else:
        # [V2.9] 使用统一的模拟数据生成方法
        data = DemandAnalysisService.generate_mock_power_factor(
            meter_point_id=meter_point_id,
            days=days,
            baseline=baseline
        )

    # 统计
    pf_values = [d["power_factor"] for d in data]
    avg_pf = sum(pf_values) / len(pf_values) if pf_values else 0
    below_baseline_days = sum(1 for pf in pf_values if pf < baseline)

    # 估算力调电费影响 - 使用统一常量
    monthly_bill = 50000  # 假设月电费5万（可配置化）
    if avg_pf < baseline:
        penalty_rate = (baseline - avg_pf) * 10  # 简化计算
        penalty = monthly_bill * penalty_rate / 100
    else:
        reward_rate = (avg_pf - baseline) * 0.75  # 每提高0.01奖励0.75%
        penalty = -monthly_bill * reward_rate / 100  # 负值表示奖励

    return ResponseModel(
        code=0,
        message="success",
        data={
            "data": data,
            "statistics": {
                "avg_power_factor": round(avg_pf, 3),
                "min_power_factor": round(min(pf_values), 3) if pf_values else 0,
                "max_power_factor": round(max(pf_values), 3) if pf_values else 0,
                "below_baseline_days": below_baseline_days,
                "baseline": baseline
            },
            "financial_impact": {
                "monthly_adjustment": round(penalty, 2),
                "annual_adjustment": round(penalty * 12, 2),
                "is_penalty": penalty > 0
            }
        }
    )
