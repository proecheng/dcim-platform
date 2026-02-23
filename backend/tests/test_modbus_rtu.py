"""Modbus RTU 适配器单元测试 — Story 1.3"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from serial import SerialException

from gateway.adapters.base import (
    AdapterState,
    DataQuality,
    DataSourceConfig,
    PointConfig,
)
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.adapters.modbus_rtu import ModbusRtuAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """保存/恢复 ADAPTER_REGISTRY，避免测试间污染"""
    original = ADAPTER_REGISTRY.copy()
    if "modbus_rtu" not in ADAPTER_REGISTRY:
        ADAPTER_REGISTRY["modbus_rtu"] = ModbusRtuAdapter
    yield
    ADAPTER_REGISTRY.clear()
    ADAPTER_REGISTRY.update(original)


def _make_config(**overrides) -> DataSourceConfig:
    """创建测试用 DataSourceConfig"""
    defaults = {
        "datasource_id": "test-rtu-1",
        "protocol_type": "modbus_rtu",
        "connection_params": {
            "port": "COM3",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "device_id": 1,
            "timeout": 3,
            "word_order": "big",
        },
        "collection_interval": 5,
        "write_enabled": False,
        "points": [],
    }
    defaults.update(overrides)
    if defaults["points"] and isinstance(defaults["points"][0], dict):
        defaults["points"] = [PointConfig(**p) for p in defaults["points"]]
    return DataSourceConfig(**defaults)


def _mock_client(connected: bool = True):
    """创建 mock AsyncModbusSerialClient"""
    client = AsyncMock()
    type(client).connected = PropertyMock(return_value=connected)
    client.close = MagicMock()
    return client


# ---------------------------------------------------------------------------
# 1. 适配器注册
# ---------------------------------------------------------------------------


class TestAdapterRegistration:
    """测试适配器注册到 ADAPTER_REGISTRY"""

    def test_modbus_rtu_registered(self):
        assert "modbus_rtu" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["modbus_rtu"] is ModbusRtuAdapter


# ---------------------------------------------------------------------------
# 2. 连接/断开生命周期
# ---------------------------------------------------------------------------


class TestConnectDisconnect:
    """测试连接和断开生命周期"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connect_success(self, MockClient):
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        config = _make_config()
        result = await adapter.connect(config)

        assert result is True
        assert adapter._state == AdapterState.CONNECTED
        assert adapter._connected_since is not None
        MockClient.assert_called_once()
        mock_instance.connect.assert_awaited_once()

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connect_failure(self, MockClient):
        mock_instance = _mock_client(connected=False)
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        config = _make_config()
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.DISCONNECTED

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connect_missing_port(self, MockClient):
        adapter = ModbusRtuAdapter()
        config = _make_config(connection_params={"baudrate": 9600})
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_reconnect_cleans_old_connection(self, MockClient):
        """重连时应先关闭旧连接"""
        old_client = _mock_client(connected=True)
        new_client = _mock_client(connected=True)
        MockClient.side_effect = [old_client, new_client]

        adapter = ModbusRtuAdapter()
        config = _make_config()

        await adapter.connect(config)
        assert adapter._client is old_client

        await adapter.connect(config)
        old_client.close.assert_called()
        assert adapter._client is new_client

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_disconnect(self, MockClient):
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())
        await adapter.disconnect()

        assert adapter._state == AdapterState.DISCONNECTED
        assert adapter._client is None
        mock_instance.close.assert_called()


# ---------------------------------------------------------------------------
# 3. 串口被占用 → CONFIG_ERROR
# ---------------------------------------------------------------------------


class TestSerialPortBusy:
    """测试串口被占用或不存在时的错误处理"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_serial_exception_config_error(self, MockClient):
        MockClient.side_effect = SerialException("Port COM3 is busy")

        adapter = ModbusRtuAdapter()
        result = await adapter.connect(_make_config())

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR
        assert adapter._error_message is not None

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_permission_error_config_error(self, MockClient):
        MockClient.side_effect = PermissionError("Access denied")

        adapter = ModbusRtuAdapter()
        result = await adapter.connect(_make_config())

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR


# ---------------------------------------------------------------------------
# 4. 四种寄存器类型读取
# ---------------------------------------------------------------------------


class TestReadRegisterTypes:
    """测试 HR, IR, CO, DI 四种寄存器类型读取"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_read_holding_registers(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [12345]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p1", address="HR:100", data_type="uint16")]
        results = await adapter.read_points(points)

        assert "p1" in results
        assert results["p1"].value == 12345
        assert results["p1"].quality == DataQuality.NORMAL
        mock_instance.read_holding_registers.assert_awaited_once_with(100, count=1, slave=1)

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_read_input_registers(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [500]
        mock_instance.read_input_registers = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p2", address="IR:200", data_type="uint16")]
        results = await adapter.read_points(points)

        assert results["p2"].value == 500
        assert results["p2"].quality == DataQuality.NORMAL

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_read_coils(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.bits = [True, False, False]
        mock_instance.read_coils = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p3", address="CO:0", data_type="bool")]
        results = await adapter.read_points(points)

        assert results["p3"].value is True
        assert results["p3"].quality == DataQuality.NORMAL

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_read_discrete_inputs(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.bits = [False, True]
        mock_instance.read_discrete_inputs = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p4", address="DI:16", data_type="bool")]
        results = await adapter.read_points(points)

        assert results["p4"].value is False
        assert results["p4"].quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 5. 读取超时重试 → UNRELIABLE
# ---------------------------------------------------------------------------


class TestReadTimeoutRetry:
    """测试读取超时重试一次，第二次仍失败返回 UNRELIABLE/ABNORMAL"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_timeout_retry_then_abnormal(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        # 两次都超时
        mock_instance.read_holding_registers = AsyncMock(side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError()])

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p_timeout", address="HR:0", data_type="uint16")]
        results = await adapter.read_points(points)

        assert results["p_timeout"].quality == DataQuality.ABNORMAL
        assert results["p_timeout"].value is None

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_timeout_retry_then_success(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        good_resp = MagicMock()
        good_resp.isError.return_value = False
        good_resp.registers = [42]

        # 第一次超时，第二次成功
        mock_instance.read_holding_registers = AsyncMock(side_effect=[asyncio.TimeoutError(), good_resp])

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        points = [PointConfig(point_id="p_retry", address="HR:0", data_type="uint16")]
        results = await adapter.read_points(points)

        assert results["p_retry"].quality == DataQuality.NORMAL
        assert results["p_retry"].value == 42


# ---------------------------------------------------------------------------
# 6. CRC 连续失败 3 次 → 日志警告
# ---------------------------------------------------------------------------


class TestCrcFailureDetection:
    """测试 CRC 失败检测和日志警告"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_crc_failure_3_consecutive_logs_warning(self, MockClient, caplog):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        # isError() 返回 True 但不是 ExceptionResponse → CRC 错误
        crc_error_resp = MagicMock()
        crc_error_resp.isError.return_value = True

        # 每次读取都返回 CRC 错误（初始 + 重试 = 2 次调用/点位）
        mock_instance.read_holding_registers = AsyncMock(return_value=crc_error_resp)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        # 读取 3 个点位，每个都 CRC 失败
        points = [
            PointConfig(point_id="p1", address="HR:0", data_type="uint16"),
            PointConfig(point_id="p2", address="HR:1", data_type="uint16"),
            PointConfig(point_id="p3", address="HR:2", data_type="uint16"),
        ]

        with caplog.at_level(logging.ERROR, logger="gateway.adapters.modbus_rtu"):
            results = await adapter.read_points(points)

        # 所有点位应为 UNRELIABLE
        for pid in ("p1", "p2", "p3"):
            assert results[pid].quality == DataQuality.UNRELIABLE

        # 应有关于检查串口参数的日志
        assert any("串口参数" in record.message or "波特率" in record.message for record in caplog.records)

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_crc_count_resets_on_success(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        good_resp = MagicMock()
        good_resp.isError.return_value = False
        good_resp.registers = [100]

        mock_instance.read_holding_registers = AsyncMock(return_value=good_resp)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())
        adapter._crc_failure_count = 2  # 模拟之前有 2 次 CRC 失败

        points = [PointConfig(point_id="p_ok", address="HR:0", data_type="uint16")]
        await adapter.read_points(points)

        assert adapter._crc_failure_count == 0


# ---------------------------------------------------------------------------
# 7. 写入 (HR/CO 允许, IR/DI 拒绝, write_enabled 检查)
# ---------------------------------------------------------------------------


class TestWritePoint:
    """测试写入点位"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_disabled_returns_false(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=False,
            points=[
                PointConfig(point_id="w1", address="HR:100", data_type="uint16"),
            ],
        )
        await adapter.connect(config)

        result = await adapter.write_point("w1", 42)
        assert result is False

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_hr_single(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_register = AsyncMock(return_value=write_resp)

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=True,
            points=[
                PointConfig(point_id="w1", address="HR:100", data_type="uint16"),
            ],
        )
        await adapter.connect(config)

        result = await adapter.write_point("w1", 42)
        assert result is True
        mock_instance.write_register.assert_awaited_once_with(100, 42, slave=1)

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_coil(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_coil = AsyncMock(return_value=write_resp)

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=True,
            points=[
                PointConfig(point_id="c1", address="CO:5", data_type="bool"),
            ],
        )
        await adapter.connect(config)

        result = await adapter.write_point("c1", True)
        assert result is True
        mock_instance.write_coil.assert_awaited_once_with(5, True, slave=1)

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_ir_rejected(self, MockClient):
        """IR (Input Register) 是只读的，写入应返回 False"""
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=True,
            points=[
                PointConfig(point_id="ir1", address="IR:100", data_type="uint16"),
            ],
        )
        await adapter.connect(config)

        result = await adapter.write_point("ir1", 42)
        assert result is False

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_di_rejected(self, MockClient):
        """DI (Discrete Input) 是只读的，写入应返回 False"""
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=True,
            points=[
                PointConfig(point_id="di1", address="DI:0", data_type="bool"),
            ],
        )
        await adapter.connect(config)

        result = await adapter.write_point("di1", True)
        assert result is False

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_write_multi_register_float32(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        write_resp = MagicMock()
        write_resp.isError.return_value = False
        mock_instance.write_registers = AsyncMock(return_value=write_resp)

        adapter = ModbusRtuAdapter()
        config = _make_config(
            write_enabled=True,
            points=[
                PointConfig(point_id="f1", address="HR:200:2", data_type="float32"),
            ],
        )
        await adapter.connect(config)

        with patch.object(MockClient, "convert_to_registers", return_value=[0x4048, 0xF5C3]):
            result = await adapter.write_point("f1", 3.14)
            assert result is True
            mock_instance.write_registers.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. test_connection (成功、失败、10s 超时)
# ---------------------------------------------------------------------------


class TestTestConnection:
    """测试连接测试功能"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connection_success_with_latency(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [42]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.sample_data == {"register_0": 42}

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connection_failure_error_message(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        mock_instance.read_holding_registers = AsyncMock(side_effect=Exception("Connection refused"))

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is False
        assert "Connection refused" in result.message

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connection_timeout_10s(self, MockClient):
        mock_instance = _mock_client()
        MockClient.return_value = mock_instance

        async def slow_read(*args, **kwargs):
            await asyncio.sleep(15)

        mock_instance.read_holding_registers = slow_read

        adapter = ModbusRtuAdapter()
        await adapter.connect(_make_config())

        result = await adapter.test_connection()
        assert result.success is False
        assert "超时" in result.message or "timeout" in result.message.lower()

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_connection_auto_connect_if_disconnected(self, MockClient):
        """未连接时 test_connection 应先尝试连接"""
        mock_instance = _mock_client(connected=True)
        MockClient.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        adapter = ModbusRtuAdapter()
        adapter._config = _make_config()
        adapter._client = None

        result = await adapter.test_connection()
        assert result.success is True


# ---------------------------------------------------------------------------
# 9. word_order 配置传递
# ---------------------------------------------------------------------------


class TestWordOrder:
    """测试 word_order 配置传递到 convert_from_registers"""

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_word_order_little(self, MockClientCls):
        mock_instance = _mock_client()
        MockClientCls.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0x86A0, 0x0001]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        config = _make_config(
            connection_params={
                "port": "COM3",
                "word_order": "little",
            }
        )

        adapter = ModbusRtuAdapter()
        await adapter.connect(config)

        points = [PointConfig(point_id="p_wo", address="HR:0:2", data_type="int32")]

        with patch(
            "gateway.adapters.modbus_tcp.AsyncModbusTcpClient.convert_from_registers",
            return_value=100000,
        ) as mock_convert:
            results = await adapter.read_points(points)
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args.kwargs.get("word_order") == "little"

    @patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
    async def test_word_order_big_default(self, MockClientCls):
        """默认 word_order 应为 big"""
        mock_instance = _mock_client()
        MockClientCls.return_value = mock_instance

        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0x0001, 0x86A0]
        mock_instance.read_holding_registers = AsyncMock(return_value=response)

        config = _make_config()
        adapter = ModbusRtuAdapter()
        await adapter.connect(config)

        points = [PointConfig(point_id="p_big", address="HR:0:2", data_type="uint32")]

        with patch(
            "gateway.adapters.modbus_tcp.AsyncModbusTcpClient.convert_from_registers",
            return_value=100000,
        ) as mock_convert:
            await adapter.read_points(points)
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args.kwargs.get("word_order") == "big"
