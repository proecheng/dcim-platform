"""
反事实分析集成测试
Story 26.1: 反事实分析
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.diagnosis import (
    DiagnosisSession,
    DiagnosisResult,
    CounterfactualAnalysis,
)
from app.services.diagnosis.counterfactual_service import analyze_counterfactual


@pytest.mark.asyncio
async def test_counterfactual_analysis_workflow_3_evidences(
    client: AsyncClient,
    async_db: AsyncSession,
    admin_token: str,
):
    """
    集成测试: 完整工作流 - 3个证据场景

    验证:
    1. 创建诊断会话和结果
    2. 执行反事实分析
    3. 通过 API 查询分析结果
    4. 验证 Top 3 证据影响分析
    """
    admin_token_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. 创建诊断会话
    from datetime import datetime
    now = datetime.now()
    session = DiagnosisSession(
        trigger_alarm_id=1001,
        device_id=101,
        engine_level="L2",
        status="success",
        max_confidence=0.85,
        start_time=now,
        end_time=now,
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 2. 创建诊断结果（包含3个证据）
    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=1001,
        alarm_no="ALM-2026-001",
        device_type="UPS",
        zone="A区",
        root_cause="UPS电池老化",
        confidence=0.85,
        evidence=[
            {
                "node_id": 101,
                "evidence_type": "sensor",
                "probability": 0.9,
                "sensor_weight": 0.95,
                "path_length": 1,
            },
            {
                "node_id": 102,
                "evidence_type": "threshold",
                "probability": 0.8,
                "sensor_weight": 0.85,
                "path_length": 2,
            },
            {
                "node_id": 103,
                "evidence_type": "history",
                "probability": 0.7,
                "sensor_weight": 0.75,
                "path_length": 3,
            },
        ],
        reasoning_path=[
            {"node_id": 101, "description": "电池电压异常", "dependencies": []},
            {"node_id": 102, "description": "充电时间延长", "dependencies": [101]},
            {"node_id": 103, "description": "历史故障记录", "dependencies": [101, 102]},
        ],
        fault_tree_version="v1.0.0",
    )
    async_db.add(result)
    await async_db.commit()
    await async_db.refresh(result)

    # 3. 执行反事实分析
    analysis = await analyze_counterfactual(session.id, top_n=3, db=async_db)

    assert analysis is not None
    assert analysis.session_id == session.id
    assert analysis.original_root_cause == "UPS电池老化"
    assert analysis.original_confidence == 0.85
    assert len(analysis.top_evidences) == 3
    assert len(analysis.analysis_results) == 3

    # 4. 通过 API 查询分析结果
    response = await client.get(
        f"/api/v1/diagnosis/counterfactual/{session.id}",
        headers=admin_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.id
    assert data["original_confidence"] == 0.85
    assert len(data["top_evidences"]) == 3
    assert len(data["analysis_results"]) == 3

    # 5. 验证 Top 3 证据影响
    for i, scenario in enumerate(data["analysis_results"]):
        assert "removed_evidence_id" in scenario
        assert "new_confidence" in scenario
        assert "confidence_change" in scenario
        assert "conclusion_changed" in scenario
        assert scenario["removed_evidence_id"] in [101, 102, 103]


@pytest.mark.asyncio
async def test_counterfactual_analysis_not_found(
    client: AsyncClient,
    admin_token: str,
):
    """
    集成测试: 分析不存在场景

    验证:
    1. 查询不存在的 session_id
    2. 返回 404 错误
    """
    admin_token_headers = {"Authorization": f"Bearer {admin_token}"}

    response = await client.get(
        "/api/v1/diagnosis/counterfactual/99999",
        headers=admin_token_headers,
    )

    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]

