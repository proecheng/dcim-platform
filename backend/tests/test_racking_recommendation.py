"""智能上架推荐 API 测试 — Story 7-5"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.asset import Cabinet, Asset
from app.models.capacity import CoolingCapacity, CapacityPlan
from app.models.user import User
from app.api.deps import get_db, require_operator, require_viewer


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
        # 清理所有数据
        await session.execute(delete(Asset))
        await session.execute(delete(CapacityPlan))
        await session.execute(delete(Cabinet))
        await session.execute(delete(CoolingCapacity))
        await session.commit()
        yield session


@pytest.fixture
def mock_viewer():
    user = User()
    user.id = 1
    user.username = "test_viewer"
    user.role = "viewer"
    user.is_active = True
    return user


@pytest.fixture
def mock_operator():
    user = User()
    user.id = 2
    user.username = "test_operator"
    user.role = "operator"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_viewer, mock_operator):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_viewer():
        return mock_viewer

    async def override_require_operator():
        return mock_operator

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[require_operator] = override_require_operator

    yield _app

    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_cabinets(db_session):
    """创建测试机柜数据"""
    cab1 = Cabinet(
        id=1, cabinet_code="A-01", cabinet_name="A区机柜01",
        location="A区/1F/Room1", total_u=42, max_power=10.0, max_weight=500.0,
    )
    cab2 = Cabinet(
        id=2, cabinet_code="A-02", cabinet_name="A区机柜02",
        location="A区/1F/Room1", total_u=42, max_power=5.0, max_weight=300.0,
    )
    cab3 = Cabinet(
        id=3, cabinet_code="B-01", cabinet_name="B区机柜01",
        location="B区/2F/Room2", total_u=42, max_power=20.0, max_weight=1000.0,
    )
    cab4 = Cabinet(
        id=4, cabinet_code="C-01", cabinet_name="C区机柜01",
        location="C区/3F/Room3", total_u=42, max_power=None, max_weight=None,
    )
    db_session.add_all([cab1, cab2, cab3, cab4])
    await db_session.commit()
    return [cab1, cab2, cab3, cab4]


@pytest.fixture
async def seed_assets(db_session, seed_cabinets):
    """在机柜中放置资产，占用U位"""
    # cab1: 占用 30U → 可用 12U
    a1 = Asset(
        asset_code="SRV-001", asset_name="服务器1", asset_type="server",
        cabinet_id=1, u_position=1, u_height=30,
    )
    # cab2: 占用 40U → 可用 2U
    a2 = Asset(
        asset_code="SRV-002", asset_name="服务器2", asset_type="server",
        cabinet_id=2, u_position=1, u_height=40,
    )
    # cab3: 无资产 → 可用 42U
    # cab4: 无资产 → 可用 42U
    db_session.add_all([a1, a2])
    await db_session.commit()
    return [a1, a2]


@pytest.fixture
async def seed_cooling(db_session):
    """创建制冷容量数据"""
    cc = CoolingCapacity(
        name="A区制冷", location="A区/1F/Room1",
        total_cooling_kw=100.0, used_cooling_kw=30.0,
    )
    db_session.add(cc)
    await db_session.commit()
    return cc


# ============================================================
# 测试 POST /api/v1/capacity/recommend
# ============================================================

class TestRackingRecommendation:

    # 3.1 基本推荐 — 只指定 required_u
    async def test_recommend_basic(self, client: AsyncClient, seed_assets):
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 4,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cabinets_evaluated"] == 4
        assert data["qualified_count"] >= 1
        assert len(data["candidates"]) >= 1
        # 候选应按 total_score 降序
        scores = [c["total_score"] for c in data["candidates"]]
        assert scores == sorted(scores, reverse=True)

    # 3.2 空间不足时排除
    async def test_recommend_excludes_insufficient_space(self, client: AsyncClient, seed_assets):
        """请求 20U，cab2 只有 2U 可用，应被排除"""
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 20,
        })
        assert resp.status_code == 200
        data = resp.json()
        cab_ids = [c["cabinet_id"] for c in data["candidates"]]
        assert 2 not in cab_ids  # cab2 只有 2U

    # 3.3 电力约束严格筛选
    async def test_recommend_power_strict(self, client: AsyncClient, seed_assets):
        """请求 15kW，cab1(10kW) 和 cab2(5kW) 在严格模式下应被排除"""
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 4,
            "required_power_kw": 15.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        # cab3(20kW) 应在候选中
        cab_ids = [c["cabinet_id"] for c in data["candidates"]]
        assert 3 in cab_ids

    # 3.4 承重约束严格筛选
    async def test_recommend_weight_strict(self, client: AsyncClient, seed_assets):
        """请求 800kg，cab1(500kg) 和 cab2(300kg) 在严格模式下应被排除"""
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 4,
            "required_weight_kg": 800.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        cab_ids = [c["cabinet_id"] for c in data["candidates"]]
        assert 3 in cab_ids  # cab3 有 1000kg

    # 3.5 制冷评分 — 有匹配的制冷数据
    async def test_recommend_with_cooling(self, client: AsyncClient, seed_assets, seed_cooling):
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 4,
            "required_cooling_kw": 10.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        # A区机柜应有制冷评分 > 50（因为有匹配的制冷数据）
        a01 = next((c for c in data["candidates"] if c["cabinet_code"] == "A-01"), None)
        if a01:
            assert a01["cooling_score"] > 50

    # 3.6 limit 参数限制返回数量
    async def test_recommend_limit(self, client: AsyncClient, seed_assets):
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 1,
            "limit": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) <= 2

    # 3.7 无机柜满足条件时返回空列表
    async def test_recommend_no_candidates(self, client: AsyncClient, seed_assets):
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 100,  # 没有机柜有 100U 可用
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualified_count"] == 0
        assert data["candidates"] == []

    # 3.8 参数校验 — required_u < 1
    async def test_recommend_invalid_required_u(self, client: AsyncClient):
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 0,
        })
        assert resp.status_code == 422

    # 3.9 放宽筛选 — 严格模式候选不足3个时放宽
    async def test_recommend_relaxed_fallback(self, client: AsyncClient, seed_assets):
        """请求 4U + 12kW 电力，严格模式只有 cab3(20kW) 满足，不足3个，应放宽"""
        resp = await client.post("/api/v1/capacity/recommend", json={
            "required_u": 4,
            "required_power_kw": 12.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        # 放宽后应包含更多候选（cab1 有 10kW < 12kW 但放宽后可入选）
        assert data["qualified_count"] >= 2


# ============================================================
# 测试 PUT /api/v1/capacity/plans/{id}/override-cabinet
# ============================================================

class TestOverrideCabinet:

    @pytest.fixture
    async def seed_plan(self, db_session, seed_cabinets):
        """创建一个容量规划"""
        plan = CapacityPlan(
            id=1, name="测试规划", description="测试用",
            required_u=10, required_power_kw=8.0, required_weight_kg=400.0,
            created_by="test",
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    # 3.10 成功覆盖 — 可行
    async def test_override_cabinet_feasible(self, client: AsyncClient, seed_plan, seed_assets):
        """覆盖到 cab3(42U可用, 20kW, 1000kg)，应可行"""
        resp = await client.put("/api/v1/capacity/plans/1/override-cabinet", json={
            "target_cabinet_id": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_cabinet_id"] == 3
        assert data["is_feasible"] is True
        assert "已覆盖为机柜" in data["feasibility_notes"]

    # 3.11 覆盖到不可行机柜
    async def test_override_cabinet_infeasible(self, client: AsyncClient, seed_plan, seed_assets):
        """覆盖到 cab2(2U可用, 5kW, 300kg)，空间不足应不可行"""
        resp = await client.put("/api/v1/capacity/plans/1/override-cabinet", json={
            "target_cabinet_id": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_cabinet_id"] == 2
        assert data["is_feasible"] is False
        assert "空间不足" in data["feasibility_notes"]

    # 3.12 规划不存在
    async def test_override_plan_not_found(self, client: AsyncClient, seed_cabinets):
        resp = await client.put("/api/v1/capacity/plans/9999/override-cabinet", json={
            "target_cabinet_id": 1,
        })
        assert resp.status_code == 404
