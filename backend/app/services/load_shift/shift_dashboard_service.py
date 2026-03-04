# -*- coding: utf-8 -*-
"""
Shift Dashboard Service
负荷转移仪表盘服务

Dashboard data aggregation and statistics
仪表盘数据聚合和统计
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import logging

from ...models.load_shift import (
    ShiftPlan,
    ShiftExecution,
    ShiftOpportunity,
    ShiftAnalysisRecord,
)
from ...schemas.load_shift import (
    ShiftDashboardOverview,
    ShiftRealtimeData,
    ShiftTrendData,
    ShiftStatisticsSummary,
    ShiftMonthlyReport,
    ShiftYearlyReport,
    ShiftPlanStatus,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)


class ShiftDashboardService:
    """Shift dashboard service - data aggregation for dashboard"""

    @staticmethod
    async def get_overview(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ShiftDashboardOverview:
        """
        Get dashboard overview with key metrics
        获取仪表盘概览及关键指标
        
        Args:
            db: Database session
            start_date: Start date for statistics (default: 30 days ago)
            end_date: End date for statistics (default: today)
            
        Returns:
            ShiftDashboardOverview with aggregated metrics
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).date()
        if not end_date:
            end_date = datetime.now().date()

        logger.info(f"Getting dashboard overview: {start_date} to {end_date}")

        # Query 1: Plan statistics
        plan_query = select(
            func.count(ShiftPlan.id).label("total_plans"),
            func.sum(case((ShiftPlan.status == ShiftPlanStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(case((ShiftPlan.status == ShiftPlanStatus.EXECUTING, 1), else_=0)).label("executing"),
            func.sum(case((ShiftPlan.status == ShiftPlanStatus.PENDING_APPROVAL, 1), else_=0)).label("pending"),
            func.sum(case((ShiftPlan.status == ShiftPlanStatus.FAILED, 1), else_=0)).label("failed"),
        ).where(
            ShiftPlan.shift_date >= start_date,
            ShiftPlan.shift_date <= end_date,
        )
        result = await db.execute(plan_query)
        plan_stats = result.first()

        total_plans = plan_stats.total_plans or 0
        completed_plans = plan_stats.completed or 0
        executing_plans = plan_stats.executing or 0
        pending_plans = plan_stats.pending or 0
        failed_plans = plan_stats.failed or 0

        # Query 2: Execution statistics
        exec_query = select(
            func.sum(ShiftExecution.actual_shift_power).label("total_power"),
            func.sum(ShiftExecution.actual_cost_saving).label("total_cost_saving"),
            func.sum(ShiftExecution.actual_energy_saving).label("total_energy_saving"),
        ).where(
            ShiftExecution.status == ExecutionStatus.COMPLETED,
            ShiftExecution.start_time >= datetime.combine(start_date, datetime.min.time()),
            ShiftExecution.start_time <= datetime.combine(end_date, datetime.max.time()),
        )
        result = await db.execute(exec_query)
        exec_stats = result.first()

        total_shift_power = exec_stats.total_power or 0.0
        total_cost_saving = exec_stats.total_cost_saving or 0.0
        total_energy_saving = exec_stats.total_energy_saving or 0.0

        # Query 3: Opportunity statistics
        opp_query = select(
            func.count(ShiftOpportunity.id).label("total_opportunities"),
            func.sum(ShiftOpportunity.estimated_cost_saving).label("potential_saving"),
        ).where(
            ShiftOpportunity.recommended_date >= start_date,
            ShiftOpportunity.recommended_date <= end_date,
            ShiftOpportunity.status == "pending",
        )
        result = await db.execute(opp_query)
        opp_stats = result.first()

        pending_opportunities = opp_stats.total_opportunities or 0
        potential_cost_saving = opp_stats.potential_saving or 0.0

        # Calculate success rate
        success_rate = (completed_plans / total_plans * 100) if total_plans > 0 else 0.0

        # Calculate average shift power
        avg_shift_power = (total_shift_power / completed_plans) if completed_plans > 0 else 0.0

        # Query 4: Today's plans
        today = datetime.now().date()
        today_query = select(func.count(ShiftPlan.id)).where(
            ShiftPlan.shift_date == today
        )
        result = await db.execute(today_query)
        today_plans = result.scalar() or 0

        # Query 5: Currently executing plan
        executing_query = select(ShiftPlan).where(
            ShiftPlan.status == ShiftPlanStatus.EXECUTING
        ).limit(1)
        result = await db.execute(executing_query)
        current_plan = result.scalar_one_or_none()

        current_plan_id = current_plan.id if current_plan else None
        current_plan_name = current_plan.plan_name if current_plan else None

        overview = ShiftDashboardOverview(
            total_plans=total_plans,
            completed_plans=completed_plans,
            executing_plans=executing_plans,
            pending_plans=pending_plans,
            failed_plans=failed_plans,
            success_rate=round(success_rate, 2),
            total_cost_saving=round(total_cost_saving, 2),
            total_energy_saving=round(total_energy_saving, 2),
            total_shift_power=round(total_shift_power, 2),
            avg_shift_power=round(avg_shift_power, 2),
            pending_opportunities=pending_opportunities,
            potential_cost_saving=round(potential_cost_saving, 2),
            today_plans=today_plans,
            current_plan_id=current_plan_id,
            current_plan_name=current_plan_name,
        )

        logger.info(
            f"Dashboard overview: {total_plans} plans, {completed_plans} completed, "
            f"¥{total_cost_saving:.2f} saved"
        )

        return overview

    @staticmethod
    async def get_realtime_data(db: AsyncSession) -> Optional[ShiftRealtimeData]:
        """
        Get realtime shift data for currently executing plan
        获取当前执行计划的实时数据
        
        Args:
            db: Database session
            
        Returns:
            ShiftRealtimeData if plan is executing, None otherwise
        """
        logger.info("Getting realtime shift data")

        # Query currently executing plan
        plan_query = select(ShiftPlan).where(
            ShiftPlan.status == ShiftPlanStatus.EXECUTING
        ).limit(1)
        result = await db.execute(plan_query)
        plan = result.scalar_one_or_none()

        if not plan:
            logger.info("No plan currently executing")
            return None

        # Query latest execution record
        exec_query = (
            select(ShiftExecution)
            .where(ShiftExecution.plan_id == plan.id)
            .order_by(ShiftExecution.start_time.desc())
            .limit(1)
        )
        result = await db.execute(exec_query)
        execution = result.scalar_one_or_none()

        if not execution:
            logger.warning(f"No execution record found for plan {plan.id}")
            return None

        # Calculate progress
        now = datetime.now()
        start_time = execution.start_time
        end_time = execution.end_time or datetime.combine(
            plan.shift_date,
            plan.end_time
        )

        total_duration = (end_time - start_time).total_seconds()
        elapsed_duration = (now - start_time).total_seconds()
        progress = min((elapsed_duration / total_duration * 100), 100.0) if total_duration > 0 else 0.0

        # Calculate current shift power (from execution record)
        current_shift_power = execution.actual_shift_power or plan.target_shift_power

        # Calculate estimated completion time
        estimated_completion = end_time

        realtime_data = ShiftRealtimeData(
            plan_id=plan.id,
            plan_name=plan.plan_name,
            execution_id=execution.id,
            status=execution.status,
            start_time=start_time,
            estimated_completion=estimated_completion,
            progress=round(progress, 2),
            current_shift_power=round(current_shift_power, 2),
            target_shift_power=plan.target_shift_power,
            cost_saving=round(execution.cost_saving or 0.0, 2),
            energy_saving=round(execution.energy_saving or 0.0, 2),
        )

        logger.info(
            f"Realtime data: plan={plan.id}, progress={progress:.1f}%, "
            f"power={current_shift_power:.2f}kW"
        )

        return realtime_data

    @staticmethod
    async def get_trends(
        db: AsyncSession,
        days: int = 7,
    ) -> List[ShiftTrendData]:
        """
        Get shift trends over time
        获取转移趋势数据
        
        Args:
            db: Database session
            days: Number of days to look back (default: 7)
            
        Returns:
            List of ShiftTrendData with daily statistics
        """
        logger.info(f"Getting shift trends for last {days} days")

        start_date = (datetime.now() - timedelta(days=days)).date()
        end_date = datetime.now().date()

        # Generate date range
        date_range = [start_date + timedelta(days=i) for i in range(days + 1)]

        trends = []
        for current_date in date_range:
            # Query plans for this date
            plan_query = select(
                func.count(ShiftPlan.id).label("total"),
                func.sum(case((ShiftPlan.status == ShiftPlanStatus.COMPLETED, 1), else_=0)).label("completed"),
            ).where(
                ShiftPlan.shift_date == current_date
            )
            result = await db.execute(plan_query)
            plan_stats = result.first()

            total_plans = plan_stats.total or 0
            completed_plans = plan_stats.completed or 0

            # Query executions for this date
            exec_query = select(
                func.sum(ShiftExecution.actual_shift_power).label("total_power"),
                func.sum(ShiftExecution.cost_saving).label("total_cost"),
                func.sum(ShiftExecution.energy_saving).label("total_energy"),
            ).where(
                ShiftExecution.status == ExecutionStatus.COMPLETED,
                func.date(ShiftExecution.start_time) == current_date,
            )
            result = await db.execute(exec_query)
            exec_stats = result.first()

            total_shift_power = exec_stats.total_power or 0.0
            cost_saving = exec_stats.total_cost or 0.0
            energy_saving = exec_stats.total_energy or 0.0

            # Calculate success rate
            success_rate = (completed_plans / total_plans * 100) if total_plans > 0 else 0.0

            trend = ShiftTrendData(
                date=current_date,
                total_plans=total_plans,
                completed_plans=completed_plans,
                success_rate=round(success_rate, 2),
                total_shift_power=round(total_shift_power, 2),
                cost_saving=round(cost_saving, 2),
                energy_saving=round(energy_saving, 2),
            )
            trends.append(trend)

        logger.info(f"Generated {len(trends)} trend data points")
        return trends

    @staticmethod
    async def get_statistics_summary(
        db: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> ShiftStatisticsSummary:
        """
        Get comprehensive statistics summary
        获取综合统计摘要
        
        Args:
            db: Database session
            start_date: Start date
            end_date: End date
            
        Returns:
            ShiftStatisticsSummary with detailed statistics
        """
        logger.info(f"Getting statistics summary: {start_date} to {end_date}")

        # Query plan statistics by period
        period_query = select(
            ShiftPlan.shift_from_period,
            ShiftPlan.shift_to_period,
            func.count(ShiftPlan.id).label("count"),
            func.sum(ShiftPlan.target_shift_power).label("total_power"),
        ).where(
            ShiftPlan.shift_date >= start_date,
            ShiftPlan.shift_date <= end_date,
            ShiftPlan.status == ShiftPlanStatus.COMPLETED,
        ).group_by(
            ShiftPlan.shift_from_period,
            ShiftPlan.shift_to_period,
        )
        result = await db.execute(period_query)
        period_stats = result.all()

        # Build period distribution
        period_distribution = {}
        for row in period_stats:
            key = f"{row.shift_from_period} -> {row.shift_to_period}"
            period_distribution[key] = {
                "count": row.count,
                "total_power": round(row.total_power or 0.0, 2),
            }

        # Query execution statistics
        exec_query = select(
            func.count(ShiftExecution.id).label("total_executions"),
            func.sum(ShiftExecution.actual_shift_power).label("total_power"),
            func.sum(ShiftExecution.cost_saving).label("total_cost"),
            func.sum(ShiftExecution.energy_saving).label("total_energy"),
            func.avg(
                func.extract("epoch", ShiftExecution.end_time - ShiftExecution.start_time) / 3600
            ).label("avg_duration"),
        ).where(
            ShiftExecution.status == ExecutionStatus.COMPLETED,
            func.date(ShiftExecution.start_time) >= start_date,
            func.date(ShiftExecution.start_time) <= end_date,
        )
        result = await db.execute(exec_query)
        exec_stats = result.first()

        total_executions = exec_stats.total_executions or 0
        total_shift_power = exec_stats.total_power or 0.0
        total_cost_saving = exec_stats.total_cost or 0.0
        total_energy_saving = exec_stats.total_energy or 0.0
        avg_duration_hours = exec_stats.avg_duration or 0.0

        # Calculate environmental impact
        # CO2 reduction: 0.785 kg/kWh
        # Coal saving: 0.4 kg/kWh
        co2_reduction = total_energy_saving * 0.785
        coal_saving = total_energy_saving * 0.4

        summary = ShiftStatisticsSummary(
            start_date=start_date,
            end_date=end_date,
            total_executions=total_executions,
            total_shift_power=round(total_shift_power, 2),
            total_cost_saving=round(total_cost_saving, 2),
            total_energy_saving=round(total_energy_saving, 2),
            avg_duration_hours=round(avg_duration_hours, 2),
            co2_reduction_kg=round(co2_reduction, 2),
            coal_saving_kg=round(coal_saving, 2),
            period_distribution=period_distribution,
        )

        logger.info(
            f"Statistics summary: {total_executions} executions, "
            f"¥{total_cost_saving:.2f} saved, {total_energy_saving:.2f}kWh saved"
        )

        return summary

    @staticmethod
    async def get_monthly_report(
        db: AsyncSession,
        year: int,
        month: int,
    ) -> ShiftMonthlyReport:
        """
        Get monthly report
        获取月度报告
        
        Args:
            db: Database session
            year: Year
            month: Month (1-12)
            
        Returns:
            ShiftMonthlyReport with monthly statistics
        """
        logger.info(f"Generating monthly report: {year}-{month:02d}")

        # Calculate date range
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # Get statistics summary
        summary = await ShiftDashboardService.get_statistics_summary(
            db=db,
            start_date=start_date,
            end_date=end_date,
        )

        # Get daily trends
        days_in_month = (end_date - start_date).days + 1
        daily_trends = await ShiftDashboardService.get_trends(
            db=db,
            days=days_in_month,
        )

        report = ShiftMonthlyReport(
            year=year,
            month=month,
            summary=summary,
            daily_trends=daily_trends,
        )

        logger.info(f"Monthly report generated: {year}-{month:02d}")
        return report

    @staticmethod
    async def get_yearly_report(
        db: AsyncSession,
        year: int,
    ) -> ShiftYearlyReport:
        """
        Get yearly report
        获取年度报告
        
        Args:
            db: Database session
            year: Year
            
        Returns:
            ShiftYearlyReport with yearly statistics
        """
        logger.info(f"Generating yearly report: {year}")

        # Calculate date range
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # Get statistics summary
        summary = await ShiftDashboardService.get_statistics_summary(
            db=db,
            start_date=start_date,
            end_date=end_date,
        )

        # Get monthly summaries
        monthly_summaries = []
        for month in range(1, 13):
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            month_summary = await ShiftDashboardService.get_statistics_summary(
                db=db,
                start_date=month_start,
                end_date=month_end,
            )
            monthly_summaries.append(month_summary)

        report = ShiftYearlyReport(
            year=year,
            summary=summary,
            monthly_summaries=monthly_summaries,
        )

        logger.info(f"Yearly report generated: {year}")
        return report
