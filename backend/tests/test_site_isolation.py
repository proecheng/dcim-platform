"""站点级数据隔离 API 测试 (Story 13-5)"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.user import User, UserSite
from app.models.device import Device
from app.models.spatial import Site
from app.core.security import get_password_hash
from app.api.deps import get_db, require_admin, require_operator, require_viewer, get_user_site_ids


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
        await session.execute(delete(UserSite))
        await session.execute(delete(Device))
        await session.execute(delete(Site))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 99999
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_admin

    # admin 默认不过滤站点
    async def override_get_user_site_ids():
        return None

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[get_user_site_ids] = override_get_user_site_ids
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_sites(db_session):
    """创建测试站点"""
    site_a = Site(site_code="SITE-A", site_name="北京站点")
    site_b = Site(site_code="SITE-B", site_name="上海站点")
    db_session.add_all([site_a, site_b])
    await db_session.commit()
    await db_session.refresh(site_a)
    await db_session.refresh(site_b)
    return site_a, site_b


@pytest.fixture
async def seed_user(db_session):
    """创建测试用户"""
    user = User(
        username="operator1",
        password_hash=get_password_hash("Test@1234"),
        role="operator",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ============================================================
# Constants
# ============================================================

USERS_URL = "/api/v1/users"
DEVICES_URL = "/api/v1/devices"


# ============================================================
# Tests
# ============================================================

@pytest.mark.anyio
async def test_assign_user_sites(client, seed_sites, seed_user):
    """为用户分配站点权限"""
    site_a, site_b = seed_sites
    resp = await client.put(
        f"{USERS_URL}/{seed_user.id}/sites",
        json={"site_ids": [site_a.id, site_b.id]}
    )
    assert resp.status_code == 200
    assert "2" in resp.json()["message"]


@pytest.mark.anyio
async def test_get_user_sites(client, seed_sites, seed_user, db_session):
    """查询用户站点列表"""
    site_a, site_b = seed_sites
    # 先分配
    db_session.add(UserSite(user_id=seed_user.id, site_id=site_a.id))
    await db_session.commit()

    resp = await client.get(f"{USERS_URL}/{seed_user.id}/sites")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["site_code"] == "SITE-A"
    assert data[0]["site_name"] == "北京站点"


@pytest.mark.anyio
async def test_update_user_sites_replaces(client, seed_sites, seed_user, db_session):
    """更新用户站点权限（全量替换）"""
    site_a, site_b = seed_sites
    # 先分配 site_a
    db_session.add(UserSite(user_id=seed_user.id, site_id=site_a.id))
    await db_session.commit()

    # 替换为 site_b
    resp = await client.put(
        f"{USERS_URL}/{seed_user.id}/sites",
        json={"site_ids": [site_b.id]}
    )
    assert resp.status_code == 200

    # 验证只有 site_b
    get_resp = await client.get(f"{USERS_URL}/{seed_user.id}/sites")
    data = get_resp.json()
    assert len(data) == 1
    assert data[0]["site_code"] == "SITE-B"


@pytest.mark.anyio
async def test_assign_invalid_site(client, seed_user):
    """分配不存在的站点"""
    resp = await client.put(
        f"{USERS_URL}/{seed_user.id}/sites",
        json={"site_ids": [99999]}
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_get_site_users(client, seed_sites, seed_user, db_session):
    """查询站点下的用户列表"""
    site_a, _ = seed_sites
    db_session.add(UserSite(user_id=seed_user.id, site_id=site_a.id))
    await db_session.commit()

    resp = await client.get(f"{USERS_URL}/sites/{site_a.id}/users")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "operator1"


@pytest.mark.anyio
async def test_device_site_filter_admin_sees_all(client, seed_sites, db_session):
    """admin 可见所有设备（不受站点限制）"""
    site_a, site_b = seed_sites
    db_session.add(Device(
        device_code="DEV-A1", device_name="设备A1",
        device_type="UPS", area_code="A", site_id=site_a.id
    ))
    db_session.add(Device(
        device_code="DEV-B1", device_name="设备B1",
        device_type="AC", area_code="B", site_id=site_b.id
    ))
    db_session.add(Device(
        device_code="DEV-NONE", device_name="无站点设备",
        device_type="PDU", area_code="C", site_id=None
    ))
    await db_session.commit()

    resp = await client.get(DEVICES_URL)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.anyio
async def test_device_site_filter_operator(client, app, seed_sites, db_session):
    """operator 仅可见授权站点设备"""
    site_a, site_b = seed_sites
    db_session.add(Device(
        device_code="DEV-A2", device_name="设备A2",
        device_type="UPS", area_code="A", site_id=site_a.id
    ))
    db_session.add(Device(
        device_code="DEV-B2", device_name="设备B2",
        device_type="AC", area_code="B", site_id=site_b.id
    ))
    await db_session.commit()

    # 模拟 operator 只有 site_a 权限
    async def override_site_ids():
        return [site_a.id]

    app.dependency_overrides[get_user_site_ids] = override_site_ids

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(DEVICES_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["device_code"] == "DEV-A2"

    # 恢复 admin 模式
    async def override_admin_site_ids():
        return None
    app.dependency_overrides[get_user_site_ids] = override_admin_site_ids


@pytest.mark.anyio
async def test_device_with_site_id_field(client, seed_sites, db_session):
    """设备创建时可指定 site_id"""
    site_a, _ = seed_sites
    resp = await client.post(DEVICES_URL, json={
        "device_code": "DEV-NEW",
        "device_name": "新设备",
        "device_type": "TH",
        "area_code": "D",
        "site_id": site_a.id
    })
    assert resp.status_code == 200
    assert resp.json()["site_id"] == site_a.id


@pytest.mark.anyio
async def test_user_not_found_for_sites(client):
    """查询不存在用户的站点"""
    resp = await client.get(f"{USERS_URL}/88888/sites")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_site_not_found_for_users(client):
    """查询不存在站点的用户"""
    resp = await client.get(f"{USERS_URL}/sites/88888/users")
    assert resp.status_code == 404
