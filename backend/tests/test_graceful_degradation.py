"""优雅降级测试 — Story 4.5"""

import pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.user import User
from app.core.security import get_password_hash


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="testadmin",
        password_hash=get_password_hash("test123"),
        real_name="测试管理员",
        email="test@dcim.local",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _make_token(username: str = "testadmin") -> str:
    """生成测试 JWT"""
    from app.core.config import get_settings
    from jose import jwt

    settings = get_settings()
    return jwt.encode({"sub": username}, settings.secret_key, algorithm=settings.algorithm)


@pytest_asyncio.fixture
async def client(db_engine, test_user):
    """创建异步测试客户端，覆盖 DB 依赖"""
    from app.main import app
    from app.api.deps import get_db

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestSystemHealthAPI:
    """系统健康 API 测试"""

    async def test_system_health_api(self, client: AsyncClient):
        """测试健康端点返回正确结构"""
        token = _make_token()
        resp = await client.get(
            "/api/v1/system/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "redis" in data
        assert "database" in data
        assert "websocket" in data
        assert "mqtt" in data
        assert data["database"]["status"] == "connected"
        assert "active_connections" in data["websocket"]

    async def test_system_health_redis_unavailable(self, client: AsyncClient):
        """Redis 不可用时返回 disconnected"""
        token = _make_token()
        with patch("app.api.v1.system_health.redis_service") as mock_redis:
            mock_redis.is_available = False
            resp = await client.get(
                "/api/v1/system/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["redis"]["status"] == "disconnected"


class TestRealtimeDegradedHeader:
    """实时数据 API 降级标志测试"""

    async def test_realtime_degraded_header(self, client: AsyncClient):
        """Redis 不可用时响应包含 X-Degraded 头"""
        token = _make_token()
        with patch("app.api.v1.realtime.redis_service") as mock_redis:
            mock_redis.is_available = False
            resp = await client.get(
                "/api/v1/realtime",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.headers.get("x-degraded") == "true"
        assert resp.headers.get("x-degraded-message") == "realtime-data-delayed"
