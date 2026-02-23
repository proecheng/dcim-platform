"""OPC-UA 适配器测试 — Story 15.4"""

import asyncio
import sys
import os
import importlib.util
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# 确保 gateway 根目录在 sys.path
_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _root)


def _load_module(name: str, filepath: str) -> types.ModuleType:
    """直接加载 .py 文件为模块，绕过 __init__.py"""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 按依赖顺序加载，绕过 gateway/adapters/__init__.py
_gw_dir = os.path.join(_root, "gateway", "adapters")
_base = _load_module("gateway.adapters.base", os.path.join(_gw_dir, "base.py"))
_registry = _load_module("gateway.adapters.registry", os.path.join(_gw_dir, "registry.py"))
_opc_ua = _load_module("gateway.adapters.opc_ua", os.path.join(_gw_dir, "opc_ua.py"))

AdapterState = _base.AdapterState
DataQuality = _base.DataQuality
DataSourceConfig = _base.DataSourceConfig
PointConfig = _base.PointConfig
PointValue = _base.PointValue
ConnectionResult = _base.ConnectionResult
ADAPTER_REGISTRY = _registry.ADAPTER_REGISTRY
OpcUaAdapter = _opc_ua.OpcUaAdapter
validate_node_id = _opc_ua.validate_node_id
SECURITY_POLICY_MAP = _opc_ua.SECURITY_POLICY_MAP


# === 辅助工厂 ===


def _make_config(
    connection_params: dict,
    points: list = None,
    write_enabled: bool = False,
    retry_max_failures: int = 5,
) -> DataSourceConfig:
    return DataSourceConfig(
        datasource_id="ds-opcua-test",
        protocol_type="opc_ua",
        connection_params=connection_params,
        collection_interval=5,
        write_enabled=write_enabled,
        points=points or [],
        retry_max_failures=retry_max_failures,
    )


def _default_params(**overrides) -> dict:
    params = {
        "endpoint_url": "opc.tcp://192.168.1.100:4840",
        "timeout": 5,
    }
    params.update(overrides)
    return params


def _make_points() -> list:
    return [
        PointConfig(point_id="temp_01", address="ns=2;i=1001", data_type="float32"),
        PointConfig(point_id="valve_01", address="ns=2;s=ValvePosition", data_type="float32"),
    ]


def _mock_asyncua():
    """创建 asyncua 模块和客户端的完整 mock"""
    mock_asyncua_mod = MagicMock()
    mock_client_instance = AsyncMock()
    mock_asyncua_mod.Client.return_value = mock_client_instance
    mock_client_instance.connect = AsyncMock()
    mock_client_instance.disconnect = AsyncMock()
    mock_client_instance.get_node = MagicMock()
    mock_client_instance.read_values = AsyncMock(return_value=[25.5, 0.75])
    mock_client_instance.session_timeout = 3600000
    mock_client_instance.set_user = MagicMock()
    mock_client_instance.set_password = MagicMock()
    mock_client_instance.set_security = AsyncMock()
    mock_client_instance.create_subscription = AsyncMock()

    mock_node = AsyncMock()
    mock_node.read_value = AsyncMock(return_value=25.5)
    mock_node.write_value = AsyncMock()
    mock_node.nodeid = MagicMock()
    mock_node.nodeid.to_string.return_value = "ns=2;i=1001"
    mock_node.read_node_class = AsyncMock()
    mock_node.read_display_name = AsyncMock()
    mock_node.get_children = AsyncMock(return_value=[])
    mock_client_instance.get_node.return_value = mock_node

    return mock_asyncua_mod, mock_client_instance, mock_node


def _patch_asyncua(mock_au):
    """返回 patch.dict 上下文管理器"""
    return patch.dict(
        "sys.modules",
        {
            "asyncua": mock_au,
            "asyncua.crypto": MagicMock(),
            "asyncua.crypto.security_policies": MagicMock(),
        },
    )


# === validate_node_id 测试 ===


class TestValidateNodeId:
    def test_valid_numeric(self):
        assert validate_node_id("ns=2;i=1001") is True

    def test_valid_string(self):
        assert validate_node_id("ns=2;s=Temperature") is True

    def test_valid_no_namespace(self):
        assert validate_node_id("i=2258") is True

    def test_valid_guid(self):
        assert validate_node_id("ns=0;g=12345678-1234-1234-1234-123456789abc") is True

    def test_valid_opaque(self):
        assert validate_node_id("ns=2;b=SGVsbG8=") is True

    def test_invalid_empty(self):
        assert validate_node_id("") is False

    def test_invalid_random_string(self):
        assert validate_node_id("random_string") is False

    def test_invalid_ns_not_numeric(self):
        assert validate_node_id("ns=abc;i=1") is False

    def test_invalid_ns_only(self):
        assert validate_node_id("ns=2") is False

    def test_invalid_missing_ns_prefix(self):
        assert validate_node_id("2;i=1001") is False


# === 注册表测试 ===


class TestAdapterRegistry:
    def test_opc_ua_registered(self):
        assert "opc_ua" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["opc_ua"] is OpcUaAdapter


# === connect 测试 ===


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_success_anonymous(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            result = await adapter.connect(config)
            assert result is True
            status = adapter.get_status()
            assert status.state == AdapterState.CONNECTED
            assert status.connected_since is not None
            assert status.error_message is None

    @pytest.mark.asyncio
    async def test_connect_success_username_auth(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            params = _default_params(
                auth_type="username",
                auth_config={"username": "admin", "password": "secret"},
            )
            config = _make_config(params, points=_make_points())
            result = await adapter.connect(config)
            assert result is True
            mock_client.set_user.assert_called_once_with("admin")
            mock_client.set_password.assert_called_once_with("secret")

    @pytest.mark.asyncio
    async def test_missing_endpoint_url(self):
        adapter = OpcUaAdapter()
        config = _make_config({"timeout": 5})
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "endpoint_url" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_missing_username_for_username_auth(self):
        adapter = OpcUaAdapter()
        params = _default_params(auth_type="username", auth_config={})
        config = _make_config(params)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "username" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_missing_cert_for_cert_auth(self):
        adapter = OpcUaAdapter()
        params = _default_params(auth_type="certificate", auth_config={})
        config = _make_config(params)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "certificate_path" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_invalid_auth_type(self):
        adapter = OpcUaAdapter()
        params = _default_params(auth_type="kerberos")
        config = _make_config(params)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR

    @pytest.mark.asyncio
    async def test_invalid_security_policy(self):
        adapter = OpcUaAdapter()
        params = _default_params(security_policy="invalid_policy")
        config = _make_config(params)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR

    @pytest.mark.asyncio
    async def test_invalid_point_address(self):
        adapter = OpcUaAdapter()
        points = [PointConfig(point_id="bad", address="INVALID_ADDR", data_type="float32")]
        config = _make_config(_default_params(), points=points)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR

    @pytest.mark.asyncio
    async def test_asyncua_not_installed(self):
        adapter = OpcUaAdapter()
        config = _make_config(_default_params(), points=_make_points())
        saved = {k: sys.modules.pop(k, None) for k in list(sys.modules) if k.startswith("asyncua")}
        try:
            result = await adapter.connect(config)
            assert result is False
            assert adapter.get_status().state == AdapterState.CONFIG_ERROR
            assert "asyncua" in adapter.get_status().error_message
        finally:
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_client.connect = AsyncMock(side_effect=Exception("Connection refused"))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            result = await adapter.connect(config)
            assert result is False
            assert adapter.get_status().state == AdapterState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_client.connect = AsyncMock(side_effect=asyncio.TimeoutError())
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            result = await adapter.connect(config)
            assert result is False
            assert adapter.get_status().state == AdapterState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_reconnect_disconnects_first(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            assert adapter.get_status().state == AdapterState.CONNECTED
            await adapter.connect(config)
            assert mock_client.disconnect.await_count >= 1
            assert adapter.get_status().state == AdapterState.CONNECTED


# === disconnect 测试 ===


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            await adapter.disconnect()
            status = adapter.get_status()
            assert status.state == AdapterState.DISCONNECTED
            assert status.connected_since is None
            mock_client.disconnect.assert_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_with_exception(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_client.disconnect = AsyncMock(side_effect=Exception("disconnect error"))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            await adapter.disconnect()  # should not raise
            assert adapter.get_status().state == AdapterState.DISCONNECTED


# === read_points 测试 ===


class TestReadPoints:
    @pytest.mark.asyncio
    async def test_batch_read_success(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_client.read_values = AsyncMock(return_value=[25.5, 0.75])
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].value == 25.5
            assert results["temp_01"].quality == DataQuality.NORMAL
            assert results["valve_01"].value == 0.75
            assert results["valve_01"].quality == DataQuality.NORMAL

    @pytest.mark.asyncio
    async def test_read_client_none(self):
        adapter = OpcUaAdapter()
        results = await adapter.read_points(_make_points())
        assert len(results) == 2
        for pv in results.values():
            assert pv.quality == DataQuality.ABNORMAL
            assert pv.value is None

    @pytest.mark.asyncio
    async def test_batch_fail_fallback_individual(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_client.read_values = AsyncMock(side_effect=Exception("batch fail"))
        mock_node.read_value = AsyncMock(return_value=25.5)
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            for pv in results.values():
                assert pv.value == 25.5
                assert pv.quality == DataQuality.NORMAL

    @pytest.mark.asyncio
    async def test_individual_read_partial_failure(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_client.read_values = AsyncMock(side_effect=Exception("batch fail"))
        call_count = 0

        async def side_effect_read():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 25.5
            raise Exception("node error")

        mock_node.read_value = AsyncMock(side_effect=side_effect_read)
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].value == 25.5
            assert results["temp_01"].quality == DataQuality.NORMAL
            assert results["valve_01"].value is None
            assert results["valve_01"].quality == DataQuality.ABNORMAL

    @pytest.mark.asyncio
    async def test_all_points_fail_consecutive_failures(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_client.read_values = AsyncMock(side_effect=Exception("batch fail"))
        mock_node.read_value = AsyncMock(side_effect=Exception("node fail"))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                retry_max_failures=3,
            )
            await adapter.connect(config)
            for _ in range(3):
                await adapter.read_points(_make_points())
            assert adapter.get_status().state == AdapterState.COMMUNICATION_INTERRUPTED

    @pytest.mark.asyncio
    async def test_read_timeout(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_client.read_values = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_node.read_value = AsyncMock(side_effect=asyncio.TimeoutError())
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                retry_max_failures=99,
            )
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            for pv in results.values():
                assert pv.quality == DataQuality.ABNORMAL

    @pytest.mark.asyncio
    async def test_none_value_unreliable(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_client.read_values = AsyncMock(return_value=[None, 0.75])
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].quality == DataQuality.UNRELIABLE
            assert results["temp_01"].value is None
            assert results["valve_01"].quality == DataQuality.NORMAL

    @pytest.mark.asyncio
    async def test_status_code_value_abnormal(self):
        mock_au, mock_client, _ = _mock_asyncua()
        bad_status = MagicMock()
        bad_status.is_good = MagicMock(return_value=False)
        mock_client.read_values = AsyncMock(return_value=[bad_status, 0.75])
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].quality == DataQuality.ABNORMAL
            assert results["valve_01"].quality == DataQuality.NORMAL


# === write_point 测试 ===


class TestWritePoint:
    @pytest.mark.asyncio
    async def test_write_success(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=True,
            )
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 30.0)
            assert result is True
            mock_node.write_value.assert_awaited_once_with(30.0)

    @pytest.mark.asyncio
    async def test_write_disabled(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=False,
            )
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 30.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_write_client_none(self):
        adapter = OpcUaAdapter()
        adapter._config = _make_config(_default_params(), write_enabled=True)
        result = await adapter.write_point("temp_01", 30.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_write_point_not_found(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=True,
            )
            await adapter.connect(config)
            result = await adapter.write_point("nonexistent", 30.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_write_none_value(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=True,
            )
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", None)
            assert result is False

    @pytest.mark.asyncio
    async def test_write_exception(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_node.write_value = AsyncMock(side_effect=Exception("write error"))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=True,
            )
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 30.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_write_timeout(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_node.write_value = AsyncMock(side_effect=asyncio.TimeoutError())
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(
                _default_params(),
                points=_make_points(),
                write_enabled=True,
            )
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 30.0)
            assert result is False


# === test_connection 测试 ===


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_success_with_latency(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_node.read_value = AsyncMock(return_value=datetime.now(timezone.utc))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            result = await adapter.test_connection()
            assert result.success is True
            assert result.latency_ms is not None
            assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_client_none(self):
        adapter = OpcUaAdapter()
        result = await adapter.test_connection()
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_node.read_value = AsyncMock(side_effect=asyncio.TimeoutError())
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            result = await adapter.test_connection()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_exception(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        mock_node.read_value = AsyncMock(side_effect=Exception("server error"))
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            result = await adapter.test_connection()
            assert result.success is False


# === get_status 测试 ===


class TestGetStatus:
    def test_initial_state(self):
        adapter = OpcUaAdapter()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None
        assert status.last_read_time is None
        assert status.consecutive_failures == 0
        assert status.error_message is None

    @pytest.mark.asyncio
    async def test_after_connect(self):
        mock_au, mock_client, _ = _mock_asyncua()
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            status = adapter.get_status()
            assert status.state == AdapterState.CONNECTED
            assert status.connected_since is not None


# === browse_nodes 测试 ===


class TestBrowseNodes:
    @pytest.mark.asyncio
    async def test_browse_success(self):
        mock_au, mock_client, mock_node = _mock_asyncua()
        child_node = AsyncMock()
        child_node.nodeid = MagicMock()
        child_node.nodeid.to_string.return_value = "ns=2;i=2001"
        mock_node_class = MagicMock()
        mock_node_class.name = "Variable"
        child_node.read_node_class = AsyncMock(return_value=mock_node_class)
        display_name = MagicMock()
        display_name.Text = "Temperature"
        child_node.read_display_name = AsyncMock(return_value=display_name)
        child_node.get_children = AsyncMock(return_value=[])
        mock_node.get_children = AsyncMock(return_value=[child_node])
        mock_ua = MagicMock()
        mock_ua.NodeClass.Object = "Object"
        mock_ua.NodeClass.Variable = "Variable"
        mock_au.ua = mock_ua
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            nodes = await adapter.browse_nodes()
            assert isinstance(nodes, list)

    @pytest.mark.asyncio
    async def test_browse_client_none(self):
        adapter = OpcUaAdapter()
        result = await adapter.browse_nodes()
        assert result == []


# === subscribe/unsubscribe 测试 ===


class TestSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_success(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_sub = AsyncMock()
        mock_sub.subscribe_data_change = AsyncMock(return_value=[1, 2])
        mock_sub.unsubscribe = AsyncMock()
        mock_sub.delete = AsyncMock()
        mock_client.create_subscription = AsyncMock(return_value=mock_sub)
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            handler = MagicMock()
            result = await adapter.subscribe_data_change(_make_points(), handler)
            assert result is True

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self):
        adapter = OpcUaAdapter()
        handler = MagicMock()
        result = await adapter.subscribe_data_change(_make_points(), handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_cleanup(self):
        mock_au, mock_client, _ = _mock_asyncua()
        mock_sub = AsyncMock()
        mock_sub.subscribe_data_change = AsyncMock(return_value=[1, 2])
        mock_sub.unsubscribe = AsyncMock()
        mock_sub.delete = AsyncMock()
        mock_client.create_subscription = AsyncMock(return_value=mock_sub)
        with _patch_asyncua(mock_au):
            adapter = OpcUaAdapter()
            config = _make_config(_default_params(), points=_make_points())
            await adapter.connect(config)
            handler = MagicMock()
            await adapter.subscribe_data_change(_make_points(), handler)
            await adapter.unsubscribe()
            mock_sub.delete.assert_awaited_once()
