"""
能效报告数据聚合服务 — Story 6-5
"""

import json
from datetime import datetime, date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import (
    PUEHistory,
    EnergyMonthly,
    EnergyDaily,
    ElectricityPricing,
    EnergyOpportunity,
    ExecutionPlan,
    ExecutionResult,
)


def _period_range(year: int, month: int):
    """返回 (period_start, period_end) datetime 对象"""
    start = datetime(year, month, 1)
    if month < 12:
        end = datetime(year, month + 1, 1)
    else:
        end = datetime(year + 1, 1, 1)
    return start, end


def _date_range(year: int, month: int):
    """返回 (date_start, date_end) date 对象"""
    start = date(year, month, 1)
    if month < 12:
        end = date(year, month + 1, 1)
    else:
        end = date(year + 1, 1, 1)
    return start, end


def _prev_month(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _change_rate(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if previous and previous != 0 and current is not None:
        return round((current - previous) / previous * 100, 2)
    return None


class EnergyReportService:
    @staticmethod
    async def generate_report_data(db: AsyncSession, year: int, month: int) -> dict:
        period_start, period_end = _period_range(year, month)
        date_start, date_end = _date_range(year, month)

        pue_trend = await EnergyReportService._pue_trend(db, year, month, period_start, period_end)
        cost_comparison = await EnergyReportService._cost_comparison(db, year, month, date_start, date_end)
        energy_saving = await EnergyReportService._energy_saving(db, period_start, period_end)
        energy_overview = await EnergyReportService._energy_overview(db, date_start, date_end, year, month)

        return {
            "year": year,
            "month": month,
            "generated_at": datetime.now().isoformat(),
            "pue_trend": pue_trend,
            "cost_comparison": cost_comparison,
            "energy_saving": energy_saving,
            "energy_overview": energy_overview,
        }

    # ------------------------------------------------------------------ PUE
    @staticmethod
    async def _pue_trend(db: AsyncSession, year: int, month: int, period_start: datetime, period_end: datetime) -> dict:
        stmt = (
            select(
                func.date(PUEHistory.record_time).label("day"),
                func.avg(PUEHistory.pue).label("avg_pue"),
                func.min(PUEHistory.pue).label("min_pue"),
                func.max(PUEHistory.pue).label("max_pue"),
            )
            .where(PUEHistory.record_time >= period_start, PUEHistory.record_time < period_end)
            .group_by(func.date(PUEHistory.record_time))
            .order_by(func.date(PUEHistory.record_time))
        )
        rows = (await db.execute(stmt)).all()

        daily_values = [
            {
                "date": str(r.day),
                "avg_pue": round(float(r.avg_pue), 4) if r.avg_pue else 0,
                "min_pue": round(float(r.min_pue), 4) if r.min_pue else 0,
                "max_pue": round(float(r.max_pue), 4) if r.max_pue else 0,
            }
            for r in rows
        ]

        month_avg_pue = (
            round(float(sum(v["avg_pue"] for v in daily_values) / len(daily_values)), 4) if daily_values else 0
        )

        # YoY — same month last year
        ly_start, ly_end = _period_range(year - 1, month)
        yoy_avg = await EnergyReportService._avg_pue(db, ly_start, ly_end)

        # MoM — last month
        pm_y, pm_m = _prev_month(year, month)
        mom_start, mom_end = _period_range(pm_y, pm_m)
        mom_avg = await EnergyReportService._avg_pue(db, mom_start, mom_end)

        return {
            "daily_values": daily_values,
            "month_avg_pue": month_avg_pue,
            "yoy_avg": yoy_avg,
            "mom_avg": mom_avg,
            "yoy_change": _change_rate(month_avg_pue, yoy_avg),
            "mom_change": _change_rate(month_avg_pue, mom_avg),
        }

    @staticmethod
    async def _avg_pue(db: AsyncSession, start: datetime, end: datetime) -> Optional[float]:
        stmt = select(func.avg(PUEHistory.pue)).where(PUEHistory.record_time >= start, PUEHistory.record_time < end)
        val = (await db.execute(stmt)).scalar()
        return round(float(val), 4) if val else None

    # ------------------------------------------------------------------ COST
    @staticmethod
    async def _cost_comparison(db: AsyncSession, year: int, month: int, date_start: date, date_end: date) -> dict:
        current = await EnergyReportService._cost_from_monthly(db, year, month)
        if current["total_energy"] == 0:
            current = await EnergyReportService._cost_from_daily(db, date_start, date_end)

        # last month
        pm_y, pm_m = _prev_month(year, month)
        pm_ds, pm_de = _date_range(pm_y, pm_m)
        last_month = await EnergyReportService._cost_from_monthly(db, pm_y, pm_m)
        if last_month["total_energy"] == 0:
            last_month = await EnergyReportService._cost_from_daily(db, pm_ds, pm_de)

        # last year same month
        ly_ds, ly_de = _date_range(year - 1, month)
        last_year = await EnergyReportService._cost_from_monthly(db, year - 1, month)
        if last_year["total_energy"] == 0:
            last_year = await EnergyReportService._cost_from_daily(db, ly_ds, ly_de)

        return {
            "current_month": current,
            "last_month": last_month,
            "last_year_month": last_year,
            "yoy_change_rate": _change_rate(current["total_cost"], last_year["total_cost"]),
            "mom_change_rate": _change_rate(current["total_cost"], last_month["total_cost"]),
        }

    @staticmethod
    async def _cost_from_monthly(db: AsyncSession, year: int, month: int) -> dict:
        stmt = select(
            func.sum(EnergyMonthly.total_energy),
            func.sum(EnergyMonthly.energy_cost),
            func.sum(EnergyMonthly.peak_energy),
            func.sum(EnergyMonthly.peak_cost),
            func.sum(EnergyMonthly.normal_energy),
            func.sum(EnergyMonthly.normal_cost),
            func.sum(EnergyMonthly.valley_energy),
            func.sum(EnergyMonthly.valley_cost),
        ).where(EnergyMonthly.stat_year == year, EnergyMonthly.stat_month == month)
        row = (await db.execute(stmt)).one()
        return EnergyReportService._cost_dict(row)

    @staticmethod
    async def _cost_from_daily(db: AsyncSession, date_start: date, date_end: date) -> dict:
        stmt = select(
            func.sum(EnergyDaily.total_energy),
            func.sum(EnergyDaily.energy_cost),
            func.sum(EnergyDaily.peak_energy),
            func.sum(EnergyDaily.normal_energy),
            func.sum(EnergyDaily.valley_energy),
        ).where(EnergyDaily.stat_date >= date_start, EnergyDaily.stat_date < date_end)
        row = (await db.execute(stmt)).one()

        total_energy = float(row[0] or 0)
        total_cost = float(row[1] or 0)
        peak_energy = float(row[2] or 0)
        normal_energy = float(row[3] or 0)
        valley_energy = float(row[4] or 0)

        # Calculate per-period costs from pricing
        pricing_map = await EnergyReportService._get_pricing_map(db)
        peak_price = pricing_map.get("peak", 0)
        flat_price = pricing_map.get("flat", 0)
        valley_price = pricing_map.get("valley", 0)

        peak_cost = round(peak_energy * peak_price, 2)
        normal_cost = round(normal_energy * flat_price, 2)
        valley_cost = round(valley_energy * valley_price, 2)

        # If we had energy_cost from daily, use it; otherwise sum calculated
        if total_cost == 0 and total_energy > 0:
            total_cost = round(peak_cost + normal_cost + valley_cost, 2)

        return {
            "total_energy": round(total_energy, 2),
            "total_cost": round(total_cost, 2),
            "peak_energy": round(peak_energy, 2),
            "peak_cost": peak_cost,
            "normal_energy": round(normal_energy, 2),
            "normal_cost": normal_cost,
            "valley_energy": round(valley_energy, 2),
            "valley_cost": valley_cost,
        }

    @staticmethod
    async def _get_pricing_map(db: AsyncSession) -> dict:
        """Return {period_type: price} for enabled pricing records."""
        stmt = select(ElectricityPricing.period_type, ElectricityPricing.price).where(
            ElectricityPricing.is_enabled == True  # noqa: E712
        )
        rows = (await db.execute(stmt)).all()
        return {r.period_type: float(r.price) for r in rows}

    @staticmethod
    def _cost_dict(row) -> dict:
        return {
            "total_energy": round(float(row[0] or 0), 2),
            "total_cost": round(float(row[1] or 0), 2),
            "peak_energy": round(float(row[2] or 0), 2),
            "peak_cost": round(float(row[3] or 0), 2),
            "normal_energy": round(float(row[4] or 0), 2),
            "normal_cost": round(float(row[5] or 0), 2),
            "valley_energy": round(float(row[6] or 0), 2),
            "valley_cost": round(float(row[7] or 0), 2),
        }

    # ------------------------------------------------------------------ SAVING
    @staticmethod
    async def _energy_saving(db: AsyncSession, period_start: datetime, period_end: datetime) -> dict:
        # Count all opportunities in period
        count_stmt = select(func.count(EnergyOpportunity.id)).where(
            EnergyOpportunity.status.in_(["completed", "executing"]),
            EnergyOpportunity.created_at >= period_start,
            EnergyOpportunity.created_at < period_end,
        )
        opportunities_count = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(
                EnergyOpportunity.id,
                EnergyOpportunity.title,
                EnergyOpportunity.category,
                ExecutionResult.energy_before,
                ExecutionResult.energy_after,
                ExecutionResult.actual_saving,
                ExecutionResult.achievement_rate,
            )
            .join(ExecutionPlan, ExecutionPlan.opportunity_id == EnergyOpportunity.id)
            .join(ExecutionResult, ExecutionResult.plan_id == ExecutionPlan.id)
            .where(
                EnergyOpportunity.status.in_(["completed", "executing"]),
                EnergyOpportunity.created_at >= period_start,
                EnergyOpportunity.created_at < period_end,
            )
        )
        rows = (await db.execute(stmt)).all()

        details = []
        total_saving_kwh = 0.0
        total_saving_cost = 0.0

        for r in rows:
            saving_kwh = EnergyReportService._calc_saving_kwh(r.energy_before, r.energy_after)
            saving_cost = float(r.actual_saving or 0)
            total_saving_kwh += saving_kwh
            total_saving_cost += saving_cost
            details.append(
                {
                    "title": r.title,
                    "category": r.category,
                    "saving_kwh": round(saving_kwh, 2),
                    "saving_cost": round(saving_cost, 2),
                    "achievement_rate": float(r.achievement_rate) if r.achievement_rate else None,
                }
            )

        avg_rate = 0.0
        rated = [d["achievement_rate"] for d in details if d["achievement_rate"] is not None]
        if rated:
            avg_rate = round(sum(rated) / len(rated), 2)

        return {
            "details": details,
            "total_saving_kwh": round(total_saving_kwh, 2),
            "total_saving_cost": round(total_saving_cost, 2),
            "opportunities_count": opportunities_count,
            "executed_count": len(rows),
            "avg_achievement_rate": avg_rate,
        }

    @staticmethod
    def _calc_saving_kwh(energy_before, energy_after) -> float:
        total_before = EnergyReportService._sum_energy_json(energy_before)
        total_after = EnergyReportService._sum_energy_json(energy_after)
        return total_before - total_after

    @staticmethod
    def _sum_energy_json(data) -> float:
        if data is None:
            return 0.0
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return 0.0
        if isinstance(data, list):
            return sum(item.get("energy", 0) for item in data if isinstance(item, dict))
        return 0.0

    # ------------------------------------------------------------------ OVERVIEW
    @staticmethod
    async def _energy_overview(db: AsyncSession, date_start: date, date_end: date, year: int, month: int) -> dict:
        stmt = (
            select(
                EnergyDaily.stat_date,
                func.sum(EnergyDaily.total_energy).label("total_energy"),
            )
            .where(EnergyDaily.stat_date >= date_start, EnergyDaily.stat_date < date_end)
            .group_by(EnergyDaily.stat_date)
            .order_by(EnergyDaily.stat_date)
        )
        rows = (await db.execute(stmt)).all()

        daily_energy = [
            {
                "date": str(r.stat_date),
                "total_energy": round(float(r.total_energy or 0), 2),
            }
            for r in rows
        ]

        total = round(sum(d["total_energy"] for d in daily_energy), 2)

        return {
            "daily_energy": daily_energy,
            "total_energy": total,
        }
