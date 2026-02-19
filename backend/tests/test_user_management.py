"""用户管理 API 测试 (Story 13-1)"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.user import User
from app.core.security import get_password_hash
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


# ============================================================
# Constants
# ============================================================

USERS_URL = "/api/v1/users"


# ============================================================
# Tests
# ============================================================

@pytest.mark.anyio
async def test_create_user(client):
    """创建用户"""
    resp = await client.post(USERS_URL, json={
        "username": "testuser1",
        "password": "Test@1234",
        "real_name": "测试用户1",
        "email": "test1@example.com",
        "role": "operator",
        "department": "运维部"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser1"
    assert data["real_name"] == "测试用户1"
    assert data["role"] == "operator"
    assert data["is_active"] is True


@pytest.mark.anyio
async def test_create_user_duplicate(client):
    """创建重复用户名"""
    await client.post(USERS_URL, json={
        "username": "dupuser",
        "password": "Test@1234",
        "role": "viewer"
    })
    resp = await client.post(USERS_URL, json={
        "username": "dupuser",
        "password": "Test@1234",
        "role": "viewer"
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_users(client):
    """获取用户列表"""
    await client.post(USERS_URL, json={
        "username": "listuser1",
        "password": "Test@1234",
        "role": "operator"
    })
    resp = await client.get(USERS_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_list_users_filter_role(client):
    """按角色筛选用户"""
    await client.post(USERS_URL, json={
        "username": "adminuser",
        "password": "Test@1234",
        "role": "admin"
    })
    await client.post(USERS_URL, json={
        "username": "vieweruser",
        "password": "Test@1234",
        "role": "viewer"
    })
    resp = await client.get(USERS_URL, params={"role": "admin"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["role"] == "admin"


@pytest.mark.anyio
async def test_update_user(client):
    """更新用户"""
    create_resp = await client.post(USERS_URL, json={
        "username": "updateuser",
        "password": "Test@1234",
        "role": "operator"
    })
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{USERS_URL}/{user_id}", json={
        "real_name": "更新姓名",
        "department": "技术部"
    })
    assert resp.status_code == 200
    assert resp.json()["real_name"] == "更新姓名"
    assert resp.json()["department"] == "技术部"


@pytest.mark.anyio
async def test_delete_user(client):
    """删除用户"""
    create_resp = await client.post(USERS_URL, json={
        "username": "deleteuser",
        "password": "Test@1234",
        "role": "viewer"
    })
    user_id = create_resp.json()["id"]

    resp = await client.delete(f"{USERS_URL}/{user_id}")
    assert resp.status_code == 200

    get_resp = await client.get(f"{USERS_URL}/{user_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_toggle_user_status(client):
    """启用/禁用用户"""
    create_resp = await client.post(USERS_URL, json={
        "username": "toggleuser",
        "password": "Test@1234",
        "role": "operator"
    })
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{USERS_URL}/{user_id}/status", params={"is_active": False})
    assert resp.status_code == 200

    get_resp = await client.get(f"{USERS_URL}/{user_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


@pytest.mark.anyio
async def test_batch_delete_users(client):
    """批量删除用户"""
    ids = []
    for i in range(3):
        resp = await client.post(USERS_URL, json={
            "username": f"batchdel{i}",
            "password": "Test@1234",
            "role": "viewer"
        })
        ids.append(resp.json()["id"])

    resp = await client.post(f"{USERS_URL}/batch-delete", json=ids)
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 3

    # 验证已删除
    list_resp = await client.get(USERS_URL)
    remaining_usernames = [u["username"] for u in list_resp.json()["items"]]
    for i in range(3):
        assert f"batchdel{i}" not in remaining_usernames


@pytest.mark.anyio
async def test_batch_delete_cannot_delete_self(client, mock_admin):
    """批量删除不能包含自己"""
    resp = await client.post(f"{USERS_URL}/batch-delete", json=[mock_admin.id])
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_reset_password(client):
    """重置密码"""
    create_resp = await client.post(USERS_URL, json={
        "username": "resetpwduser",
        "password": "Test@1234",
        "role": "operator"
    })
    user_id = create_resp.json()["id"]

    resp = await client.put(
        f"{USERS_URL}/{user_id}/reset-password",
        params={"new_password": "NewPass@123"}
    )
    assert resp.status_code == 200
