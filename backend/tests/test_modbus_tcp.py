"""Modbus TCP 适配器单元测试 — Story 1.2"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from gateway.adapters.base import (
    AdapterState,
    ConnectionResult,
    DataQuality,
    DataSourceConfig,
    PointConfig,
    PointValue,
)
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.adapters.modbus_tcp import (
    ModbusTcpAdapter,
    _parse_address,
    _convert_value,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_registry():
    """确保 modbus_tcp 注册存在，测试后清理避免污染"""
    original = ADAPTER_REGISTRY.copy()
    # 确保 modbus_tcp 已注册（可能被其他测试清理掉）
    if "modbus_tcp" not in ADAPTER_REGISTRY:
        ADAPTER_REGISTRY["modbus_tcp"] = ModbusTcpAdapter
    yield
    # 恢复原始注册表
    ADAPTER_REGISTRY.clear()
    ADAPTER_REGISTRY.update(original)


def _make_config(**overrides) -> DataSourceConfig:
    """创建测试用 DataSourceConfig"""
    defaults = {
        "datasource_id": "test-modbus-1",
        "protocol_type": "modbus_tcp",
        "connection_params": {
            "host": "192.168.1.100",
            "port": 502,
            "device_id": 1,
            "timeout": 3,
            "word_order": "big",
        },
        "collection_interval": 5,
        "write_enabled": False,
        "points": [],
    }
    defaults.update(overrides)
    # 将 points 列表中的 dict 转为 PointConfig
    if defaults["points"] and isinstance(defaults["points"][0], dict):
        defaults["points"] = [PointConfig(**p) for p in defaults["points"]]
    return DataSourceConfig(**defaults)


def _mock_client(connected: bool = True):
    """创建 mock AsyncModbusTcpClient"""
    client = AsyncMock()
    type(client).connected = PropertyMock(return_value=connected)
    client.close = MagicMock()
    return client


# ---------------------------------------------------------------------------
# 1. 适配器注册
# ---------------------------------------------------------------------------

class TestAdapterRegistration:
    """测试适配器注册到 ADAPTER_REGISTRY"""

    def test_modbus_tcp_registered(self):
        assert "modbus_tcp" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["modbus_tcp"] is ModbusTcpAdapter


# ---------------------------------------------------------------------------
# 2. 连接/断开生命周期
# ---------------------------------------------------------------------------

class TestConnectDisconnect:
    """测试连接和断开生命周期"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connect_success(self, MockClient):
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        config = _make_config()
        result = await adapter.connect(config)

        assert result is True
        assert adapter._state == AdapterState.CONNECTED
        assert adapter._connected_since is not None
        MockClient.assert_called_once()
        mock_instance.connect.assert_awaited_once()

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connect_failure(self, MockClient):
        mock_instance = _mock_client(connected=False)
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        config = _make_config()
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.DISCONNECTED

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connect_missing_host(self, MockClient):
        adapter = ModbusTcpAdapter()
        config = _make_config(connection_params={"port": 502})
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_reconnect_cleans_old_connection(self, MockClient):
        """重连时应先关闭旧连接"""
        old_client = _mock_client(connected=True)
        new_client = _mock_client(connected=True)
        MockClient.side_effect = [old_client, new_client]

        adapter = ModbusTcpAdapter()
        config = _make_config()

        await adapter.connect(config)
        assert adapter._client is old_client

        # 第二次连接应关闭旧的
        await adapter.connect(config)
        old_client.close.assert_called()
        assert adapter._client is new_client

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_disconnect(self, MockClient):
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())
        await adapter.disconnect()

        assert adapter._state == AdapterState.DISCONNECTED
        assert adapter._client is None
        mock_instance.close.assert_called()


# ---------------------------------------------------------------------------
# 3. 四种寄存器类型读取
# ---------------------------------------------------------------------------

class TestReadRegisterTypes:
    """测试 HR, IR, CO, DI 四种寄存器类型读取"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_read_holding_registers(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [12345]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p1", address="HR:100", data_type="uint16")]
        results = await adapter.read_points(points)

        assert "p1" in results
        assert results["p1"].value == 12345
        assert results["p1"].quality == DataQuality.NORMAL
        mock_instance.read_holding_registers.assert_awaited_once_with(100, count=1, slave=1)

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_read_input_registers(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [500]
        mock_instance.read_input_registers = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p2", address="IR:200", data_type="uint16")]
        results = await adapter.read_points(points)

        assert results["p2"].value == 500
        assert results["p2"].quality == DataQuality.NORMAL

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_read_coils(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.bits = [True, False, False]
        mock_instance.read_coils = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p3", address="CO:0", data_type="bool")]
        results = await adapter.read_points(points)

        assert results["p3"].value is True
        assert results["p3"].quality == DataQuality.NORMAL

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_read_discrete_inputs(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.bits = [False, True]
        mock_instance.read_discrete_inputs = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p4", address="DI:16", data_type="bool")]
        results = await adapter.read_points(points)

        assert results["p4"].value is False
        assert results["p4"].quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 4. 地址越界 → ABNORMAL
# ---------------------------------------------------------------------------

class TestAddressOutOfRange:
    """测试 ExceptionResponse(ILLEGAL_ADDRESS) → DataQuality.ABNORMAL"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_illegal_address_returns_abnormal(self, MockClient):
        from pymodbus.pdu import ExceptionResponse

        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        exc_resp = ExceptionResponse(3, 0x02)  # function_code=3, exception=ILLEGAL_ADDRESS
        mock_instance.read_holding_registers = AsyncMock(return_value=exc_resp)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p_bad", address="HR:99999", data_type="uint16")]
        results = await adapter.read_points(points)

        assert results["p_bad"].quality == DataQuality.ABNORMAL
        assert results["p_bad"].value is None


# ---------------------------------------------------------------------------
# 5. 数据类型转换
# ---------------------------------------------------------------------------

class TestDataTypeConversions:
    """测试各种数据类型转换"""

    def test_int16_positive(self):
        assert _convert_value([100], "int16") == 100

    def test_int16_negative(self):
        # 0xFFFF = 65535 → -1
        assert _convert_value([65535], "int16") == -1
        # 0x8000 = 32768 → -32768
        assert _convert_value([32768], "int16") == -32768

    def test_uint16(self):
        assert _convert_value([65535], "uint16") == 65535
        assert _convert_value([0], "uint16") == 0

    def test_bool_true(self):
        assert _convert_value([True], "bool") is True
        assert _convert_value([1], "bool") is True

    def test_bool_false(self):
        assert _convert_value([False], "bool") is False
        assert _convert_value([0], "bool") is False

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    def test_int32(self, MockClient):
        """int32 使用 convert_from_registers"""
        MockClient.convert_from_registers = MagicMock(return_value=-100000)
        result = _convert_value([0xFFFE, 0x7960], "int32", "big")
        MockClient.convert_from_registers.assert_called_once()
        assert result == -100000

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    def test_uint32(self, MockClient):
        MockClient.convert_from_registers = MagicMock(return_value=100000)
        result = _convert_value([0x0001, 0x86A0], "uint32", "big")
        assert result == 100000

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    def test_float32(self, MockClient):
        MockClient.convert_from_registers = MagicMock(return_value=3.14)
        result = _convert_value([0x4048, 0xF5C3], "float32", "big")
        assert result == pytest.approx(3.14)

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    def test_string(self, MockClient):
        MockClient.convert_from_registers = MagicMock(return_value="AB")
        result = _convert_value([0x4142], "string")
        assert result == "AB"


# ---------------------------------------------------------------------------
# 6. word_order 配置
# ---------------------------------------------------------------------------

class TestWordOrder:
    """测试 word_order 配置传递"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_word_order_little(self, MockClientCls):
        mock_instance = _mock_client()
        MockClientCls.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0x86A0, 0x0001]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        # 使用 little word_order
        config = _make_config(connection_params={
            "host": "192.168.1.100",
            "word_order": "little",
        })

        adapter = ModbusTcpAdapter()
        await adapter.connect(config)

        points = [PointConfig(point_id="p_wo", address="HR:0:2", data_type="int32")]

        with patch.object(
            MockClientCls, "convert_from_registers", return_value=100000
        ) as mock_convert:
            results = await adapter.read_points(points)
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args.kwargs.get("word_order") == "little" or call_args[0][2] == "little" if len(call_args[0]) > 2 else call_args.kwargs.get("word_order") == "little"

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_word_order_big_default(self, MockClientCls):
        """默认 word_order 应为 big"""
        mock_instance = _mock_client()
        MockClientCls.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0x0001, 0x86A0]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        config = _make_config()  # 默认 word_order=big
        adapter = ModbusTcpAdapter()
        await adapter.connect(config)

        points = [PointConfig(point_id="p_big", address="HR:0:2", data_type="uint32")]

        with patch.object(
            MockClientCls, "convert_from_registers", return_value=100000
        ) as mock_convert:
            await adapter.read_points(points)
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args.kwargs.get("word_order") == "big"


# ---------------------------------------------------------------------------
# 7. write_point
# ---------------------------------------------------------------------------

class TestWritePoint:
    """测试写入点位"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_disabled_returns_false(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=False, points=[
            PointConfig(point_id="w1", address="HR:100", data_type="uint16"),
        ])
        await adapter.connect(config)

        result = await adapter.write_point("w1", 42)
        assert result is False

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_enabled_hr_single(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_register = AsyncMock(return_value=write_resp)

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=True, points=[
            PointConfig(point_id="w1", address="HR:100", data_type="uint16"),
        ])
        await adapter.connect(config)

        result = await adapter.write_point("w1", 42)
        assert result is True
        mock_instance.write_register.assert_awaited_once_with(100, 42, slave=1)

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_coil(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_coil = AsyncMock(return_value=write_resp)

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=True, points=[
            PointConfig(point_id="c1", address="CO:5", data_type="bool"),
        ])
        await adapter.connect(config)

        result = await adapter.write_point("c1", True)
        assert result is True
        mock_instance.write_coil.assert_awaited_once_with(5, True, slave=1)

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_multi_register_float32(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_registers = AsyncMock(return_value=write_resp)

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=True, points=[
            PointConfig(point_id="f1", address="HR:200:2", data_type="float32"),
        ])
        await adapter.connect(config)

        with patch.object(
            MockClient, "convert_to_registers", return_value=[0x4048, 0xF5C3]
        ):
            result = await adapter.write_point("f1", 3.14)
            assert result is True
            mock_instance.write_registers.assert_awaited_once()

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_unknown_point_returns_false(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=True, points=[])
        await adapter.connect(config)

        result = await adapter.write_point("nonexistent", 42)
        assert result is False

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_ir_rejected(self, MockClient):
        """IR (Input Register) 是只读的，写入应返回 False"""
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        config = _make_config(write_enabled=True, points=[
            PointConfig(point_id="ir1", address="IR:100", data_type="uint16"),
        ])
        await adapter.connect(config)

        result = await adapter.write_point("ir1", 42)
        assert result is False

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_write_multi_register_word_order(self, MockClient):
        """写入多寄存器时 word_order 应正确传递"""
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_registers = AsyncMock(return_value=write_resp)

        config = _make_config(
            write_enabled=True,
            connection_params={"host": "192.168.1.100", "word_order": "little"},
            points=[
                PointConfig(point_id="f1", address="HR:200:2", data_type="float32"),
            ],
        )

        adapter = ModbusTcpAdapter()
        await adapter.connect(config)

        with patch.object(
            MockClient, "convert_to_registers", return_value=[0xF5C3, 0x4048]
        ) as mock_convert:
            await adapter.write_point("f1", 3.14)
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args.kwargs.get("word_order") == "little"


# ---------------------------------------------------------------------------
# 8. test_connection
# ---------------------------------------------------------------------------

class TestTestConnection:
    """测试连接测试功能"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connection_success_with_latency(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [42]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.sample_data == {"register_0": 42}

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connection_failure_error_message(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        mock_instance.read_holding_registers = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is False
        assert "Connection refused" in result.message

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connection_timeout_10s(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        async def slow_read(*args, **kwargs):
            await asyncio.sleep(15)  # 超过 10s 超时

        mock_instance.read_holding_registers = slow_read

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is False
        assert "超时" in result.message or "timeout" in result.message.lower()

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connection_auto_connect_if_disconnected(self, MockClient):
        """未连接时 test_connection 应先尝试连接"""
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        adapter._config = _make_config()
        # 不调用 connect，直接 test_connection
        adapter._client = None

        result = await adapter.test_connection()
        assert result.success is True


# ---------------------------------------------------------------------------
# 9. 地址解析
# ---------------------------------------------------------------------------

class TestAddressParsing:
    """测试地址格式解析"""

    def test_valid_hr(self):
        reg_type, addr, count = _parse_address("HR:100", "uint16")
        assert reg_type == "HR"
        assert addr == 100
        assert count == 1

    def test_valid_ir_with_count(self):
        reg_type, addr, count = _parse_address("IR:200:2", "int32")
        assert reg_type == "IR"
        assert addr == 200
        assert count == 2

    def test_valid_co(self):
        reg_type, addr, count = _parse_address("CO:0", "bool")
        assert reg_type == "CO"
        assert addr == 0
        assert count == 1

    def test_valid_di(self):
        reg_type, addr, count = _parse_address("DI:16", "bool")
        assert reg_type == "DI"
        assert addr == 16
        assert count == 1

    def test_case_insensitive(self):
        reg_type, addr, count = _parse_address("hr:50", "uint16")
        assert reg_type == "HR"

    def test_invalid_format_no_colon(self):
        with pytest.raises(ValueError, match="无效地址格式"):
            _parse_address("HR100", "uint16")

    def test_invalid_register_type(self):
        with pytest.raises(ValueError, match="未知寄存器类型"):
            _parse_address("XX:100", "uint16")

    def test_invalid_address_not_int(self):
        with pytest.raises(ValueError, match="无效寄存器地址"):
            _parse_address("HR:abc", "uint16")

    def test_string_requires_explicit_count(self):
        with pytest.raises(ValueError, match="string 类型必须显式指定"):
            _parse_address("HR:100", "string")

    def test_string_with_count_ok(self):
        reg_type, addr, count = _parse_address("HR:100:4", "string")
        assert count == 4

    def test_float32_default_count(self):
        _, _, count = _parse_address("HR:0", "float32")
        assert count == 2

    def test_int32_default_count(self):
        _, _, count = _parse_address("HR:0", "int32")
        assert count == 2


# ---------------------------------------------------------------------------
# 补充: 单点失败不影响其他点位
# ---------------------------------------------------------------------------

class TestSinglePointFailureIsolation:
    """单点失败不应中断整个 read_points"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_one_fails_others_succeed(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        from pymodbus.pdu import ExceptionResponse

        good_resp = MagicMock()
        good_resp.isError.return_value = False
        good_resp.registers = [42]

        bad_resp = ExceptionResponse(3, 0x02)

        mock_instance.read_holding_registers = AsyncMock(
            side_effect=[good_resp, bad_resp, good_resp]
        )

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        points = [
            PointConfig(point_id="ok1", address="HR:0", data_type="uint16"),
            PointConfig(point_id="bad", address="HR:99999", data_type="uint16"),
            PointConfig(point_id="ok2", address="HR:1", data_type="uint16"),
        ]
        results = await adapter.read_points(points)

        assert len(results) == 3
        assert results["ok1"].quality == DataQuality.NORMAL
        assert results["bad"].quality == DataQuality.ABNORMAL
        assert results["ok2"].quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 补充: 自动类型转换标记 UNRELIABLE
# ---------------------------------------------------------------------------

class TestAutoConversionQuality:
    """类型转换失败后自动转 float 应标记 UNRELIABLE"""

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_auto_convert_marks_unreliable(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [12345]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        # 使用不支持的 data_type 触发 _convert_value 失败 → 自动转 float
        points = [PointConfig(point_id="p_auto", address="HR:0", data_type="uint16")]

        # Patch _convert_value to raise, forcing auto-conversion path
        with patch("gateway.adapters.modbus_tcp._convert_value", side_effect=ValueError("mock")):
            results = await adapter.read_points(points)

        assert results["p_auto"].value == 12345.0
        assert results["p_auto"].quality == DataQuality.UNRELIABLE


# ---------------------------------------------------------------------------
# 补充: get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """测试 get_status 返回"""

    def test_initial_status(self):
        adapter = ModbusTcpAdapter()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None
        assert status.consecutive_failures == 0

    @patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient")
    async def test_connected_status(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusTcpAdapter()
        await adapter.connect(_make_config())

        status = adapter.get_status()
        assert status.state == AdapterState.CONNECTED
        assert status.connected_since is not None
