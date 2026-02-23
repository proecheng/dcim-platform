"""设备详情聚合 API 测试 — Story 4.2"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.api.deps import get_db, require_viewer
from app.models.device import Device
from app.models.point import Point, PointRealtime
from app.models.alarm import Alarm
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
async def seed_device_with_points(async_db):
    """创建设备 + 点位 + 实时数据 + 告警"""
    async with async_db() as session:
        device = Device(
            device_code="UPS-A1-001",
            device_name="A1区UPS-1",
            device_type="UPS",
            area_code="A1",
            status="online",
        )
        session.add(device)
        await session.flush()

        p1 = Point(
            point_code="UPS_A1_001_V",
            point_name="输出电压",
            point_type="AI",
            device_id=device.id,
            device_type="UPS",
            unit="V",
        )
        p2 = Point(
            point_code="UPS_A1_001_S",
            point_name="运行状态",
            point_type="DI",
            device_id=device.id,
            device_type="UPS",
        )
        session.add_all([p1, p2])
        await session.flush()

        rt1 = PointRealtime(
            point_id=p1.id,
            value=220.5,
            value_text="220.5",
            quality=0,
            status="normal",
        )
        session.add(rt1)

        alarm_active = Alarm(
            alarm_no="ALM-001",
            point_id=p1.id,
            alarm_level="major",
            alarm_message="电压偏高",
            trigger_value=220.5,
            threshold_value=220.0,
            status="active",
        )
        alarm_resolved = Alarm(
            alarm_no="ALM-002",
            point_id=p1.id,
            alarm_level="minor",
            alarm_message="电压波动",
            trigger_value=219.0,
            threshold_value=220.0,
            status="resolved",
        )
        session.add_all([alarm_active, alarm_resolved])
        await session.commit()

        return device.id


# ============================================================
# 测试
# ============================================================


class TestDeviceDetail:
    """设备详情聚合 API 测试"""

    @pytest.mark.asyncio
    async def test_device_detail_success(self, client: AsyncClient, seed_device_with_points):
        """测试设备详情返回完整数据结构"""
        device_id = seed_device_with_points
        resp = await client.get(f"/api/v1/devices/{device_id}/detail")
        assert resp.status_code == 200

        data = resp.json()
        # 设备信息
        assert data["device"]["device_code"] == "UPS-A1-001"
        assert data["device"]["device_name"] == "A1区UPS-1"
        assert data["device"]["device_type"] == "UPS"

        # 点位列表（2个）
        assert len(data["points"]) == 2
        ai_point = next(p for p in data["points"] if p["point_type"] == "AI")
        assert ai_point["point_code"] == "UPS_A1_001_V"
        assert ai_point["value"] == 220.5
        assert ai_point["unit"] == "V"
        assert ai_point["status"] == "normal"

        di_point = next(p for p in data["points"] if p["point_type"] == "DI")
        assert di_point["value"] is None
        assert di_point["status"] == "offline"

        # 告警（仅 active/acknowledged）
        assert len(data["alarms"]) == 1
        assert data["alarms"][0]["alarm_no"] == "ALM-001"
        assert data["alarms"][0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_device_detail_not_found(self, client: AsyncClient, async_db):
        """测试设备不存在返回 404"""
        resp = await client.get("/api/v1/devices/99999/detail")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_device_detail_no_points(self, client: AsyncClient, async_db):
        """测试设备无关联点位时返回空列表"""
        async with async_db() as session:
            device = Device(
                device_code="AC-B1-001",
                device_name="B1区空调-1",
                device_type="AC",
                area_code="B1",
                status="online",
            )
            session.add(device)
            await session.commit()
            device_id = device.id

        resp = await client.get(f"/api/v1/devices/{device_id}/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["device"]["device_code"] == "AC-B1-001"
        assert data["points"] == []
        assert data["alarms"] == []

    @pytest.mark.asyncio
    async def test_device_detail_only_active_alarms(self, client: AsyncClient, seed_device_with_points):
        """测试仅返回 active/acknowledged 状态的告警"""
        device_id = seed_device_with_points
        resp = await client.get(f"/api/v1/devices/{device_id}/detail")
        assert resp.status_code == 200

        data = resp.json()
        for alarm in data["alarms"]:
            assert alarm["status"] in ("active", "acknowledged")
        # resolved 告警不应出现
        alarm_nos = [a["alarm_no"] for a in data["alarms"]]
        assert "ALM-002" not in alarm_nos
