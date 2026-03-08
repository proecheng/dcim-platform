"""
误诊反馈报告服务测试
Story 26.2: 误诊反馈报告
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import SystemReport, DiagnosisImprovementRule
from app.services.diagnosis.misdiagnosis_report_service import MisdiagnosisReportService


@pytest.mark.asyncio
async def test_generate_monthly_report_no_data(async_db: AsyncSession):
    """测试无数据场景"""
    period = "2026-01"

    report = await MisdiagnosisReportService.generate_monthly_report(period, async_db)

    # 无诊断数据时应返回 None
    assert report is None


@pytest.mark.asyncio
async def test_improvement_rule_query(async_db: AsyncSession):
    """测试改进建议规则查询"""
    from sqlalchemy import select

    # 先插入测试数据
    rule1 = DiagnosisImprovementRule(
        rule_type="false_positive",
        node_id="root_ups_battery",
        suggestion_template="建议增加电池SOH算法精度",
        priority=10,
        is_active=True,
    )
    rule2 = DiagnosisImprovementRule(
        rule_type="false_positive",
        node_id="*",
        suggestion_template="建议人工审查该节点的故障树逻辑和先验概率设置",
        priority=0,
        is_active=True,
    )
    async_db.add_all([rule1, rule2])
    await async_db.commit()

    # 查询误报规则
    result = await async_db.execute(
        select(DiagnosisImprovementRule).where(
            DiagnosisImprovementRule.rule_type == "false_positive"
        )
    )
    rules = result.scalars().all()

    # 应该至少有示例规则（包括通用兜底规则）
    assert len(rules) >= 2

    # 查询通用兜底规则
    result = await async_db.execute(
        select(DiagnosisImprovementRule).where(
            DiagnosisImprovementRule.node_id == "*"
        )
    )
    fallback_rule = result.scalar_one_or_none()

    assert fallback_rule is not None
    assert fallback_rule.priority == 0


@pytest.mark.asyncio
async def test_system_report_table_exists(async_db: AsyncSession):
    """测试 system_reports 表是否存在"""
    from sqlalchemy import select

    # 尝试查询表
    result = await async_db.execute(select(SystemReport).limit(1))
    # 不应该抛出异常
    assert result is not None
