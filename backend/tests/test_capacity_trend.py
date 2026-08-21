"""容量趋势预测 API 测试 — Story 7-6"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.capacity import (
    CapacityHistory,
    CapacityType,
    SpaceCapacity,
)
from app.models.user import User, UserSession
from app.api.deps import get_db, require_viewer
from app.api.v1.capacity import _to_utc_naive
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
            username="capacity_trend_admin",
            password_hash="test-only",
            real_name="容量趋势管理员",
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
        # 清理
        await session.execute(delete(CapacityHistory))
        await session.execute(delete(SpaceCapacity))
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

    async def override_require_viewer():
        return mock_admin

    _app.dependency_overrides[get_db] = override_get_db
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
# Helper
# ============================================================


async def _insert_history(session, cap_type, days_ago, usage_rate, total=1000.0, used=None):
    """插入一条 CapacityHistory 记录"""
    if used is None:
        used = total * usage_rate / 100.0
    ts = datetime.now() - timedelta(days=days_ago)
    h = CapacityHistory(
        capacity_type=cap_type,
        reference_id=0,
        reference_name="全局聚合",
        total_value=total,
        used_value=used,
        usage_rate=usage_rate,
        recorded_at=ts,
    )
    session.add(h)
    await session.flush()
    return h


# ============================================================
# 测试 GET /api/v1/capacity/trend
# ============================================================


class TestCapacityTrend:
    def test_aware_query_time_is_normalized_for_naive_database_column(self):
        value = datetime(2026, 8, 21, 12, 0, tzinfo=timezone(timedelta(hours=8)))

        assert _to_utc_naive(value) == datetime(2026, 8, 21, 4, 0)
        assert _to_utc_naive(value).tzinfo is None

    async def test_trend_accepts_utc_browser_timestamps(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/capacity/trend",
            params={
                "type": "space",
                "start_time": "2026-07-22T04:57:03.284Z",
                "end_time": "2026-08-21T04:57:03.284Z",
                "interval": "day",
            },
        )

        assert resp.status_code == 200

    async def test_trend_empty_data(self, client: AsyncClient):
        """无数据时返回空数组"""
        resp = await client.get("/api/v1/capacity/trend", params={"type": "space"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["timestamps"] == []
        assert data["total"] == []
        assert data["used"] == []
        assert data["usage_rate"] == []

    async def test_trend_with_data(self, client: AsyncClient, db_session):
        """插入数据后查询趋势"""
        for i in range(5):
            await _insert_history(db_session, CapacityType.space, days_ago=i, usage_rate=40.0 + i)
        await db_session.commit()

        resp = await client.get("/api/v1/capacity/trend", params={"type": "space"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["timestamps"]) >= 1
        assert len(data["total"]) == len(data["timestamps"])
        assert len(data["used"]) == len(data["timestamps"])
        assert len(data["usage_rate"]) == len(data["timestamps"])

    async def test_trend_interval_auto(self, client: AsyncClient, db_session):
        """不传 interval 时自动选择"""
        # 插入跨2天的数据 → 应自动选 day
        for i in range(3):
            await _insert_history(db_session, CapacityType.space, days_ago=i, usage_rate=50.0)
        await db_session.commit()

        resp = await client.get("/api/v1/capacity/trend", params={"type": "space"})
        assert resp.status_code == 200
        data = resp.json()
        # 应该有数据返回
        assert len(data["timestamps"]) >= 1

    async def test_trend_invalid_type(self, client: AsyncClient):
        """type=network 返回 400"""
        resp = await client.get("/api/v1/capacity/trend", params={"type": "network"})
        assert resp.status_code == 400


# ============================================================
# 测试 GET /api/v1/capacity/forecast
# ============================================================


class TestCapacityForecast:
    async def test_forecast_demo(self, client: AsyncClient):
        """数据不足时返回 demo 数据"""
        resp = await client.get("/api/v1/capacity/forecast", params={"type": "space", "days": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_demo"] is True
        assert len(data["timestamps"]) == 30
        assert len(data["predicted_usage"]) == 30
        assert len(data["confidence_upper"]) == 30
        assert len(data["confidence_lower"]) == 30

    async def test_forecast_with_data(self, client: AsyncClient, db_session):
        """插入 30+ 天数据后返回真实预测"""
        for i in range(35):
            await _insert_history(
                db_session,
                CapacityType.space,
                days_ago=35 - i,
                usage_rate=30.0 + i * 0.5,
            )
        await db_session.commit()

        resp = await client.get("/api/v1/capacity/forecast", params={"type": "space", "days": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_demo"] is False
        assert len(data["timestamps"]) == 30
        assert len(data["predicted_usage"]) == 30
        # 预测值应在合理范围
        for v in data["predicted_usage"]:
            assert 0 <= v <= 100
        for v in data["confidence_lower"]:
            assert v >= 0
        for v in data["confidence_upper"]:
            assert v <= 100

    async def test_forecast_expansion_suggestion(self, client: AsyncClient, db_session):
        """高使用率数据触发扩容建议"""
        # 插入递增到接近80%的数据
        for i in range(35):
            rate = 60.0 + i * 0.8  # 从60%到88%
            await _insert_history(
                db_session,
                CapacityType.space,
                days_ago=35 - i,
                usage_rate=min(rate, 95.0),
            )
        await db_session.commit()

        resp = await client.get("/api/v1/capacity/forecast", params={"type": "space", "days": 90})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_demo"] is False
        # 应有扩容建议（当前已超80%或预测将超）
        assert len(data["expansion_suggestions"]) >= 1

    async def test_forecast_already_exceeded(self, client: AsyncClient, db_session):
        """当前已超 80% 时立即生成建议"""
        for i in range(35):
            await _insert_history(
                db_session,
                CapacityType.space,
                days_ago=35 - i,
                usage_rate=85.0 + i * 0.1,
            )
        await db_session.commit()

        resp = await client.get("/api/v1/capacity/forecast", params={"type": "space", "days": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_demo"] is False
        suggestions = data["expansion_suggestions"]
        assert len(suggestions) >= 1
        # 应有"当前"相关的建议
        found_current = any("当前" in s["predicted_exceed_date"] or "当前" in s["suggestion"] for s in suggestions)
        assert found_current
