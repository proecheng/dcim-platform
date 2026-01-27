"""
测试节能方案 Pydantic Schemas
"""
import pytest
from decimal import Decimal
from datetime import datetime
from app.schemas.proposal_schema import (
    ProposalCreate,
    ProposalResponse,
    MeasureResponse,
    MeasureAcceptRequest,
    ProposalMonitoringResponse,
    ExecutionLogResponse,
    MeasureMonitoringResponse
)


def test_proposal_create_schema():
    """测试创建方案请求"""
    data = {"template_id": "A1", "analysis_days": 30}
    schema = ProposalCreate(**data)
    assert schema.template_id == "A1"
    assert schema.analysis_days == 30


def test_proposal_create_default_analysis_days():
    """测试默认分析天数"""
    data = {"template_id": "A2"}
    schema = ProposalCreate(**data)
    assert schema.analysis_days == 30


def test_proposal_create_validation():
    """测试字段验证"""
    # analysis_days 必须在 1-365 之间
    with pytest.raises(Exception):
        ProposalCreate(template_id="A1", analysis_days=500)

    with pytest.raises(Exception):
        ProposalCreate(template_id="A1", analysis_days=0)


def test_proposal_create_edge_values():
    """测试边界值"""
    # 最小值
    schema = ProposalCreate(template_id="A1", analysis_days=1)
    assert schema.analysis_days == 1

    # 最大值
    schema = ProposalCreate(template_id="A1", analysis_days=365)
    assert schema.analysis_days == 365


def test_measure_accept_request():
    """测试接受方案请求"""
    data = {"selected_measure_ids": [1, 2, 3]}
    schema = MeasureAcceptRequest(**data)
    assert len(schema.selected_measure_ids) == 3
    assert schema.selected_measure_ids == [1, 2, 3]


def test_measure_accept_request_empty():
    """测试空的措施列表"""
    data = {"selected_measure_ids": []}
    schema = MeasureAcceptRequest(**data)
    assert len(schema.selected_measure_ids) == 0


def test_measure_response_from_dict():
    """测试措施响应模型"""
    data = {
        "id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "regulation_description": "降低运行台数",
        "current_state": {"running_count": 4},
        "target_state": {"running_count": 3},
        "calculation_formula": "节省功率 = (4-3) * 单台功率",
        "calculation_basis": "历史运行数据",
        "annual_benefit": Decimal("50.00"),
        "investment": Decimal("0.00"),
        "is_selected": False,
        "execution_status": "pending",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    schema = MeasureResponse(**data)
    assert schema.measure_code == "A1-001-M001"
    assert schema.annual_benefit == Decimal("50.00")
    assert schema.regulation_object == "空压机系统"
    assert schema.current_state["running_count"] == 4
    assert schema.target_state["running_count"] == 3


def test_measure_response_minimal():
    """测试措施响应模型的最小必需字段"""
    data = {
        "id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    schema = MeasureResponse(**data)
    assert schema.id == 1
    assert schema.measure_code == "A1-001-M001"
    assert schema.regulation_description is None
    assert schema.current_state is None


def test_proposal_response_from_dict():
    """测试方案响应模型"""
    data = {
        "id": 1,
        "proposal_code": "A1-20260124-001",
        "proposal_type": "A",
        "template_id": "A1",
        "template_name": "峰谷套利优化方案",
        "total_benefit": Decimal("100.00"),
        "total_investment": Decimal("0.00"),
        "status": "pending",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "measures": []
    }
    schema = ProposalResponse(**data)
    assert schema.proposal_code == "A1-20260124-001"
    assert schema.template_name == "峰谷套利优化方案"
    assert schema.total_benefit == Decimal("100.00")
    assert len(schema.measures) == 0


def test_proposal_response_with_measures():
    """测试包含措施的方案响应"""
    measure_data = {
        "id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "annual_benefit": Decimal("50.00"),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    data = {
        "id": 1,
        "proposal_code": "A1-20260124-001",
        "proposal_type": "A",
        "template_id": "A1",
        "template_name": "峰谷套利优化方案",
        "total_benefit": Decimal("50.00"),
        "status": "pending",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "measures": [measure_data]
    }
    schema = ProposalResponse(**data)
    assert len(schema.measures) == 1
    assert schema.measures[0].measure_code == "A1-001-M001"


def test_execution_log_response():
    """测试执行日志响应"""
    data = {
        "id": 1,
        "execution_time": datetime.now(),
        "power_before": Decimal("100.00"),
        "power_after": Decimal("80.00"),
        "power_saved": Decimal("20.00"),
        "expected_power_saved": Decimal("18.00"),
        "result": "success",
        "result_message": "执行成功"
    }
    schema = ExecutionLogResponse(**data)
    assert schema.power_saved == Decimal("20.00")
    assert schema.result == "success"


def test_measure_monitoring_response():
    """测试措施监控响应"""
    log_data = {
        "id": 1,
        "execution_time": datetime.now(),
        "power_before": Decimal("100.00"),
        "power_after": Decimal("80.00"),
        "power_saved": Decimal("20.00"),
        "expected_power_saved": Decimal("18.00"),
        "result": "success",
        "result_message": "执行成功"
    }

    data = {
        "measure_id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "expected_benefit": Decimal("50.00"),
        "actual_benefit": Decimal("45.00"),
        "execution_count": 10,
        "success_count": 9,
        "latest_execution": log_data
    }
    schema = MeasureMonitoringResponse(**data)
    assert schema.measure_id == 1
    assert schema.execution_count == 10
    assert schema.success_count == 9
    assert schema.latest_execution.power_saved == Decimal("20.00")


def test_proposal_monitoring_response():
    """测试方案监控响应"""
    measure_monitoring = {
        "measure_id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "expected_benefit": Decimal("50.00"),
        "execution_count": 10,
        "success_count": 9
    }

    data = {
        "proposal_id": 1,
        "proposal_code": "A1-20260124-001",
        "template_name": "峰谷套利优化方案",
        "total_expected_benefit": Decimal("100.00"),
        "total_actual_benefit": Decimal("90.00"),
        "measures": [measure_monitoring]
    }
    schema = ProposalMonitoringResponse(**data)
    assert schema.proposal_id == 1
    assert schema.total_expected_benefit == Decimal("100.00")
    assert len(schema.measures) == 1


def test_decimal_precision():
    """测试 Decimal 精度"""
    data = {
        "id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "annual_benefit": Decimal("50.12345"),  # 高精度
        "investment": Decimal("100.99"),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    schema = MeasureResponse(**data)
    # Decimal 应该保留原始精度
    assert schema.annual_benefit == Decimal("50.12345")
    assert schema.investment == Decimal("100.99")


def test_optional_fields():
    """测试可选字段"""
    data = {
        "measure_id": 1,
        "measure_code": "A1-001-M001",
        "regulation_object": "空压机系统",
        "expected_benefit": None,
        "actual_benefit": None,
        "execution_count": 0,
        "success_count": 0,
        "latest_execution": None
    }
    schema = MeasureMonitoringResponse(**data)
    assert schema.expected_benefit is None
    assert schema.actual_benefit is None
    assert schema.latest_execution is None
