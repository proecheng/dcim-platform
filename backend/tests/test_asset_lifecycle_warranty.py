"""资产生命周期 & 保修预警测试 — Story 7-3"""

import pytest
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.asset import (
    Asset,
    Cabinet,
    AssetLifecycle,
    AssetType,
    AssetStatus,
    MaintenanceRecord,
    AssetInventory,
    AssetInventoryItem,
)
from app.models.user import User
from app.api.deps import SiteAccessContext
from app.schemas.asset import AssetCreate, AssetUpdate
from app.api.v1.asset import (
    create_asset,
    update_asset,
    get_asset_lifecycle,
    get_warranty_alerts,
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
        await session.execute(delete(AssetLifecycle))
        await session.execute(delete(AssetInventoryItem))
        await session.execute(delete(AssetInventory))
        await session.execute(delete(MaintenanceRecord))
        await session.execute(delete(Asset))
        await session.execute(delete(Cabinet))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
async def user(db: AsyncSession):
    u = User(
        username="test_lc_warranty_user",
        password_hash="fakehash",
        role="operator",
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _admin_context(user: User) -> SiteAccessContext:
    return SiteAccessContext(user.id, "admin", "test-jti", None)


# ============================================================
# 测试
# ============================================================


class TestAssetLifecycleWarranty:
    # ---- 生命周期测试 ----

    async def test_create_asset_auto_lifecycle(self, db: AsyncSession, user: User):
        """创建资产后应自动生成 purchase 生命周期记录"""
        data = AssetCreate(
            asset_code="LC-001",
            asset_name="生命周期测试服务器",
            asset_type=AssetType.server,
        )
        context = _admin_context(user)
        result = await create_asset(data, db, user, context)
        asset_id = result.id

        lifecycle = await get_asset_lifecycle(asset_id, db, user, context)
        actions = [r.action for r in lifecycle]
        assert "purchase" in actions

    async def test_update_asset_status_change_lifecycle(self, db: AsyncSession, user: User):
        """更新资产状态为 scrapped 应生成 scrap 生命周期记录"""
        data = AssetCreate(
            asset_code="LC-002",
            asset_name="报废测试服务器",
            asset_type=AssetType.server,
        )
        context = _admin_context(user)
        result = await create_asset(data, db, user, context)
        asset_id = result.id

        await update_asset(asset_id, AssetUpdate(status=AssetStatus.scrapped), db, user, context)

        lifecycle = await get_asset_lifecycle(asset_id, db, user, context)
        actions = [r.action for r in lifecycle]
        assert "scrap" in actions

    async def test_update_asset_location_change_lifecycle(self, db: AsyncSession, user: User):
        """移动资产到另一个机柜应生成 move 生命周期记录"""
        cab1 = Cabinet(
            cabinet_code="CAB-LC-001",
            cabinet_name="机柜1",
            location="A区",
            total_u=42,
        )
        cab2 = Cabinet(
            cabinet_code="CAB-LC-002",
            cabinet_name="机柜2",
            location="B区",
            total_u=42,
        )
        db.add_all([cab1, cab2])
        await db.commit()
        await db.refresh(cab1)
        await db.refresh(cab2)

        data = AssetCreate(
            asset_code="LC-003",
            asset_name="移动测试服务器",
            asset_type=AssetType.server,
            cabinet_id=cab1.id,
            u_position=1,
            u_height=2,
        )
        context = _admin_context(user)
        result = await create_asset(data, db, user, context)
        asset_id = result.id

        await update_asset(
            asset_id,
            AssetUpdate(cabinet_id=cab2.id, u_position=1),
            db,
            user,
            context,
        )

        lifecycle = await get_asset_lifecycle(asset_id, db, user, context)
        actions = [r.action for r in lifecycle]
        assert "move" in actions

    # ---- 保修预警测试 ----

    async def test_warranty_alerts_grouping(self, db: AsyncSession, user: User):
        """三个资产分别在 30/60/90 天内到期，应正确分组"""
        today = date.today()
        for i, delta in enumerate([15, 45, 75]):
            asset = Asset(
                asset_code=f"WA-{i + 1:03d}",
                asset_name=f"预警测试资产{i + 1}",
                asset_type=AssetType.server,
                status=AssetStatus.in_use,
                warranty_end=today + timedelta(days=delta),
            )
            db.add(asset)
        await db.commit()

        resp = await get_warranty_alerts(db, user, _admin_context(user))
        assert len(resp.within_30_days) == 1
        assert len(resp.within_60_days) == 1
        assert len(resp.within_90_days) == 1
        assert resp.total_count == 3

    async def test_warranty_alerts_excludes_scrapped(self, db: AsyncSession, user: User):
        """已报废资产不应出现在保修预警中"""
        today = date.today()
        asset = Asset(
            asset_code="WA-SCRAPPED",
            asset_name="已报废资产",
            asset_type=AssetType.server,
            status=AssetStatus.scrapped,
            warranty_end=today + timedelta(days=15),
        )
        db.add(asset)
        await db.commit()

        resp = await get_warranty_alerts(db, user, _admin_context(user))
        assert resp.total_count == 0

    async def test_warranty_alerts_excludes_expired(self, db: AsyncSession, user: User):
        """已过保资产不应出现在保修预警中"""
        today = date.today()
        asset = Asset(
            asset_code="WA-EXPIRED",
            asset_name="已过保资产",
            asset_type=AssetType.server,
            status=AssetStatus.in_use,
            warranty_end=today - timedelta(days=1),
        )
        db.add(asset)
        await db.commit()

        resp = await get_warranty_alerts(db, user, _admin_context(user))
        assert resp.total_count == 0

    async def test_warranty_alerts_empty(self, db: AsyncSession, user: User):
        """无资产时保修预警应返回空"""
        resp = await get_warranty_alerts(db, user, _admin_context(user))
        assert resp.total_count == 0
        assert resp.within_30_days == []
        assert resp.within_60_days == []
        assert resp.within_90_days == []
