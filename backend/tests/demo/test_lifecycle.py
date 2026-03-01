"""演示模块生命周期钩子测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.demo import lifecycle


class _SessionCtx:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeTask:
    def __init__(self):
        self._cancelled = False

    def done(self):
        return False

    def cancel(self):
        self._cancelled = True

    def __await__(self):
        async def _raise_cancelled():
            raise asyncio.CancelledError

        return _raise_cancelled().__await__()


async def test_lifecycle_startup_noop_when_demo_disabled(monkeypatch):
    lifecycle._simulator_task = None

    monkeypatch.setattr("app.demo.config.is_demo_enabled", lambda: False)
    create_task_mock = MagicMock()
    monkeypatch.setattr("app.demo.lifecycle.asyncio.create_task", create_task_mock)

    await lifecycle.startup()

    create_task_mock.assert_not_called()
    assert lifecycle._simulator_task is None


async def test_lifecycle_startup_initializes_seeds_and_simulator(async_db, monkeypatch):
    lifecycle._simulator_task = None

    seed_dc = AsyncMock()
    seed_power = AsyncMock()
    seed_cooling = AsyncMock()
    sim_start = AsyncMock()
    fake_task = _FakeTask()

    class _FakeSyncService:
        def __init__(self, _session):
            pass

        async def migrate_existing_data(self):
            return {
                "linked_panels": 1,
                "linked_power_devices": 2,
                "created_devices_for_panels": 0,
                "created_devices_for_power": 0,
            }

    monkeypatch.setattr("app.demo.config.is_demo_enabled", lambda: True)
    monkeypatch.setattr("app.demo.seeds.datacenter_seed.seed_datacenter", seed_dc)
    monkeypatch.setattr("app.demo.seeds.power_seed.seed_power_devices", seed_power)
    monkeypatch.setattr("app.demo.seeds.cooling_seed.seed_cooling_devices", seed_cooling)
    monkeypatch.setattr("app.services.device_sync.DeviceSyncService", _FakeSyncService)
    monkeypatch.setattr("app.core.database.async_session", _SessionCtx(async_db))
    monkeypatch.setattr("app.demo.engine.simulator.start", sim_start)

    def _fake_create_task(coro):
        # 测试中不真正调度后台任务，主动关闭协程避免未 await 警告。
        coro.close()
        return fake_task

    monkeypatch.setattr("app.demo.lifecycle.asyncio.create_task", _fake_create_task)

    await lifecycle.startup()

    seed_dc.assert_awaited_once()
    seed_power.assert_awaited_once()
    seed_cooling.assert_awaited_once()
    sim_start.assert_called_once_with(interval=5)
    assert lifecycle._simulator_task is fake_task


async def test_lifecycle_shutdown_stops_and_cancels_task(monkeypatch):
    monkeypatch.setattr("app.demo.config.is_demo_enabled", lambda: True)

    stop_mock = MagicMock()
    monkeypatch.setattr("app.demo.engine.simulator.stop", stop_mock)

    task = asyncio.create_task(asyncio.sleep(60))
    lifecycle._simulator_task = task

    await lifecycle.shutdown()

    stop_mock.assert_called_once()
    assert lifecycle._simulator_task is None
    assert task.cancelled()
