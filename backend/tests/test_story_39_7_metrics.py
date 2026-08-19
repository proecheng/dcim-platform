import logging

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.metrics import MetricsCollector, metrics_collector
from app.middleware.metrics_middleware import MetricsMiddleware


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


@pytest.mark.anyio
async def test_metrics_collector_reports_bounded_rolling_window_and_nearest_rank_percentiles():
    clock = FakeClock()
    collector = MetricsCollector(clock=clock, rolling_window_seconds=300)

    for duration_ms, status_code in ((10, 200), (20, 200), (30, 500), (40, 404)):
        await collector.record_request("GET", "/api/v1/example", status_code, duration_ms)

    snapshot = await collector.get_metrics()

    assert snapshot["requests"] == {"total": 4, "errors": 2, "error_rate_percent": 50.0}
    assert snapshot["rolling_window"] == {
        "window_seconds": 300,
        "requests": 4,
        "errors": 2,
        "request_rate_per_second": 0.0133,
        "error_rate_percent": 50.0,
    }
    assert snapshot["latency"]["p50_ms"] == 20
    assert snapshot["latency"]["p95_ms"] == 40
    assert snapshot["latency"]["p99_ms"] == 40

    clock.value += 301
    expired = await collector.get_metrics()
    assert expired["requests"]["total"] == 4
    assert expired["rolling_window"]["requests"] == 0
    assert expired["rolling_window"]["error_rate_percent"] == 0.0


@pytest.mark.anyio
async def test_metrics_collector_bounds_cumulative_samples_without_losing_counters():
    clock = FakeClock()
    collector = MetricsCollector(clock=clock, max_duration_samples=3)

    for duration_ms in (10, 20, 30, 40):
        await collector.record_request("POST", "/api/v1/items", 201, duration_ms)

    snapshot = await collector.get_metrics()
    assert snapshot["requests"]["total"] == 4
    assert snapshot["latency"]["min_ms"] == 20
    assert snapshot["latency"]["max_ms"] == 40
    assert snapshot["endpoints"]["POST /api/v1/items"]["count"] == 4


@pytest.mark.anyio
async def test_rolling_window_aggregates_high_volume_without_dropping_requests():
    clock = FakeClock()
    collector = MetricsCollector(clock=clock, rolling_window_seconds=300)

    for index in range(100_001):
        await collector.record_request("GET", "/bulk", 500 if index == 100_000 else 200, 1.0)

    snapshot = await collector.get_metrics()
    assert snapshot["rolling_window"]["requests"] == 100_001
    assert snapshot["rolling_window"]["errors"] == 1
    assert snapshot["rolling_window"]["error_rate_percent"] == 0.0


@pytest.mark.anyio
async def test_rolling_window_uses_exact_five_minute_boundary():
    clock = FakeClock(1_000.25)
    collector = MetricsCollector(clock=clock, rolling_window_seconds=300)
    await collector.record_request("GET", "/boundary", 200, 1.0)

    clock.value = 1_300.249
    assert (await collector.get_metrics())["rolling_window"]["requests"] == 1
    clock.value = 1_300.25
    assert (await collector.get_metrics())["rolling_window"]["requests"] == 0


@pytest.mark.anyio
async def test_metrics_middleware_records_unhandled_exception_and_skips_probes(caplog):
    await metrics_collector.reset()

    async def ok(_request):
        return JSONResponse({"ok": True})

    async def explode(_request):
        raise RuntimeError("request exploded")

    test_app = Starlette(
        routes=[
            Route("/api/health", ok),
            Route("/api/metrics", ok),
            Route("/api/v1/system/health", ok),
            Route("/business", ok),
            Route("/explode", explode),
        ]
    )
    test_app.add_middleware(MetricsMiddleware)

    caplog.set_level(logging.ERROR, logger="app.middleware.metrics_middleware")
    async with AsyncClient(transport=ASGITransport(app=test_app, raise_app_exceptions=False), base_url="http://test") as client:
        assert (await client.get("/api/health")).status_code == 200
        assert (await client.get("/api/metrics")).status_code == 200
        assert (await client.get("/api/v1/system/health")).status_code == 200
        assert (await client.get("/business")).status_code == 200
        assert (await client.get("/explode")).status_code == 500

    snapshot = await metrics_collector.get_metrics()
    assert snapshot["requests"]["total"] == 2
    assert snapshot["requests"]["errors"] == 1
    assert snapshot["status_codes"] == {200: 1, 500: 1}
    assert any(record.message == "Unhandled request exception" for record in caplog.records)
    assert any(getattr(record, "request_path", None) == "/explode" for record in caplog.records)

    await metrics_collector.reset()
