from datetime import date, datetime, time

import pytest

from app.models.load_shift import ShiftExecution, ShiftPlan
from app.services.load_shift.shift_report_service import ShiftReportService


@pytest.mark.asyncio
async def test_empty_report_does_not_claim_success(async_db):
    report = await ShiftReportService.generate_monthly_report(async_db, 2026, 8)

    assert report["execution_count"] == 0
    assert report["success_rate"] is None
    assert report["data_sufficient"] is False
    assert "暂无" in report["warning"]
    assert report["details"] == []


@pytest.mark.asyncio
async def test_report_uses_real_closed_loop_records(async_db, admin_user):
    user, _ = admin_user
    plan = ShiftPlan(
        plan_code="REPORT-INTEGRITY-001",
        plan_name="收益报表闭环测试",
        shift_from_period="peak",
        shift_to_period="valley",
        shift_date=date(2026, 8, 16),
        start_time=time(10, 0),
        end_time=time(11, 0),
        target_shift_power=10,
        status="completed",
        created_by=user.id,
    )
    async_db.add(plan)
    await async_db.flush()
    async_db.add_all(
        [
            ShiftExecution(
                plan_id=plan.id,
                execution_code="REPORT-EXEC-COMPLETED",
                start_time=datetime(2026, 8, 16, 10, 0),
                end_time=datetime(2026, 8, 16, 11, 0),
                status="completed",
                actual_shift_power=8,
                actual_cost_saving=12.5,
                actual_energy_saving=9.5,
            ),
            ShiftExecution(
                plan_id=plan.id,
                execution_code="REPORT-EXEC-PENDING",
                start_time=datetime(2026, 8, 16, 12, 0),
                status="pending",
            ),
        ]
    )
    await async_db.flush()

    report = await ShiftReportService.generate_monthly_report(async_db, 2026, 8)

    assert report["execution_count"] == 2
    assert report["success_rate"] == 100
    assert report["total_shift_power"] == 8
    assert report["total_cost_saving"] == 12.5
    assert report["period_stats"]["peak_to_valley"] == 2
    assert "1 条执行尚未" in report["warning"]

    excel = ShiftReportService.export_report_excel(report)
    pdf = ShiftReportService.export_report_pdf(report)
    assert excel.read(2) == b"PK"
    assert pdf.read(4) == b"%PDF"
