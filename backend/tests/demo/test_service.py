"""演示数据服务加载/卸载测试。"""

from datetime import date, datetime

from sqlalchemy import func, select, text

from app.demo import service as demo_service_module
from app.demo.service import DemoDataService
from app.models.alarm import Alarm, AlarmThreshold
from app.models.energy import (
    DistributionCircuit,
    DistributionPanel,
    EnergyDaily,
    EnergyHourly,
    EnergyMonthly,
    MeterPoint,
    PowerDevice,
    Transformer,
)
from app.models.floor_map import FloorMap
from app.models.history import PointHistory
from app.models.point import Point, PointRealtime
from app.services import ingest_pipeline


class _SessionCtx:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_load_demo_data_happy_path(async_db, monkeypatch):
    svc = DemoDataService()

    async def _seed_noop():
        return None

    async def _status_ok():
        return {
            "is_loaded": False,
            "point_count": 0,
            "demo_point_count": 0,
            "history_count": 0,
            "device_count": 0,
            "linked_device_count": 0,
            "sync_status": "not_synced",
            "loading": False,
            "progress": 0,
            "progress_message": "",
        }

    async def _create_points(_progress_callback):
        return 6

    async def _create_distribution(_progress_callback):
        return None

    async def _generate_history(_days, _progress_callback):
        return 24

    async def _generate_noop(*_args, **_kwargs):
        return None

    class _FakeSyncService:
        def __init__(self, _session):
            pass

        async def migrate_existing_data(self):
            return {"linked_panels": 0, "linked_power_devices": 0}

    monkeypatch.setattr(demo_service_module, "init_db", _generate_noop)
    monkeypatch.setattr(svc, "check_demo_data_status", _status_ok)
    monkeypatch.setattr("app.demo.seeds.datacenter_seed.seed_datacenter", _seed_noop)
    monkeypatch.setattr("app.demo.seeds.power_seed.seed_power_devices", _seed_noop)
    monkeypatch.setattr("app.demo.seeds.cooling_seed.seed_cooling_devices", _seed_noop)
    monkeypatch.setattr("app.demo.seeds.asset_capacity_seed.seed_asset_capacity", _seed_noop)
    monkeypatch.setattr(demo_service_module, "async_session", _SessionCtx(async_db))
    monkeypatch.setattr("app.services.device_sync.DeviceSyncService", _FakeSyncService)
    monkeypatch.setattr(svc, "_create_points", _create_points)
    monkeypatch.setattr(svc, "_create_distribution_system", _create_distribution)
    monkeypatch.setattr(svc, "_generate_history", _generate_history)
    monkeypatch.setattr(svc, "_generate_demand_data", _generate_noop)
    monkeypatch.setattr(svc, "_generate_floor_maps", _generate_noop)
    monkeypatch.setattr(svc, "_generate_pue_history", _generate_noop)

    result = await svc.load_demo_data(days=1)

    assert result["success"] is True
    assert result["point_count"] == 6
    assert result["history_count"] == 24
    assert svc.is_loaded is True
    assert svc.loading is False
    assert svc.progress == 100
    assert "加载完成" in svc.progress_message


async def test_unload_demo_data_integrity_and_fk_cleanup(async_db, monkeypatch):
    svc = DemoDataService()
    monkeypatch.setattr(demo_service_module, "async_session", _SessionCtx(async_db))

    point = Point(
        point_code="UNLOAD_AI_001",
        point_name="卸载测试点位",
        point_type="AI",
        device_type="TEST",
        is_enabled=True,
        is_demo=True,
    )
    async_db.add(point)
    await async_db.flush()

    async_db.add(PointRealtime(point_id=point.id, value=10.0, raw_value=10.0, status="normal"))
    async_db.add(PointHistory(point_id=point.id, value=10.0))
    threshold = AlarmThreshold(
        point_id=point.id,
        threshold_type="high",
        threshold_value=9.0,
        alarm_level="minor",
        alarm_message="阈值告警",
        is_enabled=True,
        is_demo=True,
    )
    async_db.add(threshold)
    await async_db.flush()
    async_db.add(
        Alarm(
            alarm_no="ALM_TEST_UNLOAD_001",
            point_id=point.id,
            threshold_id=threshold.id,
            alarm_level="minor",
            alarm_type="threshold",
            alarm_message="测试告警",
            trigger_value=10.0,
            threshold_value=9.0,
        )
    )

    transformer = Transformer(
        transformer_code="TR-T-001",
        transformer_name="测试变压器",
        rated_capacity=1000,
        is_demo=True,
    )
    async_db.add(transformer)
    await async_db.flush()

    meter = MeterPoint(
        meter_code="M-T-001",
        meter_name="测试计量点",
        transformer_id=transformer.id,
        is_demo=True,
    )
    async_db.add(meter)
    await async_db.flush()

    panel = DistributionPanel(
        panel_code="P-T-001",
        panel_name="测试配电柜",
        panel_type="main",
        meter_point_id=meter.id,
        is_demo=True,
    )
    async_db.add(panel)
    await async_db.flush()

    circuit = DistributionCircuit(
        circuit_code="C-T-001",
        circuit_name="测试回路",
        panel_id=panel.id,
        is_demo=True,
    )
    async_db.add(circuit)
    await async_db.flush()

    power_device = PowerDevice(
        device_code="PD-T-001",
        device_name="测试用电设备",
        device_type="UPS",
        circuit_id=circuit.id,
        power_point_id=point.id,
        is_demo=True,
    )
    async_db.add(power_device)
    await async_db.flush()

    async_db.add(EnergyHourly(device_id=power_device.id, stat_time=datetime.now(), total_energy=1.0))
    async_db.add(EnergyDaily(device_id=power_device.id, stat_date=date.today(), total_energy=2.0))
    async_db.add(EnergyMonthly(device_id=power_device.id, stat_year=2026, stat_month=3, total_energy=3.0))
    async_db.add(
        FloorMap(
            floor_code="F1",
            floor_name="F1",
            map_type="2d",
            map_data="{}",
            is_demo=True,
        )
    )
    await async_db.commit()

    ingest_pipeline._point_meta_cache[point.id] = {"is_enabled": True}
    ingest_pipeline._cache_loaded = True

    result = await svc.unload_demo_data()

    assert result["success"] is True
    assert svc.is_loaded is False

    assert await async_db.scalar(select(func.count(Point.id))) == 0
    assert await async_db.scalar(select(func.count(PointRealtime.point_id))) == 0
    assert await async_db.scalar(select(func.count(PointHistory.id))) == 0
    assert await async_db.scalar(select(func.count(AlarmThreshold.id))) == 0
    assert await async_db.scalar(select(func.count(Alarm.id))) == 0
    assert await async_db.scalar(select(func.count(Transformer.id))) == 0
    assert await async_db.scalar(select(func.count(MeterPoint.id))) == 0
    assert await async_db.scalar(select(func.count(DistributionPanel.id))) == 0
    assert await async_db.scalar(select(func.count(DistributionCircuit.id))) == 0
    assert await async_db.scalar(select(func.count(PowerDevice.id))) == 0
    assert await async_db.scalar(select(func.count(EnergyHourly.id))) == 0
    assert await async_db.scalar(select(func.count(EnergyDaily.id))) == 0
    assert await async_db.scalar(select(func.count(EnergyMonthly.id))) == 0
    assert await async_db.scalar(select(func.count(FloorMap.id))) == 0

    # 数据完整性：不应存在孤儿记录
    orphan_realtime = await async_db.scalar(
        text("SELECT COUNT(*) FROM point_realtime pr LEFT JOIN points p ON pr.point_id = p.id WHERE p.id IS NULL")
    )
    orphan_history = await async_db.scalar(
        text("SELECT COUNT(*) FROM point_history ph LEFT JOIN points p ON ph.point_id = p.id WHERE p.id IS NULL")
    )
    assert orphan_realtime == 0
    assert orphan_history == 0

    # 卸载后必须失效点位缓存
    assert ingest_pipeline._point_meta_cache == {}
    assert ingest_pipeline._cache_loaded is False
