"""网关模块单元测试 — Story 1.1 Task 7.1-7.6"""
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from gateway.adapters.base import (
    AdapterState,
    AdapterStatus,
    BaseProtocolAdapter,
    ConnectionResult,
    DataQuality,
    DataSourceConfig,
    NormalizedReading,
    PointConfig,
    PointValue,
)
from gateway.adapters.registry import (
    ADAPTER_REGISTRY,
    get_adapter,
    list_adapters,
    register_adapter,
)
from gateway.config_loader import LocalFileConfigLoader
from gateway.normalizer import DataNormalizer
from gateway.retry import RetryPolicy
from gateway.scheduler import CollectionScheduler


# ============================================================
# 7.1 BaseProtocolAdapter 接口约束
# ============================================================

class TestBaseProtocolAdapter:
    """测试抽象基类接口约束"""

    def test_cannot_instantiate_abc(self):
        """不能直接实例化抽象基类"""
        with pytest.raises(TypeError):
            BaseProtocolAdapter()

    def test_subclass_must_implement_all_methods(self):
        """子类必须实现所有抽象方法"""

        class IncompleteAdapter(BaseProtocolAdapter):
            async def connect(self, config: DataSourceConfig) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_complete_subclass_can_instantiate(self):
        """完整实现所有方法的子类可以实例化"""

        class CompleteAdapter(BaseProtocolAdapter):
            async def connect(self, config: DataSourceConfig) -> bool:
                return True

            async def disconnect(self) -> None:
                pass

            async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
                return {}

            async def write_point(self, point_id: str, value) -> bool:
                return True

            async def test_connection(self) -> ConnectionResult:
                return ConnectionResult(success=True, message="ok")

            def get_status(self) -> AdapterStatus:
                return AdapterStatus(state=AdapterState.DISCONNECTED)

        adapter = CompleteAdapter()
        assert adapter is not None

    def test_connect_accepts_typed_config(self):
        """connect 方法接受 DataSourceConfig 类型化参数"""
        config = DataSourceConfig(
            datasource_id="ds-1",
            protocol_type="modbus_tcp",
            connection_params={"ip": "192.168.1.1", "port": 502},
            points=[
                PointConfig(point_id="p1", address="40001", data_type="int16"),
            ],
        )
        assert config.datasource_id == "ds-1"
        assert len(config.points) == 1
        assert config.retry_base_delay == 1.0

    def test_data_quality_enum_values(self):
        """DataQuality 枚举值正确"""
        assert DataQuality.NORMAL.value == "normal"
        assert DataQuality.UNRELIABLE.value == "unreliable"
        assert DataQuality.ABNORMAL.value == "abnormal"

    def test_adapter_state_enum_values(self):
        """AdapterState 枚举值正确"""
        assert AdapterState.DISCONNECTED.value == "disconnected"
        assert AdapterState.CONNECTED.value == "connected"
        assert AdapterState.COMMUNICATION_INTERRUPTED.value == "communication_interrupted"
        assert AdapterState.CONFIG_ERROR.value == "config_error"


# ============================================================
# 7.2 ADAPTER_REGISTRY 注册/发现（含装饰器注册）
# ============================================================

class TestAdapterRegistry:
    """测试适配器注册表"""

    def setup_method(self):
        """每个测试前清空注册表"""
        ADAPTER_REGISTRY.clear()

    def teardown_method(self):
        """每个测试后清空注册表"""
        ADAPTER_REGISTRY.clear()

    def test_register_adapter_decorator(self):
        """装饰器注册适配器"""

        @register_adapter("test_protocol")
        class TestAdapter(BaseProtocolAdapter):
            async def connect(self, config): return True
            async def disconnect(self): pass
            async def read_points(self, points): return {}
            async def write_point(self, point_id, value): return True
            async def test_connection(self): return ConnectionResult(True, "ok")
            def get_status(self): return AdapterStatus(state=AdapterState.DISCONNECTED)

        assert "test_protocol" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["test_protocol"] is TestAdapter

    def test_get_adapter_returns_class(self):
        """get_adapter 返回已注册的适配器类"""

        @register_adapter("mock_proto")
        class MockAdapter(BaseProtocolAdapter):
            async def connect(self, config): return True
            async def disconnect(self): pass
            async def read_points(self, points): return {}
            async def write_point(self, point_id, value): return True
            async def test_connection(self): return ConnectionResult(True, "ok")
            def get_status(self): return AdapterStatus(state=AdapterState.DISCONNECTED)

        cls = get_adapter("mock_proto")
        assert cls is MockAdapter

    def test_get_adapter_unknown_raises(self):
        """获取未注册的协议类型抛出 ValueError"""
        with pytest.raises(ValueError, match="未知协议类型"):
            get_adapter("nonexistent")

    def test_list_adapters_empty(self):
        """空注册表返回空列表"""
        assert list_adapters() == []

    def test_list_adapters_returns_registered(self):
        """list_adapters 返回所有已注册的协议类型"""
        ADAPTER_REGISTRY["proto_a"] = MagicMock()
        ADAPTER_REGISTRY["proto_b"] = MagicMock()
        result = list_adapters()
        assert "proto_a" in result
        assert "proto_b" in result

    def test_decorator_returns_original_class(self):
        """装饰器返回原始类（不包装）"""

        @register_adapter("passthrough")
        class PassthroughAdapter(BaseProtocolAdapter):
            async def connect(self, config): return True
            async def disconnect(self): pass
            async def read_points(self, points): return {}
            async def write_point(self, point_id, value): return True
            async def test_connection(self): return ConnectionResult(True, "ok")
            def get_status(self): return AdapterStatus(state=AdapterState.DISCONNECTED)

        assert PassthroughAdapter.__name__ == "PassthroughAdapter"


# ============================================================
# 7.3 CollectionScheduler 并发调度
# ============================================================

class TestCollectionScheduler:
    """测试采集调度器"""

    def _make_config(self, ds_id="ds-1", interval=1):
        return DataSourceConfig(
            datasource_id=ds_id,
            protocol_type="mock",
            connection_params={},
            collection_interval=interval,
            points=[PointConfig(point_id="p1", address="1", data_type="float32")],
        )

    def _register_mock_adapter(self):
        """注册一个 mock 适配器"""
        ADAPTER_REGISTRY.clear()

        class MockAdapter(BaseProtocolAdapter):
            async def connect(self, config):
                return True

            async def disconnect(self):
                pass

            async def read_points(self, points):
                return {
                    "p1": PointValue(
                        point_id="p1",
                        value=25.0,
                        quality=DataQuality.NORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )
                }

            async def write_point(self, point_id, value):
                return True

            async def test_connection(self):
                return ConnectionResult(True, "ok")

            def get_status(self):
                return AdapterStatus(state=AdapterState.CONNECTED)

        ADAPTER_REGISTRY["mock"] = MockAdapter

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """调度器启动和停止"""
        self._register_mock_adapter()
        scheduler = CollectionScheduler()
        scheduler.start()
        assert scheduler._running is True

        # 添加一个数据源，stop 后 _configs 应保留
        config = self._make_config()
        scheduler.add_datasource(config)
        await asyncio.sleep(0.2)

        await scheduler.stop()
        assert scheduler._running is False
        # stop() 不再清空 _configs
        assert "ds-1" in scheduler._configs

    @pytest.mark.asyncio
    async def test_add_datasource_without_start_raises(self):
        """未启动调度器时添加数据源抛出 RuntimeError"""
        scheduler = CollectionScheduler()
        config = self._make_config()
        with pytest.raises(RuntimeError, match="调度器未启动"):
            scheduler.add_datasource(config)

    @pytest.mark.asyncio
    async def test_add_datasource_creates_task(self):
        """添加数据源创建采集任务"""
        self._register_mock_adapter()
        data_received = []

        async def on_data(readings):
            data_received.extend(readings)

        scheduler = CollectionScheduler(on_data=on_data)
        scheduler.start()
        config = self._make_config(interval=1)
        scheduler.add_datasource(config)

        assert "ds-1" in scheduler._tasks
        # 等待一个采集周期
        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert len(data_received) > 0
        assert data_received[0].point_id == "p1"

    @pytest.mark.asyncio
    async def test_remove_datasource(self):
        """移除数据源取消采集任务"""
        self._register_mock_adapter()
        scheduler = CollectionScheduler()
        scheduler.start()
        scheduler.add_datasource(self._make_config())

        assert "ds-1" in scheduler._tasks
        await scheduler.remove_datasource("ds-1")
        assert "ds-1" not in scheduler._tasks
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_reload_datasource(self):
        """热重载数据源配置"""
        self._register_mock_adapter()
        scheduler = CollectionScheduler()
        scheduler.start()
        scheduler.add_datasource(self._make_config(interval=5))

        new_config = self._make_config(interval=2)
        await scheduler.reload_datasource(new_config)

        assert "ds-1" in scheduler._tasks
        assert scheduler._configs["ds-1"].collection_interval == 2
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_communication_interrupted_triggers_alarm(self):
        """通信中断触发告警回调"""
        ADAPTER_REGISTRY.clear()

        class FailAdapter(BaseProtocolAdapter):
            async def connect(self, config): return True
            async def disconnect(self): pass
            async def read_points(self, points): raise ConnectionError("模拟失败")
            async def write_point(self, point_id, value): return True
            async def test_connection(self): return ConnectionResult(False, "fail")
            def get_status(self): return AdapterStatus(state=AdapterState.DISCONNECTED)

        ADAPTER_REGISTRY["fail"] = FailAdapter

        alarms = []

        async def on_alarm(ds_id, msg):
            alarms.append((ds_id, msg))

        config = DataSourceConfig(
            datasource_id="ds-fail",
            protocol_type="fail",
            connection_params={},
            collection_interval=1,
            retry_base_delay=0.1,
            retry_max_delay=0.2,
            retry_max_failures=3,
            points=[PointConfig(point_id="p1", address="1", data_type="float32")],
        )

        scheduler = CollectionScheduler(on_alarm=on_alarm)
        scheduler.start()
        scheduler.add_datasource(config)

        # 等待足够时间让 3 次失败发生
        await asyncio.sleep(3)
        await scheduler.stop()

        assert len(alarms) > 0
        assert alarms[0][0] == "ds-fail"

    @pytest.mark.asyncio
    async def test_connect_failure_retries(self):
        """连接失败后指数退避重试，最终成功后数据流通"""
        ADAPTER_REGISTRY.clear()

        connect_attempts = []

        class RetryAdapter(BaseProtocolAdapter):
            async def connect(self, config):
                connect_attempts.append(1)
                if len(connect_attempts) < 3:
                    raise ConnectionError("模拟连接失败")
                return True

            async def disconnect(self):
                pass

            async def read_points(self, points):
                return {
                    "p1": PointValue(
                        point_id="p1",
                        value=42.0,
                        quality=DataQuality.NORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )
                }

            async def write_point(self, point_id, value):
                return True

            async def test_connection(self):
                return ConnectionResult(True, "ok")

            def get_status(self):
                return AdapterStatus(state=AdapterState.CONNECTED)

        ADAPTER_REGISTRY["retry_proto"] = RetryAdapter

        data_received = []

        async def on_data(readings):
            data_received.extend(readings)

        config = DataSourceConfig(
            datasource_id="ds-retry",
            protocol_type="retry_proto",
            connection_params={},
            collection_interval=1,
            retry_base_delay=0.1,
            retry_max_delay=0.5,
            retry_max_failures=5,
            points=[PointConfig(point_id="p1", address="1", data_type="float32")],
        )

        scheduler = CollectionScheduler(on_data=on_data)
        scheduler.start()
        scheduler.add_datasource(config)

        # 等待足够时间让重试 + 至少一次采集完成
        await asyncio.sleep(4)
        await scheduler.stop()

        # 验证重试了多次连接
        assert len(connect_attempts) >= 3
        # 验证最终数据流通
        assert len(data_received) > 0
        assert data_received[0].point_id == "p1"


# ============================================================
# 7.4 DataNormalizer 转换逻辑
# ============================================================

class TestDataNormalizer:
    """测试数据归一化"""

    def _make_config(self, points=None):
        if points is None:
            points = [
                PointConfig(point_id="p1", address="1", data_type="float32", scale=2.0, offset=10.0),
                PointConfig(point_id="p2", address="2", data_type="int16", enum_mapping={"0": "关", "1": "开"}),
            ]
        return DataSourceConfig(
            datasource_id="ds-1",
            protocol_type="mock",
            connection_params={},
            points=points,
        )

    def test_scale_and_offset(self):
        """缩放和偏移转换"""
        normalizer = DataNormalizer()
        config = self._make_config()
        raw = {
            "p1": PointValue("p1", 5.0, DataQuality.NORMAL, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert len(readings) == 1
        # 5.0 * 2.0 + 10.0 = 20.0
        assert readings[0].value == 20.0
        assert readings[0].raw_value == 5.0

    def test_enum_mapping(self):
        """枚举映射转换（非数值类型触发枚举映射）"""
        normalizer = DataNormalizer()
        config = self._make_config(
            points=[
                PointConfig(
                    point_id="p2", address="2", data_type="string",
                    enum_mapping={"on": "开", "off": "关"},
                ),
            ]
        )
        raw = {
            "p2": PointValue("p2", "on", DataQuality.NORMAL, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert len(readings) == 1
        assert readings[0].value == "开"

    def test_missing_point_config_skipped(self):
        """未配置的点位被跳过"""
        normalizer = DataNormalizer()
        config = self._make_config()
        raw = {
            "unknown": PointValue("unknown", 1.0, DataQuality.NORMAL, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert len(readings) == 0

    def test_timestamp_converted_to_utc(self):
        """时间戳统一为 UTC"""
        normalizer = DataNormalizer()
        config = self._make_config(
            points=[PointConfig(point_id="p1", address="1", data_type="float32")]
        )
        naive_ts = datetime(2026, 1, 1, 12, 0, 0)
        raw = {
            "p1": PointValue("p1", 1.0, DataQuality.NORMAL, naive_ts),
        }
        readings = normalizer.normalize(raw, config)
        assert readings[0].timestamp.tzinfo == timezone.utc

    def test_output_is_normalized_reading(self):
        """输出类型为 NormalizedReading"""
        normalizer = DataNormalizer()
        config = self._make_config(
            points=[PointConfig(point_id="p1", address="1", data_type="float32")]
        )
        raw = {
            "p1": PointValue("p1", 1.0, DataQuality.NORMAL, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert isinstance(readings[0], NormalizedReading)
        assert readings[0].datasource_id == "ds-1"

    def test_quality_preserved(self):
        """数据质量标记保留"""
        normalizer = DataNormalizer()
        config = self._make_config(
            points=[PointConfig(point_id="p1", address="1", data_type="float32")]
        )
        raw = {
            "p1": PointValue("p1", 1.0, DataQuality.UNRELIABLE, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert readings[0].quality == DataQuality.UNRELIABLE

    def test_dry_contact_enum_mapping(self):
        """干接点类型优先使用枚举映射而非缩放"""
        normalizer = DataNormalizer()
        config = self._make_config(
            points=[
                PointConfig(
                    point_id="p_di", address="3", data_type="int16",
                    is_dry_contact=True,
                    enum_mapping={"0": "关", "1": "开"},
                    scale=10.0, offset=5.0,
                ),
            ]
        )
        raw = {
            "p_di": PointValue("p_di", 1, DataQuality.NORMAL, datetime.now(timezone.utc)),
        }
        readings = normalizer.normalize(raw, config)
        assert len(readings) == 1
        # 干接点应走枚举映射，值为 "开"，而非 1*10+5=15.0
        assert readings[0].value == "开"
        assert readings[0].raw_value == 1


# ============================================================
# 7.5 RetryPolicy 指数退避和通信中断标记
# ============================================================

class TestRetryPolicy:
    """测试重试策略"""

    def test_exponential_backoff(self):
        """指数退避延迟"""
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0, max_failures=5)
        delays = [policy.record_failure() for _ in range(5)]
        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_max_delay_cap(self):
        """延迟不超过 max_delay"""
        policy = RetryPolicy(base_delay=1.0, max_delay=10.0, max_failures=10)
        for _ in range(10):
            delay = policy.record_failure()
        assert delay <= 10.0

    def test_success_resets_counter(self):
        """成功重置失败计数"""
        policy = RetryPolicy()
        policy.record_failure()
        policy.record_failure()
        assert policy.failure_count == 2
        policy.record_success()
        assert policy.failure_count == 0

    def test_is_interrupted_threshold(self):
        """达到阈值标记通信中断"""
        policy = RetryPolicy(max_failures=3)
        for _ in range(2):
            policy.record_failure()
        assert not policy.is_interrupted
        policy.record_failure()
        assert policy.is_interrupted

    def test_reset_clears_state(self):
        """reset 清除所有状态"""
        policy = RetryPolicy(max_failures=3)
        for _ in range(5):
            policy.record_failure()
        assert policy.is_interrupted
        policy.reset()
        assert policy.failure_count == 0
        assert not policy.is_interrupted

    def test_custom_parameters(self):
        """自定义参数"""
        policy = RetryPolicy(base_delay=2.0, max_delay=30.0, max_failures=10)
        assert policy.base_delay == 2.0
        assert policy.max_delay == 30.0
        assert policy.max_failures == 10
        delay = policy.record_failure()
        assert delay == 2.0  # 2.0 * 2^0 = 2.0


# ============================================================
# 7.6 ConfigLoader 从本地文件加载
# ============================================================

class TestConfigLoader:
    """测试配置加载器"""

    def _write_yaml(self, data: dict) -> str:
        """写入临时 YAML 文件并返回路径"""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.dump(data, f, allow_unicode=True)
        f.close()
        return f.name

    @pytest.mark.asyncio
    async def test_load_datasources(self):
        """加载数据源配置列表"""
        data = {
            "datasources": [
                {
                    "datasource_id": "ds-1",
                    "protocol_type": "modbus_tcp",
                    "connection_params": {"ip": "192.168.1.1", "port": 502},
                    "collection_interval": 10,
                    "points": [
                        {"point_id": "p1", "address": "40001", "data_type": "int16"},
                    ],
                }
            ]
        }
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        configs = await loader.load_datasources()
        assert len(configs) == 1
        assert configs[0].datasource_id == "ds-1"
        assert configs[0].collection_interval == 10
        assert len(configs[0].points) == 1
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_load_datasource_by_id(self):
        """按 ID 加载单个数据源"""
        data = {
            "datasources": [
                {"datasource_id": "ds-1", "protocol_type": "modbus_tcp", "connection_params": {}},
                {"datasource_id": "ds-2", "protocol_type": "snmp_v2c", "connection_params": {}},
            ]
        }
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        config = await loader.load_datasource("ds-2")
        assert config is not None
        assert config.protocol_type == "snmp_v2c"
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_load_datasource_not_found(self):
        """加载不存在的数据源返回 None"""
        data = {"datasources": []}
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        config = await loader.load_datasource("nonexistent")
        assert config is None
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self):
        """文件不存在抛出 FileNotFoundError"""
        loader = LocalFileConfigLoader("/nonexistent/path.yaml")
        with pytest.raises(FileNotFoundError):
            await loader.load_datasources()

    @pytest.mark.asyncio
    async def test_empty_datasources_returns_empty(self):
        """空配置返回空列表"""
        data = {"other_key": "value"}
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        configs = await loader.load_datasources()
        assert configs == []
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_point_config_defaults(self):
        """点位配置默认值"""
        data = {
            "datasources": [
                {
                    "datasource_id": "ds-1",
                    "protocol_type": "modbus_tcp",
                    "connection_params": {},
                    "points": [
                        {"point_id": "p1", "address": "40001", "data_type": "float32"},
                    ],
                }
            ]
        }
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        configs = await loader.load_datasources()
        point = configs[0].points[0]
        assert point.scale == 1.0
        assert point.offset == 0.0
        assert point.enum_mapping is None
        assert point.is_dry_contact is False
        Path(path).unlink()
