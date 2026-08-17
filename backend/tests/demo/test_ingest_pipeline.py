"""统一入库管道测试。"""

import time
from datetime import datetime
from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.models.gateway import PointDataLatest
from app.models.history import PointHistory
from app.models.point import Point, PointRealtime
from app.services import ingest_pipeline
from app.services.ingest_pipeline import IngestPoint, process_payload


async def _create_points(async_db, count: int, *, point_type: str = "AI", enabled: bool = True, start_index: int = 1):
    points = []
    for idx in range(start_index, start_index + count):
        point = Point(
            point_code=f"TEST_{point_type}_{idx:04d}",
            point_name=f"测试点位{idx}",
            point_type=point_type,
            device_type="TEST",
            is_enabled=enabled,
            min_range=0,
            max_range=100,
        )
        async_db.add(point)
        points.append(point)
    await async_db.flush()
    return points


async def _stub_side_effects(monkeypatch):
    monkeypatch.setattr(ingest_pipeline, "_evaluate_alarms", AsyncMock(return_value={"created": 0, "resolved": 0}))
    monkeypatch.setattr(ingest_pipeline, "_broadcast_realtime", AsyncMock())
    monkeypatch.setattr(ingest_pipeline, "_update_redis_cache", AsyncMock())


def _assert_recent(ts: datetime):
    assert isinstance(ts, datetime)
    assert (datetime.now() - ts).total_seconds() < 10


async def test_process_payload_batch_and_boundary(async_db, monkeypatch):
    ingest_pipeline.invalidate_point_cache()
    await _stub_side_effects(monkeypatch)

    ai_point = (await _create_points(async_db, 1, point_type="AI"))[0]
    di_point = (await _create_points(async_db, 1, point_type="DI", start_index=1000))[0]
    disabled_point = (await _create_points(async_db, 1, point_type="AI", enabled=False, start_index=2000))[0]
    await async_db.commit()

    payload = [
        IngestPoint(point_id=ai_point.id, value=21.5, source="demo"),
        IngestPoint(point_id=di_point.id, value=1, source="demo"),
        IngestPoint(point_id=disabled_point.id, value=66.6, source="demo"),
        IngestPoint(point_id=999999, value=12.3, source="demo"),
    ]

    result = await process_payload(payload, session=async_db)

    assert result.total == 4
    assert result.written == 2
    assert result.alarms_created == 0
    assert result.alarms_resolved == 0
    assert any("点位 999999 不存在" in err for err in result.errors)

    realtime_rows = (await async_db.execute(select(PointRealtime))).scalars().all()
    assert len(realtime_rows) == 2
    di_row = next(row for row in realtime_rows if row.point_id == di_point.id)
    assert di_row.value_text == "告警"

    latest_rows = (await async_db.execute(select(PointDataLatest))).scalars().all()
    assert len(latest_rows) == 2
    assert {row.point_id for row in latest_rows} == {str(ai_point.id), str(di_point.id)}

    history_rows = (await async_db.execute(select(PointHistory))).scalars().all()
    assert len(history_rows) == 1
    assert history_rows[0].point_id == ai_point.id

    _assert_recent(payload[0].timestamp)
    _assert_recent(payload[1].timestamp)


async def test_process_payload_empty_returns_zero(async_db):
    ingest_pipeline.invalidate_point_cache()

    result = await process_payload([], session=async_db)

    assert result.total == 0
    assert result.written == 0
    assert result.alarms_created == 0
    assert result.alarms_resolved == 0
    assert result.errors == []


async def test_broadcast_realtime_skips_points_without_site(monkeypatch):
    broadcast = AsyncMock(return_value=1)
    monkeypatch.setattr(ingest_pipeline.ws_manager, "broadcast_realtime", broadcast)
    monkeypatch.setattr(
        ingest_pipeline,
        "_point_meta_cache",
        {
            1: {"point_code": "NO_SITE", "point_type": "AI", "site_id": None},
            2: {"point_code": "SITE_1", "point_type": "AI", "site_id": 1},
        },
    )

    await ingest_pipeline._broadcast_realtime(
        [IngestPoint(point_id=1, value=10), IngestPoint(point_id=2, value=20)]
    )

    broadcast.assert_awaited_once()
    assert broadcast.await_args.kwargs["site_id"] == 1
    assert [item["point_id"] for item in broadcast.await_args.args[0]] == [2]


async def test_process_payload_300_points_performance(async_db, monkeypatch):
    ingest_pipeline.invalidate_point_cache()
    await _stub_side_effects(monkeypatch)

    points = await _create_points(async_db, 300, point_type="AI", start_index=3000)
    await async_db.commit()

    payload = [IngestPoint(point_id=point.id, value=float(i % 100), source="benchmark") for i, point in enumerate(points)]

    start = time.perf_counter()
    result = await process_payload(payload, session=async_db)
    elapsed = time.perf_counter() - start

    assert result.total == 300
    assert result.written == 300
    assert not result.errors

    rt_count = await async_db.scalar(select(func.count(PointRealtime.point_id)))
    latest_count = await async_db.scalar(select(func.count(PointDataLatest.point_id)))
    history_count = await async_db.scalar(select(func.count(PointHistory.id)))
    assert rt_count == 300
    assert latest_count == 300
    assert history_count == 300

    # 性能基准: 300 点位批量处理在单机测试环境应可在 10 秒内完成
    assert elapsed < 10
