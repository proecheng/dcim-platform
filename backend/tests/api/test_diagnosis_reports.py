"""
误诊反馈报告 API 集成测试
Story 26.2: 误诊反馈报告
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import SystemReport, DiagnosisImprovementRule


@pytest.mark.asyncio
async def test_get_misdiagnosis_report_not_found(
    client: AsyncClient,
    admin_token: str,
):
    """测试查询不存在的报告"""
    response = await client.get(
        "/api/v1/diagnosis/reports/misdiagnosis?period=2025-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_misdiagnosis_report_no_data(
    client: AsyncClient,
    admin_token: str,
):
    """测试生成报告（无数据场景）"""
    response = await client.post(
        "/api/v1/diagnosis/reports/misdiagnosis/generate?period=2026-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # 无数据时应返回 400
    assert response.status_code == 400
    data = response.json()
    assert "报告生成失败" in data["detail"]


@pytest.mark.asyncio
async def test_get_misdiagnosis_report_unauthorized(
    client: AsyncClient,
):
    """测试未授权访问"""
    response = await client.get(
        "/api/v1/diagnosis/reports/misdiagnosis?period=2026-01",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_misdiagnosis_report_not_found(
    client: AsyncClient,
    admin_token: str,
):
    """测试导出不存在的报告"""
    response = await client.get(
        "/api/v1/diagnosis/reports/misdiagnosis/export?period=2025-01&format=pdf",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
