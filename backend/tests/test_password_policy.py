"""密码策略管理 API 测试 (Story 13-6)"""

import pytest

from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.user import User, PasswordHistory
from app.models.config import SystemConfig
from app.core.security import get_password_hash
from app.api.deps import get_db, get_current_user, require_admin
from app.api.v1.auth import login_limiter
from app.schemas.user import validate_password_complexity


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
        await session.execute(delete(PasswordHistory))
        await session.execute(delete(SystemConfig))
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
    user.password_hash = get_password_hash("OldPass@123")
    user.password_changed_at = datetime.now()
    return user


@pytest.fixture
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_admin

    async def override_require_admin():
        return mock_admin

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[get_current_user] = override_get_current_user
    _app.dependency_overrides[require_admin] = override_require_admin
    login_limiter.attempts.clear()
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

AUTH_URL = "/api/v1/auth"


# ============================================================
# Tests — 密码复杂度
# ============================================================


def test_password_complexity_3_of_4_passes():
    """至少3类字符通过"""
    # 大写 + 小写 + 数字 (3类，无特殊字符)
    result = validate_password_complexity("Abcdef12")
    assert result == "Abcdef12"


def test_password_complexity_2_of_4_fails():
    """仅2类字符拒绝"""
    with pytest.raises(ValueError, match="至少3类"):
        validate_password_complexity("abcdefgh1")  # 小写 + 数字 = 2类


def test_password_complexity_too_short():
    """密码太短"""
    with pytest.raises(ValueError, match="至少8个字符"):
        validate_password_complexity("Ab1@")


# ============================================================
# Tests — 密码策略配置
# ============================================================


@pytest.mark.anyio
async def test_get_password_policy_default(client):
    """获取默认密码策略"""
    resp = await client.get(f"{AUTH_URL}/password-policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_length"] == 8
    assert data["min_categories"] == 3
    assert data["history_count"] == 5
    assert data["expire_days"] == 90


@pytest.mark.anyio
async def test_update_password_policy(client):
    """更新密码策略"""
    resp = await client.put(
        f"{AUTH_URL}/password-policy",
        json={"min_length": 10, "min_categories": 4, "history_count": 3, "expire_days": 60},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_length"] == 10
    assert data["min_categories"] == 4

    # 验证持久化
    get_resp = await client.get(f"{AUTH_URL}/password-policy")
    assert get_resp.json()["min_length"] == 10
    assert get_resp.json()["expire_days"] == 60


# ============================================================
# Tests — 密码历史
# ============================================================


@pytest.mark.anyio
async def test_change_password_records_history(client, mock_admin, db_session):
    """修改密码后记录历史"""
    resp = await client.put(
        f"{AUTH_URL}/password",
        json={"old_password": "OldPass@123", "new_password": "NewPass@456", "confirm_password": "NewPass@456"},
    )
    assert resp.status_code == 200

    # 验证历史记录已保存
    from sqlalchemy import select, func

    count_result = await db_session.execute(
        select(func.count(PasswordHistory.id)).where(PasswordHistory.user_id == mock_admin.id)
    )
    assert count_result.scalar() >= 1


@pytest.mark.anyio
async def test_change_password_reuse_blocked(client, mock_admin, db_session):
    """不能重用最近5次密码"""
    # 先在历史中插入一条记录
    old_hash = get_password_hash("ReusedPwd@1")
    db_session.add(PasswordHistory(user_id=mock_admin.id, password_hash=old_hash))
    await db_session.commit()

    # 尝试使用相同密码
    resp = await client.put(
        f"{AUTH_URL}/password",
        json={"old_password": "OldPass@123", "new_password": "ReusedPwd@1", "confirm_password": "ReusedPwd@1"},
    )
    assert resp.status_code == 400
    assert "最近" in resp.json()["detail"]


# ============================================================
# Tests — 密码过期提醒
# ============================================================


@pytest.mark.anyio
async def test_login_password_expired_warning(app, db_session):
    """密码超过90天登录时返回警告"""
    # 创建一个密码已过期的用户
    old_date = datetime.now() - timedelta(days=100)
    user = User(
        username="expired_user",
        password_hash=get_password_hash("Test@1234"),
        role="operator",
        is_active=True,
        password_changed_at=old_date,
    )
    db_session.add(user)
    await db_session.commit()

    # 移除 get_current_user override 以使用真实登录
    app.dependency_overrides.pop(get_current_user, None)
    login_limiter.attempts.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"{AUTH_URL}/login", data={"username": "expired_user", "password": "Test@1234"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["password_expired_warning"] is not None
        assert "90" in data["password_expired_warning"]


@pytest.mark.anyio
async def test_login_password_not_expired(app, db_session):
    """密码未过期时无警告"""
    user = User(
        username="fresh_user",
        password_hash=get_password_hash("Test@1234"),
        role="operator",
        is_active=True,
        password_changed_at=datetime.now(),
    )
    db_session.add(user)
    await db_session.commit()

    app.dependency_overrides.pop(get_current_user, None)
    login_limiter.attempts.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"{AUTH_URL}/login", data={"username": "fresh_user", "password": "Test@1234"})
        assert resp.status_code == 200
        assert resp.json()["password_expired_warning"] is None
