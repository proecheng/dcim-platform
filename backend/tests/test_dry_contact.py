"""干接点状态变化监测器单元测试 — Story 1.6"""
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.config_loader import LocalFileConfigLoader
from gateway.dry_contact import DryContactEvent, DryContactMonitor
from gateway.scheduler import CollectionScheduler


# ============================================================
# 辅助工具
# ============================================================

def _make_point(
    point_id: str = "di-1",
    is_dry_contact: bool = True,
    fire_signal: bool = False,
    enum_mapping: dict | None = None,
) -> PointConfig:
    return PointConfig(
        point_id=point_id,
        address="1",
        data_type="int16",
        is_dry_contact=is_dry_contact,
        fire_signal=fire_signal,
        enum_mapping=enum_mapping,
    )


def _make_config(
    ds_id: str = "ds-1",
    points: list[PointConfig] | None = None,
    interval: int = 1,
) -> DataSourceConfig:
    if points is None:
        points = [_make_point()]
    return DataSourceConfig(
        datasource_id=ds_id,
        protocol_type="mock",
        connection_params={},
        collection_interval=interval,
        points=points,
    )


def _make_reading(
    point_id: str = "di-1",
    value: object = "正常",
    raw_value: object = 0,
    quality: DataQuality = DataQuality.NORMAL,
    ds_id: str = "ds-1",
) -> NormalizedReading:
    return NormalizedReading(
        point_id=point_id,
        value=value,
        raw_value=raw_value,
        quality=quality,
        timestamp=datetime.now(timezone.utc),
        datasource_id=ds_id,
    )


# ============================================================
# DryContactMonitor 核心测试
# ============================================================

class TestDryContactMonitor:
    """干接点监测器核心逻辑"""

    def test_first_read_no_event(self):
        """首次读取记录初始状态，不触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        readings = [_make_reading(raw_value=0, value="正常")]
        events = monitor.check(readings, config)
        assert events == []

    def test_state_change_0_to_1(self):
        """raw_value 0→1 触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        # 首次
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        # 变化
        events = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        assert len(events) == 1
        assert events[0].raw_old_value == 0
        assert events[0].raw_new_value == 1

    def test_state_change_1_to_0(self):
        """raw_value 1→0 触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=1, value="火警")], config)
        events = monitor.check([_make_reading(raw_value=0, value="正常")], config)
        assert len(events) == 1
        assert events[0].raw_old_value == 1
        assert events[0].raw_new_value == 0

    def test_no_change_no_event(self):
        """raw_value 不变时不触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check([_make_reading(raw_value=0, value="正常")], config)
        assert events == []

    def test_non_dry_contact_skipped(self):
        """非干接点点位被忽略"""
        monitor = DryContactMonitor()
        point = _make_point(is_dry_contact=False)
        config = _make_config(points=[point])
        monitor.check([_make_reading(raw_value=0)], config)
        events = monitor.check([_make_reading(raw_value=1)], config)
        assert events == []

    def test_fire_signal_flag(self):
        """fire_signal=True 传播到事件"""
        monitor = DryContactMonitor()
        point = _make_point(fire_signal=True)
        config = _make_config(points=[point])
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        assert len(events) == 1
        assert events[0].is_fire_signal is True

    def test_fire_signal_false_by_default(self):
        """fire_signal 默认为 False"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        assert len(events) == 1
        assert events[0].is_fire_signal is False

    def test_abnormal_quality_skipped(self):
        """ABNORMAL 质量的读数不触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check(
            [_make_reading(raw_value=1, value="火警", quality=DataQuality.ABNORMAL)],
            config,
        )
        assert events == []

    def test_abnormal_quality_no_state_update(self):
        """ABNORMAL 读数不更新 last_values，后续正常读数仍与原始值比较"""
        monitor = DryContactMonitor()
        config = _make_config()
        # 初始 raw=0
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        # ABNORMAL raw=1 → 不更新
        monitor.check(
            [_make_reading(raw_value=1, value="火警", quality=DataQuality.ABNORMAL)],
            config,
        )
        # 再次 raw=0 → 与初始值相同，不触发
        events = monitor.check([_make_reading(raw_value=0, value="正常")], config)
        assert events == []

    def test_reset_clears_datasource(self):
        """reset 清除指定数据源的状态"""
        monitor = DryContactMonitor()
        config = _make_config(ds_id="ds-1")
        monitor.check([_make_reading(raw_value=0, ds_id="ds-1")], config)
        assert len(monitor._last_values) == 1
        monitor.reset("ds-1")
        assert len(monitor._last_values) == 0

    def test_reset_other_datasource_unaffected(self):
        """reset 不影响其他数据源"""
        monitor = DryContactMonitor()
        config1 = _make_config(ds_id="ds-1")
        config2 = _make_config(ds_id="ds-2")
        monitor.check([_make_reading(raw_value=0, ds_id="ds-1")], config1)
        monitor.check([_make_reading(raw_value=0, ds_id="ds-2")], config2)
        assert len(monitor._last_values) == 2
        monitor.reset("ds-1")
        assert len(monitor._last_values) == 1
        assert "ds-2:di-1" in monitor._last_values

    def test_clear_all(self):
        """clear_all 清除所有状态"""
        monitor = DryContactMonitor()
        config1 = _make_config(ds_id="ds-1")
        config2 = _make_config(ds_id="ds-2")
        monitor.check([_make_reading(raw_value=0, ds_id="ds-1")], config1)
        monitor.check([_make_reading(raw_value=0, ds_id="ds-2")], config2)
        monitor.clear_all()
        assert len(monitor._last_values) == 0

    def test_event_has_raw_values(self):
        """事件包含 raw_old_value 和 raw_new_value"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        event = events[0]
        assert event.raw_old_value == 0
        assert event.raw_new_value == 1

    def test_event_has_normalized_values(self):
        """事件包含归一化后的 old_value 和 new_value"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        event = events[0]
        assert event.old_value == "正常"
        assert event.new_value == "火警"

    def test_multiple_points_independent(self):
        """多个点位独立跟踪"""
        monitor = DryContactMonitor()
        p1 = _make_point(point_id="di-1")
        p2 = _make_point(point_id="di-2")
        config = _make_config(points=[p1, p2])
        # 初始化两个点位
        monitor.check(
            [
                _make_reading(point_id="di-1", raw_value=0, value="正常"),
                _make_reading(point_id="di-2", raw_value=0, value="正常"),
            ],
            config,
        )
        # 只有 di-1 变化
        events = monitor.check(
            [
                _make_reading(point_id="di-1", raw_value=1, value="火警"),
                _make_reading(point_id="di-2", raw_value=0, value="正常"),
            ],
            config,
        )
        assert len(events) == 1
        assert events[0].point_id == "di-1"

    def test_unreliable_quality_still_triggers(self):
        """UNRELIABLE 质量仍然触发事件（只有 ABNORMAL 被过滤）"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        events = monitor.check(
            [_make_reading(raw_value=1, value="火警", quality=DataQuality.UNRELIABLE)],
            config,
        )
        assert len(events) == 1
        assert events[0].raw_new_value == 1

    def test_event_datasource_id(self):
        """事件包含正确的 datasource_id"""
        monitor = DryContactMonitor()
        config = _make_config(ds_id="ds-fire")
        monitor.check([_make_reading(raw_value=0, ds_id="ds-fire")], config)
        events = monitor.check([_make_reading(raw_value=1, ds_id="ds-fire")], config)
        assert events[0].datasource_id == "ds-fire"

    def test_event_timestamp(self):
        """事件 timestamp 来自 reading"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0)], config)
        reading = _make_reading(raw_value=1)
        events = monitor.check([reading], config)
        assert events[0].timestamp == reading.timestamp

    def test_consecutive_changes(self):
        """连续多次变化都能检测"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0, value="正常")], config)
        # 0→1
        events1 = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        assert len(events1) == 1
        # 1→0
        events2 = monitor.check([_make_reading(raw_value=0, value="正常")], config)
        assert len(events2) == 1
        # 0→1 again
        events3 = monitor.check([_make_reading(raw_value=1, value="火警")], config)
        assert len(events3) == 1

    def test_reset_then_first_read_no_event(self):
        """reset 后首次读取不触发事件"""
        monitor = DryContactMonitor()
        config = _make_config()
        monitor.check([_make_reading(raw_value=0)], config)
        monitor.reset("ds-1")
        events = monitor.check([_make_reading(raw_value=1)], config)
        assert events == []  # 首次读取，不触发


# ============================================================
# CollectionScheduler 集成测试
# ============================================================

class TestSchedulerDryContact:
    """调度器干接点集成"""

    def _register_mock_adapter(self, read_values: list[dict[str, PointValue]] | None = None):
        """注册 mock 适配器，可自定义返回值序列"""
        ADAPTER_REGISTRY.clear()
        call_count = [0]

        class MockAdapter(BaseProtocolAdapter):
            async def connect(self, config):
                return True

            async def disconnect(self):
                pass

            async def read_points(self, points):
                if read_values:
                    idx = min(call_count[0], len(read_values) - 1)
                    call_count[0] += 1
                    return read_values[idx]
                return {
                    "di-1": PointValue(
                        point_id="di-1",
                        value=0,
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
    async def test_scheduler_dry_contact_callback(self):
        """on_dry_contact 回调在状态变化时被调用"""
        ts = datetime.now(timezone.utc)
        read_values = [
            {"di-1": PointValue("di-1", 0, DataQuality.NORMAL, ts)},
            {"di-1": PointValue("di-1", 1, DataQuality.NORMAL, ts)},
        ]
        self._register_mock_adapter(read_values)

        dc_events_received: list[DryContactEvent] = []

        async def on_dc(events):
            dc_events_received.extend(events)

        point = _make_point(point_id="di-1", fire_signal=True)
        config = _make_config(points=[point], interval=1)

        scheduler = CollectionScheduler(on_dry_contact=on_dc)
        scheduler.start()
        scheduler.add_datasource(config)

        # 等待至少两个采集周期
        await asyncio.sleep(3)
        await scheduler.stop()

        assert len(dc_events_received) >= 1
        assert dc_events_received[0].point_id == "di-1"
        assert dc_events_received[0].is_fire_signal is True

    @pytest.mark.asyncio
    async def test_scheduler_remove_resets_monitor(self):
        """remove_datasource 调用 monitor.reset"""
        self._register_mock_adapter()
        scheduler = CollectionScheduler()
        scheduler.start()

        config = _make_config()
        scheduler.add_datasource(config)
        await asyncio.sleep(0.3)

        # 验证 monitor 有状态
        # 移除后应清除
        await scheduler.remove_datasource("ds-1")
        assert not any(
            k.startswith("ds-1:") for k in scheduler._dry_contact_monitor._last_values
        )
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop_clears_monitor(self):
        """stop() 调用 monitor.clear_all"""
        self._register_mock_adapter()
        scheduler = CollectionScheduler()
        scheduler.start()
        scheduler.add_datasource(_make_config())
        await asyncio.sleep(0.3)

        await scheduler.stop()
        assert len(scheduler._dry_contact_monitor._last_values) == 0

    @pytest.mark.asyncio
    async def test_scheduler_no_callback_no_error(self):
        """on_dry_contact=None 时不报错"""
        ts = datetime.now(timezone.utc)
        read_values = [
            {"di-1": PointValue("di-1", 0, DataQuality.NORMAL, ts)},
            {"di-1": PointValue("di-1", 1, DataQuality.NORMAL, ts)},
        ]
        self._register_mock_adapter(read_values)

        point = _make_point(point_id="di-1")
        config = _make_config(points=[point], interval=1)

        scheduler = CollectionScheduler(on_dry_contact=None)
        scheduler.start()
        scheduler.add_datasource(config)
        await asyncio.sleep(2.5)
        await scheduler.stop()
        # 没有异常即通过


# ============================================================
# ConfigLoader fire_signal 解析测试
# ============================================================

class TestConfigLoaderFireSignal:
    """配置加载器 fire_signal 字段解析"""

    def _write_yaml(self, data: dict) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.dump(data, f, allow_unicode=True)
        f.close()
        return f.name

    @pytest.mark.asyncio
    async def test_config_loader_fire_signal(self):
        """fire_signal 从 YAML 配置正确解析"""
        data = {
            "datasources": [
                {
                    "datasource_id": "ds-1",
                    "protocol_type": "modbus_tcp",
                    "connection_params": {"ip": "192.168.1.1", "port": 502},
                    "points": [
                        {
                            "point_id": "di-fire",
                            "address": "10001",
                            "data_type": "int16",
                            "is_dry_contact": True,
                            "fire_signal": True,
                            "enum_mapping": {"0": "正常", "1": "火警"},
                        },
                        {
                            "point_id": "di-normal",
                            "address": "10002",
                            "data_type": "int16",
                            "is_dry_contact": True,
                            "fire_signal": False,
                        },
                        {
                            "point_id": "ai-temp",
                            "address": "40001",
                            "data_type": "float32",
                        },
                    ],
                }
            ]
        }
        path = self._write_yaml(data)
        loader = LocalFileConfigLoader(path)
        configs = await loader.load_datasources()
        points = configs[0].points

        assert points[0].fire_signal is True
        assert points[0].is_dry_contact is True
        assert points[1].fire_signal is False
        assert points[2].fire_signal is False  # 默认值
        Path(path).unlink()
