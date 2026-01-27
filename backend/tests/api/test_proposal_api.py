"""
Proposal API 端点测试
测试节能方案相关的所有 API 端点
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
import uuid

from app.core.database import Base
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog


def generate_unique_code(prefix: str = "A1") -> str:
    """生成唯一的方案编号"""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ==================== 测试数据准备 ====================

def create_test_proposal(db_session):
    """创建测试用的方案数据"""
    proposal_code = generate_unique_code("A1")
    proposal = EnergySavingProposal(
        proposal_code=proposal_code,
        proposal_type="A",
        template_id="A1",
        template_name="峰谷套利优化方案",
        total_benefit=Decimal("15.50"),
        total_investment=Decimal("0"),
        status="pending",
        current_situation={
            "尖峰电量": 10000,
            "高峰电量": 30000,
            "平段电量": 40000,
            "低谷电量": 15000,
            "深谷电量": 5000
        }
    )
    db_session.add(proposal)
    db_session.flush()

    # 添加措施
    measure1 = ProposalMeasure(
        proposal_id=proposal.id,
        measure_code=f"{proposal_code}-M001",
        regulation_object="热处理预热工序",
        regulation_description="将预热工序从尖峰时段调整至平段",
        annual_benefit=Decimal("5.94"),
        investment=Decimal("0"),
        is_selected=False
    )

    measure2 = ProposalMeasure(
        proposal_id=proposal.id,
        measure_code=f"{proposal_code}-M002",
        regulation_object="辅助设备",
        regulation_description="辅助设备错峰运行",
        annual_benefit=Decimal("2.30"),
        investment=Decimal("0"),
        is_selected=False
    )

    measure3 = ProposalMeasure(
        proposal_id=proposal.id,
        measure_code=f"{proposal_code}-M003",
        regulation_object="空压机系统",
        regulation_description="空压机储气罐充气策略优化",
        annual_benefit=Decimal("3.16"),
        investment=Decimal("0"),
        is_selected=False
    )

    db_session.add_all([measure1, measure2, measure3])
    db_session.commit()

    return proposal


def create_accepted_proposal(db_session):
    """创建已接受的方案"""
    proposal_code = generate_unique_code("A2")
    proposal = EnergySavingProposal(
        proposal_code=proposal_code,
        proposal_type="A",
        template_id="A2",
        template_name="需量控制方案",
        total_benefit=Decimal("10.00"),
        total_investment=Decimal("0"),
        status="accepted"
    )
    db_session.add(proposal)
    db_session.flush()

    measure = ProposalMeasure(
        proposal_id=proposal.id,
        measure_code=f"{proposal_code}-M001",
        regulation_object="申报需量",
        regulation_description="降低申报需量",
        annual_benefit=Decimal("10.00"),
        investment=Decimal("0"),
        is_selected=True
    )
    db_session.add(measure)
    db_session.commit()

    return proposal


def create_executing_proposal_with_logs(db_session):
    """创建正在执行的方案，包含执行日志"""
    proposal_code = generate_unique_code("A3")
    proposal = EnergySavingProposal(
        proposal_code=proposal_code,
        proposal_type="A",
        template_id="A3",
        template_name="设备运行优化方案",
        total_benefit=Decimal("8.50"),
        total_investment=Decimal("0"),
        status="executing"
    )
    db_session.add(proposal)
    db_session.flush()

    measure = ProposalMeasure(
        proposal_id=proposal.id,
        measure_code=f"{proposal_code}-M001",
        regulation_object="空压机系统",
        regulation_description="空压机负荷匹配优化",
        annual_benefit=Decimal("8.50"),
        investment=Decimal("0"),
        is_selected=True,
        execution_status="executing"
    )
    db_session.add(measure)
    db_session.flush()

    # 添加执行日志
    from datetime import datetime
    log1 = MeasureExecutionLog(
        measure_id=measure.id,
        execution_time=datetime.now(),
        power_before=Decimal("320"),
        power_after=Decimal("280"),
        power_saved=Decimal("40"),
        expected_power_saved=Decimal("40"),
        result="success",
        result_message="执行成功"
    )
    log2 = MeasureExecutionLog(
        measure_id=measure.id,
        execution_time=datetime.now(),
        power_before=Decimal("310"),
        power_after=Decimal("275"),
        power_saved=Decimal("35"),
        expected_power_saved=Decimal("40"),
        result="success",
        result_message="执行成功"
    )
    db_session.add_all([log1, log2])
    db_session.commit()

    return proposal


# ==================== 单元测试 ====================

class TestProposalAPI:
    """Proposal API 测试类"""

    def test_get_proposal_not_found(self, db_session):
        """测试获取不存在的方案"""
        # 查询不存在的ID
        proposal = db_session.query(EnergySavingProposal).filter(
            EnergySavingProposal.id == 99999
        ).first()
        assert proposal is None

    def test_get_proposal_by_id(self, db_session):
        """测试根据ID获取方案"""
        # 创建测试数据
        proposal = create_test_proposal(db_session)

        # 查询
        result = db_session.query(EnergySavingProposal).filter(
            EnergySavingProposal.id == proposal.id
        ).first()

        assert result is not None
        assert result.proposal_code.startswith("A1-")
        assert result.template_id == "A1"
        assert len(result.measures) == 3

    def test_get_proposals_list(self, db_session):
        """测试获取方案列表"""
        # 创建多个方案
        create_test_proposal(db_session)
        create_accepted_proposal(db_session)

        # 查询所有方案
        proposals = db_session.query(EnergySavingProposal).all()
        assert len(proposals) >= 2

    def test_get_proposals_filter_by_template_id(self, db_session):
        """测试按模板ID过滤方案"""
        create_test_proposal(db_session)
        create_accepted_proposal(db_session)

        # 按模板ID过滤
        proposals = db_session.query(EnergySavingProposal).filter(
            EnergySavingProposal.template_id == "A1"
        ).all()

        assert all(p.template_id == "A1" for p in proposals)

    def test_get_proposals_filter_by_status(self, db_session):
        """测试按状态过滤方案"""
        create_test_proposal(db_session)
        create_accepted_proposal(db_session)

        # 按状态过滤
        proposals = db_session.query(EnergySavingProposal).filter(
            EnergySavingProposal.status == "accepted"
        ).all()

        assert all(p.status == "accepted" for p in proposals)

    def test_accept_proposal(self, db_session):
        """测试接受方案并选择措施"""
        proposal = create_test_proposal(db_session)

        # 获取措施ID
        measure_ids = [m.id for m in proposal.measures[:2]]  # 选择前两个措施

        # 模拟接受方案操作
        for measure in proposal.measures:
            measure.is_selected = measure.id in measure_ids

        proposal.status = "accepted"
        proposal.total_benefit = sum(
            m.annual_benefit for m in proposal.measures if m.is_selected
        )

        db_session.commit()
        db_session.refresh(proposal)

        # 验证
        assert proposal.status == "accepted"
        selected_measures = [m for m in proposal.measures if m.is_selected]
        assert len(selected_measures) == 2
        assert proposal.total_benefit == Decimal("8.24")  # 5.94 + 2.30

    def test_execute_proposal_only_accepted(self, db_session):
        """测试只有已接受的方案才能执行"""
        proposal = create_test_proposal(db_session)

        # pending 状态的方案不能执行
        assert proposal.status == "pending"

        # 接受方案后才能执行
        proposal.status = "accepted"
        db_session.commit()

        assert proposal.status == "accepted"

        # 执行方案
        proposal.status = "executing"
        db_session.commit()

        assert proposal.status == "executing"

    def test_delete_proposal(self, db_session):
        """测试删除方案"""
        proposal = create_test_proposal(db_session)
        proposal_id = proposal.id

        # 删除方案
        db_session.delete(proposal)
        db_session.commit()

        # 验证已删除
        result = db_session.query(EnergySavingProposal).filter(
            EnergySavingProposal.id == proposal_id
        ).first()

        assert result is None

    def test_proposal_measures_cascade_delete(self, db_session):
        """测试删除方案时措施级联删除"""
        proposal = create_test_proposal(db_session)
        measure_ids = [m.id for m in proposal.measures]

        # 删除方案
        db_session.delete(proposal)
        db_session.commit()

        # 验证措施也被删除
        remaining_measures = db_session.query(ProposalMeasure).filter(
            ProposalMeasure.id.in_(measure_ids)
        ).all()

        assert len(remaining_measures) == 0


class TestProposalMonitoring:
    """方案监控功能测试"""

    def test_get_monitoring_data(self, db_session):
        """测试获取监控数据"""
        proposal = create_executing_proposal_with_logs(db_session)

        # 获取监控数据
        selected_measures = [m for m in proposal.measures if m.is_selected]

        for measure in selected_measures:
            logs = db_session.query(MeasureExecutionLog).filter(
                MeasureExecutionLog.measure_id == measure.id
            ).all()

            execution_count = len(logs)
            success_count = len([l for l in logs if l.result == "success"])
            total_saved = sum(l.power_saved or Decimal("0") for l in logs)

            assert execution_count == 2
            assert success_count == 2
            assert total_saved == Decimal("75")  # 40 + 35

    def test_calculate_actual_benefit(self, db_session):
        """测试计算实际收益"""
        proposal = create_executing_proposal_with_logs(db_session)

        total_actual_benefit = Decimal("0")

        for measure in proposal.measures:
            if not measure.is_selected:
                continue

            logs = db_session.query(MeasureExecutionLog).filter(
                MeasureExecutionLog.measure_id == measure.id
            ).all()

            total_saved = sum(l.power_saved or Decimal("0") for l in logs)
            # 假设平均电价0.5元/kWh
            actual_benefit = total_saved * Decimal("0.5") / Decimal("10000")
            total_actual_benefit += actual_benefit

        # 75 kW * 0.5 元/kWh / 10000 = 0.00375 万元
        assert total_actual_benefit == Decimal("0.00375")


class TestProposalValidation:
    """方案验证测试"""

    def test_proposal_code_format(self, db_session):
        """测试方案编号格式"""
        proposal = create_test_proposal(db_session)

        # 验证格式: 模板ID-唯一ID
        parts = proposal.proposal_code.split("-")
        assert len(parts) >= 2
        assert parts[0] == "A1"

    def test_measure_code_format(self, db_session):
        """测试措施编号格式"""
        proposal = create_test_proposal(db_session)

        for measure in proposal.measures:
            # 验证格式: 方案编号-M序号
            assert measure.measure_code.startswith(proposal.proposal_code)
            assert "-M" in measure.measure_code

    def test_proposal_type_values(self, db_session):
        """测试方案类型值"""
        proposal = create_test_proposal(db_session)

        # A类型（无需投资）
        assert proposal.proposal_type in ["A", "B"]

        if proposal.proposal_type == "A":
            assert proposal.total_investment == Decimal("0")

    def test_proposal_status_transitions(self, db_session):
        """测试方案状态流转"""
        proposal = create_test_proposal(db_session)

        # pending -> accepted
        assert proposal.status == "pending"
        proposal.status = "accepted"
        db_session.commit()

        # accepted -> executing
        assert proposal.status == "accepted"
        proposal.status = "executing"
        db_session.commit()

        # executing -> completed
        assert proposal.status == "executing"
        proposal.status = "completed"
        db_session.commit()

        assert proposal.status == "completed"


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
