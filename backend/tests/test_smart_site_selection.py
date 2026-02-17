"""智能选址推荐 API 测试 — Story 8-3"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.asset import Cabinet, Asset
from app.models.device import Device
from app.models.topology_config import PowerPhaseMapping, CoolingZone, CoolingZoneCabinet
from app.models.user import User
from app.api.deps import get_db, require_viewer


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


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(delete(CoolingZoneCabinet))
        await session.execute(delete(CoolingZone))
        await session.execute(delete(PowerPhaseMapping))
        await session.execute(delete(Asset))
        await session.execute(delete(Cabinet))
        await session.execute(delete(Device))
        await session.commit()
        yield session


@pytest.fixture
def mock_viewer():
    user = User()
    user.id = 1
    user.username = "test_viewer"
    user.role = "viewer"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_viewer):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_viewer():
        return mock_viewer

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_viewer] = override_require_viewer
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_cabinets(db_session):
    cab1 = Cabinet(
        id=1, cabinet_code="A-01", cabinet_name="A区机柜01",
        location="A区/1F/Room1", total_u=42, max_power=10.0, max_weight=500.0,
    )
    cab2 = Cabinet(
        id=2, cabinet_code="A-02", cabinet_name="A区机柜02",
        location="A区/1F/Room1", total_u=42, max_power=5.0, max_weight=300.0,
    )
    cab3 = Cabinet(
        id=3, cabinet_code="B-01", cabinet_name="B区机柜01",
        location="B区/2F/Room2", total_u=42, max_power=20.0, max_weight=1000.0,
    )
    cab4 = Cabinet(
        id=4, cabinet_code="C-01", cabinet_name="C区机柜01",
        location="C区/3F/Room3", total_u=42, max_power=None, max_weight=None,
    )
    db_session.add_all([cab1, cab2, cab3, cab4])
    await db_session.commit()
    return [cab1, cab2, cab3, cab4]


@pytest.fixture
async def seed_assets(db_session, seed_cabinets):
    a1 = Asset(
        asset_code="SRV-001", asset_name="服务器1", asset_type="server",
        cabinet_id=1, u_position=1, u_height=30,
    )
    db_session.add(a1)
    await db_session.commit()
    return [a1]


@pytest.fixture
async def seed_pdu_device(db_session):
    dev = Device(id=901, device_code="PDU-001", device_name="测试PDU", device_type="PDU", area_code="A")
    db_session.add(dev)
    await db_session.commit()
    return dev


@pytest.fixture
async def seed_phase_mapping(db_session, seed_cabinets, seed_pdu_device):
    ppm1 = PowerPhaseMapping(cabinet_id=1, pdu_device_id=901, phase="A", feed_type="primary")
    ppm2 = PowerPhaseMapping(cabinet_id=2, pdu_device_id=901, phase="B", feed_type="primary")
    db_session.add_all([ppm1, ppm2])
    await db_session.commit()
    return [ppm1, ppm2]


@pytest.fixture
async def seed_cooling_zone(db_session, seed_cabinets):
    zone = CoolingZone(id=1, zone_code="CZ-001", zone_name="测试制冷区", design_capacity_kw=100.0)
    db_session.add(zone)
    await db_session.flush()
    czc1 = CoolingZoneCabinet(zone_id=1, cabinet_id=1)
    czc2 = CoolingZoneCabinet(zone_id=1, cabinet_id=2)
    db_session.add_all([czc1, czc2])
    await db_session.commit()
    return zone


# ============================================================
# Tests
# ============================================================

URL = "/api/v1/topology-config/smart-site-selection"


@pytest.mark.anyio
async def test_smart_site_basic(client, seed_cabinets):
    resp = await client.post(URL, json={"required_u": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    assert "total_evaluated" in data
    assert data["total_evaluated"] == 4
    assert len(data["candidates"]) > 0
    c = data["candidates"][0]
    assert "dimensions" in c
    assert len(c["dimensions"]) == 5
    assert "confidence" in c


@pytest.mark.anyio
async def test_smart_site_space_scoring(client, seed_cabinets, seed_assets):
    resp = await client.post(URL, json={"required_u": 20})
    data = resp.json()
    ids = [c["cabinet_id"] for c in data["candidates"]]
    assert 1 not in ids
    assert data["qualified_count"] == 3


@pytest.mark.anyio
async def test_smart_site_power_scoring(client, seed_cabinets):
    resp = await client.post(URL, json={"required_u": 1, "required_power_kw": 8.0})
    data = resp.json()
    for c in data["candidates"]:
        power_dim = next(d for d in c["dimensions"] if d["dimension"] == "电力容量")
        if c["cabinet_id"] == 4:
            assert power_dim["data_available"] is False
            assert power_dim["score"] == 50.0
        elif c["cabinet_id"] == 3:
            assert power_dim["data_available"] is True
            assert power_dim["score"] == 100.0


@pytest.mark.anyio
async def test_smart_site_phase_balance(client, seed_cabinets, seed_pdu_device, seed_phase_mapping):
    resp = await client.post(URL, json={"required_u": 1, "required_power_kw": 5.0})
    data = resp.json()
    for c in data["candidates"]:
        phase_dim = next(d for d in c["dimensions"] if d["dimension"] == "三相平衡度")
        if c["cabinet_id"] in (1, 2):
            assert phase_dim["data_available"] is True
        else:
            assert phase_dim["data_available"] is False
            assert phase_dim["score"] == 50.0


@pytest.mark.anyio
async def test_smart_site_temperature(client, seed_cabinets, seed_cooling_zone):
    resp = await client.post(URL, json={"required_u": 1})
    data = resp.json()
    for c in data["candidates"]:
        temp_dim = next(d for d in c["dimensions"] if d["dimension"] == "温度环境")
        if c["cabinet_id"] in (1, 2):
            assert temp_dim["data_available"] is True
        else:
            assert temp_dim["data_available"] is False


@pytest.mark.anyio
async def test_smart_site_cooling_remaining(client, seed_cabinets, seed_cooling_zone):
    resp = await client.post(URL, json={"required_u": 1, "required_power_kw": 5.0})
    data = resp.json()
    for c in data["candidates"]:
        cool_dim = next(d for d in c["dimensions"] if d["dimension"] == "制冷余量")
        if c["cabinet_id"] in (1, 2):
            assert cool_dim["data_available"] is True
        else:
            assert cool_dim["data_available"] is False


@pytest.mark.anyio
async def test_smart_site_confidence(client, seed_cabinets, seed_pdu_device, seed_phase_mapping, seed_cooling_zone):
    resp = await client.post(URL, json={"required_u": 1, "required_power_kw": 5.0})
    data = resp.json()
    for c in data["candidates"]:
        if c["cabinet_id"] == 1:
            assert c["confidence"] == "high"
        elif c["cabinet_id"] == 3:
            assert c["confidence"] == "low"


@pytest.mark.anyio
async def test_smart_site_custom_weights(client, seed_cabinets):
    resp = await client.post(URL, json={
        "required_u": 1,
        "weights": {"space": 50, "power": 50, "phase_balance": 50, "temperature": 50, "cooling": 50}
    })
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_smart_site_no_candidates(client, seed_cabinets):
    resp = await client.post(URL, json={"required_u": 999})
    data = resp.json()
    assert data["qualified_count"] == 0
    assert len(data["candidates"]) == 0


@pytest.mark.anyio
async def test_smart_site_required_power_zero(client, seed_cabinets):
    resp = await client.post(URL, json={"required_u": 1, "required_power_kw": 0})
    assert resp.status_code == 200
    data = resp.json()
    for c in data["candidates"]:
        power_dim = next(d for d in c["dimensions"] if d["dimension"] == "电力容量")
        assert power_dim["score"] == 100.0
        cool_dim = next(d for d in c["dimensions"] if d["dimension"] == "制冷余量")
        assert cool_dim["score"] == 100.0
