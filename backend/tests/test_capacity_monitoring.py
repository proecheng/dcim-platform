"""容量监控 — 按区域统计 & 预警列表测试 — Story 7-4"""
import pytest

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.capacity import (
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityStatus,
)
from app.models.user import User
from app.api.v1.capacity import (
    get_capacity_statistics_by_location,
    get_capacity_alerts,
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
async def db(session_factory):
    async with session_factory() as session:
        await session.execute(delete(SpaceCapacity))
        await session.execute(delete(PowerCapacity))
        await session.execute(delete(CoolingCapacity))
        await session.execute(delete(WeightCapacity))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
async def viewer(db: AsyncSession):
    u = User(
        username="test_cap_viewer",
        password_hash="fakehash",
        role="viewer",
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def seed_data(db: AsyncSession):
    """插入测试数据：两个区域各有四维容量记录"""
    # A区/1F/Room1
    db.add(SpaceCapacity(
        name="A区空间1", location="A区/1F/Room1",
        total_u_positions=100, used_u_positions=80,
        warning_threshold=80, critical_threshold=95,
        status=CapacityStatus.warning,
    ))
    db.add(PowerCapacity(
        name="A区电力1", location="A区/1F/Room1",
        total_capacity_kw=500, used_capacity_kw=400,
        warning_threshold=70, critical_threshold=85,
        status=CapacityStatus.warning,
    ))
    db.add(CoolingCapacity(
        name="A区制冷1", location="A区/1F/Room1",
        total_cooling_kw=300, used_cooling_kw=100,
        warning_threshold=75, critical_threshold=90,
        status=CapacityStatus.normal,
    ))
    db.add(WeightCapacity(
        name="A区承重1", location="A区/1F/Room1",
        total_weight_kg=5000, used_weight_kg=4800,
        warning_threshold=80, critical_threshold=95,
        status=CapacityStatus.critical,
    ))
    # B区/2F/Room2
    db.add(SpaceCapacity(
        name="B区空间1", location="B区/2F/Room2",
        total_u_positions=200, used_u_positions=50,
        warning_threshold=80, critical_threshold=95,
        status=CapacityStatus.normal,
    ))
    db.add(PowerCapacity(
        name="B区电力1", location="B区/2F/Room2",
        total_capacity_kw=1000, used_capacity_kw=950,
        warning_threshold=70, critical_threshold=85,
        status=CapacityStatus.critical,
    ))
    await db.commit()


# ============================================================
# 测试
# ============================================================

class TestCapacityMonitoring:

    # ---- 按区域统计 ----

    async def test_statistics_by_location(self, db: AsyncSession, viewer: User, seed_data):
        """默认 dimension=area，应返回 items 列表，按区域聚合"""
        resp = await get_capacity_statistics_by_location(
            dimension="area", db=db, _=viewer,
        )
        items = resp["items"]
        assert isinstance(items, list)
        assert len(items) >= 2
        locs = {item["location"] for item in items}
        assert "A区" in locs
        assert "B区" in locs
        # 验证 A区 space 聚合
        a_item = next(i for i in items if i["location"] == "A区")
        assert a_item["space"]["total_u_positions"] == 100
        assert a_item["space"]["used_u_positions"] == 80
        assert a_item["space"]["usage_rate"] == 80.0

    async def test_statistics_by_location_dimension(self, db: AsyncSession, viewer: User, seed_data):
        """dimension=floor 应按楼层聚合"""
        resp = await get_capacity_statistics_by_location(
            dimension="floor", db=db, _=viewer,
        )
        items = resp["items"]
        assert isinstance(items, list)
        locs = {item["location"] for item in items}
        # floor 维度取前两段拼接
        assert "A区-1F" in locs
        assert "B区-2F" in locs

    # ---- 预警列表 ----

    async def test_alerts_list(self, db: AsyncSession, viewer: User, seed_data):
        """应返回所有 warning/critical/full 状态的记录"""
        resp = await get_capacity_alerts(cap_type=None, status=None, db=db, _=viewer)
        assert isinstance(resp, list)
        # seed_data 中有 4 条非 normal: space-warning, power-warning, weight-critical, power-critical
        assert len(resp) >= 4
        statuses = {a["status"] for a in resp}
        assert statuses <= {"warning", "critical", "full"}

    async def test_alerts_filter_by_type(self, db: AsyncSession, viewer: User, seed_data):
        """type=space 应只返回 space 类型的预警"""
        resp = await get_capacity_alerts(cap_type="space", status=None, db=db, _=viewer)
        assert isinstance(resp, list)
        for alert in resp:
            assert alert["type"] == "space"
        # seed_data 中 space 有 1 条 warning
        assert len(resp) == 1
        assert resp[0]["status"] == "warning"
        assert resp[0]["name"] == "A区空间1"
