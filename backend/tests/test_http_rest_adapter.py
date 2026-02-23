"""HTTP REST 适配器测试 — Story 15.2"""

import asyncio
import sys
import os
import importlib.util
import types
import pytest
from unittest.mock import AsyncMock, MagicMock

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


# 按依赖顺序加载，绕过 gateway/adapters/__init__.py（它会导入 pymodbus）
_gw_dir = os.path.join(_root, "gateway", "adapters")
_base = _load_module("gateway.adapters.base", os.path.join(_gw_dir, "base.py"))
_registry = _load_module("gateway.adapters.registry", os.path.join(_gw_dir, "registry.py"))
_utils = _load_module("gateway.adapters.utils", os.path.join(_gw_dir, "utils.py"))
_http = _load_module("gateway.adapters.http_rest", os.path.join(_gw_dir, "http_rest.py"))

AdapterState = _base.AdapterState
DataQuality = _base.DataQuality
DataSourceConfig = _base.DataSourceConfig
PointConfig = _base.PointConfig
PointValue = _base.PointValue
ConnectionResult = _base.ConnectionResult
ADAPTER_REGISTRY = _registry.ADAPTER_REGISTRY
HttpRestAdapter = _http.HttpRestAdapter
_build_json_extractor = _utils.build_json_extractor


# ─── 辅助工厂 ─────────────────────────────────────────────────


def _make_config(
    connection_params: dict,
    points: list[PointConfig] | None = None,
    write_enabled: bool = False,
) -> DataSourceConfig:
    return DataSourceConfig(
        datasource_id="ds-http-test",
        protocol_type="http_rest",
        connection_params=connection_params,
        collection_interval=30,
        write_enabled=write_enabled,
        points=points or [],
    )


def _default_params(**overrides) -> dict:
    """默认 HTTP REST 连接参数"""
    params = {
        "base_url": "https://api.example.com",
        "method": "GET",
        "endpoint": "/api/v1/sensors",
        "auth_type": "none",
        "timeout": 5,
    }
    params.update(overrides)
    return params


def _make_points() -> list[PointConfig]:
    return [
        PointConfig(point_id="temp_01", address="temperature", data_type="float32"),
        PointConfig(point_id="humi_01", address="humidity", data_type="float32"),
    ]


# ─── 注册表测试 ──────────────────────────────────────────────


class TestAdapterRegistry:
    """适配器注册表"""

    def test_http_rest_adapter_registered(self):
        """http_rest 协议类型已注册"""
        assert "http_rest" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["http_rest"] is HttpRestAdapter


# ─── JSON 路径提取器测试 ─────────────────────────────────────


class TestJsonExtractor:
    """JSON 路径提取器（与 MQTT 适配器共用逻辑）"""

    def test_simple_key(self):
        extractor = _build_json_extractor("temperature")
        assert extractor({"temperature": 25.3}) == 25.3

    def test_nested_path(self):
        extractor = _build_json_extractor("data.sensors.temp")
        assert extractor({"data": {"sensors": {"temp": 22.1}}}) == 22.1

    def test_array_index(self):
        extractor = _build_json_extractor("sensors[0].value")
        assert extractor({"sensors": [{"value": 10}, {"value": 20}]}) == 10

    def test_missing_key_raises(self):
        extractor = _build_json_extractor("nonexistent")
        with pytest.raises(KeyError):
            extractor({"temperature": 25.3})


# ─── 连接配置验证测试 ────────────────────────────────────────


class TestConnectValidation:
    """connect() 配置验证"""

    @pytest.mark.asyncio
    async def test_missing_base_url(self):
        """缺少 base_url 应返回 CONFIG_ERROR"""
        adapter = HttpRestAdapter()
        config = _make_config({"method": "GET", "endpoint": "/api"})
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "base_url" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_unsupported_method(self):
        """不支持的 HTTP 方法应返回 CONFIG_ERROR"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(method="DELETE"))
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "DELETE" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_basic_auth_missing_username(self):
        """Basic Auth 缺少 username 应返回 CONFIG_ERROR"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                auth_type="basic",
                auth_config={"password": "secret"},
            )
        )
        result = await adapter.connect(config)
        assert result is False
        assert "username" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_bearer_auth_missing_token(self):
        """Bearer Token 缺少 token 应返回 CONFIG_ERROR"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                auth_type="bearer",
                auth_config={},
            )
        )
        result = await adapter.connect(config)
        assert result is False
        assert "token" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_unsupported_auth_type(self):
        """不支持的认证方式应返回 CONFIG_ERROR"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(auth_type="oauth2"))
        result = await adapter.connect(config)
        assert result is False
        assert "oauth2" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_connect_success_no_auth(self):
        """无认证连接成功"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        result = await adapter.connect(config)
        assert result is True
        assert adapter.get_status().state == AdapterState.CONNECTED
        assert adapter.get_status().error_message is None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_success_basic_auth(self):
        """Basic Auth 连接成功"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                auth_type="basic",
                auth_config={"username": "admin", "password": "secret"},
            )
        )
        result = await adapter.connect(config)
        assert result is True
        assert adapter.get_status().state == AdapterState.CONNECTED
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_success_bearer_auth(self):
        """Bearer Token 连接成功"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                auth_type="bearer",
                auth_config={"token": "eyJhbGciOiJIUzI1NiJ9.test"},
            )
        )
        result = await adapter.connect(config)
        assert result is True
        assert adapter.get_status().state == AdapterState.CONNECTED
        await adapter.disconnect()


# ─── 断开连接测试 ────────────────────────────────────────────


class TestDisconnect:
    """disconnect() 测试"""

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        """断开后状态重置"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)
        await adapter.disconnect()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None

    @pytest.mark.asyncio
    async def test_disconnect_without_connect(self):
        """未连接时断开不报错"""
        adapter = HttpRestAdapter()
        await adapter.disconnect()  # 不应抛异常
        assert adapter.get_status().state == AdapterState.DISCONNECTED


# ─── read_points 测试 ────────────────────────────────────────


class TestReadPoints:
    """read_points() 测试"""

    @pytest.mark.asyncio
    async def test_read_without_client(self):
        """未连接时 read_points 返回 ABNORMAL"""
        adapter = HttpRestAdapter()
        points = _make_points()
        results = await adapter.read_points(points)
        assert len(results) == 2
        for pv in results.values():
            assert pv.quality == DataQuality.ABNORMAL
            assert pv.value is None

    @pytest.mark.asyncio
    async def test_read_get_success(self):
        """GET 请求成功读取点位"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)

        # Mock httpx 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"temperature": 25.3, "humidity": 60.1}

        adapter._client.get = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(_make_points())
        assert results["temp_01"].value == 25.3
        assert results["temp_01"].quality == DataQuality.NORMAL
        assert results["humi_01"].value == 60.1
        assert results["humi_01"].quality == DataQuality.NORMAL
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_post_success(self):
        """POST 请求成功读取点位"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(method="POST", request_body={"ids": ["temp_01"]}),
            points=_make_points(),
        )
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"temperature": 30.0, "humidity": 55.0}

        adapter._client.post = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(_make_points())
        assert results["temp_01"].value == 30.0
        assert results["humi_01"].value == 55.0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_with_response_root(self):
        """配置 response_root 后从根节点提取"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(response_root="data.readings"),
            points=_make_points(),
        )
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"readings": {"temperature": 22.5, "humidity": 45.0}},
        }

        adapter._client.get = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(_make_points())
        assert results["temp_01"].value == 22.5
        assert results["humi_01"].value == 45.0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_partial_data(self):
        """响应中缺少部分点位数据"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"temperature": 25.3}  # 缺少 humidity

        adapter._client.get = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(_make_points())
        assert results["temp_01"].value == 25.3
        assert results["temp_01"].quality == DataQuality.NORMAL
        assert results["humi_01"].value is None
        assert results["humi_01"].quality == DataQuality.ABNORMAL
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_nested_address(self):
        """嵌套 JSON 路径提取"""
        adapter = HttpRestAdapter()
        points = [
            PointConfig(point_id="deep_val", address="level1.level2.value", data_type="float32"),
        ]
        config = _make_config(_default_params(), points=points)
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"level1": {"level2": {"value": 99.9}}}

        adapter._client.get = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(points)
        assert results["deep_val"].value == 99.9
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_array_index_address(self):
        """数组索引 JSON 路径提取"""
        adapter = HttpRestAdapter()
        points = [
            PointConfig(point_id="sensor_0", address="sensors[0].value", data_type="float32"),
            PointConfig(point_id="sensor_1", address="sensors[1].value", data_type="float32"),
        ]
        config = _make_config(_default_params(), points=points)
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"sensors": [{"value": 10.0}, {"value": 20.0}]}

        adapter._client.get = AsyncMock(return_value=mock_response)

        results = await adapter.read_points(points)
        assert results["sensor_0"].value == 10.0
        assert results["sensor_1"].value == 20.0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_http_error(self):
        """HTTP 请求失败时所有点位标记 ABNORMAL"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)

        import httpx

        adapter._client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )

        results = await adapter.read_points(_make_points())
        assert len(results) == 2
        for pv in results.values():
            assert pv.quality == DataQuality.ABNORMAL
            assert pv.value is None
        assert adapter._consecutive_failures == 1
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_read_timeout(self):
        """HTTP 请求超时"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)

        adapter._client.get = AsyncMock(side_effect=asyncio.TimeoutError())

        results = await adapter.read_points(_make_points())
        for pv in results.values():
            assert pv.quality == DataQuality.ABNORMAL
        assert adapter._consecutive_failures == 1
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_consecutive_failures_trigger_interrupted(self):
        """连续失败超过阈值触发 COMMUNICATION_INTERRUPTED"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(),
            points=_make_points(),
        )
        # 设置 retry_max_failures=3
        config.retry_max_failures = 3
        await adapter.connect(config)

        adapter._client.get = AsyncMock(side_effect=Exception("network error"))

        for _ in range(3):
            await adapter.read_points(_make_points())

        assert adapter.get_status().state == AdapterState.COMMUNICATION_INTERRUPTED
        await adapter.disconnect()


# ─── write_point 测试 ────────────────────────────────────────


class TestWritePoint:
    """write_point() 测试"""

    @pytest.mark.asyncio
    async def test_write_not_supported(self):
        """HTTP REST 适配器不支持写入"""
        adapter = HttpRestAdapter()
        result = await adapter.write_point("temp_01", 25.0)
        assert result is False


# ─── test_connection 测试 ────────────────────────────────────


class TestTestConnection:
    """test_connection() 测试"""

    @pytest.mark.asyncio
    async def test_connection_without_client(self):
        """未初始化客户端时测试连接"""
        adapter = HttpRestAdapter()
        result = await adapter.test_connection()
        assert result.success is False
        assert "未初始化" in result.message

    @pytest.mark.asyncio
    async def test_connection_get_success(self):
        """GET 连接测试成功"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params())
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "ok", "version": "1.0"}

        adapter._client.get = AsyncMock(return_value=mock_response)

        result = await adapter.test_connection()
        assert result.success is True
        assert "200" in result.message
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert "status" in result.sample_data
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection_post_success(self):
        """POST 连接测试成功"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(method="POST", request_body={"ping": True}))
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "sensor_01"}]

        adapter._client.post = AsyncMock(return_value=mock_response)

        result = await adapter.test_connection()
        assert result.success is True
        assert result.sample_data["count"] == 1
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """连接测试超时"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params())
        await adapter.connect(config)

        adapter._client.get = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await adapter.test_connection()
        assert result.success is False
        assert "超时" in result.message
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """连接测试网络错误"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params())
        await adapter.connect(config)

        adapter._client.get = AsyncMock(side_effect=ConnectionError("refused"))

        result = await adapter.test_connection()
        assert result.success is False
        assert "refused" in result.message
        await adapter.disconnect()


# ─── get_status 测试 ─────────────────────────────────────────


class TestGetStatus:
    """get_status() 测试"""

    def test_initial_status(self):
        """初始状态为 DISCONNECTED"""
        adapter = HttpRestAdapter()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None
        assert status.last_read_time is None
        assert status.consecutive_failures == 0
        assert status.error_message is None

    @pytest.mark.asyncio
    async def test_connected_status(self):
        """连接后状态"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params())
        await adapter.connect(config)
        status = adapter.get_status()
        assert status.state == AdapterState.CONNECTED
        assert status.connected_since is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_last_read_time_updated(self):
        """read_points 后 last_read_time 更新"""
        adapter = HttpRestAdapter()
        config = _make_config(_default_params(), points=_make_points())
        await adapter.connect(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"temperature": 25.0, "humidity": 50.0}
        adapter._client.get = AsyncMock(return_value=mock_response)

        await adapter.read_points(_make_points())
        assert adapter.get_status().last_read_time is not None
        await adapter.disconnect()


# ─── 认证集成测试 ────────────────────────────────────────────


class TestAuthIntegration:
    """认证方式集成测试"""

    @pytest.mark.asyncio
    async def test_basic_auth_client_created(self):
        """Basic Auth 创建带认证的客户端"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                auth_type="basic",
                auth_config={"username": "user", "password": "pass"},
            )
        )
        await adapter.connect(config)
        # httpx.AsyncClient 应该带有 BasicAuth
        assert adapter._client is not None
        assert adapter._client._auth is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_bearer_token_in_headers(self):
        """Bearer Token 写入请求头"""
        adapter = HttpRestAdapter()
        token = "eyJhbGciOiJIUzI1NiJ9.test_token"
        config = _make_config(
            _default_params(
                auth_type="bearer",
                auth_config={"token": token},
            )
        )
        await adapter.connect(config)
        # 检查 Authorization header
        assert adapter._client is not None
        auth_header = adapter._client.headers.get("authorization")
        assert auth_header == f"Bearer {token}"
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_custom_headers(self):
        """自定义请求头"""
        adapter = HttpRestAdapter()
        config = _make_config(
            _default_params(
                headers={"X-API-Key": "abc123", "X-Custom": "value"},
            )
        )
        await adapter.connect(config)
        assert adapter._client.headers.get("x-api-key") == "abc123"
        assert adapter._client.headers.get("x-custom") == "value"
        await adapter.disconnect()
