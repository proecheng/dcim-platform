"""联动引擎 API 测试 — Story 9-1"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.linkage import LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog
from app.models.user import User
from app.api.deps import get_db, require_admin, require_operator, require_viewer


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
        await session.execute(delete(LinkageLog))
        await session.execute(delete(LinkageExecution))
        await session.execute(delete(LinkageAction))
        await session.execute(delete(LinkagePolicy))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer():
    user = User()
    user.id = 2
    user.username = "test_viewer"
    user.role = "viewer"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin, mock_viewer):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_viewer

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_policy(db_session):
    """创建测试策略"""
    policy = LinkagePolicy(
        name="测试告警联动",
        trigger_type="alarm.triggered",
        trigger_condition={"alarm_level": "critical"},
        priority="normal",
        is_enabled=True,
        is_system=False,
    )
    db_session.add(policy)
    await db_session.flush()

    action = LinkageAction(
        policy_id=policy.id,
        action_type="ALARM_NOTIFY",
        action_config={"message": "联动测试通知"},
        sort_order=0,
        timeout_seconds=3,
    )
    db_session.add(action)
    await db_session.commit()
    return policy


@pytest.fixture
async def seed_system_policy(db_session):
    """创建系统策略"""
    policy = LinkagePolicy(
        name="消防联动策略",
        trigger_type="alarm.triggered",
        trigger_condition={"alarm_level": "critical"},
        priority="fire_signal",
        is_enabled=True,
        is_system=True,
    )
    db_session.add(policy)
    await db_session.commit()
    return policy


# ============================================================
# Tests
# ============================================================

BASE_URL = "/api/v1/linkage"


@pytest.mark.anyio
async def test_create_policy(client):
    """创建联动策略"""
    resp = await client.post(f"{BASE_URL}/policies", json={
        "name": "新建测试策略",
        "trigger_type": "alarm.triggered",
        "trigger_condition": {"alarm_level": "major"},
        "priority": "normal",
        "actions": [
            {
                "action_type": "ALARM_NOTIFY",
                "action_config": {"message": "测试"},
                "sort_order": 0,
                "timeout_seconds": 5,
                "retry_count": 0,
            }
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["message"] == "策略创建成功"


@pytest.mark.anyio
async def test_list_policies(client, seed_policy):
    """获取策略列表"""
    resp = await client.get(f"{BASE_URL}/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_get_policy_detail(client, seed_policy):
    """获取策略详情"""
    resp = await client.get(f"{BASE_URL}/policies/{seed_policy.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试告警联动"
    assert data["trigger_type"] == "alarm.triggered"
    assert len(data["actions"]) == 1


@pytest.mark.anyio
async def test_toggle_policy(client, seed_policy):
    """切换策略启用状态"""
    resp = await client.put(f"{BASE_URL}/policies/{seed_policy.id}/toggle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is False


@pytest.mark.anyio
async def test_delete_system_policy_forbidden(client, seed_system_policy):
    """删除系统策略 → 403"""
    resp = await client.delete(f"{BASE_URL}/policies/{seed_system_policy.id}")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_get_action_types(client):
    """获取动作类型列表"""
    resp = await client.get(f"{BASE_URL}/action-types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    types = {item["action_type"] for item in data}
    assert "ALARM_NOTIFY" in types
    assert "WEBHOOK" in types


@pytest.mark.anyio
async def test_policy_not_found(client):
    """不存在的策略 → 404"""
    resp = await client.get(f"{BASE_URL}/policies/99999")
    assert resp.status_code == 404
