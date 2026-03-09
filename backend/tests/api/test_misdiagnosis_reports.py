"""
API 测试: 误判分析报告
Story 26.6 Task 7
"""

import pytest
from datetime import datetime, timezone, date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportRecord
from app.models.user import User



@pytest.fixture
async def sample_report(async_db: AsyncSession):
    """创建示例报告"""
    report = ReportRecord(
        report_name="2026年2月误判分析报告",
        report_type="diagnosis_monthly",
        start_time=datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
        status="completed",
        file_path="/tmp/test-report.md",
        file_size=1024,
        report_data='{"summary": {"total_diagnosis_count": 1000}}',
        generated_by=1,
    )
    async_db.add(report)
    await async_db.commit()
    await async_db.refresh(report)
    return report


class TestListMisdiagnosisReports:
    """测试查询历史报告列表"""

    @pytest.mark.asyncio
    async def test_list_reports_success(self, client: AsyncClient, admin_token: str, sample_report):
        """测试成功查询报告列表"""
        response = await client.get(
            "/api/v1/diagnosis/misdiagnosis-reports",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert len(data["items"]) > 0

    @pytest.mark.asyncio
    async def test_list_reports_with_pagination(self, client: AsyncClient, admin_token: str, sample_report):
        """测试分页查询"""
        response = await client.get(
            "/api/v1/diagnosis/misdiagnosis-reports?page=1&page_size=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_reports_unauthorized(self, client: AsyncClient):
        """测试未授权访问"""
        response = await client.get("/api/v1/diagnosis/misdiagnosis-reports")

        assert response.status_code == 401


class TestGetMisdiagnosisReport:
    """测试查询单个报告详情"""

    @pytest.mark.asyncio
    async def test_get_report_success(self, client: AsyncClient, admin_token: str, sample_report):
        """测试成功查询报告详情"""
        response = await client.get(
            f"/api/v1/diagnosis/misdiagnosis-reports/{sample_report.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_report.id
        assert data["report_name"] == sample_report.report_name
        assert "report_data" in data

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, client: AsyncClient, admin_token: str):
        """测试报告不存在"""
        response = await client.get(
            "/api/v1/diagnosis/misdiagnosis-reports/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404


class TestGenerateMisdiagnosisReport:
    """测试手动触发报告生成"""

    @pytest.mark.asyncio
    async def test_generate_report_success(self, client: AsyncClient, admin_token: str, async_db: AsyncSession):
        """测试成功生成报告"""
        response = await client.post(
            "/api/v1/diagnosis/misdiagnosis-reports/generate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31"
            }
        )

        # 可能返回 202 (成功) 或 409 (已存在)
        assert response.status_code in [202, 409]

    @pytest.mark.asyncio
    async def test_generate_report_invalid_date_range(self, client: AsyncClient, admin_token: str):
        """测试无效的日期范围"""
        response = await client.post(
            "/api/v1/diagnosis/misdiagnosis-reports/generate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "start_date": "2026-01-15",  # 不是月初
                "end_date": "2026-01-31"
            }
        )

        assert response.status_code == 422  # Validation error


# TODO: 添加更多测试用例
# - 测试下载 Markdown 文件
# - 测试权限控制（非管理员访问）
# - 测试时间范围过滤
