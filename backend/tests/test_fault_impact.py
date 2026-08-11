"""故障影响分析 API 测试 — Story 8-4"""

import uuid

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.asset import Cabinet, Asset
from app.models.device import Device
from app.models.topology_config import PowerPhaseMapping, CoolingZone, CoolingZoneCabinet, CoolingZoneUnit
from app.models.cooling import CoolingUnit
from app.models.user import User, UserSession
from app.api.deps import get_db
from tests.conftest import _create_test_token, auth_headers


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="module")
async def admin_token(session_factory):
    async with session_factory() as session:
        admin = User(
            username="fault_impact_admin",
            password_hash="test-only",
            real_name="故障影响管理员",
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()
        jti = uuid.uuid4().hex
        session.add(UserSession(user_id=admin.id, token_jti=jti, is_active=True))
        await session.commit()
        return _create_test_token(admin.username, jti)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(delete(CoolingZoneUnit))
        await session.execute(delete(CoolingZoneCabinet))
        await session.execute(delete(CoolingZone))
        await session.execute(delete(CoolingUnit))
        await session.execute(delete(PowerPhaseMapping))
        await session.execute(delete(Asset))
        await session.execute(delete(Cabinet))
        await session.execute(delete(Device))
        await session.commit()
        yield session


@pytest.fixture
async def app(db_session):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    _app.dependency_overrides[get_db] = override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app, admin_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=auth_headers(admin_token),
    ) as c:
        yield c


@pytest.fixture
async def seed_pdu_device(db_session):
    dev = Device(id=801, device_code="PDU-FI-001", device_name="故障测试PDU", device_type="PDU", area_code="A")
    db_session.add(dev)
    await db_session.commit()
    return dev


@pytest.fixture
async def seed_cabinets(db_session):
    cab1 = Cabinet(
        id=101,
        cabinet_code="FI-A01",
        cabinet_name="故障测试机柜01",
        location="A区/1F",
        total_u=42,
        max_power=10.0,
        max_weight=500.0,
    )
    cab2 = Cabinet(
        id=102,
        cabinet_code="FI-A02",
        cabinet_name="故障测试机柜02",
        location="A区/1F",
        total_u=42,
        max_power=5.0,
        max_weight=300.0,
    )
    db_session.add_all([cab1, cab2])
    await db_session.commit()
    return [cab1, cab2]


@pytest.fixture
async def seed_phase_mapping(db_session, seed_cabinets, seed_pdu_device):
    ppm1 = PowerPhaseMapping(cabinet_id=101, pdu_device_id=801, phase="A", feed_type="primary")
    ppm2 = PowerPhaseMapping(cabinet_id=102, pdu_device_id=801, phase="B", feed_type="primary")
    db_session.add_all([ppm1, ppm2])
    await db_session.commit()
    return [ppm1, ppm2]


@pytest.fixture
async def seed_assets(db_session, seed_cabinets):
    a1 = Asset(
        asset_code="FI-SRV-001",
        asset_name="故障测试服务器1",
        asset_type="server",
        cabinet_id=101,
        u_position=1,
        u_height=2,
    )
    a2 = Asset(
        asset_code="FI-SRV-002",
        asset_name="故障测试服务器2",
        asset_type="server",
        cabinet_id=101,
        u_position=3,
        u_height=2,
    )
    db_session.add_all([a1, a2])
    await db_session.commit()
    return [a1, a2]


@pytest.fixture
async def seed_backup_pdu(db_session):
    """创建备用 PDU 用于双路供电测试"""
    dev = Device(id=802, device_code="PDU-FI-002", device_name="备用PDU", device_type="PDU", area_code="A")
    db_session.add(dev)
    await db_session.commit()
    return dev


@pytest.fixture
async def seed_dual_feed(db_session, seed_cabinets, seed_pdu_device, seed_backup_pdu):
    """为机柜101创建双路供电 (primary=801, backup=802)"""
    ppm_primary = PowerPhaseMapping(cabinet_id=101, pdu_device_id=801, phase="A", feed_type="primary")
    ppm_backup = PowerPhaseMapping(cabinet_id=101, pdu_device_id=802, phase="B", feed_type="backup")
    ppm_single = PowerPhaseMapping(cabinet_id=102, pdu_device_id=801, phase="B", feed_type="primary")
    db_session.add_all([ppm_primary, ppm_backup, ppm_single])
    await db_session.commit()
    return [ppm_primary, ppm_backup, ppm_single]


# ============================================================
# Tests
# ============================================================

URL = "/api/v1/topology-config/fault-impact-analysis"


@pytest.mark.anyio
async def test_fault_impact_pdu_basic(client, seed_pdu_device, seed_cabinets, seed_phase_mapping, seed_assets):
    """PDU 故障基本分析: 验证响应结构和受影响机柜"""
    resp = await client.post(
        URL,
        json={
            "fault_source_type": "pdu",
            "fault_source_id": 801,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    # 响应结构
    assert data["fault_source_type"] == "pdu"
    assert data["fault_source_id"] == 801
    assert data["fault_source_name"] == "故障测试PDU"
    assert "affected_cabinets" in data
    assert "affected_assets" in data
    assert "cooling_impacts" in data
    assert "related_alarms" in data
    assert "suggestions" in data
    assert "analysis_time" in data

    # 受影响机柜
    assert len(data["affected_cabinets"]) == 2
    cab_ids = {c["cabinet_id"] for c in data["affected_cabinets"]}
    assert cab_ids == {101, 102}

    # 受影响资产 (机柜101有2台资产)
    assert len(data["affected_assets"]) == 2

    # 建议不为空
    assert len(data["suggestions"]) > 0


@pytest.mark.anyio
async def test_fault_impact_pdu_not_found(client):
    """不存在的 PDU → 404"""
    resp = await client.post(
        URL,
        json={
            "fault_source_type": "pdu",
            "fault_source_id": 99999,
        },
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_fault_impact_invalid_type(client):
    """无效的 fault_source_type → 400"""
    resp = await client.post(
        URL,
        json={
            "fault_source_type": "invalid",
            "fault_source_id": 1,
        },
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_fault_impact_pdu_no_mapping(client, seed_pdu_device):
    """PDU 存在但无 PowerPhaseMapping → 200 + 空 affected_cabinets"""
    resp = await client.post(
        URL,
        json={
            "fault_source_type": "pdu",
            "fault_source_id": 801,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["affected_cabinets"]) == 0
    assert len(data["affected_assets"]) == 0
    # 应有"未发现受影响"的建议
    assert any("未发现" in s for s in data["suggestions"])


@pytest.mark.anyio
async def test_fault_impact_dual_feed(
    client, seed_cabinets, seed_pdu_device, seed_backup_pdu, seed_dual_feed, seed_assets
):
    """双路供电: 机柜101有 primary+backup → degraded, 机柜102只有 primary → power_loss"""
    resp = await client.post(
        URL,
        json={
            "fault_source_type": "pdu",
            "fault_source_id": 801,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    cab_map = {c["cabinet_id"]: c for c in data["affected_cabinets"]}

    # 机柜101: 有备用PDU 802 → degraded
    assert 101 in cab_map
    assert cab_map[101]["impact_level"] == "degraded"
    assert cab_map[101]["has_redundancy"] is True

    # 机柜102: 只有 PDU 801 → power_loss
    assert 102 in cab_map
    assert cab_map[102]["impact_level"] == "power_loss"
    assert cab_map[102]["has_redundancy"] is False

    # 建议中应包含降级和断电信息
    suggestions_text = " ".join(data["suggestions"])
    assert "降级" in suggestions_text
    assert "失去供电" in suggestions_text
