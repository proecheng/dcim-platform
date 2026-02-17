"""实时数据 Redis 优先读取测试 — Story 4.1"""
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.point import Point, PointRealtime
from app.services.datasource_bridge import sync_point_data, link_datasource_to_point


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_point(db_session: AsyncSession):
    """创建测试点位和实时值"""
    point = Point(
        point_code="TEST_TH_001",
        point_name="测试温度传感器",
        point_type="AI",
        device_type="TH",
        area_code="A1",
        unit="°C",
        min_range=0,
        max_range=50,
        is_enabled=True,
    )
    db_session.add(point)
    await db_session.flush()

    realtime = PointRealtime(
        point_id=point.id,
        value=25.5,
        raw_value=25.5,
        value_text="25.5",
        quality=0,
        status="normal",
    )
    db_session.add(realtime)
    await db_session.commit()
    await db_session.refresh(point)
    return point


class TestDatasourceBridge:
    """数据源桥接服务测试"""

    async def test_sync_point_data(self, db_session: AsyncSession, sample_point: Point):
        """测试同步点位数据到 PointRealtime"""
        with patch("app.services.datasource_bridge.redis_service") as mock_redis:
            mock_redis.is_available = False

            await sync_point_data(
                session=db_session,
                point_id=sample_point.id,
                value=28.3,
                quality=0,
                status="normal",
            )

        # 验证 PointRealtime 已更新
        from sqlalchemy import select
        result = await db_session.execute(
            select(PointRealtime).where(PointRealtime.point_id == sample_point.id)
        )
        rt = result.scalar_one()
        assert rt.value == 28.3
        assert rt.status == "normal"

    async def test_sync_point_data_with_redis(self, db_session: AsyncSession, sample_point: Point):
        """测试同步点位数据同时写入 Redis"""
        with patch("app.services.datasource_bridge.redis_service") as mock_redis:
            mock_redis.is_available = True
            mock_redis.set = AsyncMock()

            await sync_point_data(
                session=db_session,
                point_id=sample_point.id,
                value=30.0,
                quality=0,
                status="alarm",
                alarm_level="minor",
            )

        # 验证 Redis 被调用
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert f"point:{sample_point.id}:latest" == call_args[0][0]
        cached = json.loads(call_args[0][1])
        assert cached["value"] == 30.0
        assert cached["status"] == "alarm"

    async def test_sync_point_data_redis_failure(self, db_session: AsyncSession, sample_point: Point):
        """测试 Redis 写入失败不影响数据库更新"""
        with patch("app.services.datasource_bridge.redis_service") as mock_redis:
            mock_redis.is_available = True
            mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))

            # 不应抛出异常
            await sync_point_data(
                session=db_session,
                point_id=sample_point.id,
                value=26.0,
            )

        # 数据库仍然更新成功
        from sqlalchemy import select
        result = await db_session.execute(
            select(PointRealtime).where(PointRealtime.point_id == sample_point.id)
        )
        rt = result.scalar_one()
        assert rt.value == 26.0

    async def test_sync_preserves_alarm_level(self, db_session: AsyncSession, sample_point: Point):
        """测试同步保留告警级别"""
        with patch("app.services.datasource_bridge.redis_service") as mock_redis:
            mock_redis.is_available = False

            await sync_point_data(
                session=db_session,
                point_id=sample_point.id,
                value=45.0,
                quality=0,
                status="alarm",
                alarm_level="critical",
            )

        from sqlalchemy import select
        result = await db_session.execute(
            select(PointRealtime).where(PointRealtime.point_id == sample_point.id)
        )
        rt = result.scalar_one()
        assert rt.alarm_level == "critical"
        assert rt.status == "alarm"
