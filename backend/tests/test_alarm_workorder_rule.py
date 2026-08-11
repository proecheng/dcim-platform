"""告警-工单规则 API 测试 — 告警自动生成工单"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.alarm import Alarm
from app.models.operation import AlarmWorkOrderRule, WorkOrder, WorkOrderLog
from app.models.user import User, UserSession
from app.api.deps import get_db, require_admin, require_operator, require_viewer
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
            username="alarm_rule_admin",
            password_hash="test-only",
            real_name="告警规则管理员",
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
        await session.execute(delete(WorkOrderLog))
        await session.execute(delete(WorkOrder))
        await session.execute(delete(AlarmWorkOrderRule))
        await session.execute(delete(Alarm))
        session.add_all(
            [
                Alarm(
                    id=alarm_id,
                    alarm_no=f"ALM-RULE-{alarm_id}",
                    alarm_level=alarm_level,
                    alarm_message="告警规则测试",
                )
                for alarm_id, alarm_level in ((1, "critical"), (2, "minor"), (3, "critical"), (42, "critical"))
            ]
        )
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

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
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


# ============================================================
# Constants & Helpers
# ============================================================

RULES_URL = "/api/v1/operation/alarm-rules"
CHECK_URL = "/api/v1/operation/alarm-rules/check"

RULE_PAYLOAD = {
    "name": "紧急告警自动工单",
    "alarm_level": "critical",
    "order_type": "故障报修",
    "priority": "紧急",
    "assignee": "张三",
    "is_enabled": True,
}


async def _create_rule(client: AsyncClient, **overrides) -> dict:
    """通过 API 创建一条告警-工单规则并返回响应 JSON"""
    payload = {**RULE_PAYLOAD, **overrides}
    resp = await client.post(RULES_URL, json=payload)
    assert resp.status_code == 200
    return resp.json()


# ============================================================
# Tests
# ============================================================


@pytest.mark.anyio
async def test_create_rule(client):
    """POST /alarm-rules 创建规则，验证 name 和 is_enabled"""
    data = await _create_rule(client)
    assert data["name"] == "紧急告警自动工单"
    assert data["is_enabled"] is True
    assert "id" in data


@pytest.mark.anyio
async def test_list_rules(client):
    """GET /alarm-rules 返回列表"""
    await _create_rule(client)
    resp = await client.get(RULES_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_list_rules_filter_enabled(client):
    """GET /alarm-rules?is_enabled=true 按启用状态过滤"""
    await _create_rule(client, is_enabled=True)
    await _create_rule(client, name="已禁用规则", is_enabled=False)
    resp = await client.get(RULES_URL, params={"is_enabled": True})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for rule in data:
        assert rule["is_enabled"] is True


@pytest.mark.anyio
async def test_update_rule(client):
    """PUT /alarm-rules/{id} 更新规则名称"""
    created = await _create_rule(client)
    rule_id = created["id"]

    resp = await client.put(f"{RULES_URL}/{rule_id}", json={"name": "更新后的规则名"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新后的规则名"


@pytest.mark.anyio
async def test_delete_rule(client):
    """DELETE /alarm-rules/{id} 删除规则后列表为空"""
    created = await _create_rule(client)
    rule_id = created["id"]

    resp = await client.delete(f"{RULES_URL}/{rule_id}")
    assert resp.status_code == 200

    resp = await client.get(RULES_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


@pytest.mark.anyio
async def test_check_alarm_match(client):
    """POST /alarm-rules/check critical 告警匹配规则，返回 matched=true"""
    await _create_rule(client, alarm_level="critical")
    resp = await client.post(CHECK_URL, json={"alarm_id": 1, "alarm_level": "critical", "alarm_message": "温度超限"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["work_order"] is not None


@pytest.mark.anyio
async def test_check_alarm_no_match(client):
    """POST /alarm-rules/check minor 告警无匹配规则，返回 matched=false"""
    resp = await client.post(CHECK_URL, json={"alarm_id": 2, "alarm_level": "minor", "alarm_message": "温度偏高"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is False


@pytest.mark.anyio
async def test_check_alarm_auto_assign(client):
    """创建带 assignee 的规则，check 后工单状态为已派单"""
    await _create_rule(client, assignee="张三")
    resp = await client.post(CHECK_URL, json={"alarm_id": 3, "alarm_level": "critical", "alarm_message": "温度超限"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    wo = data["work_order"]
    assert wo["status"] == "已派单"
    assert wo["assignee"] == "张三"


@pytest.mark.anyio
async def test_check_alarm_workorder_has_alarm_id(client):
    """check 传入 alarm_id，工单中包含 alarm_id"""
    await _create_rule(client, alarm_level="critical")
    resp = await client.post(CHECK_URL, json={"alarm_id": 42, "alarm_level": "critical", "alarm_message": "温度超限"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["work_order"]["alarm_id"] == 42


@pytest.mark.anyio
async def test_delete_rule_not_found(client):
    """DELETE /alarm-rules/99999 不存在返回 404"""
    resp = await client.delete(f"{RULES_URL}/99999")
    assert resp.status_code == 404
