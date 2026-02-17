"""数据质量标记与误报防护测试 — Story 5-4"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.engines.alarm_engine import AlarmEngine, ThresholdCache, EvaluateResult
from app.models.point import Point, PointRealtime
from app.models.user import User
from app.api.deps import get_db, require_viewer


# ==================== 告警引擎质量缓存单元测试 ====================


@pytest.fixture
def engine():
    """创建测试用告警引擎"""
    e = AlarmEngine()
    e._loaded = True
    return e


@pytest.fixture
def sample_thresholds():
    """示例阈值配置（点位 100）"""
    return [
        ThresholdCache(id=1, point_id=100, threshold_type="high",
                       threshold_value=40.0, alarm_level="major",
                       alarm_message="温度偏高", delay_seconds=0, dead_band=0, priority=3),
    ]


class TestQualitySkipEvaluate:
    """quality==2 时跳过告警检测"""

    def test_quality_2_returns_empty(self, engine, sample_thresholds):
        """quality==2 的点位应跳过告警检测，返回空列表"""
        engine._thresholds = {100: sample_thresholds}
        engine._point_quality = {100: 2}
        results = engine.evaluate(100, 55.0, "AI")
        assert results == []

    def test_quality_2_still_tracks_prev_value(self, engine, sample_thresholds):
        """quality==2 时仍应更新 _prev_values 用于变化检测"""
        engine._thresholds = {100: sample_thresholds}
        engine._point_quality = {100: 2}
        engine.evaluate(100, 55.0, "AI")
        assert engine._prev_values[100] == 55.0


class TestQualityUncertainPrefix:
    """quality==1 时添加前缀"""

    def test_quality_1_adds_prefix(self, engine, sample_thresholds):
        """quality==1 的点位告警消息应添加 [数据质量不确定] 前缀"""
        engine._thresholds = {100: sample_thresholds}
        engine._point_quality = {100: 1}
        results = engine.evaluate(100, 55.0, "AI")
        assert len(results) == 1
        assert results[0].alarm_message.startswith("[数据质量不确定]")

    def test_quality_1_preserves_original_message(self, engine, sample_thresholds):
        """quality==1 前缀后应保留原始告警消息"""
        engine._thresholds = {100: sample_thresholds}
        engine._point_quality = {100: 1}
        results = engine.evaluate(100, 55.0, "AI")
        assert "温度偏高" in results[0].alarm_message


class TestQualityNormalDetection:
    """quality==0 正常检测"""

    def test_quality_0_normal_detection(self, engine, sample_thresholds):
        """quality==0 的点位应正常触发告警"""
        engine._thresholds = {100: sample_thresholds}
        engine._point_quality = {100: 0}
        results = engine.evaluate(100, 55.0, "AI")
        assert len(results) == 1
        assert results[0].alarm_level == "major"
        assert not results[0].alarm_message.startswith("[数据质量不确定]")

    def test_quality_default_normal_detection(self, engine, sample_thresholds):
        """未设置 quality 的点位默认为 0，正常检测"""
        engine._thresholds = {100: sample_thresholds}
        # _point_quality 中没有 100
        engine._point_quality = {}
        results = engine.evaluate(100, 55.0, "AI")
        assert len(results) == 1
        assert results[0].alarm_level == "major"


class TestQualityCacheMethods:
    """质量缓存方法测试"""

    def test_update_point_quality(self, engine):
        """update_point_quality 应更新单个点位质量"""
        engine.update_point_quality(100, 2)
        assert engine.get_point_quality(100) == 2

    def test_update_points_quality(self, engine):
        """update_points_quality 应批量更新点位质量"""
        engine.update_points_quality([100, 200, 300], 1)
        assert engine.get_point_quality(100) == 1
        assert engine.get_point_quality(200) == 1
        assert engine.get_point_quality(300) == 1

    def test_get_point_quality_default(self, engine):
        """未设置的点位质量默认为 0"""
        assert engine.get_point_quality(999) == 0

    def test_update_overwrites(self, engine):
        """更新应覆盖旧值"""
        engine.update_point_quality(100, 2)
        engine.update_point_quality(100, 0)
        assert engine.get_point_quality(100) == 0


# ==================== 数据质量 API 测试 ====================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def api_engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(api_engine):
    return async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(delete(PointRealtime))
        await session.execute(delete(Point))
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    user = User()
    user.id = 1
    user.username = "testviewer"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_user):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_viewer():
        return mock_user

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
async def seed_quality_data(db_session):
    """创建测试点位和实时数据（含不同质量等级）"""
    # 正常点位
    p1 = Point()
    p1.id = 1
    p1.point_code = "TH-A1-001"
    p1.point_name = "A1区温度"
    p1.point_type = "AI"
    p1.device_type = "TH"
    db_session.add(p1)

    # 不确定点位
    p2 = Point()
    p2.id = 2
    p2.point_code = "TH-A1-002"
    p2.point_name = "A1区湿度"
    p2.point_type = "AI"
    p2.device_type = "TH"
    db_session.add(p2)

    # 不可靠点位
    p3 = Point()
    p3.id = 3
    p3.point_code = "UPS-A1-001"
    p3.point_name = "A1区UPS电压"
    p3.point_type = "AI"
    p3.device_type = "UPS"
    db_session.add(p3)

    await db_session.flush()

    # 实时数据
    pr1 = PointRealtime(point_id=1, value=25.0, quality=0, status="normal")
    pr2 = PointRealtime(point_id=2, value=50.0, quality=1, status="normal")
    pr3 = PointRealtime(point_id=3, value=220.0, quality=2, status="offline")
    db_session.add_all([pr1, pr2, pr3])
    await db_session.commit()


class TestDataQualityStatusAPI:
    """GET /api/v1/data-quality/status"""

    async def test_status_returns_correct_counts(self, client, seed_quality_data):
        """状态接口应返回正确的各质量等级计数"""
        resp = await client.get("/api/v1/data-quality/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["normal_count"] == 1
        assert data["uncertain_count"] == 1
        assert data["unreliable_count"] == 1

    async def test_status_includes_unreliable_details(self, client, seed_quality_data):
        """状态接口应包含不可靠点位详情"""
        resp = await client.get("/api/v1/data-quality/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["unreliable_points"]) == 1
        point = data["unreliable_points"][0]
        assert point["point_id"] == 3
        assert point["quality"] == 2
        assert point["quality_text"] == "不可靠"


class TestDataQualityPointsAPI:
    """GET /api/v1/data-quality/points"""

    async def test_points_returns_all(self, client, seed_quality_data):
        """无过滤时应返回所有点位"""
        resp = await client.get("/api/v1/data-quality/points")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_points_filter_by_quality(self, client, seed_quality_data):
        """按 quality 过滤应只返回匹配的点位"""
        resp = await client.get("/api/v1/data-quality/points?quality=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["point_id"] == 3
        assert data[0]["quality_text"] == "不可靠"

    async def test_points_filter_quality_0(self, client, seed_quality_data):
        """过滤 quality=0 应只返回正常点位"""
        resp = await client.get("/api/v1/data-quality/points?quality=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["point_id"] == 1

    async def test_points_filter_quality_1(self, client, seed_quality_data):
        """过滤 quality=1 应只返回不确定点位"""
        resp = await client.get("/api/v1/data-quality/points?quality=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["point_id"] == 2
        assert data[0]["quality_text"] == "不确定"
