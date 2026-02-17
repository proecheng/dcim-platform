"""机柜 U 位可视化测试 — Story 7-2"""
import pytest
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, select

from app.core.database import Base
from app.models.asset import (
    Asset, Cabinet, AssetLifecycle, AssetType, AssetStatus,
    MaintenanceRecord, AssetInventory, AssetInventoryItem,
)
from app.models.user import User
from app.api.v1.asset import get_cabinet_usage, move_asset_in_cabinet, MoveAssetRequest


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
async def sample_cabinet(db: AsyncSession):
    cab = Cabinet(
        cabinet_code="CAB-U-001",
        cabinet_name="U位测试机柜",
        location="A区",
        total_u=42,
    )
    db.add(cab)
    await db.commit()
    await db.refresh(cab)
    return cab


@pytest.fixture
async def sample_asset(db: AsyncSession, sample_cabinet):
    asset = Asset(
        asset_code="SRV-U-001",
        asset_name="U位测试服务器",
        asset_type=AssetType.server,
        brand="Dell",
        model="R740",
        cabinet_id=sample_cabinet.id,
        u_position=1,
        u_height=4,
        status=AssetStatus.in_use,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@pytest.fixture
async def sample_user(db: AsyncSession):
    user = User(
        username="test_cabinet_user",
        password_hash="fakehash",
        role="operator",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================
# 测试
# ============================================================

class TestGetCabinetUsage:

    async def test_get_cabinet_usage_returns_assets(
        self, db: AsyncSession, sample_cabinet, sample_asset, sample_user
    ):
        """get_cabinet_usage 应返回 assets 数组，包含完整字段"""
        result = await get_cabinet_usage(sample_cabinet.id, db, sample_user)

        assert "assets" in result
        assets = result["assets"]
        assert len(assets) == 1

        a = assets[0]
        assert a["asset_id"] == sample_asset.id
        assert a["asset_code"] == "SRV-U-001"
        assert a["asset_name"] == "U位测试服务器"
        assert a["asset_type"] == "server"
        assert a["model"] == "R740"
        assert a["brand"] == "Dell"
        assert a["status"] == "in_use"
        assert a["u_position"] == 1
        assert a["u_height"] == 4


class TestMoveAsset:

    async def test_move_asset_success(
        self, db: AsyncSession, sample_cabinet, sample_asset, sample_user
    ):
        """移动资产到 U10，验证位置更新和生命周期记录"""
        req = MoveAssetRequest(asset_id=sample_asset.id, new_u_position=10)
        result = await move_asset_in_cabinet(sample_cabinet.id, req, db, sample_user)

        # 验证返回的 usage 数据
        assert result["cabinet_id"] == sample_cabinet.id

        # 验证资产位置已更新
        await db.refresh(sample_asset)
        assert sample_asset.u_position == 10

        # 验证生命周期记录
        lc_result = await db.execute(
            select(AssetLifecycle).where(
                AssetLifecycle.asset_id == sample_asset.id,
                AssetLifecycle.action == "move",
            )
        )
        lc = lc_result.scalar_one_or_none()
        assert lc is not None
        assert lc.from_location == "U1"
        assert lc.to_location == "U10"
        assert lc.remark == "U位拖拽移动"

    async def test_move_asset_conflict(
        self, db: AsyncSession, sample_cabinet, sample_asset, sample_user
    ):
        """移动到已被占用的 U 位应返回 400"""
        from fastapi import HTTPException

        # 创建第二个资产占 U10-U13
        asset2 = Asset(
            asset_code="SRV-U-002",
            asset_name="冲突服务器",
            asset_type=AssetType.server,
            cabinet_id=sample_cabinet.id,
            u_position=10,
            u_height=4,
            status=AssetStatus.in_use,
        )
        db.add(asset2)
        await db.commit()
        await db.refresh(asset2)

        # 尝试移动 sample_asset（u_height=4）到 U10
        req = MoveAssetRequest(asset_id=sample_asset.id, new_u_position=10)
        with pytest.raises(HTTPException) as exc_info:
            await move_asset_in_cabinet(sample_cabinet.id, req, db, sample_user)
        assert exc_info.value.status_code == 400

    async def test_move_asset_out_of_range(
        self, db: AsyncSession, sample_cabinet, sample_asset, sample_user
    ):
        """移动到超出机柜范围的 U 位应返回 400"""
        from fastapi import HTTPException

        # sample_asset u_height=4, U40+4-1=U43 > 42
        req = MoveAssetRequest(asset_id=sample_asset.id, new_u_position=40)
        with pytest.raises(HTTPException) as exc_info:
            await move_asset_in_cabinet(sample_cabinet.id, req, db, sample_user)
        assert exc_info.value.status_code == 400
        assert "U位超出机柜范围" in exc_info.value.detail

    async def test_move_asset_wrong_cabinet(
        self, db: AsyncSession, sample_cabinet, sample_asset, sample_user
    ):
        """用错误的 cabinet_id 移动应返回 400"""
        from fastapi import HTTPException

        # 创建另一个机柜
        cab2 = Cabinet(
            cabinet_code="CAB-U-002",
            cabinet_name="另一个机柜",
            location="B区",
            total_u=42,
        )
        db.add(cab2)
        await db.commit()
        await db.refresh(cab2)

        # sample_asset 属于 sample_cabinet，用 cab2.id 调用
        req = MoveAssetRequest(asset_id=sample_asset.id, new_u_position=5)
        with pytest.raises(HTTPException) as exc_info:
            await move_asset_in_cabinet(cab2.id, req, db, sample_user)
        assert exc_info.value.status_code == 400
        assert "资产不属于该机柜" in exc_info.value.detail
