"""SNMP v2c/v3 适配器单元测试 — Story 1.4"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.adapters.base import (
    AdapterState,
    DataQuality,
    DataSourceConfig,
    PointConfig,
)
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.adapters.snmp import (
    SnmpAdapter,
    _parse_oid,
    _normalize_value,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """保存/恢复 ADAPTER_REGISTRY，避免测试间污染"""
    original = ADAPTER_REGISTRY.copy()
    yield
    ADAPTER_REGISTRY.clear()
    ADAPTER_REGISTRY.update(original)


@pytest.fixture(autouse=True)
def _mock_transport():
    """Mock UdpTransportTarget.create — 避免真实 DNS 解析"""
    mock_transport = MagicMock(spec=["__call__"])
    with patch(
        "gateway.adapters.snmp.UdpTransportTarget.create",
        new_callable=AsyncMock,
        return_value=mock_transport,
    ):
        yield mock_transport


def _make_config(protocol_type: str = "snmp_v2c", **overrides) -> DataSourceConfig:
    """创建测试用 DataSourceConfig"""
    if protocol_type == "snmp_v2c":
        default_params = {
            "host": "192.168.1.100",
            "port": 161,
            "community": "public",
            "timeout": 5,
        }
    else:
        default_params = {
            "host": "192.168.1.100",
            "port": 161,
            "username": "snmpuser",
            "auth_protocol": "SHA",
            "auth_key": "authpass123",
            "priv_protocol": "AES",
            "priv_key": "privpass123",
            "timeout": 5,
        }

    params = overrides.pop("connection_params", default_params)
    defaults = {
        "datasource_id": "test-snmp-1",
        "protocol_type": protocol_type,
        "connection_params": params,
        "collection_interval": 5,
        "write_enabled": False,
        "points": [],
    }
    defaults.update(overrides)
    if defaults["points"] and isinstance(defaults["points"][0], dict):
        defaults["points"] = [PointConfig(**p) for p in defaults["points"]]
    return DataSourceConfig(**defaults)


def _mock_var_bind(oid_str: str, value):
    """创建模拟的 var_bind (oid, value) 元组"""
    oid = MagicMock()
    oid.prettyPrint.return_value = oid_str
    if not hasattr(value, "prettyPrint"):
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = str(value)
        # 确保不是 NoSuchObject/NoSuchInstance
        mock_val.__class__ = type(value) if isinstance(value, type) else type("MockVal", (), {})
        return (oid, mock_val)
    return (oid, value)


def _success_response(var_binds):
    """构造成功的 getCmd 返回值"""
    return (None, 0, 0, var_binds)


def _error_response(error_indication, var_binds=None):
    """构造错误的 getCmd 返回值"""
    return (error_indication, 0, 0, var_binds or [])


# ---------------------------------------------------------------------------
# 6.1: 适配器注册
# ---------------------------------------------------------------------------


class TestAdapterRegistration:
    """测试适配器双注册到 ADAPTER_REGISTRY"""

    def test_snmp_v2c_registered(self):
        assert "snmp_v2c" in ADAPTER_REGISTRY

    def test_snmp_v3_registered(self):
        assert "snmp_v3" in ADAPTER_REGISTRY

    def test_same_class(self):
        assert ADAPTER_REGISTRY["snmp_v2c"] is ADAPTER_REGISTRY["snmp_v3"]
        assert ADAPTER_REGISTRY["snmp_v2c"] is SnmpAdapter


# ---------------------------------------------------------------------------
# 6.2: v2c connect/disconnect 生命周期
# ---------------------------------------------------------------------------


class TestV2cConnectDisconnect:
    """测试 v2c 连接和断开生命周期"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v2c_connect_success(self, mock_get_cmd):
        """v2c 连接成功 — sysDescr 读取正常"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux server"
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        config = _make_config("snmp_v2c")
        result = await adapter.connect(config)

        assert result is True
        assert adapter._state == AdapterState.CONNECTED
        assert adapter._connected_since is not None
        assert adapter._engine is not None
        mock_get_cmd.assert_awaited_once()

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v2c_disconnect(self, mock_get_cmd):
        """v2c 断开连接"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux"
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))
        assert adapter._state == AdapterState.CONNECTED

        await adapter.disconnect()
        assert adapter._state == AdapterState.DISCONNECTED
        assert adapter._engine is None
        assert adapter._connected_since is None

    async def test_v2c_connect_missing_host(self):
        """v2c 缺少 host 参数"""
        adapter = SnmpAdapter()
        config = _make_config("snmp_v2c", connection_params={"port": 161})
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR


# ---------------------------------------------------------------------------
# 6.3: v3 connect/disconnect 生命周期
# ---------------------------------------------------------------------------


class TestV3ConnectDisconnect:
    """测试 v3 连接和断开生命周期"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v3_connect_success(self, mock_get_cmd):
        """v3 authPriv 连接成功"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Cisco IOS"
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        config = _make_config("snmp_v3")
        result = await adapter.connect(config)

        assert result is True
        assert adapter._state == AdapterState.CONNECTED
        mock_get_cmd.assert_awaited_once()

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v3_disconnect(self, mock_get_cmd):
        """v3 断开连接"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Cisco"
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v3"))
        await adapter.disconnect()

        assert adapter._state == AdapterState.DISCONNECTED
        assert adapter._engine is None


# ---------------------------------------------------------------------------
# 6.4: v3 安全级别校验
# ---------------------------------------------------------------------------


class TestV3SecurityValidation:
    """测试 v3 安全级别校验"""

    async def test_priv_without_auth_raises_error(self):
        """提供 priv 但未提供 auth → 报错"""
        adapter = SnmpAdapter()
        config = _make_config(
            "snmp_v3",
            connection_params={
                "host": "192.168.1.100",
                "username": "user1",
                "priv_protocol": "AES",
                "priv_key": "privpass",
            },
        )
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR
        assert "加密需要先启用认证" in adapter._error_message


# ---------------------------------------------------------------------------
# 6.5: GET 操作
# ---------------------------------------------------------------------------


class TestGetOperation:
    """测试 GET 操作读取单个 OID"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_get_single_oid(self, mock_get_cmd):
        """GET 读取单个 OID 成功"""
        # connect 调用
        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"
        # read 调用 — 返回温度值 25.5
        mock_val_read = MagicMock()
        mock_val_read.prettyPrint.return_value = "25.5"
        mock_val_read.__class__ = type("Integer", (), {})

        mock_get_cmd.side_effect = [
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]),
            _success_response([(_mock_var_bind(".1.3.6.1.4.1.1.1.0", "x")[0], mock_val_read)]),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="temp1", address="get:.1.3.6.1.4.1.1.1.0", data_type="float")]
        results = await adapter.read_points(points)

        assert "temp1" in results
        assert results["temp1"].value == 25.5
        assert results["temp1"].quality == DataQuality.NORMAL

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_get_bare_oid(self, mock_get_cmd):
        """无前缀 OID 默认为 GET"""
        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"
        mock_val_read = MagicMock()
        mock_val_read.prettyPrint.return_value = "42"
        mock_val_read.__class__ = type("Integer", (), {})

        mock_get_cmd.side_effect = [
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]),
            _success_response([(_mock_var_bind(".1.3.6.1.4.1.1.1.0", "x")[0], mock_val_read)]),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="p1", address=".1.3.6.1.4.1.1.1.0", data_type="int")]
        results = await adapter.read_points(points)

        assert results["p1"].value == 42.0
        assert results["p1"].quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 6.6: WALK 操作
# ---------------------------------------------------------------------------


class TestWalkOperation:
    """测试 WALK 操作遍历子树"""

    @patch("gateway.adapters.snmp.bulk_walk_cmd")
    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_walk_takes_first_leaf(self, mock_get_cmd, mock_walk_cmd):
        """WALK 取第一个叶子节点的值"""
        # connect
        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"
        mock_get_cmd.return_value = _success_response(
            [(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]
        )

        # walk 返回 async iterator
        mock_val1 = MagicMock()
        mock_val1.prettyPrint.return_value = "100"
        mock_val1.__class__ = type("Integer", (), {})
        mock_val2 = MagicMock()
        mock_val2.prettyPrint.return_value = "200"
        mock_val2.__class__ = type("Integer", (), {})

        oid1 = MagicMock()
        oid2 = MagicMock()

        async def mock_walk_gen(*args, **kwargs):
            yield (None, 0, 0, [(oid1, mock_val1)])
            yield (None, 0, 0, [(oid2, mock_val2)])

        mock_walk_cmd.return_value = mock_walk_gen()

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="w1", address="walk:.1.3.6.1.2.1.1", data_type="int")]
        results = await adapter.read_points(points)

        assert "w1" in results
        assert results["w1"].value == 100.0  # 取第一个叶子
        assert results["w1"].quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 6.7: 认证失败
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """测试认证失败错误提示"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v2c_timeout_mentions_community(self, mock_get_cmd):
        """v2c 超时提示包含团体名"""
        mock_get_cmd.return_value = _error_response("requestTimedOut")

        adapter = SnmpAdapter()
        config = _make_config("snmp_v2c")
        result = await adapter.connect(config)

        assert result is False
        assert "团体名" in adapter._error_message

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_v3_auth_failure_precise(self, mock_get_cmd):
        """v3 认证失败精确提示"""
        mock_get_cmd.return_value = _error_response("unknownUserName")

        adapter = SnmpAdapter()
        config = _make_config("snmp_v3")
        result = await adapter.connect(config)

        assert result is False
        assert adapter._state == AdapterState.CONFIG_ERROR
        assert "认证失败" in adapter._error_message


# ---------------------------------------------------------------------------
# 6.8: OID 不存在
# ---------------------------------------------------------------------------


class TestOidNotFound:
    """测试 OID 不存在处理"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_no_such_object_skips_point(self, mock_get_cmd):
        """NoSuchObject → 跳过 + warning + ABNORMAL"""
        from pysnmp.hlapi.asyncio import NoSuchObject as RealNoSuchObject

        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"

        no_such = RealNoSuchObject()

        mock_get_cmd.side_effect = [
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]),
            _success_response([(_mock_var_bind(".1.3.6.1.4.1.999.0", "x")[0], no_such)]),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="missing", address=".1.3.6.1.4.1.999.0", data_type="int")]
        results = await adapter.read_points(points)

        assert results["missing"].quality == DataQuality.ABNORMAL
        assert results["missing"].value is None

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_no_such_instance_skips_point(self, mock_get_cmd):
        """NoSuchInstance → 跳过 + ABNORMAL"""
        from pysnmp.hlapi.asyncio import NoSuchInstance as RealNoSuchInstance

        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"

        no_such = RealNoSuchInstance()

        mock_get_cmd.side_effect = [
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]),
            _success_response([(_mock_var_bind(".1.3.6.1.4.1.999.0", "x")[0], no_such)]),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="missing2", address=".1.3.6.1.4.1.999.0", data_type="int")]
        results = await adapter.read_points(points)

        assert results["missing2"].quality == DataQuality.ABNORMAL


# ---------------------------------------------------------------------------
# 6.9: 超时重试
# ---------------------------------------------------------------------------


class TestTimeoutRetry:
    """测试超时重试 1 次 → UNRELIABLE"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_timeout_retry_then_unreliable(self, mock_get_cmd):
        """GET 超时重试一次，仍失败 → UNRELIABLE"""
        mock_val_connect = MagicMock()
        mock_val_connect.prettyPrint.return_value = "Linux"

        mock_get_cmd.side_effect = [
            # connect 成功
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val_connect)]),
            # 第一次 GET 超时
            _error_response("requestTimedOut"),
            # 重试仍超时
            _error_response("requestTimedOut"),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        points = [PointConfig(point_id="slow", address=".1.3.6.1.4.1.1.1.0", data_type="int")]
        results = await adapter.read_points(points)

        assert results["slow"].quality == DataQuality.UNRELIABLE
        assert results["slow"].value is None
        # getCmd 被调用 3 次: connect + first try + retry
        assert mock_get_cmd.await_count == 3


# ---------------------------------------------------------------------------
# 6.10: 数据归一化
# ---------------------------------------------------------------------------


class TestDataNormalization:
    """测试数据归一化（scale、offset、enum_mapping）"""

    def test_scale_and_offset(self):
        """scale=0.1, offset=10 → 25.5*0.1+10 = 12.55"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "25.5"
        point = PointConfig(point_id="t1", address=".1.0", data_type="float", scale=0.1, offset=10.0)
        value, quality = _normalize_value(mock_val, point)
        assert value == pytest.approx(12.55)
        assert quality == DataQuality.NORMAL

    def test_enum_mapping(self):
        """枚举映射: 数值 1 → '运行'"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "1"
        point = PointConfig(
            point_id="s1",
            address=".1.0",
            data_type="int",
            enum_mapping={"1": "运行", "0": "停止"},
        )
        value, quality = _normalize_value(mock_val, point)
        assert value == "运行"
        assert quality == DataQuality.NORMAL

    def test_string_enum_mapping(self):
        """字符串枚举映射"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "active"
        point = PointConfig(
            point_id="s2",
            address=".1.0",
            data_type="string",
            enum_mapping={"active": "活跃", "inactive": "不活跃"},
        )
        value, quality = _normalize_value(mock_val, point)
        assert value == "活跃"
        assert quality == DataQuality.NORMAL

    def test_default_scale_offset(self):
        """默认 scale=1.0, offset=0.0 → 原值"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "42"
        point = PointConfig(point_id="d1", address=".1.0", data_type="int")
        value, quality = _normalize_value(mock_val, point)
        assert value == 42.0
        assert quality == DataQuality.NORMAL


# ---------------------------------------------------------------------------
# 6.11: write_point 始终返回 False
# ---------------------------------------------------------------------------


class TestWritePoint:
    """测试 write_point 始终返回 False"""

    async def test_write_always_false(self):
        adapter = SnmpAdapter()
        result = await adapter.write_point("any_point", 42)
        assert result is False


# ---------------------------------------------------------------------------
# 6.12: test_connection
# ---------------------------------------------------------------------------


class TestTestConnection:
    """测试 test_connection 含 10 秒超时"""

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_connection_success(self, mock_get_cmd):
        """test_connection 成功返回 sysDescr"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux server 5.4"

        # connect + test_connection 各调用一次 getCmd
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        result = await adapter.test_connection()
        assert result.success is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.sample_data["sysDescr"] == "Linux server 5.4"

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_connection_timeout_10s(self, mock_get_cmd):
        """test_connection 超时 10 秒"""
        # connect 成功
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux"

        call_count = 0

        async def slow_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # connect 调用正常返回
                return _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])
            # test_connection 调用超时
            await asyncio.sleep(15)

        mock_get_cmd.side_effect = slow_get

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        result = await adapter.test_connection()
        assert result.success is False
        assert "超时" in result.message or "10s" in result.message


# ---------------------------------------------------------------------------
# 6.13: get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    """测试 get_status 返回正确 AdapterStatus"""

    def test_initial_status(self):
        adapter = SnmpAdapter()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None
        assert status.consecutive_failures == 0
        assert status.error_message is None

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_connected_status(self, mock_get_cmd):
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux"
        mock_get_cmd.return_value = _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)])

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))

        status = adapter.get_status()
        assert status.state == AdapterState.CONNECTED
        assert status.connected_since is not None
        assert status.consecutive_failures == 0

    @patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
    async def test_status_after_read(self, mock_get_cmd):
        """读取后 last_read_time 应更新"""
        mock_val = MagicMock()
        mock_val.prettyPrint.return_value = "Linux"
        mock_val_read = MagicMock()
        mock_val_read.prettyPrint.return_value = "42"
        mock_val_read.__class__ = type("Integer", (), {})

        mock_get_cmd.side_effect = [
            _success_response([(_mock_var_bind(".1.3.6.1.2.1.1.1.0", "x")[0], mock_val)]),
            _success_response([(_mock_var_bind(".1.3.6.1.4.1.1.0", "x")[0], mock_val_read)]),
        ]

        adapter = SnmpAdapter()
        await adapter.connect(_make_config("snmp_v2c"))
        assert adapter.get_status().last_read_time is None

        points = [PointConfig(point_id="p1", address=".1.3.6.1.4.1.1.0", data_type="int")]
        await adapter.read_points(points)

        status = adapter.get_status()
        assert status.last_read_time is not None


# ---------------------------------------------------------------------------
# 补充: _parse_oid 解析
# ---------------------------------------------------------------------------


class TestParseOid:
    """测试 OID 地址解析"""

    def test_get_prefix(self):
        op, oid = _parse_oid("get:.1.3.6.1.2.1.1.1.0")
        assert op == "get"
        assert oid == ".1.3.6.1.2.1.1.1.0"

    def test_walk_prefix(self):
        op, oid = _parse_oid("walk:.1.3.6.1.2.1.1")
        assert op == "walk"
        assert oid == ".1.3.6.1.2.1.1"

    def test_bare_oid_defaults_to_get(self):
        op, oid = _parse_oid(".1.3.6.1.2.1.1.1.0")
        assert op == "get"
        assert oid == ".1.3.6.1.2.1.1.1.0"
