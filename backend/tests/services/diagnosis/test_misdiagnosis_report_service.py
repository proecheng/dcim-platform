"""
误诊反馈报告服务测试
Story 26.2: 误诊反馈报告
Story 26.6: 月度误判分析报告
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import SystemReport, DiagnosisImprovementRule
from app.services.diagnosis.misdiagnosis_report_service import MisdiagnosisReportService, MisdiagnosisReportServiceV2


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


# ============================================================
# Story 26.6: 月度误判分析报告测试
# ============================================================

@pytest.fixture
def mock_db_session_v2():
    """模拟数据库会话 (Story 26.6)"""
    session = AsyncMock(spec=AsyncSession)
    session.bind = MagicMock()
    session.bind.dialect.name = "sqlite"
    return session


@pytest.fixture
def service_v2(mock_db_session_v2):
    """创建服务实例 (Story 26.6)"""
    return MisdiagnosisReportServiceV2(mock_db_session_v2)


class TestDiagnosisSummaryV2:
    """测试诊断概览统计查询 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_diagnosis_summary_with_data(self, service_v2, mock_db_session_v2):
        """测试有数据的情况"""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_diagnosis_count = 1000
        mock_row.annotated_count = 250
        mock_row.annotation_coverage_rate = 0.25
        mock_result.fetchone.return_value = mock_row
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_diagnosis_summary(start_date, end_date)

        assert result["total_diagnosis_count"] == 1000
        assert result["annotated_count"] == 250
        assert result["annotation_coverage_rate"] == 0.25


class TestRecommendationsV2:
    """测试改进建议生成 (Story 26.6)"""

    def test_generate_recommendations_high_misdiagnosis_rate(self, service_v2):
        """测试高误判率节点的建议"""
        top_nodes = [
            {
                "node_id": "N-UPS-BATTERY",
                "node_name": "UPS电池故障",
                "misdiagnosis_count": 40,
                "total_count": 100,
                "misdiagnosis_rate": 0.4,
            }
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 1
        assert "检查先验概率或增加证据维度" in recommendations[0]

    def test_generate_recommendations_low_sample_size(self, service_v2):
        """测试样本量不足的建议"""
        top_nodes = [
            {
                "node_id": "N-AC-FAULT",
                "node_name": "空调故障",
                "misdiagnosis_count": 3,
                "total_count": 5,
                "misdiagnosis_rate": 0.6,
            }
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 1
        assert "样本量不足" in recommendations[0]


class TestMarkdownRenderingV2:
    """测试 Markdown 报告渲染 (Story 26.6)"""

    def test_render_markdown_report_with_all_data(self, service_v2):
        """测试完整数据的报告渲染"""
        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        report_data = {
            "summary": {
                "total_diagnosis_count": 1000,
                "annotated_count": 250,
                "annotation_coverage_rate": 0.25,
            },
            "misdiagnosis_distribution": {
                "false_positive_count": 50,
                "false_positive_rate": 0.1,
                "false_negative_count": 20,
                "false_negative_rate": 0.02,
                "false_negative_available": True,
            },
            "top_misdiagnosed_nodes": [
                {
                    "node_id": "N-UPS-BATTERY",
                    "node_name": "UPS电池故障",
                    "misdiagnosis_count": 40,
                    "total_count": 100,
                    "misdiagnosis_rate": 0.4,
                }
            ],
            "device_type_distribution": [
                {
                    "device_type": "UPS",
                    "total_count": 500,
                    "misdiagnosis_count": 50,
                    "misdiagnosis_rate": 0.1,
                }
            ],
            "recommendations": ["节点 UPS电池故障 误判率 40.0%（样本量 100），建议检查先验概率或增加证据维度"],
        }

        markdown = service_v2._render_markdown_report(start_date, end_date, report_data)

        assert "2026年2月误判分析报告" in markdown
        assert "总诊断次数 | 1000" in markdown
        assert "标注覆盖率 | 25.0%" in markdown
        assert "误报率 | 10.0%" in markdown
        assert "漏报率 | 2.0%" in markdown
        assert "UPS电池故障" in markdown
        assert "UPS" in markdown

    def test_render_markdown_report_without_work_orders(self, service_v2):
        """测试工单系统未配置的报告渲染"""
        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        report_data = {
            "summary": {
                "total_diagnosis_count": 1000,
                "annotated_count": 250,
                "annotation_coverage_rate": 0.25,
            },
            "misdiagnosis_distribution": {
                "false_positive_count": 50,
                "false_positive_rate": 0.1,
                "false_negative_count": 0,
                "false_negative_rate": 0.0,
                "false_negative_available": False,
            },
            "top_misdiagnosed_nodes": [],
            "device_type_distribution": [],
            "recommendations": [],
        }

        markdown = service_v2._render_markdown_report(start_date, end_date, report_data)

        assert "工单系统未配置，漏报统计不可用" in markdown
        assert "暂无误判节点数据" in markdown
        assert "暂无设备类型误判数据" in markdown
