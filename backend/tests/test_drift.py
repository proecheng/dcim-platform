"""传感器数据漂移检测 API 测试 — Story 9-7"""

import pytest
import random
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.drift import DriftDetectionResult
from app.models.point import Point, PointRealtime
from app.models.history import PointHistory
from app.models.user import User
from app.api.deps import (
    SiteAccessContext,
    enforce_inventory_authorization,
    get_db,
    get_site_access_context,
    require_admin,
    require_operator,
    require_viewer,
)


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
        # 清理测试数据
        await session.execute(delete(DriftDetectionResult))
        await session.execute(delete(PointHistory))
        await session.execute(delete(PointRealtime))
        await session.execute(delete(Point))
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

    async def override_inventory_authorization():
        return None

    async def override_site_access_context():
        return SiteAccessContext(user_id=mock_admin.id, role="admin", jti="test-jti", site_ids=None)

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[enforce_inventory_authorization] = override_inventory_authorization
    _app.dependency_overrides[get_site_access_context] = override_site_access_context
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

BASE_URL = "/api/v1/drift"


# ============================================================
# Helpers
# ============================================================


async def _create_point(
    session: AsyncSession, point_code: str = "AI_TH_A1_001", point_name: str = "A1区温度传感器"
) -> Point:
    """创建一个 AI 类型测试点位"""
    point = Point(
        point_code=point_code,
        point_name=point_name,
        point_type="AI",
        area_code="A1",
        device_type="TH",
        is_enabled=True,
        unit="C",
    )
    session.add(point)
    await session.flush()
    return point


async def _create_realtime(session: AsyncSession, point_id: int, value: float, quality: int = 0) -> PointRealtime:
    """创建点位实时值"""
    rt = PointRealtime(point_id=point_id, value=value, quality=quality)
    session.add(rt)
    await session.flush()
    return rt


async def _create_history(session: AsyncSession, point_id: int, count: int, mean: float = 25.0, std: float = 1.0):
    """创建历史数据记录，值围绕 mean 正态分布"""
    now = datetime.now()
    rng = random.Random(42)  # 固定种子保证可重复
    for i in range(count):
        val = rng.gauss(mean, std)
        record = PointHistory(
            point_id=point_id,
            value=round(val, 2),
            quality=0,
            recorded_at=now - timedelta(hours=i * 48 / max(count, 1)),
        )
        session.add(record)
    await session.flush()


async def _create_drift_record(
    session: AsyncSession,
    point_id: int,
    status: str = "suspected",
    point_code: str = "AI_TH_A1_001",
    point_name: str = "A1区温度传感器",
) -> DriftDetectionResult:
    """直接创建一条漂移检测结果"""
    record = DriftDetectionResult(
        point_id=point_id,
        point_code=point_code,
        point_name=point_name,
        area_code="A1",
        status=status,
        mean_value=25.0,
        std_value=1.0,
        current_value=35.0,
        deviation_sigma=10.0,
        cross_validation_result="skipped",
        diagnosis="测试诊断",
        detected_at=datetime.now(),
    )
    if status == "resolved":
        record.resolved_at = datetime.now()
    session.add(record)
    await session.flush()
    return record


# ============================================================
# Tests — POST /detect
# ============================================================


@pytest.mark.anyio
async def test_trigger_detection_no_data(client):
    """无点位数据时触发检测，total_checked=0"""
    resp = await client.post(f"{BASE_URL}/detect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 0
    assert data["new_suspected"] == 0
    assert data["new_confirmed"] == 0


@pytest.mark.anyio
async def test_trigger_detection_insufficient_data(client, db_session):
    """点位历史数据不足 100 条时，应被跳过"""
    point = await _create_point(db_session)
    await _create_realtime(db_session, point.id, value=25.0)
    await _create_history(db_session, point.id, count=50, mean=25.0)
    await db_session.commit()

    resp = await client.post(f"{BASE_URL}/detect")
    assert resp.status_code == 200
    data = resp.json()
    # 数据不足，被跳过，不计入 total_checked
    assert data["total_checked"] == 0
    assert data["new_suspected"] == 0


@pytest.mark.anyio
async def test_trigger_detection_normal(client, db_session):
    """充足历史数据且当前值在正常范围内，不产生漂移"""
    point = await _create_point(db_session)
    await _create_realtime(db_session, point.id, value=25.0)
    await _create_history(db_session, point.id, count=150, mean=25.0, std=1.0)
    await db_session.commit()

    resp = await client.post(f"{BASE_URL}/detect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 1
    assert data["new_suspected"] == 0
    assert data["new_confirmed"] == 0


@pytest.mark.anyio
async def test_trigger_detection_suspected(client, db_session):
    """当前值远超 3 sigma，应检测到漂移（suspected 或 confirmed）"""
    point = await _create_point(db_session)
    # 当前值 35.0，历史均值 25.0，std~1.0 → 偏差约 10σ
    await _create_realtime(db_session, point.id, value=35.0)
    await _create_history(db_session, point.id, count=150, mean=25.0, std=1.0)
    await db_session.commit()

    resp = await client.post(f"{BASE_URL}/detect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 1
    # 只有一个同区域点位，交叉验证 skipped → suspected
    assert data["new_suspected"] + data["new_confirmed"] >= 1


# ============================================================
# Tests — GET /results
# ============================================================


@pytest.mark.anyio
async def test_list_results(client, db_session):
    """列出漂移检测结果，验证分页结构"""
    point = await _create_point(db_session)
    await _create_drift_record(db_session, point.id, status="suspected")
    await _create_drift_record(
        db_session, point.id + 100, status="resolved", point_code="AI_TH_A1_002", point_name="A1区温度传感器2"
    )
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/results", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.anyio
async def test_list_results_filter_status(client, db_session):
    """按状态筛选漂移检测结果"""
    point = await _create_point(db_session)
    await _create_drift_record(db_session, point.id, status="suspected")
    await _create_drift_record(
        db_session, point.id + 100, status="resolved", point_code="AI_TH_A1_003", point_name="A1区温度传感器3"
    )
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/results", params={"status": "suspected"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["status"] == "suspected"


# ============================================================
# Tests — GET /results/{id}
# ============================================================


@pytest.mark.anyio
async def test_get_result_detail(client, db_session):
    """获取单条漂移检测结果详情"""
    point = await _create_point(db_session)
    record = await _create_drift_record(db_session, point.id, status="suspected")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/results/{record.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == record.id
    assert data["status"] == "suspected"
    assert data["point_code"] == "AI_TH_A1_001"
    assert data["deviation_sigma"] == 10.0


@pytest.mark.anyio
async def test_get_result_not_found(client):
    """获取不存在的漂移检测记录，返回 404"""
    resp = await client.get(f"{BASE_URL}/results/99999")
    assert resp.status_code == 404


# ============================================================
# Tests — POST /results/{id}/resolve
# ============================================================


@pytest.mark.anyio
async def test_resolve_drift(client, db_session):
    """手动解除漂移标记，验证状态变为 resolved"""
    point = await _create_point(db_session)
    await _create_realtime(db_session, point.id, value=35.0, quality=1)
    record = await _create_drift_record(db_session, point.id, status="suspected")
    await db_session.commit()

    resp = await client.post(f"{BASE_URL}/results/{record.id}/resolve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None

    # 验证 PointRealtime.quality 恢复为 0
    rt_result = await db_session.execute(select(PointRealtime).where(PointRealtime.point_id == point.id))
    rt = rt_result.scalar_one()
    assert rt.quality == 0


@pytest.mark.anyio
async def test_resolve_already_resolved(client, db_session):
    """解除已解除的漂移记录，返回 400"""
    point = await _create_point(db_session)
    record = await _create_drift_record(db_session, point.id, status="resolved")
    await db_session.commit()

    resp = await client.post(f"{BASE_URL}/results/{record.id}/resolve")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_resolve_not_found(client):
    """解除不存在的漂移记录，返回 404"""
    resp = await client.post(f"{BASE_URL}/results/99999/resolve")
    assert resp.status_code == 404


# ============================================================
# Tests — GET /summary
# ============================================================


@pytest.mark.anyio
async def test_get_summary(client, db_session):
    """获取漂移检测统计概览"""
    point = await _create_point(db_session)
    await _create_drift_record(db_session, point.id, status="suspected")
    await _create_drift_record(
        db_session, point.id + 100, status="confirmed", point_code="AI_TH_A1_004", point_name="A1区温度传感器4"
    )
    await _create_drift_record(
        db_session, point.id + 200, status="resolved", point_code="AI_TH_A1_005", point_name="A1区温度传感器5"
    )
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suspected_count"] >= 1
    assert data["confirmed_count"] >= 1
    assert data["resolved_count"] >= 1
    assert data["total_checked"] >= 3
