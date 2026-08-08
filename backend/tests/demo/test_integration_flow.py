"""演示模块集成流程测试：加载 -> 生成 -> 卸载。"""

from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.demo.engine import DataSimulator
from app.demo.service import DemoDataService
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


async def test_demo_flow_load_generate_unload_with_api(async_db, client, monkeypatch):
    svc = DemoDataService()

    async def _noop(*_args, **_kwargs):
        return None

    async def _create_points(_progress_callback):
        ai = Point(
            point_code="FLOW_AI_001",
            point_name="流程温度",
            point_type="AI",
            device_type="TH",
            is_enabled=True,
            min_range=0,
            max_range=50,
            source="demo",
            is_demo=True,
        )
        di = Point(
            point_code="FLOW_DI_001",
            point_name="流程门禁",
            point_type="DI",
            device_type="DOOR",
            is_enabled=True,
            min_range=0,
            max_range=1,
            source="demo",
            is_demo=True,
        )
        ao = Point(
            point_code="FLOW_AO_001",
            point_name="流程控制输出",
            point_type="AO",
            device_type="UPS",
            is_enabled=True,
            source="demo",
            is_demo=True,
        )
        async_db.add_all([ai, di, ao])
        await async_db.flush()
        async_db.add(PointRealtime(point_id=ao.id, value=5.0, raw_value=5.0, status="normal"))
        await async_db.commit()
        return 3

    class _FakeSyncService:
        def __init__(self, _session):
            pass

        async def migrate_existing_data(self):
            return {"linked_panels": 0, "linked_power_devices": 0}

    monkeypatch.setattr("app.demo.router.demo_data_service", svc)
    monkeypatch.setattr("app.demo.service.async_session", _SessionCtx(async_db))
    monkeypatch.setattr("app.demo.engine.async_session", _SessionCtx(async_db))
    monkeypatch.setattr("app.demo.service.init_db", _noop)
    monkeypatch.setattr("app.demo.seeds.datacenter_seed.seed_datacenter", _noop)
    monkeypatch.setattr("app.demo.seeds.power_seed.seed_power_devices", _noop)
    monkeypatch.setattr("app.demo.seeds.cooling_seed.seed_cooling_devices", _noop)
    monkeypatch.setattr("app.demo.seeds.asset_capacity_seed.seed_asset_capacity", _noop)
    monkeypatch.setattr("app.services.device_sync.DeviceSyncService", _FakeSyncService)
    monkeypatch.setattr(svc, "_create_points", _create_points)
    monkeypatch.setattr(svc, "_create_distribution_system", _noop)
    monkeypatch.setattr(svc, "_generate_history", AsyncMock(return_value=0))
    monkeypatch.setattr(svc, "_generate_demand_data", _noop)
    monkeypatch.setattr(svc, "_generate_floor_maps", _noop)
    monkeypatch.setattr(svc, "_generate_pue_history", _noop)

    # 避免告警/WS/Redis 副作用影响流程测试
    monkeypatch.setattr(ingest_pipeline, "_evaluate_alarms", AsyncMock(return_value={"created": 0, "resolved": 0}))
    monkeypatch.setattr(ingest_pipeline, "_broadcast_realtime", AsyncMock())
    monkeypatch.setattr(ingest_pipeline, "_update_redis_cache", AsyncMock())

    load_result = await svc.load_demo_data(days=1)
    assert load_result["success"] is True

    # 使用 AsyncClient 验证 API 可见状态
    status_resp = await client.get("/api/v1/demo/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()["data"]
    assert status_data["point_count"] == 3

    simulator = DataSimulator()
    await simulator.run_collection_cycle()
    history_count_after_generate = await async_db.scalar(select(func.count(PointHistory.id)))
    assert history_count_after_generate >= 1

    unload_resp = await client.post("/api/v1/demo/unload")
    assert unload_resp.status_code == 200
    unload_data = unload_resp.json()
    assert unload_data["success"] is True

    point_count_after_unload = await async_db.scalar(select(func.count(Point.id)))
    history_count_after_unload = await async_db.scalar(select(func.count(PointHistory.id)))
    assert point_count_after_unload == 0
    assert history_count_after_unload == 0
