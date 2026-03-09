"""
误诊反馈报告服务测试
Story 26.2: 误诊反馈报告
Story 26.6: 月度误判分析报告
"""

import pytest
import os
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import SystemReport, DiagnosisImprovementRule
from app.models.report import ReportRecord
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


class TestFalsePositiveStats:
    """测试误报统计查询 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_false_positive_stats(self, service_v2, mock_db_session_v2):
        """测试误报统计"""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.false_positive_count = 50
        mock_row.total_positive_count = 500
        mock_result.fetchone.return_value = mock_row
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_false_positive_stats(start_date, end_date)

        assert result["false_positive_count"] == 50
        assert result["false_positive_rate"] == 0.1

    @pytest.mark.asyncio
    async def test_query_false_positive_stats_no_data(self, service_v2, mock_db_session_v2):
        """测试无数据的误报统计"""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.false_positive_count = 0
        mock_row.total_positive_count = 0
        mock_result.fetchone.return_value = mock_row
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_false_positive_stats(start_date, end_date)

        assert result["false_positive_count"] == 0
        assert result["false_positive_rate"] == 0.0


class TestFalseNegativeStats:
    """测试漏报统计查询 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_false_negative_stats_work_orders_not_exist(self, service_v2, mock_db_session_v2):
        """测试工单表不存在的情况"""
        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_false_negative_stats(start_date, end_date, work_orders_exists=False)

        assert result["false_negative_count"] == 0
        assert result["false_negative_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_query_false_negative_stats_with_data(self, service_v2, mock_db_session_v2):
        """测试有漏报数据的情况"""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.false_negative_count = 20
        mock_row.total_count = 1000
        mock_result.fetchone.return_value = mock_row
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_false_negative_stats(start_date, end_date, work_orders_exists=True)

        assert result["false_negative_count"] == 20
        assert result["false_negative_rate"] == 0.02


class TestTopMisdiagnosedNodes:
    """测试高频误判节点查询 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_top_nodes_with_fault_tree_table(self, service_v2, mock_db_session_v2):
        """测试有故障树节点表的情况"""
        mock_result = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.node_id = "N-UPS-BATTERY"
        mock_row1.node_name = "UPS电池故障"
        mock_row1.misdiagnosis_count = 40
        mock_row1.total_count = 100
        mock_row1.misdiagnosis_rate = 0.4
        mock_result.fetchall.return_value = [mock_row1]
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_top_misdiagnosed_nodes(start_date, end_date, fault_tree_nodes_exists=True)

        assert len(result) == 1
        assert result[0]["node_id"] == "N-UPS-BATTERY"
        assert result[0]["node_name"] == "UPS电池故障"
        assert result[0]["misdiagnosis_count"] == 40

    @pytest.mark.asyncio
    async def test_query_top_nodes_without_fault_tree_table(self, service_v2, mock_db_session_v2):
        """测试无故障树节点表的情况"""
        mock_result = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.node_id = "N-UPS-BATTERY"
        mock_row1.node_name = "N-UPS-BATTERY"  # 使用 node_id 作为 node_name
        mock_row1.misdiagnosis_count = 40
        mock_row1.total_count = 100
        mock_row1.misdiagnosis_rate = 0.4
        mock_result.fetchall.return_value = [mock_row1]
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_top_misdiagnosed_nodes(start_date, end_date, fault_tree_nodes_exists=False)

        assert len(result) == 1
        assert result[0]["node_name"] == "N-UPS-BATTERY"  # node_id 作为 node_name


class TestDeviceTypeDistribution:
    """测试设备类型误判分布查询 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_device_type_distribution(self, service_v2, mock_db_session_v2):
        """测试设备类型分布查询"""
        mock_result = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.device_type = "UPS"
        mock_row1.total_count = 500
        mock_row1.misdiagnosis_count = 50
        mock_row1.misdiagnosis_rate = 0.1
        mock_result.fetchall.return_value = [mock_row1]
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_device_type_distribution(start_date, end_date)

        assert len(result) == 1
        assert result[0]["device_type"] == "UPS"
        assert result[0]["total_count"] == 500
        assert result[0]["misdiagnosis_rate"] == 0.1


class TestCheckTableExists:
    """测试表存在性检查 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_check_table_exists_sqlite(self, service_v2, mock_db_session_v2):
        """测试 SQLite 表存在性检查"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "work_orders"
        mock_db_session_v2.execute.return_value = mock_result

        result = await service_v2._check_table_exists("work_orders")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_table_not_exists_sqlite(self, service_v2, mock_db_session_v2):
        """测试 SQLite 表不存在"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session_v2.execute.return_value = mock_result

        result = await service_v2._check_table_exists("non_existent_table")

        assert result is False


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


class TestRecommendationsV2Branches:
    """测试改进建议的所有分支覆盖 (Story 26.6)"""

    def test_generate_recommendations_medium_misdiagnosis_rate(self, service_v2):
        """测试中等误判率节点的建议 (0.2 <= rate <= 0.3)"""
        top_nodes = [
            {
                "node_id": "N-COOLING",
                "node_name": "冷却系统故障",
                "misdiagnosis_count": 25,
                "total_count": 100,
                "misdiagnosis_rate": 0.25,
            }
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 1
        assert "审查诊断逻辑" in recommendations[0]

    def test_generate_recommendations_low_misdiagnosis_rate(self, service_v2):
        """测试较低误判率节点的建议 (0.1 <= rate < 0.2)"""
        top_nodes = [
            {
                "node_id": "N-POWER",
                "node_name": "电源故障",
                "misdiagnosis_count": 15,
                "total_count": 100,
                "misdiagnosis_rate": 0.15,
            }
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 1
        assert "增加标注样本" in recommendations[0]

    def test_generate_recommendations_good_diagnosis(self, service_v2):
        """测试诊断效果良好的建议 (rate < 0.1)"""
        top_nodes = [
            {
                "node_id": "N-TEMP",
                "node_name": "温度异常",
                "misdiagnosis_count": 5,
                "total_count": 100,
                "misdiagnosis_rate": 0.05,
            }
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 1
        assert "诊断效果良好" in recommendations[0]

    def test_generate_recommendations_empty_nodes(self, service_v2):
        """测试空节点列表"""
        recommendations = service_v2._generate_recommendations([])
        assert len(recommendations) == 0

    def test_generate_recommendations_multiple_nodes(self, service_v2):
        """测试多节点混合建议"""
        top_nodes = [
            {
                "node_id": "N-1",
                "node_name": "节点1",
                "misdiagnosis_count": 40,
                "total_count": 100,
                "misdiagnosis_rate": 0.4,
            },
            {
                "node_id": "N-2",
                "node_name": "节点2",
                "misdiagnosis_count": 2,
                "total_count": 5,
                "misdiagnosis_rate": 0.4,
            },
        ]

        recommendations = service_v2._generate_recommendations(top_nodes)

        assert len(recommendations) == 2
        assert "检查先验概率" in recommendations[0]
        assert "样本量不足" in recommendations[1]


class TestCheckExistingReport:
    """测试已有报告检查 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_check_existing_report_found(self, service_v2, mock_db_session_v2):
        """测试找到已有报告"""
        mock_report = MagicMock(spec=ReportRecord)
        mock_report.id = 42
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._check_existing_report(start_date, end_date)

        assert result is not None
        assert result.id == 42

    @pytest.mark.asyncio
    async def test_check_existing_report_not_found(self, service_v2, mock_db_session_v2):
        """测试未找到已有报告"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._check_existing_report(start_date, end_date)

        assert result is None


class TestSaveMarkdownFile:
    """测试 Markdown 文件保存 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_save_markdown_file(self, service_v2, tmp_path):
        """测试保存 Markdown 文件到磁盘"""
        with patch("app.services.diagnosis.misdiagnosis_report_service.settings") as mock_settings:
            mock_settings.REPORT_DIR = str(tmp_path / "reports")

            start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
            content = "# 测试报告\n\n内容..."

            file_path, file_size = await service_v2._save_markdown_file(start_date, content)

            assert os.path.exists(file_path)
            assert file_size > 0
            assert "2026-02-misdiagnosis.md" in file_path
            with open(file_path, "r", encoding="utf-8") as f:
                assert f.read() == content


class TestCheckTableExistsPostgresql:
    """测试 PostgreSQL 表存在性检查 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_check_table_exists_postgresql(self):
        """测试 PostgreSQL 的表存在性检查 SQL"""
        session = AsyncMock(spec=AsyncSession)
        session.bind = MagicMock()
        session.bind.dialect.name = "postgresql"

        service = MisdiagnosisReportServiceV2(session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "work_orders"
        session.execute.return_value = mock_result

        result = await service._check_table_exists("work_orders")

        assert result is True
        # 验证使用了 pg_tables 查询
        call_args = session.execute.call_args
        query_str = str(call_args[0][0])
        assert "pg_tables" in query_str


class TestDiagnosisSummaryNoData:
    """测试诊断概览统计边缘场景 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_diagnosis_summary_no_annotations(self, service_v2, mock_db_session_v2):
        """测试无标注数据"""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_diagnosis_count = 500
        mock_row.annotated_count = 0
        mock_row.annotation_coverage_rate = None  # 除零返回 None
        mock_result.fetchone.return_value = mock_row
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service_v2._query_diagnosis_summary(start_date, end_date)

        assert result["total_diagnosis_count"] == 500
        assert result["annotated_count"] == 0
        assert result["annotation_coverage_rate"] == 0.0  # None 应被转为 0.0


class TestGenerateMonthlyReportV2:
    """测试完整报告生成流程 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_generate_report_duplicate_raises(self, service_v2, mock_db_session_v2):
        """测试重复生成报告抛出 ValueError"""
        # 模拟已存在报告
        mock_existing = MagicMock(spec=ReportRecord)
        mock_existing.id = 99
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_db_session_v2.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="已存在"):
            await service_v2.generate_monthly_report_v2(start_date, end_date)

    @pytest.mark.asyncio
    async def test_generate_report_success_flow(self, mock_db_session_v2, tmp_path):
        """测试完整成功流程"""
        service = MisdiagnosisReportServiceV2(mock_db_session_v2)

        # 1. _check_existing_report 返回 None
        # 2. flush 设置 report.id
        # 3. 各 _query 方法返回数据
        # 4. _save_markdown_file 保存文件
        call_count = [0]

        def side_effect_execute(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # _check_existing_report
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 2:
                # _check_table_exists (work_orders)
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 3:
                # _check_table_exists (fault_tree_nodes)
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 4:
                # _query_diagnosis_summary
                mock_row = MagicMock()
                mock_row.total_diagnosis_count = 100
                mock_row.annotated_count = 50
                mock_row.annotation_coverage_rate = 0.5
                mock_result.fetchone.return_value = mock_row
            elif call_count[0] == 5:
                # _query_false_positive_stats
                mock_row = MagicMock()
                mock_row.false_positive_count = 10
                mock_row.total_positive_count = 50
                mock_result.fetchone.return_value = mock_row
            elif call_count[0] == 6:
                # _query_top_misdiagnosed_nodes (no fault_tree so uses simple query)
                mock_result.fetchall.return_value = []
            elif call_count[0] == 7:
                # _query_device_type_distribution
                mock_result.fetchall.return_value = []
            return mock_result

        mock_db_session_v2.execute = AsyncMock(side_effect=side_effect_execute)

        # 模拟 flush 设置 report id
        async def mock_flush():
            pass
        mock_db_session_v2.flush = AsyncMock(side_effect=mock_flush)
        mock_db_session_v2.commit = AsyncMock()

        # 模拟 add 捕获 report 对象
        added_objects = []
        def mock_add(obj):
            added_objects.append(obj)
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = 1  # 模拟数据库分配 ID
        mock_db_session_v2.add = MagicMock(side_effect=mock_add)

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        with patch("app.services.diagnosis.misdiagnosis_report_service.settings") as mock_settings:
            mock_settings.REPORT_DIR = str(tmp_path / "reports")

            report_id = await service.generate_monthly_report_v2(start_date, end_date, generated_by=1)

        assert report_id == 1
        # 验证创建了 ReportRecord 和 OperationLog
        assert len(added_objects) >= 2
        report_obj = added_objects[0]
        assert report_obj.status == "completed"
        assert report_obj.file_path is not None

    @pytest.mark.asyncio
    async def test_generate_report_failure_sets_failed_status(self, mock_db_session_v2):
        """测试生成失败时设置 failed 状态"""
        service = MisdiagnosisReportServiceV2(mock_db_session_v2)

        call_count = [0]

        def side_effect_execute(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # _check_existing_report
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 2:
                # _check_table_exists (work_orders)
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 3:
                # _check_table_exists (fault_tree_nodes)
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 4:
                # _query_diagnosis_summary 抛出异常
                raise RuntimeError("数据库连接失败")
            return mock_result

        mock_db_session_v2.execute = AsyncMock(side_effect=side_effect_execute)
        mock_db_session_v2.flush = AsyncMock()
        mock_db_session_v2.commit = AsyncMock()

        added_objects = []
        def mock_add(obj):
            added_objects.append(obj)
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = 1
        mock_db_session_v2.add = MagicMock(side_effect=mock_add)

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        with pytest.raises(RuntimeError, match="数据库连接失败"):
            await service.generate_monthly_report_v2(start_date, end_date)

        # 验证报告状态被设为 failed
        report_obj = added_objects[0]
        assert report_obj.status == "failed"
        assert "数据库连接失败" in report_obj.error_message


class TestQueryPostgresqlBranches:
    """测试 PostgreSQL SQL 分支 (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_query_diagnosis_summary_postgresql(self):
        """测试 PostgreSQL 的诊断概览查询"""
        session = AsyncMock(spec=AsyncSession)
        session.bind = MagicMock()
        session.bind.dialect.name = "postgresql"

        service = MisdiagnosisReportServiceV2(session)

        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_diagnosis_count = 200
        mock_row.annotated_count = 100
        mock_row.annotation_coverage_rate = 0.5
        mock_result.fetchone.return_value = mock_row
        session.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service._query_diagnosis_summary(start_date, end_date)

        assert result["total_diagnosis_count"] == 200
        # 验证使用了 PostgreSQL 的 FLOAT 转换
        call_args = session.execute.call_args
        query_str = str(call_args[0][0])
        assert "FLOAT" in query_str

    @pytest.mark.asyncio
    async def test_query_false_positive_stats_postgresql(self):
        """测试 PostgreSQL 的误报统计查询"""
        session = AsyncMock(spec=AsyncSession)
        session.bind = MagicMock()
        session.bind.dialect.name = "postgresql"

        service = MisdiagnosisReportServiceV2(session)

        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.false_positive_count = 30
        mock_row.total_positive_count = 100
        mock_result.fetchone.return_value = mock_row
        session.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service._query_false_positive_stats(start_date, end_date)

        assert result["false_positive_count"] == 30
        assert result["false_positive_rate"] == 0.3
        # 验证使用了 FILTER 语法
        call_args = session.execute.call_args
        query_str = str(call_args[0][0])
        assert "FILTER" in query_str

    @pytest.mark.asyncio
    async def test_query_false_negative_stats_postgresql(self):
        """测试 PostgreSQL 的漏报统计查询"""
        session = AsyncMock(spec=AsyncSession)
        session.bind = MagicMock()
        session.bind.dialect.name = "postgresql"

        service = MisdiagnosisReportServiceV2(session)

        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.false_negative_count = 5
        mock_row.total_count = 200
        mock_result.fetchone.return_value = mock_row
        session.execute.return_value = mock_result

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        result = await service._query_false_negative_stats(start_date, end_date, work_orders_exists=True)

        assert result["false_negative_count"] == 5
        assert result["false_negative_rate"] == 0.025
        # 验证使用了 INTERVAL 语法
        call_args = session.execute.call_args
        query_str = str(call_args[0][0])
        assert "INTERVAL" in query_str


class TestPerformance:
    """性能测试：验证报告生成 < 60s (Story 26.6)"""

    @pytest.mark.asyncio
    async def test_report_generation_performance(self, mock_db_session_v2, tmp_path):
        """测试完整报告生成流程在 60 秒内完成"""
        import time

        service = MisdiagnosisReportServiceV2(mock_db_session_v2)

        call_count = [0]

        def side_effect_execute(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = "work_orders"
            elif call_count[0] == 3:
                mock_result.scalar_one_or_none.return_value = "fault_tree_nodes"
            elif call_count[0] == 4:
                mock_row = MagicMock()
                mock_row.total_diagnosis_count = 50000
                mock_row.annotated_count = 10000
                mock_row.annotation_coverage_rate = 0.2
                mock_result.fetchone.return_value = mock_row
            elif call_count[0] == 5:
                mock_row = MagicMock()
                mock_row.false_positive_count = 1500
                mock_row.total_positive_count = 10000
                mock_result.fetchone.return_value = mock_row
            elif call_count[0] == 6:
                mock_row = MagicMock()
                mock_row.false_negative_count = 300
                mock_row.total_count = 50000
                mock_result.fetchone.return_value = mock_row
            elif call_count[0] == 7:
                # 大量节点数据
                rows = []
                for i in range(5):
                    row = MagicMock()
                    row.node_id = f"N-NODE-{i}"
                    row.node_name = f"故障节点{i}"
                    row.misdiagnosis_count = 100 - i * 15
                    row.total_count = 500 - i * 50
                    row.misdiagnosis_rate = row.misdiagnosis_count / row.total_count
                    rows.append(row)
                mock_result.fetchall.return_value = rows
            elif call_count[0] == 8:
                rows = []
                for dtype in ["UPS", "空调", "配电柜", "PDU", "传感器"]:
                    row = MagicMock()
                    row.device_type = dtype
                    row.total_count = 10000
                    row.misdiagnosis_count = 500
                    row.misdiagnosis_rate = 0.05
                    rows.append(row)
                mock_result.fetchall.return_value = rows
            return mock_result

        mock_db_session_v2.execute = AsyncMock(side_effect=side_effect_execute)
        mock_db_session_v2.flush = AsyncMock()
        mock_db_session_v2.commit = AsyncMock()

        added_objects = []
        def mock_add(obj):
            added_objects.append(obj)
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = 1
        mock_db_session_v2.add = MagicMock(side_effect=mock_add)

        start_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

        with patch("app.services.diagnosis.misdiagnosis_report_service.settings") as mock_settings:
            mock_settings.REPORT_DIR = str(tmp_path / "reports")

            start_time = time.time()
            report_id = await service.generate_monthly_report_v2(start_date, end_date, generated_by=1)
            elapsed = time.time() - start_time

        assert report_id == 1
        assert elapsed < 60.0, f"报告生成耗时 {elapsed:.2f}s，超过 60s 限制"
        # 验证文件确实被写入
        report_obj = added_objects[0]
        assert report_obj.file_path is not None
        assert os.path.exists(report_obj.file_path)
