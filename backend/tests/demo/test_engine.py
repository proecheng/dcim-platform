"""演示数据生成引擎测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.demo.engine import DataSimulator
from app.models.point import Point, PointRealtime


async def _add_point(async_db, code: str, name: str, point_type: str):
    point = Point(
        point_code=code,
        point_name=name,
        point_type=point_type,
        device_type="TEST",
        is_enabled=True,
        min_range=0,
        max_range=100,
    )
    async_db.add(point)
    await async_db.flush()
    return point


def test_generate_ai_value_clamp_and_round(monkeypatch):
    simulator = DataSimulator()
    point = Point(
        point_code="AI_001",
        point_name="普通温度",
        point_type="AI",
        min_range=0,
        max_range=100,
    )

    monkeypatch.setattr("app.demo.engine.random.uniform", lambda a, b: 5)
    value = simulator.generate_ai_value(point, current_value=99.0)

    assert value == 100.0


def test_generate_di_value_paths(monkeypatch):
    simulator = DataSimulator()

    door_point = Point(point_code="DI_DOOR", point_name="机房门禁状态", point_type="DI")
    monkeypatch.setattr("app.demo.engine.random.choice", lambda seq: 1)
    assert simulator.generate_di_value(door_point) == 1

    normal_point = Point(point_code="DI_NORMAL", point_name="消防输入", point_type="DI")
    monkeypatch.setattr("app.demo.engine.random.random", lambda: 0.99)
    assert simulator.generate_di_value(normal_point) == 0
    monkeypatch.setattr("app.demo.engine.random.random", lambda: 0.001)
    assert simulator.generate_di_value(normal_point) == 1


async def test_run_collection_cycle_builds_ingest_payload(async_db, monkeypatch):
    ai_point = await _add_point(async_db, "ENG_AI_001", "环境温度", "AI")
    di_point = await _add_point(async_db, "ENG_DI_001", "门禁状态", "DI")
    ao_point = await _add_point(async_db, "ENG_AO_001", "控制输出", "AO")
    async_db.add(PointRealtime(point_id=ao_point.id, value=12.0, raw_value=12.0, status="normal"))
    await async_db.commit()

    class _SessionCtx:
        def __init__(self, session):
            self.session = session

        def __call__(self):
            return self

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    captured = {}
    process_payload_mock = AsyncMock()

    async def _capture(points, session=None):
        captured["points"] = points
        captured["session"] = session
        return None

    process_payload_mock.side_effect = _capture

    monkeypatch.setattr("app.demo.engine.async_session", _SessionCtx(async_db))
    monkeypatch.setattr("app.services.ingest_pipeline.process_payload", process_payload_mock)

    simulator = DataSimulator()
    await simulator.run_collection_cycle()

    process_payload_mock.assert_awaited_once()
    ingest_points = captured["points"]
    assert captured["session"] is async_db
    assert len(ingest_points) == 3
    assert {p.point_id for p in ingest_points} == {ai_point.id, di_point.id, ao_point.id}
    assert all(p.source == "demo" for p in ingest_points)

    ao_ingest = next(p for p in ingest_points if p.point_id == ao_point.id)
    assert ao_ingest.value == 12.0

    # 缓存应记录每个点位最近值
    assert set(simulator.value_cache.keys()) == {ai_point.id, di_point.id, ao_point.id}

    # 数据库点位仍存在，避免 run_collection_cycle 误改结构性数据
    db_points = (await async_db.execute(select(Point.id))).scalars().all()
    assert set(db_points) == {ai_point.id, di_point.id, ao_point.id}


async def test_run_collection_cycle_rotates_large_point_sets(async_db, monkeypatch):
    points = [await _add_point(async_db, f"BATCH_AI_{index:03d}", f"批次点位{index}", "AI") for index in range(5)]
    await async_db.commit()

    class _SessionCtx:
        def __call__(self):
            return self

        async def __aenter__(self):
            return async_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    captured_batches = []

    async def _capture(payload, session=None):
        captured_batches.append([point.point_id for point in payload])

    monkeypatch.setattr("app.demo.engine.async_session", _SessionCtx())
    monkeypatch.setattr("app.services.ingest_pipeline.process_payload", AsyncMock(side_effect=_capture))
    monkeypatch.setattr("app.core.config.get_settings", lambda: SimpleNamespace(simulation_batch_size=2))

    simulator = DataSimulator()
    await simulator.run_collection_cycle()
    await simulator.run_collection_cycle()
    await simulator.run_collection_cycle()

    assert [len(batch) for batch in captured_batches] == [2, 2, 1]
    assert {point_id for batch in captured_batches for point_id in batch} == {point.id for point in points}
