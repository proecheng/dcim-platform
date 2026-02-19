"""BACnet/IP 适配器测试 — Story 15.3"""
import asyncio
import sys
import os
import importlib.util
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# 确保 gateway 根目录在 sys.path
_root = os.path.join(os.path.dirname(__file__), "..", "..")
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
_bacnet = _load_module("gateway.adapters.bacnet_ip", os.path.join(_gw_dir, "bacnet_ip.py"))

AdapterState = _base.AdapterState
DataQuality = _base.DataQuality
DataSourceConfig = _base.DataSourceConfig
PointConfig = _base.PointConfig
PointValue = _base.PointValue
ConnectionResult = _base.ConnectionResult
ADAPTER_REGISTRY = _registry.ADAPTER_REGISTRY
BacnetIpAdapter = _bacnet.BacnetIpAdapter
parse_point_address = _bacnet.parse_point_address
OBJECT_TYPE_MAP = _bacnet.OBJECT_TYPE_MAP
OBJECT_TYPE_ALIASES = _bacnet.OBJECT_TYPE_ALIASES
_network_manager = _bacnet._network_manager


# ─── 辅助工厂 ─────────────────────────────────────────────────

def _make_config(
    connection_params: dict,
    points: list[PointConfig] | None = None,
    write_enabled: bool = False,
    retry_max_failures: int = 5,
) -> DataSourceConfig:
    return DataSourceConfig(
        datasource_id="ds-bacnet-test",
        protocol_type="bacnet_ip",
        connection_params=connection_params,
        collection_interval=5,
        write_enabled=write_enabled,
        points=points or [],
        retry_max_failures=retry_max_failures,
    )


def _default_params(**overrides) -> dict:
    """默认 BACnet/IP 连接参数"""
    params = {
        "device_instance": 1234,
        "device_address": "192.168.1.100",
        "timeout": 5,
    }
    params.update(overrides)
    return params


def _make_points() -> list[PointConfig]:
    return [
        PointConfig(point_id="temp_01", address="AI:1", data_type="float32"),
        PointConfig(point_id="valve_01", address="BO:3", data_type="float32"),
    ]


# ─── 注册表测试 ──────────────────────────────────────────────

class TestAdapterRegistry:
    """适配器注册表"""

    def test_bacnet_ip_adapter_registered(self):
        """bacnet_ip 协议类型已注册"""
        assert "bacnet_ip" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["bacnet_ip"] is BacnetIpAdapter


# ─── parse_point_address 测试 ────────────────────────────────

class TestParsePointAddress:
    """parse_point_address() 测试"""

    def test_full_name(self):
        """完整名称 analogInput:1"""
        obj_type, instance, prop = parse_point_address("analogInput:1")
        assert obj_type == "analogInput"
        assert instance == 1
        assert prop == "presentValue"

    def test_alias_ai(self):
        """缩写 AI:5"""
        obj_type, instance, prop = parse_point_address("AI:5")
        assert obj_type == "analogInput"
        assert instance == 5
        assert prop == "presentValue"

    def test_alias_with_property(self):
        """缩写带属性 BO:3:statusFlags"""
        obj_type, instance, prop = parse_point_address("BO:3:statusFlags")
        assert obj_type == "binaryOutput"
        assert instance == 3
        assert prop == "statusFlags"

    def test_all_aliases(self):
        """所有 9 种对象类型缩写"""
        expected = {
            "AI": "analogInput",
            "AO": "analogOutput",
            "AV": "analogValue",
            "BI": "binaryInput",
            "BO": "binaryOutput",
            "BV": "binaryValue",
            "MI": "multiStateInput",
            "MO": "multiStateOutput",
            "MV": "multiStateValue",
        }
        for alias, full_name in expected.items():
            obj_type, instance, prop = parse_point_address(f"{alias}:1")
            assert obj_type == full_name, f"{alias} should map to {full_name}"

    def test_invalid_too_few_parts(self):
        """缺少部分 — 只有类型没有实例号"""
        with pytest.raises(ValueError, match="无效 BACnet 地址格式"):
            parse_point_address("AI")

    def test_invalid_too_many_parts(self):
        """过多部分"""
        with pytest.raises(ValueError, match="无效 BACnet 地址格式"):
            parse_point_address("AI:1:prop:extra")

    def test_invalid_unknown_type(self):
        """未知对象类型"""
        with pytest.raises(ValueError, match="未知 BACnet 对象类型"):
            parse_point_address("XX:1")

    def test_invalid_non_numeric_instance(self):
        """非数字实例号"""
        with pytest.raises(ValueError, match="无效对象实例号"):
            parse_point_address("AI:abc")


# ─── connect 配置验证测试 ────────────────────────────────────

class TestConnectValidation:
    """connect() 配置验证"""

    @pytest.mark.asyncio
    async def test_missing_device_instance(self):
        """缺少 device_instance → CONFIG_ERROR"""
        adapter = BacnetIpAdapter()
        config = _make_config({"device_address": "192.168.1.100"})
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR
        assert "device_instance" in adapter.get_status().error_message

    @pytest.mark.asyncio
    async def test_invalid_point_address(self):
        """无效点位地址 → CONFIG_ERROR"""
        adapter = BacnetIpAdapter()
        points = [PointConfig(point_id="bad", address="INVALID", data_type="float32")]
        config = _make_config(_default_params(), points=points)
        result = await adapter.connect(config)
        assert result is False
        assert adapter.get_status().state == AdapterState.CONFIG_ERROR

    @pytest.mark.asyncio
    async def test_bac0_not_installed(self):
        """BAC0 未安装 → CONFIG_ERROR"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(side_effect=ImportError("BAC0 未安装"))
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            result = await adapter.connect(config)
            assert result is False
            assert adapter.get_status().state == AdapterState.CONFIG_ERROR
            assert "BAC0" in adapter.get_status().error_message
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """连接成功 — mock _network_manager.acquire"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            result = await adapter.connect(config)
            assert result is True
            assert adapter.get_status().state == AdapterState.CONNECTED
            assert adapter.get_status().error_message is None
            assert adapter.get_status().connected_since is not None
        finally:
            _bacnet._network_manager = original_mgr


# ─── disconnect 测试 ─────────────────────────────────────────

class TestDisconnect:
    """disconnect() 测试"""

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        """断开后状态重置，调用 release"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            await adapter.disconnect()
            status = adapter.get_status()
            assert status.state == AdapterState.DISCONNECTED
            assert status.connected_since is None
            mock_mgr.release.assert_awaited_once()
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_disconnect_without_connect(self):
        """未连接时断开不报错"""
        adapter = BacnetIpAdapter()
        await adapter.disconnect()
        assert adapter.get_status().state == AdapterState.DISCONNECTED


# ─── read_points 测试 ────────────────────────────────────────

class TestReadPoints:
    """read_points() 测试"""

    @pytest.mark.asyncio
    async def test_read_without_network(self):
        """未连接时 read_points 返回 ABNORMAL"""
        adapter = BacnetIpAdapter()
        points = _make_points()
        results = await adapter.read_points(points)
        assert len(results) == 2
        for pv in results.values():
            assert pv.quality == DataQuality.ABNORMAL
            assert pv.value is None

    @pytest.mark.asyncio
    async def test_rpm_success(self):
        """RPM 批量读取成功"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        rpm_result = {
            "analogInput:1": {"presentValue": 25.3},
            "binaryOutput:3": {"presentValue": 1},
        }
        mock_network.readMultiple = AsyncMock(return_value=rpm_result)
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].value == 25.3
            assert results["temp_01"].quality == DataQuality.NORMAL
            assert results["valve_01"].value == 1
            assert results["valve_01"].quality == DataQuality.NORMAL
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_rpm_fail_fallback_individual_success(self):
        """RPM 失败 fallback 逐点位读取成功"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_network.readMultiple = AsyncMock(side_effect=Exception("RPM not supported"))

        async def mock_read(request):
            if "analogInput" in request:
                return 25.3
            if "binaryOutput" in request:
                return 1
            return None

        mock_network.read = AsyncMock(side_effect=mock_read)
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].value == 25.3
            assert results["temp_01"].quality == DataQuality.NORMAL
            assert results["valve_01"].value == 1
            assert results["valve_01"].quality == DataQuality.NORMAL
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_individual_read_partial_failure(self):
        """逐点位读取部分失败"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_network.readMultiple = AsyncMock(side_effect=Exception("RPM fail"))

        call_count = 0

        async def mock_read(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 25.3
            raise Exception("device timeout")

        mock_network.read = AsyncMock(side_effect=mock_read)
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            assert results["temp_01"].value == 25.3
            assert results["temp_01"].quality == DataQuality.NORMAL
            assert results["valve_01"].value is None
            assert results["valve_01"].quality == DataQuality.ABNORMAL
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_read_timeout(self):
        """读取超时"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(timeout=0.01), points=_make_points())

        mock_network = MagicMock()
        mock_network.readMultiple = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_network.read = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            results = await adapter.read_points(_make_points())
            for pv in results.values():
                assert pv.quality == DataQuality.ABNORMAL
                assert pv.value is None
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_consecutive_failures_trigger_interrupted(self):
        """连续失败触发 COMMUNICATION_INTERRUPTED — 真实路径（B1 修复验证）"""
        adapter = BacnetIpAdapter()
        config = _make_config(
            _default_params(),
            points=_make_points(),
            retry_max_failures=3,
        )

        mock_network = MagicMock()
        mock_network.readMultiple = AsyncMock(side_effect=Exception("RPM fail"))
        # 所有点位逐个读取也失败 → _read_points_individually 抛 RuntimeError
        mock_network.read = AsyncMock(side_effect=Exception("device unreachable"))
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            for _ in range(3):
                await adapter.read_points(_make_points())
            assert adapter.get_status().state == AdapterState.COMMUNICATION_INTERRUPTED
        finally:
            _bacnet._network_manager = original_mgr


# ─── write_point 测试 ────────────────────────────────────────

class TestWritePoint:
    """write_point() 测试"""

    @pytest.mark.asyncio
    async def test_write_disabled(self):
        """写入禁用时返回 False"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points(), write_enabled=False)

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 25.0)
            assert result is False
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_write_no_network(self):
        """网络未连接返回 False"""
        adapter = BacnetIpAdapter()
        adapter._config = _make_config(_default_params(), write_enabled=True)
        result = await adapter.write_point("temp_01", 25.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_write_point_not_found(self):
        """未找到点位配置返回 False"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points(), write_enabled=True)

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.write_point("nonexistent_point", 25.0)
            assert result is False
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_write_success(self):
        """写入成功"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points(), write_enabled=True)

        mock_network = MagicMock()
        mock_network.write = AsyncMock(return_value=None)
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 25.0)
            assert result is True
            mock_network.write.assert_awaited_once()
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_write_timeout(self):
        """写入超时返回 False"""
        adapter = BacnetIpAdapter()
        config = _make_config(
            _default_params(timeout=0.01), points=_make_points(), write_enabled=True
        )

        mock_network = MagicMock()
        mock_network.write = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", 25.0)
            assert result is False
        finally:
            _bacnet._network_manager = original_mgr


# ─── test_connection 测试 ────────────────────────────────────

class TestTestConnection:
    """test_connection() 测试"""

    @pytest.mark.asyncio
    async def test_no_network(self):
        """网络未初始化"""
        adapter = BacnetIpAdapter()
        result = await adapter.test_connection()
        assert result.success is False
        assert "未初始化" in result.message

    @pytest.mark.asyncio
    async def test_success(self):
        """成功读取 objectName"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_network.read = AsyncMock(return_value="AHU-01")
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.test_connection()
            assert result.success is True
            assert "成功" in result.message
            assert result.latency_ms is not None
            assert result.latency_ms >= 0
            assert result.sample_data["object_name"] == "AHU-01"
            assert result.sample_data["device_instance"] == 1234
        finally:
            _bacnet._network_manager = original_mgr

    @pytest.mark.asyncio
    async def test_timeout(self):
        """连接测试超时"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(timeout=0.01), points=_make_points())

        mock_network = MagicMock()
        mock_network.read = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.test_connection()
            assert result.success is False
            assert "超时" in result.message
        finally:
            _bacnet._network_manager = original_mgr


# ─── get_status 测试 ─────────────────────────────────────────

class TestGetStatus:
    """get_status() 测试"""

    def test_initial_status(self):
        """初始状态为 DISCONNECTED"""
        adapter = BacnetIpAdapter()
        status = adapter.get_status()
        assert status.state == AdapterState.DISCONNECTED
        assert status.connected_since is None
        assert status.last_read_time is None
        assert status.consecutive_failures == 0
        assert status.error_message is None

    @pytest.mark.asyncio
    async def test_connected_status(self):
        """连接后状态"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            status = adapter.get_status()
            assert status.state == AdapterState.CONNECTED
            assert status.connected_since is not None
        finally:
            _bacnet._network_manager = original_mgr


# ─── _BacnetNetworkManager 测试 ──────────────────────────────

class TestBacnetNetworkManager:
    """_BacnetNetworkManager 引用计数测试"""

    @pytest.mark.asyncio
    async def test_ref_count_acquire_twice(self):
        """acquire 两次 ref_count=2"""
        mgr = _bacnet._BacnetNetworkManager()
        mock_bac0 = MagicMock()
        mock_bac0.start = AsyncMock(return_value=MagicMock())

        with patch.dict("sys.modules", {"BAC0": mock_bac0}):
            net1 = await mgr.acquire("", 47808)
            net2 = await mgr.acquire("", 47808)
            assert mgr._ref_count == 2
            assert net1 is net2  # 同一个网络实例

    @pytest.mark.asyncio
    async def test_release_once_keeps_network(self):
        """release 一次 ref_count=1 网络不关闭"""
        mgr = _bacnet._BacnetNetworkManager()
        mock_bac0 = MagicMock()
        mock_net = MagicMock()
        mock_bac0.start = AsyncMock(return_value=mock_net)

        with patch.dict("sys.modules", {"BAC0": mock_bac0}):
            await mgr.acquire("", 47808)
            await mgr.acquire("", 47808)
            await mgr.release()
            assert mgr._ref_count == 1
            assert mgr._network is not None
            mock_net.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_all_closes_network(self):
        """release 第二次 ref_count=0 网络关闭"""
        mgr = _bacnet._BacnetNetworkManager()
        mock_bac0 = MagicMock()
        mock_net = MagicMock()
        mock_bac0.start = AsyncMock(return_value=mock_net)

        with patch.dict("sys.modules", {"BAC0": mock_bac0}):
            await mgr.acquire("", 47808)
            await mgr.acquire("", 47808)
            await mgr.release()
            await mgr.release()
            assert mgr._ref_count == 0
            assert mgr._network is None
            mock_net.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_import_error(self):
        """BAC0 未安装时 acquire 抛 ImportError"""
        mgr = _bacnet._BacnetNetworkManager()
        # 确保 BAC0 不在 sys.modules 中
        saved = sys.modules.pop("BAC0", None)
        try:
            with pytest.raises(ImportError, match="BAC0 未安装"):
                await mgr.acquire("", 47808)
        finally:
            if saved is not None:
                sys.modules["BAC0"] = saved


# ─── discover_devices 测试 ───────────────────────────────────

class TestDiscoverDevices:
    """discover_devices() 测试"""

    @pytest.mark.asyncio
    async def test_no_network(self):
        """网络未连接返回空列表"""
        adapter = BacnetIpAdapter()
        result = await adapter.discover_devices()
        assert result == []


# ─── browse_objects 测试 ─────────────────────────────────────

class TestBrowseObjects:
    """browse_objects() 测试"""

    @pytest.mark.asyncio
    async def test_no_network(self):
        """网络未连接返回空列表"""
        adapter = BacnetIpAdapter()
        result = await adapter.browse_objects()
        assert result == []


# ─── 重复 connect 引用泄漏测试 (B3) ─────────────────────────

class TestRepeatedConnect:
    """重复 connect() 不先 disconnect() 的引用计数安全"""

    @pytest.mark.asyncio
    async def test_repeated_connect_releases_old(self):
        """重复 connect 会先 disconnect 旧连接"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points())

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            assert mock_mgr.acquire.await_count == 1
            # 第二次 connect 应先 release 再 acquire
            await adapter.connect(config)
            assert mock_mgr.release.await_count == 1
            assert mock_mgr.acquire.await_count == 2
        finally:
            _bacnet._network_manager = original_mgr


# ─── write_point None 值防护测试 (I4) ────────────────────────

class TestWritePointNone:
    """write_point 写入 None 值防护"""

    @pytest.mark.asyncio
    async def test_write_none_value(self):
        """写入 None 值返回 False"""
        adapter = BacnetIpAdapter()
        config = _make_config(_default_params(), points=_make_points(), write_enabled=True)

        mock_network = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.acquire = AsyncMock(return_value=mock_network)
        mock_mgr.release = AsyncMock()
        original_mgr = _bacnet._network_manager
        _bacnet._network_manager = mock_mgr
        try:
            await adapter.connect(config)
            result = await adapter.write_point("temp_01", None)
            assert result is False
        finally:
            _bacnet._network_manager = original_mgr
