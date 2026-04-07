"""
Shift Report Service
负荷转移报表服务 - 生成月度/年度报表并支持导出
"""

from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.load_shift import ShiftExecution


class ShiftReportService:
    """负荷转移报表服务"""

    @staticmethod
    async def generate_monthly_report(db: AsyncSession, year: int, month: int) -> Dict[str, Any]:
        """
        生成月度报表

        Args:
            db: 数据库会话
            year: 年份
            month: 月份

        Returns:
            月度报表数据
        """
        # 查询该月的所有执行记录
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        result = await db.execute(
            select(ShiftExecution).where(
                and_(ShiftExecution.start_time >= start_date, ShiftExecution.start_time < end_date)
            )
        )
        executions = result.scalars().all()

        # 统计数据
        total_executions = len(executions)
        success_count = sum(1 for e in executions if e.status == "completed")
        failed_count = sum(1 for e in executions if e.status == "failed")

        total_cost_saving = sum(float(e.actual_cost_saving) if e.actual_cost_saving else 0 for e in executions)
        total_energy_saving = sum(float(e.actual_energy_saving) if e.actual_energy_saving else 0 for e in executions)
        total_shift_power = sum(float(e.actual_shift_power) if e.actual_shift_power else 0 for e in executions)

        success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0

        # 按日统计
        daily_stats = {}
        for execution in executions:
            date_key = execution.start_time.strftime("%Y-%m-%d")
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    "date": date_key,
                    "execution_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "total_shift_power": 0.0,
                    "cost_saving": 0.0,
                    "energy_saving": 0.0,
                }

            daily_stats[date_key]["execution_count"] += 1
            if execution.status == "completed":
                daily_stats[date_key]["success_count"] += 1
            elif execution.status == "failed":
                daily_stats[date_key]["failed_count"] += 1

            daily_stats[date_key]["total_shift_power"] += float(execution.actual_shift_power or 0)
            daily_stats[date_key]["cost_saving"] += float(execution.actual_cost_saving or 0)
            daily_stats[date_key]["energy_saving"] += float(execution.actual_energy_saving or 0)

        # 计算每日成功率
        details = []
        for date_key in sorted(daily_stats.keys()):
            stat = daily_stats[date_key]
            stat["success_rate"] = (
                stat["success_count"] / stat["execution_count"] * 100 if stat["execution_count"] > 0 else 0
            )
            details.append(stat)

        # 趋势数据
        trend_data = [
            {"date": stat["date"], "cost_saving": stat["cost_saving"], "energy_saving": stat["energy_saving"]}
            for stat in details
        ]

        # 执行统计
        execution_stats = {"success": success_count, "failed": failed_count}

        # 时段统计（模拟数据，实际应从 shift_from_period 和 shift_to_period 统计）
        period_stats = {
            "peak_to_valley": int(total_executions * 0.6),
            "valley_to_peak": int(total_executions * 0.3),
            "peak_to_flat": int(total_executions * 0.1),
        }

        return {
            "report_type": "monthly",
            "year": year,
            "month": month,
            "total_cost_saving": total_cost_saving,
            "total_energy_saving": total_energy_saving,
            "total_shift_power": total_shift_power,
            "execution_count": total_executions,
            "success_rate": success_rate,
            "details": details,
            "trend_data": trend_data,
            "execution_stats": execution_stats,
            "period_stats": period_stats,
        }

    @staticmethod
    async def generate_yearly_report(db: AsyncSession, year: int) -> Dict[str, Any]:
        """
        生成年度报表

        Args:
            db: 数据库会话
            year: 年份

        Returns:
            年度报表数据
        """
        # 查询该年的所有执行记录
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)

        result = await db.execute(
            select(ShiftExecution).where(
                and_(ShiftExecution.start_time >= start_date, ShiftExecution.start_time < end_date)
            )
        )
        executions = result.scalars().all()

        # 统计数据
        total_executions = len(executions)
        success_count = sum(1 for e in executions if e.status == "completed")
        failed_count = sum(1 for e in executions if e.status == "failed")

        total_cost_saving = sum(float(e.actual_cost_saving) if e.actual_cost_saving else 0 for e in executions)
        total_energy_saving = sum(float(e.actual_energy_saving) if e.actual_energy_saving else 0 for e in executions)
        total_shift_power = sum(float(e.actual_shift_power) if e.actual_shift_power else 0 for e in executions)

        success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0

        # 按月统计
        monthly_stats = {}
        for execution in executions:
            month_key = execution.start_time.strftime("%Y-%m")
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {
                    "date": month_key,
                    "execution_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "total_shift_power": 0.0,
                    "cost_saving": 0.0,
                    "energy_saving": 0.0,
                }

            monthly_stats[month_key]["execution_count"] += 1
            if execution.status == "completed":
                monthly_stats[month_key]["success_count"] += 1
            elif execution.status == "failed":
                monthly_stats[month_key]["failed_count"] += 1

            monthly_stats[month_key]["total_shift_power"] += float(execution.actual_shift_power or 0)
            monthly_stats[month_key]["cost_saving"] += float(execution.actual_cost_saving or 0)
            monthly_stats[month_key]["energy_saving"] += float(execution.actual_energy_saving or 0)

        # 计算每月成功率
        details = []
        for month_key in sorted(monthly_stats.keys()):
            stat = monthly_stats[month_key]
            stat["success_rate"] = (
                stat["success_count"] / stat["execution_count"] * 100 if stat["execution_count"] > 0 else 0
            )
            details.append(stat)

        # 趋势数据
        trend_data = [
            {"date": stat["date"], "cost_saving": stat["cost_saving"], "energy_saving": stat["energy_saving"]}
            for stat in details
        ]

        # 执行统计
        execution_stats = {"success": success_count, "failed": failed_count}

        # 时段统计
        period_stats = {
            "peak_to_valley": int(total_executions * 0.6),
            "valley_to_peak": int(total_executions * 0.3),
            "peak_to_flat": int(total_executions * 0.1),
        }

        return {
            "report_type": "yearly",
            "year": year,
            "total_cost_saving": total_cost_saving,
            "total_energy_saving": total_energy_saving,
            "total_shift_power": total_shift_power,
            "execution_count": total_executions,
            "success_rate": success_rate,
            "details": details,
            "trend_data": trend_data,
            "execution_stats": execution_stats,
            "period_stats": period_stats,
        }

    @staticmethod
    async def export_report_excel(report_data: Dict[str, Any]) -> str:
        """
        导出 Excel 格式报表

        Args:
            report_data: 报表数据

        Returns:
            文件路径
        """
        # TODO: 使用 openpyxl 或 xlsxwriter 生成 Excel 文件
        # 这里返回模拟路径
        filename = f"shift_report_{report_data['report_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        return f"/exports/{filename}"

    @staticmethod
    async def export_report_pdf(report_data: Dict[str, Any]) -> str:
        """
        导出 PDF 格式报表

        Args:
            report_data: 报表数据

        Returns:
            文件路径
        """
        # TODO: 使用 reportlab 或 weasyprint 生成 PDF 文件
        # 这里返回模拟路径
        filename = f"shift_report_{report_data['report_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return f"/exports/{filename}"
