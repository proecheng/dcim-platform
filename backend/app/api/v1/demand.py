"""
需量板块嵌入式 API
提供精简数据接口，供节能中心详情页嵌入组件调用
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
    """
    # 获取最近12个月的需量历史
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    query = select(DemandHistory).where(
        and_(
            DemandHistory.stat_year * 100 + DemandHistory.stat_month >=
                start_date.year * 100 + start_date.month,
            DemandHistory.stat_year * 100 + DemandHistory.stat_month <=
                end_date.year * 100 + end_date.month
        )
    )

    if meter_point_id:
        query = query.where(DemandHistory.meter_point_id == meter_point_id)

    result = await db.execute(query)
    records = result.scalars().all()

    if not records:
        # 返回模拟数据（当没有历史数据时）
        return ResponseModel(
            code=0,
            message="success",
            data=DemandComparisonData(
                meter_point_id=meter_point_id,
                meter_point_name="全站" if not meter_point_id else f"计量点#{meter_point_id}",
                current_declared=800.0,
                max_demand_12m=685.0,
                avg_demand_12m=520.0,
                utilization_rate=0.856,
                over_declared=115.0,
                recommendation={
                    "suggested_demand": 750,
                    "reduce_amount": 50,
                    "monthly_saving": 1400,
                    "risk_level": "low"
                }
            )
        )

    # 计算统计数据
    max_demand = max(r.max_demand or 0 for r in records)
    avg_demand = sum(r.avg_demand or 0 for r in records) / len(records)
    current_declared = records[0].declared_demand or 800.0

    utilization_rate = max_demand / current_declared if current_declared > 0 else 0
    over_declared = current_declared - max_demand

    # 生成建议
    suggested_demand = max_demand * 1.1  # 留10%余量
    suggested_demand = round(suggested_demand / 10) * 10  # 取整到10

    recommendation = {
        "suggested_demand": suggested_demand,
        "reduce_amount": max(0, current_declared - suggested_demand),
        "monthly_saving": max(0, (current_declared - suggested_demand) * 28),  # 假设28元/kW
        "risk_level": "low" if suggested_demand > max_demand * 1.05 else "medium"
    }

    # 获取计量点名称
    meter_point_name = "全站"
    if meter_point_id:
        mp_result = await db.execute(
            select(MeterPoint).where(MeterPoint.id == meter_point_id)
        )
        mp = mp_result.scalar_one_or_none()
        if mp:
            meter_point_name = mp.name

    return ResponseModel(
        code=0,
        message="success",
        data=DemandComparisonData(
            meter_point_id=meter_point_id,
            meter_point_name=meter_point_name,
            current_declared=current_declared,
            max_demand_12m=max_demand,
            avg_demand_12m=round(avg_demand, 1),
            utilization_rate=round(utilization_rate, 3),
            over_declared=round(over_declared, 1),
            recommendation=recommendation
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
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)

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
        # 返回模拟数据
        import random
        base_demand = 650
        data = []
        max_value = 0
        max_month = ""

        for i in range(months):
            month_date = end_date - timedelta(days=(months - i - 1) * 30)
            month_str = month_date.strftime("%Y-%m")
            demand = base_demand + random.randint(-50, 80)
            data.append(DemandCurvePoint(
                month=month_str,
                max_demand=demand,
                declared_demand=800
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
                declared_demand=800
            )
        )

    # 处理真实数据
    data = []
    max_value = 0
    max_month = ""
    declared_demand = records[0].declared_demand if records else 800

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
        # 返回5时段模拟数据
        import random
        base_powers = {
            'deep_valley': 380,  # 深谷时段基础功率最低
            'valley': 450,       # 谷时段基础功率
            'flat': 550,         # 平时段基础功率
            'peak': 680,         # 峰时段基础功率
            'sharp': 750         # 尖峰时段基础功率最高
        }

        for hour in range(24):
            period = period_map.get(hour, 'flat')
            power = base_powers[period] + random.randint(-30, 30)

            hourly_data.append(HourlyLoadPoint(
                hour=hour,
                power=power,
                period=period
            ))

            period_stats[period]['kwh'] += power
            period_stats[period]['hours'] += 1
            period_stats[period]['power_sum'] += power

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
    """
    # 模拟数据（实际应从功率因数历史表获取）
    import random

    end_date = datetime.now()
    data = []
    baseline = 0.90  # 基准功率因数

    for i in range(days):
        day = end_date - timedelta(days=days - i - 1)
        pf = 0.85 + random.uniform(0, 0.12)  # 0.85-0.97之间波动
        data.append({
            "date": day.strftime("%Y-%m-%d"),
            "power_factor": round(pf, 3),
            "status": "good" if pf >= 0.90 else ("warning" if pf >= 0.85 else "bad")
        })

    # 统计
    pf_values = [d["power_factor"] for d in data]
    avg_pf = sum(pf_values) / len(pf_values)
    below_baseline_days = sum(1 for pf in pf_values if pf < baseline)

    # 估算力调电费影响
    monthly_bill = 50000  # 假设月电费5万
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
                "min_power_factor": round(min(pf_values), 3),
                "max_power_factor": round(max(pf_values), 3),
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
