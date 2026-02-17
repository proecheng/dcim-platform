"""设备状态看板 API 测试 — Story 4.3"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, PropertyMock
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.api.deps import get_db, require_viewer
from app.models.device import Device
from app.models.user import User
from app.main import app


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def async_db():
    """创建测试用异步数据库"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db):
    """创建测试 HTTP 客户端（跳过认证）"""
    mock_user = User(id=1, username="test_admin", role="admin", is_active=True, password_hash="x")
    app.dependency_overrides[require_viewer] = lambda: mock_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_devices(async_db):
    """创建多区域多类型设备"""
    async with async_db() as session:
        devices = [
            Device(device_code="UPS-A1-001", device_name="A1区UPS-1", device_type="UPS", area_code="A1", status="online"),
            Device(device_code="UPS-A1-002", device_name="A1区UPS-2", device_type="UPS", area_code="A1", status="offline"),
            Device(device_code="AC-A1-001", device_name="A1区空调-1", device_type="AC", area_code="A1", status="online"),
            Device(device_code="UPS-B1-001", device_name="B1区UPS-1", device_type="UPS", area_code="B1", status="alarm"),
            Device(device_code="TH-B1-001", device_name="B1区温湿度-1", device_type="TH", area_code="B1", status="maintenance"),
        ]
        session.add_all(devices)
        await session.commit()
        return [d.id for d in devices]


# ============================================================
# 测试
# ============================================================

class TestDeviceStatusBoard:
    """设备状态看板 API 测试"""

    @pytest.mark.asyncio
    async def test_status_board_grouped(self, client: AsyncClient, seed_devices):
        """测试分组统计和汇总"""
        resp = await client.get("/api/v1/devices/status-board")
        assert resp.status_code == 200

        data = resp.json()
        summary = data["summary"]
        assert summary["total"] == 5
        assert summary["online"] == 2
        assert summary["offline"] == 1
        assert summary["alarm"] == 1
        assert summary["maintenance"] == 1

        groups = data["groups"]
        # 应有 4 个分组: A1_UPS, A1_AC, B1_UPS, B1_TH
        assert len(groups) == 4

        # 验证 A1_UPS 分组有 2 台设备
        a1_ups = next(g for g in groups if g["area_code"] == "A1" and g["device_type"] == "UPS")
        assert len(a1_ups["devices"]) == 2
        assert a1_ups["stats"]["online"] == 1
        assert a1_ups["stats"]["offline"] == 1

    @pytest.mark.asyncio
    async def test_status_board_filter_area(self, client: AsyncClient, seed_devices):
        """测试按区域筛选"""
        resp = await client.get("/api/v1/devices/status-board", params={"area_code": "B1"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["summary"]["total"] == 2
        for group in data["groups"]:
            assert group["area_code"] == "B1"

    @pytest.mark.asyncio
    async def test_status_board_filter_type(self, client: AsyncClient, seed_devices):
        """测试按设备类型筛选"""
        resp = await client.get("/api/v1/devices/status-board", params={"device_type": "UPS"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["summary"]["total"] == 3
        for group in data["groups"]:
            assert group["device_type"] == "UPS"

    @pytest.mark.asyncio
    async def test_status_board_redis_online(self, client: AsyncClient, seed_devices):
        """测试 Redis 在线状态覆盖数据库状态"""
        device_ids = seed_devices
        # device_ids[1] 是 A1区UPS-2，数据库状态 offline
        # 模拟 Redis 返回该设备在线

        mock_redis = AsyncMock()
        mock_redis.is_available = True

        async def mock_mget(keys):
            results = []
            for key in keys:
                # 只有 device_ids[1] 在 Redis 中有值（在线）
                if key == f"device:{device_ids[1]}:online":
                    results.append("2026-01-01T00:00:00")
                else:
                    results.append(None)
            return results

        mock_redis.mget = mock_mget

        with patch("app.api.v1.device.redis_service", mock_redis):
            resp = await client.get("/api/v1/devices/status-board")

        assert resp.status_code == 200
        data = resp.json()

        # device_ids[1] 应该被 Redis 覆盖为 online
        # 原来: online=2, offline=1 → 现在: online=3, offline=0
        assert data["summary"]["online"] == 3
        assert data["summary"]["offline"] == 0

        # 验证该设备在分组中状态为 online
        a1_ups = next(g for g in data["groups"] if g["area_code"] == "A1" and g["device_type"] == "UPS")
        ups2 = next(d for d in a1_ups["devices"] if d["device_code"] == "UPS-A1-002")
        assert ups2["status"] == "online"
