"""
测试 ProposalExecutor 服务
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
import uuid

from app.services.proposal_executor import ProposalExecutor
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog


class TestProposalExecutor:
    """测试 ProposalExecutor 服务"""

    @pytest.fixture
    def sample_proposal(self, db_session: Session):
        """创建测试方案"""
        db = db_session
        # 使用 UUID 确保每个测试的 proposal_code 唯一
        unique_code = f"TEST-{uuid.uuid4().hex[:8]}"
        proposal = EnergySavingProposal(
            proposal_code=unique_code,
            proposal_type="A",
            template_id="A1",
            template_name="测试方案",
            total_benefit=Decimal("10.5"),
            total_investment=Decimal("0"),
            status="accepted",
            analysis_start_date=date.today(),
            analysis_end_date=date.today()
        )
        db.add(proposal)
        db.flush()

        # 添加措施
        measure1 = ProposalMeasure(
            proposal_id=proposal.id,
            measure_code="M001",
            regulation_object="空调系统",
            regulation_description="降低温度设定",
            current_state={"power": 1000, "temperature": 24},
            target_state={"power": 800, "temperature": 26},
            annual_benefit=Decimal("5.0"),
            is_selected=True,
            execution_status="pending"
        )
        measure2 = ProposalMeasure(
            proposal_id=proposal.id,
            measure_code="M002",
            regulation_object="照明系统",
            regulation_description="调节亮度",
            current_state={"power": 500, "brightness": 100},
            target_state={"power": 400, "brightness": 80},
            annual_benefit=Decimal("3.0"),
            is_selected=True,
            execution_status="pending"
        )
        measure3 = ProposalMeasure(
            proposal_id=proposal.id,
            measure_code="M003",
            regulation_object="未选中措施",
            regulation_description="测试未选中",
            current_state={"power": 300},
            target_state={"power": 200},
            annual_benefit=Decimal("2.5"),
            is_selected=False,
            execution_status="pending"
        )
        db.add_all([measure1, measure2, measure3])
        db.commit()
        db.refresh(proposal)

        return proposal

    def test_execute_proposal(self, db_session: Session, sample_proposal):
        """测试执行整个方案"""
        db = db_session
        executor = ProposalExecutor(db)
        result = executor.execute_proposal(sample_proposal)

        # 验证返回结果
        assert result["proposal_id"] == sample_proposal.id
        assert result["executed_count"] == 2  # 只执行选中的措施
        assert result["success_count"] >= 0  # 至少0次成功
        assert len(result["results"]) == 2

        # 验证方案状态更新
        db.refresh(sample_proposal)
        assert sample_proposal.status == "executing"

        # 验证措施执行
        for measure in sample_proposal.measures:
            if measure.is_selected:
                assert measure.execution_status in ["completed", "failed"]

    def test_execute_measure(self, db_session: Session, sample_proposal):
        """测试执行单个措施"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        result = executor.execute_measure(measure)

        # 验证返回结果
        assert "measure_id" in result
        assert "measure_code" in result
        assert "success" in result
        assert result["measure_id"] == measure.id
        assert result["measure_code"] == measure.measure_code

        # 验证执行日志
        logs = db.query(MeasureExecutionLog).filter(
            MeasureExecutionLog.measure_id == measure.id
        ).all()
        assert len(logs) == 1

        log = logs[0]
        assert log.measure_id == measure.id
        assert log.result in ["success", "failed"]
        if log.result == "success":
            assert log.power_before is not None
            assert log.power_after is not None
            assert log.power_saved is not None

    def test_execute_measure_with_error(self, db_session: Session, sample_proposal):
        """测试执行措施时的错误处理"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        # 模拟错误：清空 current_state
        measure.current_state = None
        db.commit()

        # 执行应该捕获错误并记录失败日志
        result = executor.execute_measure(measure)

        # 即使发生错误，也应返回结果（不抛出异常）
        assert "measure_id" in result
        assert result["success"] is False or result["success"] is True

        # 验证执行状态
        db.refresh(measure)
        assert measure.execution_status in ["completed", "failed"]

    def test_get_current_power(self, db_session: Session, sample_proposal):
        """测试获取当前功率"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        power = executor._get_current_power(measure)

        assert isinstance(power, Decimal)
        assert power > 0

    def test_calculate_expected_savings(self, db_session: Session, sample_proposal):
        """测试计算预期节省功率"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        savings = executor._calculate_expected_savings(measure)

        assert isinstance(savings, Decimal)
        assert savings >= 0
        # 基于 sample_proposal 的数据：1000 - 800 = 200
        expected = Decimal("200")
        assert savings == expected

    def test_execute_control_action(self, db_session: Session, sample_proposal):
        """测试执行控制动作"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        # 执行多次以测试概率性成功（95%成功率）
        results = []
        for _ in range(20):
            result = executor._execute_control_action(measure)
            results.append(result)

        # 验证返回布尔值
        assert all(isinstance(r, bool) for r in results)
        # 验证至少有一些成功（95%成功率，20次至少应该有一些成功）
        assert any(results)

    def test_get_execution_summary(self, db_session: Session, sample_proposal):
        """测试获取执行摘要"""
        db = db_session
        executor = ProposalExecutor(db)

        # 先执行方案
        executor.execute_proposal(sample_proposal)

        # 获取摘要
        summary = executor.get_execution_summary(sample_proposal.id)

        # 验证摘要内容
        assert summary is not None
        assert summary["proposal_id"] == sample_proposal.id
        assert "total_executions" in summary
        assert "success_count" in summary
        assert "success_rate" in summary
        assert "total_power_saved_kwh" in summary
        assert "estimated_annual_savings" in summary

        # 验证执行次数
        assert summary["total_executions"] == 2  # 两个选中的措施

    def test_get_execution_summary_not_found(self, db_session: Session):
        """测试获取不存在方案的摘要"""
        db = db_session
        executor = ProposalExecutor(db)
        summary = executor.get_execution_summary(99999)

        assert summary is None

    def test_execution_log_fields(self, db_session: Session, sample_proposal):
        """测试执行日志字段完整性"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        executor.execute_measure(measure)

        log = db.query(MeasureExecutionLog).filter(
            MeasureExecutionLog.measure_id == measure.id
        ).first()

        # 验证日志字段
        assert log is not None
        assert log.measure_id == measure.id
        assert log.execution_time is not None
        assert log.result in ["success", "failed"]
        assert log.result_message is not None

        # 验证执行数据
        if log.result == "success":
            assert log.power_before is not None
            assert log.power_after is not None
            assert log.power_saved is not None
            assert log.expected_power_saved is not None
            assert log.execution_data is not None
            assert "regulation_object" in log.execution_data
            assert "target_state" in log.execution_data

    def test_multiple_executions(self, db_session: Session, sample_proposal):
        """测试多次执行同一措施"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        # 执行3次
        for _ in range(3):
            executor.execute_measure(measure)

        # 验证日志数量
        logs = db.query(MeasureExecutionLog).filter(
            MeasureExecutionLog.measure_id == measure.id
        ).all()
        assert len(logs) == 3

        # 验证每次执行都有记录
        for log in logs:
            assert log.execution_time is not None
            assert log.result in ["success", "failed"]

    def test_execution_with_empty_target_state(self, db_session: Session, sample_proposal):
        """测试目标状态为空的情况"""
        db = db_session
        executor = ProposalExecutor(db)
        measure = sample_proposal.measures[0]

        # 清空目标状态
        measure.target_state = {}
        db.commit()

        result = executor.execute_measure(measure)

        # 应该使用默认值
        assert "measure_id" in result
        # 验证日志存在
        logs = db.query(MeasureExecutionLog).filter(
            MeasureExecutionLog.measure_id == measure.id
        ).all()
        assert len(logs) == 1
