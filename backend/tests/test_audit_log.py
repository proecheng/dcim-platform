"""操作审计日志 API 测试 (Story 13-3)"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.user import User
from app.models.log import OperationLog
from app.api.deps import get_db, require_admin


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
        await session.execute(delete(OperationLog))
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

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
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

LOGS_URL = "/api/v1/logs"


# ============================================================
# Tests
# ============================================================


@pytest.mark.anyio
async def test_get_operation_logs_empty(client):
    """获取操作日志 — 空列表"""
    resp = await client.get(f"{LOGS_URL}/operations")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0


@pytest.mark.anyio
async def test_get_operation_logs_with_data(client, db_session):
    """获取操作日志 — 有数据"""
    log = OperationLog(
        user_id=1, username="admin", module="user", action="create", target_name="testuser", ip_address="127.0.0.1"
    )
    db_session.add(log)
    await db_session.commit()

    resp = await client.get(f"{LOGS_URL}/operations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["module"] == "user"
    assert data["items"][0]["action"] == "create"


@pytest.mark.anyio
async def test_get_operation_logs_filter_module(client, db_session):
    """按模块筛选操作日志"""
    for mod in ["user", "alarm", "config"]:
        log = OperationLog(user_id=1, username="admin", module=mod, action="query")
        db_session.add(log)
    await db_session.commit()

    resp = await client.get(f"{LOGS_URL}/operations", params={"module": "alarm"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["module"] == "alarm"


@pytest.mark.anyio
async def test_get_log_statistics(client, db_session):
    """获取日志统计"""
    log = OperationLog(user_id=1, username="admin", module="user", action="create")
    db_session.add(log)
    await db_session.commit()

    resp = await client.get(f"{LOGS_URL}/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert "operation_logs" in data
    assert "system_logs" in data
    assert "communication_logs" in data


@pytest.mark.anyio
async def test_export_operation_logs(client, db_session):
    """导出操作日志 CSV"""
    log = OperationLog(user_id=1, username="admin", module="user", action="export")
    db_session.add(log)
    await db_session.commit()

    resp = await client.get(f"{LOGS_URL}/export", params={"log_type": "operation"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
