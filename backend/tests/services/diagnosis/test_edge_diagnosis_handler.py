"""边缘诊断接口和 Stub 实现测试。

Story 26.8 — AC #1, #2, #6
"""
import pytest

from app.services.diagnosis.edge_diagnosis_handler import (
    EdgeDiagnosisHandler,
    EDGE_DIAGNOSIS_TOPICS,
    get_edge_diagnosis_config,
)
from app.services.diagnosis.edge_diagnosis_stub import EdgeDiagnosisStub


class TestEdgeDiagnosisHandler:
    """抽象接口测试"""

    def test_cannot_instantiate_abstract_class(self):
        """ABC 不可直接实例化"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            EdgeDiagnosisHandler()


class TestEdgeDiagnosisStub:
    """Stub 实现测试"""

    def test_stub_is_subclass(self):
        """Stub 是 EdgeDiagnosisHandler 的子类"""
        stub = EdgeDiagnosisStub()
        assert isinstance(stub, EdgeDiagnosisHandler)

    @pytest.mark.asyncio
    async def test_connect_returns_false(self):
        """connect 返回 False"""
        stub = EdgeDiagnosisStub()
        result = await stub.connect("gw-1", "mqtt://broker:1883")
        assert result is False

    @pytest.mark.asyncio
    async def test_receive_rules_returns_empty(self):
        """receive_rules 返回空列表"""
        stub = EdgeDiagnosisStub()
        result = await stub.receive_rules("gw-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_l1_returns_not_implemented_status(self):
        """execute_l1 返回 not_implemented 状态"""
        stub = EdgeDiagnosisStub()
        result = await stub.execute_l1([{"id": "R1"}], {"temp": 25.0})
        assert result["status"] == "not_implemented"
        assert "边缘推理" in result["message"]

    @pytest.mark.asyncio
    async def test_report_result_returns_false(self):
        """report_result 返回 False"""
        stub = EdgeDiagnosisStub()
        result = await stub.report_result("gw-1", {"diagnosis": "ok"})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_logs_call(self, caplog):
        """connect 记录日志"""
        stub = EdgeDiagnosisStub()
        with caplog.at_level("INFO"):
            await stub.connect("gw-test", "mqtt://broker:1883")
        assert "[EdgeStub] connect called" in caplog.text
        assert "gw-test" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_l1_logs_rule_count(self, caplog):
        """execute_l1 日志包含规则数量"""
        stub = EdgeDiagnosisStub()
        rules = [{"id": f"R{i}"} for i in range(3)]
        with caplog.at_level("INFO"):
            await stub.execute_l1(rules, {})
        assert "3 rules" in caplog.text


class TestEdgeDiagnosisConfig:
    """预留配置测试"""

    def test_get_edge_diagnosis_config_structure(self):
        """配置包含必要键"""
        config = get_edge_diagnosis_config()
        assert "enabled" in config
        assert "status" in config
        assert "mqtt_topics" in config
        assert "supported_levels" in config
        assert "arbitration" in config

    def test_config_disabled_by_default(self):
        """默认禁用"""
        config = get_edge_diagnosis_config()
        assert config["enabled"] is False

    def test_mqtt_topics_contain_gateway_placeholder(self):
        """{gateway_id} 占位符存在"""
        config = get_edge_diagnosis_config()
        for topic in config["mqtt_topics"].values():
            assert "{gateway_id}" in topic

    def test_topics_constant_keys(self):
        """MQTT topic 常量包含正确的键"""
        assert "rules_push" in EDGE_DIAGNOSIS_TOPICS
        assert "results_report" in EDGE_DIAGNOSIS_TOPICS
