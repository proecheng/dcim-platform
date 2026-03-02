"""
能耗数据聚合服务
从 PointHistory 聚合到 EnergyHourly / EnergyDaily / EnergyMonthly
由定时任务定期调用
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly, ElectricityPricing
from ..models.history import PointHistory

logger = logging.getLogger(__name__)


def _get_period_type_for_hour(hour: int, pricing_records) -> str:
    """
    根据小时和电价配置判断时段类型
    返回: 'peak' / 'normal' / 'valley'
    """
    time_str = f"{hour:02d}:00"
    for p in pricing_records:
        start = p.start_time
        end = p.end_time
        
        # 将 00:00 视为 24:00 以正确处理跨日时段
        if end == "00:00":
            end = "24:00"
        
        # 处理跨日时段（如 22:00 - 24:00）
        if start < end:
            if start <= time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
        else:
            # 跨日时段（如 23:00 - 07:00，但这种情况现在不应该出现）
            if time_str >= start or time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
    return "normal"


async def aggregate_hourly(db: AsyncSession, target_time: Optional[datetime] = None):
    """
    小时聚合：从 PointHistory 聚合到 EnergyHourly
    target_time: 要聚合的整点时间，默认为上一个整点
    """
    if target_time is None:
        now = datetime.now()
        target_time = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    hour_start = target_time
    hour_end = hour_start + timedelta(hours=1)

    # 获取所有有 power_point_id 的设备
    result = await db.execute(
        select(PowerDevice).where(PowerDevice.is_enabled == True, PowerDevice.power_point_id != None)
    )
    devices = result.scalars().all()

    count = 0
    for device in devices:
        try:
            # 幂等检查
            existing = await db.execute(
                select(EnergyHourly).where(EnergyHourly.device_id == device.id, EnergyHourly.stat_time == hour_start)
            )
            if existing.scalar_one_or_none():
                continue

            # 查询该设备功率点位在这个小时内的历史数据
            ph_result = await db.execute(
                select(
                    func.avg(PointHistory.value),
                    func.max(PointHistory.value),
                    func.min(PointHistory.value),
                    func.count(PointHistory.id),
                ).where(
                    PointHistory.point_id == device.power_point_id,
                    PointHistory.recorded_at >= hour_start,
                    PointHistory.recorded_at < hour_end,
                    PointHistory.quality == 0,  # 仅好数据
                )
            )
            row = ph_result.first()
            if row is None or row[0] is None or row[3] == 0:
                continue

            avg_power = row[0]
            max_power = row[1]
            min_power = row[2]
            # kW × 1h = kWh
            total_energy = avg_power * 1.0

            hourly = EnergyHourly(
                device_id=device.id,
                stat_time=hour_start,
                total_energy=round(total_energy, 4),
                avg_power=round(avg_power, 4),
                max_power=round(max_power, 4),
                min_power=round(min_power, 4),
            )
            db.add(hourly)
            await db.commit()
            count += 1
        except Exception as e:
            logger.warning("小时聚合失败 device_id=%s: %s", device.id, e)
            await db.rollback()
            continue

    if count > 0:
        logger.info("小时聚合完成: %s, 写入 %d 条", hour_start, count)


async def aggregate_daily(db: AsyncSession, target_date: Optional[date] = None):
    """
    日聚合：从 EnergyHourly + ElectricityPricing 聚合到 EnergyDaily
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    # 获取电价配置（用于五时段分类：尖峰/高峰/平段/低谷/深谷）
    today = date.today()
    pricing_result = await db.execute(
        select(ElectricityPricing)
        .where(ElectricityPricing.is_enabled == True, ElectricityPricing.effective_date <= today)
        .order_by(ElectricityPricing.start_time)
    )
    pricing_records = pricing_result.scalars().all()

    # 获取所有有 power_point_id 的设备
    result = await db.execute(
        select(PowerDevice).where(PowerDevice.is_enabled == True, PowerDevice.power_point_id != None)
    )
    devices = result.scalars().all()

    count = 0
    for device in devices:
        try:
            # 幂等检查
            existing = await db.execute(
                select(EnergyDaily).where(EnergyDaily.device_id == device.id, EnergyDaily.stat_date == target_date)
            )
            if existing.scalar_one_or_none():
                continue

            # 查询该设备当天的小时数据
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            hourly_result = await db.execute(
                select(EnergyHourly)
                .where(
                    EnergyHourly.device_id == device.id,
                    EnergyHourly.stat_time >= day_start,
                    EnergyHourly.stat_time < day_end,
                )
                .order_by(EnergyHourly.stat_time)
            )
            hourly_records = hourly_result.scalars().all()

            if not hourly_records:
                continue

            total_energy = 0.0
            peak_energy = 0.0
            normal_energy = 0.0
            valley_energy = 0.0
            max_power = 0.0
            max_power_time = None
            power_sum = 0.0

            for h in hourly_records:
                energy = h.total_energy or 0
                total_energy += energy
                power_sum += h.avg_power or 0

                if (h.max_power or 0) > max_power:
                    max_power = h.max_power or 0
                    max_power_time = h.stat_time

                # 根据时段分类
                hour = h.stat_time.hour
                period = _get_period_type_for_hour(hour, pricing_records)
                if period == "peak":
                    peak_energy += energy
                elif period == "valley":
                    valley_energy += energy
                else:
                    normal_energy += energy

            avg_power = power_sum / len(hourly_records) if hourly_records else 0

            # 计算日电费（使用当前电价）
            peak_price = 1.2
            normal_price = 0.8
            valley_price = 0.4
            for p in pricing_records:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    peak_price = p.price
                elif pt == "flat":
                    normal_price = p.price
                elif pt in ("valley", "deep_valley"):
                    valley_price = p.price
            energy_cost = round(
                peak_energy * peak_price + normal_energy * normal_price + valley_energy * valley_price, 2
            )

            daily = EnergyDaily(
                device_id=device.id,
                stat_date=target_date,
                total_energy=round(total_energy, 4),
                peak_energy=round(peak_energy, 4),
                normal_energy=round(normal_energy, 4),
                valley_energy=round(valley_energy, 4),
                max_power=round(max_power, 4),
                avg_power=round(avg_power, 4),
                max_power_time=max_power_time,
                energy_cost=energy_cost,
            )
            db.add(daily)
            await db.commit()
            count += 1
        except Exception as e:
            logger.warning("日聚合失败 device_id=%s: %s", device.id, e)
            await db.rollback()
            continue

    if count > 0:
        logger.info("日聚合完成: %s, 写入 %d 条", target_date, count)


async def aggregate_monthly(db: AsyncSession, target_year: Optional[int] = None, target_month: Optional[int] = None):
    """
    月聚合：从 EnergyDaily 聚合到 EnergyMonthly
    """
    if target_year is None or target_month is None:
        last_month = date.today().replace(day=1) - timedelta(days=1)
        target_year = last_month.year
        target_month = last_month.month

    # 获取电价
    from ..services.pricing_service import PricingService

    pricing_service = PricingService(db)
    prices = await pricing_service.get_all_prices()
    peak_price = prices.get("peak_price", 0.0)
    normal_price = prices.get("normal_price", 0.0)
    valley_price = prices.get("valley_price", 0.0)

    # 获取所有有 power_point_id 的设备
    result = await db.execute(
        select(PowerDevice).where(PowerDevice.is_enabled == True, PowerDevice.power_point_id != None)
    )
    devices = result.scalars().all()

    month_start = date(target_year, target_month, 1)
    if target_month == 12:
        month_end = date(target_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(target_year, target_month + 1, 1) - timedelta(days=1)

    count = 0
    for device in devices:
        try:
            # 幂等检查
            existing = await db.execute(
                select(EnergyMonthly).where(
                    EnergyMonthly.device_id == device.id,
                    EnergyMonthly.stat_year == target_year,
                    EnergyMonthly.stat_month == target_month,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # 查询该设备当月的日数据
            daily_result = await db.execute(
                select(
                    func.sum(EnergyDaily.total_energy),
                    func.sum(EnergyDaily.peak_energy),
                    func.sum(EnergyDaily.normal_energy),
                    func.sum(EnergyDaily.valley_energy),
                    func.max(EnergyDaily.max_power),
                    func.avg(EnergyDaily.avg_power),
                    func.avg(EnergyDaily.pue),
                ).where(
                    EnergyDaily.device_id == device.id,
                    EnergyDaily.stat_date >= month_start,
                    EnergyDaily.stat_date <= month_end,
                )
            )
            row = daily_result.first()
            if row is None or row[0] is None:
                continue

            total = row[0] or 0
            peak = row[1] or 0
            normal = row[2] or 0
            valley = row[3] or 0

            peak_cost = round(peak * peak_price, 2)
            normal_cost = round(normal * normal_price, 2)
            valley_cost = round(valley * valley_price, 2)
            energy_cost = round(peak_cost + normal_cost + valley_cost, 2)

            # 查找最大功率日期
            max_power_row = await db.execute(
                select(EnergyDaily.stat_date)
                .where(
                    EnergyDaily.device_id == device.id,
                    EnergyDaily.stat_date >= month_start,
                    EnergyDaily.stat_date <= month_end,
                )
                .order_by(EnergyDaily.max_power.desc())
                .limit(1)
            )
            max_power_date = max_power_row.scalar_one_or_none()

            monthly = EnergyMonthly(
                device_id=device.id,
                stat_year=target_year,
                stat_month=target_month,
                total_energy=round(total, 4),
                peak_energy=round(peak, 4),
                normal_energy=round(normal, 4),
                valley_energy=round(valley, 4),
                max_power=round(row[4] or 0, 4),
                avg_power=round(row[5] or 0, 4),
                max_power_date=max_power_date,
                energy_cost=energy_cost,
                peak_cost=peak_cost,
                normal_cost=normal_cost,
                valley_cost=valley_cost,
                avg_pue=round(row[6] or 0, 2) if row[6] else None,
            )
            db.add(monthly)
            await db.commit()
            count += 1
        except Exception as e:
            logger.warning("月聚合失败 device_id=%s: %s", device.id, e)
            await db.rollback()
            continue

    if count > 0:
        logger.info("月聚合完成: %d-%02d, 写入 %d 条", target_year, target_month, count)
