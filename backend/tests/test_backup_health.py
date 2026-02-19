"""数据备份与系统健康 API 测试 (Story 13-4)"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.user import User
from app.models.config import SystemConfig
from app.api.deps import get_db, require_admin, require_viewer


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
        await session.execute(delete(SystemConfig))
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

    async def override_require_viewer():
        return mock_admin

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
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

SYSTEM_URL = "/api/v1/system"


# ============================================================
# Tests
# ============================================================

@pytest.mark.anyio
async def test_system_health(client):
    """获取系统健康状态"""
    resp = await client.get(f"{SYSTEM_URL}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert "storage" in data


@pytest.mark.anyio
async def test_get_backup_config_default(client):
    """获取默认备份配置"""
    resp = await client.get(f"{SYSTEM_URL}/backup/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_backup_enabled" in data
    assert "backup_time" in data
    assert "retention_count" in data
    assert data["auto_backup_enabled"] is False
    assert data["backup_time"] == "02:00"
    assert data["retention_count"] == 7


@pytest.mark.anyio
async def test_update_backup_config(client):
    """更新备份配置"""
    resp = await client.put(f"{SYSTEM_URL}/backup/config", params={
        "auto_backup_enabled": True,
        "backup_time": "03:30",
        "retention_count": 14
    })
    assert resp.status_code == 200

    # 验证更新
    resp = await client.get(f"{SYSTEM_URL}/backup/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_backup_enabled"] is True
    assert data["backup_time"] == "03:30"
    assert data["retention_count"] == 14


@pytest.mark.anyio
async def test_list_backups_empty(client):
    """获取备份列表 — 空"""
    resp = await client.get(f"{SYSTEM_URL}/backup/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "backups" in data
    assert isinstance(data["backups"], list)


@pytest.mark.anyio
async def test_restore_backup_not_found(client):
    """恢复不存在的备份 — 404"""
    resp = await client.post(f"{SYSTEM_URL}/backup/restore", params={
        "backup_name": "nonexistent.db"
    })
    assert resp.status_code == 404
