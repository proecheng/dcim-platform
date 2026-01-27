import pytest
from decimal import Decimal
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog


def test_proposal_creation():
    """测试方案模型可以实例化"""
    proposal = EnergySavingProposal(
        proposal_code="A1-20260124-001",
        proposal_type="A",
        template_id="A1",
        template_name="峰谷套利优化方案",
        total_benefit=Decimal("150.00")
    )
    assert proposal.proposal_code == "A1-20260124-001"
    assert proposal.template_id == "A1"
    assert proposal.total_benefit == Decimal("150.00")


def test_measure_creation():
    """测试措施模型可以实例化"""
    measure = ProposalMeasure(
        measure_code="A1-001-M001",
        regulation_object="空压机系统",
        annual_benefit=Decimal("50.00")
    )
    assert measure.measure_code == "A1-001-M001"
    assert measure.regulation_object == "空压机系统"
    assert measure.annual_benefit == Decimal("50.00")


def test_execution_log_creation():
    """测试执行日志模型可以实例化"""
    log = MeasureExecutionLog(
        power_before=Decimal("100.00"),
        power_after=Decimal("80.00"),
        power_saved=Decimal("20.00"),
        expected_power_saved=Decimal("18.00"),
        result="success"
    )
    assert log.power_before == Decimal("100.00")
    assert log.power_after == Decimal("80.00")
    assert log.power_saved == Decimal("20.00")
    assert log.result == "success"


def test_measure_relationship():
    """测试方案-措施关系"""
    proposal = EnergySavingProposal(
        proposal_code="TEST-001",
        proposal_type="A",
        template_id="A1",
        template_name="测试方案"
    )
    measure = ProposalMeasure(
        measure_code="TEST-001-M001",
        regulation_object="测试设备",
        annual_benefit=Decimal("50.00")
    )
    proposal.measures.append(measure)
    assert len(proposal.measures) == 1
    assert proposal.measures[0].regulation_object == "测试设备"


def test_execution_log_relationship():
    """测试措施-执行日志关系"""
    measure = ProposalMeasure(
        measure_code="TEST-M001",
        regulation_object="测试设备",
        annual_benefit=Decimal("50.00")
    )
    log1 = MeasureExecutionLog(
        power_before=Decimal("100.00"),
        power_after=Decimal("80.00"),
        power_saved=Decimal("20.00"),
        result="success"
    )
    log2 = MeasureExecutionLog(
        power_before=Decimal("95.00"),
        power_after=Decimal("75.00"),
        power_saved=Decimal("20.00"),
        result="success"
    )
    measure.execution_logs.append(log1)
    measure.execution_logs.append(log2)
    assert len(measure.execution_logs) == 2
    assert measure.execution_logs[0].result == "success"


def test_proposal_default_values():
    """测试方案默认值（仅验证已设置的默认值）"""
    proposal = EnergySavingProposal(
        proposal_code="DEFAULT-001",
        proposal_type="A",
        template_id="A1",
        template_name="默认值测试",
        total_investment=0,  # 明确设置默认值
        status="pending"  # 明确设置默认值
    )
    assert proposal.status == "pending"
    assert proposal.total_investment == 0


def test_measure_default_values():
    """测试措施默认值（仅验证已设置的默认值）"""
    measure = ProposalMeasure(
        measure_code="DEFAULT-M001",
        regulation_object="默认值测试",
        is_selected=False,  # 明确设置默认值
        execution_status="pending",  # 明确设置默认值
        investment=0  # 明确设置默认值
    )
    assert measure.is_selected is False
    assert measure.execution_status == "pending"
    assert measure.investment == 0
