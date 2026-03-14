"""
测试设备同步服务的回路绑定逻辑

覆盖所有边界情况和优先级规则
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.device_sync import DeviceSyncService
from app.models.device import Device


@pytest.fixture
def circuit_map():
    """模拟回路映射表"""
    return {
        # UPS 回路
        "C-F1-UPS-01": 1,
        "C-F2-UPS-01": 2,
        "C-F3-UPS-01": 3,
        "C-F4-UPS-01": 4,
        # PDU 回路
        "C-F2-PDU-01": 10,
        "C-F3-PDU-01": 11,
        "C-F4-PDU-01": 12,
        "C-A1-01": 13,
        "C-B1-01": 14,
        # HVAC 回路 - 冷通道
        "C-F2-CA-01": 20,
        "C-F3-CA-01": 21,
        "C-F4-CA-01": 22,
        "C-CA-A-01": 23,
        "C-CA-GENERIC": 24,
        # HVAC 回路 - 水泵
        "C-CHWP-01": 30,  # 冷冻水泵
        "C-CWP-01": 31,  # 冷却水泵
        "C-PMP-01": 32,  # 水泵1
        "C-PMP-02": 33,  # 水泵2
        "C-PMP-GENERIC": 34,  # 通用水泵
        # HVAC 回路 - 其他
        "C-AC-OUT-01": 40,  # 室外机
        "C-CH-01": 41,  # 冷机
        "C-CT-01": 42,  # 冷却塔
        "C-F1-AC-01": 43,  # F1空调
        "C-F2-AC-01": 44,  # F2空调
        "C-AC-01": 45,  # 精密空调A
        "C-AC-02": 46,  # 精密空调B
        # 照明
        "C-LIGHT": 50,
    }


@pytest.fixture
def floors():
    """模拟楼层列表（与 circuit_map 中的楼层一致）"""
    return ["F1", "F2", "F3", "F4"]


@pytest.fixture
def sync_service():
    """创建同步服务实例"""
    # 创建 mock db session (这些方法不需要数据库)
    mock_db = MagicMock()
    return DeviceSyncService(db=mock_db)


class TestUPSCircuitInference:
    """测试 UPS 设备回路推断"""

    def test_ups_f1_format1(self, sync_service, circuit_map, floors):
        """测试 UPS-F1-XX 格式"""
        device = MagicMock(spec=Device)
        device.device_code = "UPS-F1-01"
        device.device_type = "UPS"
        result = sync_service._infer_ups_circuit(device.device_code, circuit_map, floors)
        assert result == 1

    def test_ups_f2_format2(self, sync_service, circuit_map, floors):
        """测试 F2-UPS-XX 格式"""
        device = MagicMock(spec=Device)
        device.device_code = "F2-UPS-01"
        device.device_type = "UPS"
        result = sync_service._infer_ups_circuit(device.device_code, circuit_map, floors)
        assert result == 2

    def test_ups_unknown_floor(self, sync_service, circuit_map, floors):
        """测试未知楼层 UPS"""
        device = MagicMock(spec=Device)
        device.device_code = "UPS-F5-01"
        device.device_type = "UPS"
        result = sync_service._infer_ups_circuit(device.device_code, circuit_map, floors)
        assert result is None


class TestPDUCircuitInference:
    """测试 PDU 设备回路推断"""

    def test_pdu_f2_priority(self, sync_service, circuit_map, floors):
        """测试 PDU-F2-XX 优先级"""
        result = sync_service._infer_pdu_circuit("PDU-F2-01", None, circuit_map, floors)
        assert result == 10

    def test_pdu_f3_priority(self, sync_service, circuit_map, floors):
        """测试 PDU-F3-XX 优先级"""
        result = sync_service._infer_pdu_circuit("PDU-F3-02", None, circuit_map, floors)
        assert result == 11

    def test_pdu_area_a1_by_code(self, sync_service, circuit_map, floors):
        """测试通过编码识别 A1 区域"""
        result = sync_service._infer_pdu_circuit("PDU-A-01", None, circuit_map, floors)
        assert result == 13

    def test_pdu_area_b1_by_area_code(self, sync_service, circuit_map, floors):
        """测试通过 area_code 识别 B1 区域"""
        result = sync_service._infer_pdu_circuit("PDU-01", "B1", circuit_map, floors)
        assert result == 14

    def test_pdu_unknown(self, sync_service, circuit_map, floors):
        """测试未知 PDU"""
        result = sync_service._infer_pdu_circuit("PDU-UNKNOWN", None, circuit_map, floors)
        assert result is None


class TestHVACCircuitInference:
    """测试 HVAC 设备回路推断 - 关键优先级测试"""

    # 冷通道优先级测试
    def test_ca_floor_specific_priority(self, sync_service, circuit_map, floors):
        """测试楼层冷通道优先级最高 (CA-F2-XX → C-F2-CA-01)"""
        result = sync_service._infer_hvac_circuit("CA-F2-01", circuit_map, floors)
        assert result == 20, "CA-F2-01 应绑定到 C-F2-CA-01 (楼层特定)"

    def test_ca_area_specific_priority(self, sync_service, circuit_map, floors):
        """测试区域冷通道优先级次之 (CA-A01 → C-CA-A-01)"""
        result = sync_service._infer_hvac_circuit("CA-A01", circuit_map, floors)
        assert result == 23, "CA-A01 应绑定到 C-CA-A-01 (区域特定)"

    def test_ca_generic_priority(self, sync_service, circuit_map, floors):
        """测试通用冷通道优先级最低 (CA-XX → C-CA-GENERIC)"""
        result = sync_service._infer_hvac_circuit("CA-99", circuit_map, floors)
        assert result == 24, "CA-99 应绑定到 C-CA-GENERIC (通用)"

    def test_ca_priority_conflict_resolved(self, sync_service, circuit_map, floors):
        """测试优先级冲突解决 - CA-F2-01 不应绑定到 GENERIC"""
        result = sync_service._infer_hvac_circuit("CA-F2-01", circuit_map, floors)
        assert result != 24, "CA-F2-01 不应绑定到 C-CA-GENERIC"
        assert result == 20, "CA-F2-01 应绑定到 C-F2-CA-01"

    # 水泵测试
    def test_pmp_chilled_water_pump(self, sync_service, circuit_map, floors):
        """测试冷冻水泵 (PMP-F1-01~04 → C-CHWP-01)"""
        for i in [1, 2, 3, 4]:
            result = sync_service._infer_hvac_circuit(f"PMP-F1-0{i}", circuit_map, floors)
            assert result == 30, f"PMP-F1-0{i} 应绑定到 C-CHWP-01"

    def test_pmp_cooling_water_pump(self, sync_service, circuit_map, floors):
        """测试冷却水泵 (PMP-F1-07~09 → C-CWP-01)"""
        for i in [7, 8, 9]:
            result = sync_service._infer_hvac_circuit(f"PMP-F1-0{i}", circuit_map, floors)
            assert result == 31, f"PMP-F1-0{i} 应绑定到 C-CWP-01"

    def test_pmp_round_robin_odd(self, sync_service, circuit_map, floors):
        """测试水泵轮询分配 - 奇数 (PMP-F1-05 → C-PMP-01)"""
        result = sync_service._infer_hvac_circuit("PMP-F1-05", circuit_map, floors)
        assert result == 32, "PMP-F1-05 应轮询到 C-PMP-01"

    def test_pmp_round_robin_even(self, sync_service, circuit_map, floors):
        """测试水泵轮询分配 - 偶数 (PMP-F1-06 → C-PMP-02)"""
        result = sync_service._infer_hvac_circuit("PMP-F1-06", circuit_map, floors)
        assert result == 33, "PMP-F1-06 应轮询到 C-PMP-02"

    def test_pmp_invalid_number_fallback(self, sync_service, circuit_map, floors):
        """测试水泵编号无效时回退到通用回路"""
        result = sync_service._infer_hvac_circuit("PMP-F1-XX", circuit_map, floors)
        assert result == 34, "PMP-F1-XX 应回退到 C-PMP-GENERIC"

    # 室外机测试
    def test_ac_out_priority(self, sync_service, circuit_map, floors):
        """测试室外机绑定 (AC-OUT-XX → C-AC-OUT-01)"""
        result = sync_service._infer_hvac_circuit("AC-OUT-01", circuit_map, floors)
        assert result == 40, "AC-OUT-01 应绑定到 C-AC-OUT-01"

    def test_ac_out_not_generic(self, sync_service, circuit_map, floors):
        """测试室外机不应绑定到 GENERIC (修复前的 bug)"""
        result = sync_service._infer_hvac_circuit("AC-OUT-02", circuit_map, floors)
        assert result == 40, "AC-OUT-02 应绑定到 C-AC-OUT-01 而非 GENERIC"

    # 冷机和冷却塔
    def test_chiller(self, sync_service, circuit_map, floors):
        """测试冷机 (CH-XX → C-CH-01)"""
        result = sync_service._infer_hvac_circuit("CH-01", circuit_map, floors)
        assert result == 41

    def test_cooling_tower(self, sync_service, circuit_map, floors):
        """测试冷却塔 (CT-XX → C-CT-01)"""
        result = sync_service._infer_hvac_circuit("CT-01", circuit_map, floors)
        assert result == 42

    # 楼层空调
    def test_floor_ac(self, sync_service, circuit_map, floors):
        """测试楼层空调 (F2-AC-XX → C-F2-AC-01)"""
        result = sync_service._infer_hvac_circuit("F2-AC-01", circuit_map, floors)
        assert result == 44

    # 精密空调
    def test_precision_ac_a(self, sync_service, circuit_map, floors):
        """测试精密空调 A (AC-A → C-AC-01)"""
        result = sync_service._infer_hvac_circuit("AC-A", circuit_map, floors)
        assert result == 45

    def test_precision_ac_b(self, sync_service, circuit_map, floors):
        """测试精密空调 B (AC-B → C-AC-02)"""
        result = sync_service._infer_hvac_circuit("AC-B", circuit_map, floors)
        assert result == 46


class TestITCircuitInference:
    """测试 IT 设备回路推断"""

    def test_it_area_a1_by_code(self, sync_service, circuit_map):
        """测试通过编码识别 A1 区域"""
        result = sync_service._infer_it_circuit("IT-A-01", None, circuit_map)
        assert result == 13

    def test_it_area_b1_by_area_code(self, sync_service, circuit_map):
        """测试通过 area_code 识别 B1 区域"""
        result = sync_service._infer_it_circuit("IT-01", "B1", circuit_map)
        assert result == 14

    def test_it_unknown(self, sync_service, circuit_map):
        """测试未知 IT 设备"""
        result = sync_service._infer_it_circuit("IT-UNKNOWN", None, circuit_map)
        assert result is None


class TestMainInferCircuitId:
    """测试主入口方法 _infer_circuit_id"""

    def test_ups_device(self, sync_service, circuit_map):
        """测试 UPS 设备路由"""
        device = MagicMock(spec=Device)
        device.device_code = "UPS-F2-01"
        device.device_type = "UPS"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result == 2

    def test_pdu_device(self, sync_service, circuit_map):
        """测试 PDU 设备路由"""
        device = MagicMock(spec=Device)
        device.device_code = "PDU-F3-01"
        device.device_type = "PDU"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result == 11

    def test_hvac_device(self, sync_service, circuit_map):
        """测试 HVAC 设备路由"""
        device = MagicMock(spec=Device)
        device.device_code = "CA-F2-01"
        device.device_type = "HVAC"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result == 20

    def test_it_device(self, sync_service, circuit_map):
        """测试 IT 设备路由"""
        device = MagicMock(spec=Device)
        device.device_code = "IT-A-01"
        device.device_type = "IT"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result == 13

    def test_light_device(self, sync_service, circuit_map):
        """测试照明设备路由"""
        device = MagicMock(spec=Device)
        device.device_code = "LIGHT-01"
        device.device_type = "LIGHT"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result == 50

    def test_unknown_device_type(self, sync_service, circuit_map):
        """测试未知设备类型"""
        device = MagicMock(spec=Device)
        device.device_code = "UNKNOWN-01"
        device.device_type = "UNKNOWN"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result is None


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_circuit_map(self, sync_service):
        """测试空回路映射表"""
        device = MagicMock(spec=Device)
        device.device_code = "UPS-F1-01"
        device.device_type = "UPS"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, {})
        assert result is None

    def test_none_device_code(self, sync_service, circuit_map):
        """测试 None 设备编码"""
        device = MagicMock(spec=Device)
        device.device_code = None
        device.device_type = "UPS"
        device.area_code = None
        # 应该不会抛出异常
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result is None

    def test_empty_device_code(self, sync_service, circuit_map):
        """测试空字符串设备编码"""
        device = MagicMock(spec=Device)
        device.device_code = ""
        device.device_type = "UPS"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        assert result is None

    def test_case_sensitivity(self, sync_service, circuit_map):
        """测试大小写敏感性"""
        device = MagicMock(spec=Device)
        device.device_code = "ups-f1-01"  # 小写
        device.device_type = "UPS"
        device.area_code = None
        result = sync_service._infer_circuit_id(device, circuit_map)
        # 当前实现是大小写敏感的，小写不匹配
        assert result is None


class TestPriorityConflictResolution:
    """测试优先级冲突解决 - 这是修复的核心"""

    def test_ca_f2_not_generic(self, sync_service, circuit_map, floors):
        """
        关键测试: CA-F2-01 应绑定到 C-F2-CA-01 而非 C-CA-GENERIC
        这是修复前的主要 bug
        """
        result = sync_service._infer_hvac_circuit("CA-F2-01", circuit_map, floors)
        assert result == 20, "CA-F2-01 必须绑定到 C-F2-CA-01 (楼层特定)"
        assert result != 24, "CA-F2-01 不能绑定到 C-CA-GENERIC"

    def test_ca_f3_not_generic(self, sync_service, circuit_map, floors):
        """测试 CA-F3-XX 优先级"""
        result = sync_service._infer_hvac_circuit("CA-F3-02", circuit_map, floors)
        assert result == 21, "CA-F3-02 必须绑定到 C-F3-CA-01"
        assert result != 24

    def test_ca_a01_not_generic(self, sync_service, circuit_map, floors):
        """测试 CA-A01 优先级"""
        result = sync_service._infer_hvac_circuit("CA-A01", circuit_map, floors)
        assert result == 23, "CA-A01 必须绑定到 C-CA-A-01"
        assert result != 24

    def test_ac_out_not_generic(self, sync_service, circuit_map, floors):
        """
        关键测试: AC-OUT-XX 应绑定到 C-AC-OUT-01 而非 C-AC-OUT-GENERIC
        这是修复前的另一个 bug
        """
        result = sync_service._infer_hvac_circuit("AC-OUT-01", circuit_map, floors)
        assert result == 40, "AC-OUT-01 必须绑定到 C-AC-OUT-01"

    def test_pmp_round_robin_not_generic(self, sync_service, circuit_map, floors):
        """测试水泵轮询优先于通用回路"""
        result = sync_service._infer_hvac_circuit("PMP-F1-05", circuit_map, floors)
        assert result in [32, 33], "PMP-F1-05 应轮询到 C-PMP-01/02"
        assert result != 34, "不应回退到 C-PMP-GENERIC"
