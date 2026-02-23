"""PUE 计算服务测试 — Story 6-1"""

import pytest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.energy import PowerDevice, PUEHistory
from app.models.point import PointRealtime
from app.services.pue_calculator import calculate_realtime_pue, write_pue_history, PUEResult


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
        # 清理测试数据
        await session.execute(delete(PointRealtime))
        await session.execute(delete(PUEHistory))
        await session.execute(delete(PowerDevice))
        await session.commit()
        yield session


# ==================== PUE 计算单元测试 ====================


class TestCalculateRealtimePUE:
    """测试 PUE 计算（真实数据模式）"""

    @pytest.mark.anyio
    async def test_pue_with_it_load(self, db_session):
        """有 IT 负载时正确计算 PUE"""
        # 创建 IT 设备
        it_device = PowerDevice(
            device_code="IT-001",
            device_name="服务器1",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=1001,
        )
        # 创建 AC 设备
        ac_device = PowerDevice(
            device_code="AC-001",
            device_name="空调1",
            device_type="AC",
            rated_power=50.0,
            is_it_load=False,
            is_enabled=True,
            power_point_id=1002,
        )
        db_session.add_all([it_device, ac_device])
        await db_session.flush()

        # 创建实时数据
        rt_it = PointRealtime(
            point_id=1001,
            value=80.0,
            quality=0,
            updated_at=datetime.now(),
        )
        rt_ac = PointRealtime(
            point_id=1002,
            value=30.0,
            quality=0,
            updated_at=datetime.now(),
        )
        db_session.add_all([rt_it, rt_ac])
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        assert result.data_source == "realtime"
        assert result.it_power == 80.0
        assert result.cooling_power == 30.0
        assert result.total_power == 110.0
        assert result.current_pue == round(110.0 / 80.0, 3)
        assert result.unreliable_count == 0

    @pytest.mark.anyio
    async def test_pue_it_power_zero(self, db_session):
        """IT 负载为 0 时返回 None"""
        # 只创建 AC 设备（无 IT 负载）
        ac_device = PowerDevice(
            device_code="AC-002",
            device_name="空调2",
            device_type="AC",
            rated_power=50.0,
            is_it_load=False,
            is_enabled=True,
            power_point_id=2001,
        )
        db_session.add(ac_device)
        await db_session.flush()

        rt_ac = PointRealtime(
            point_id=2001,
            value=30.0,
            quality=0,
            updated_at=datetime.now(),
        )
        db_session.add(rt_ac)
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        assert result.current_pue is None
        assert result.it_power == 0
        assert result.data_source == "realtime"

    @pytest.mark.anyio
    async def test_pue_skip_quality_2(self, db_session):
        """quality==2 (中断) 的点位应被跳过"""
        it_device = PowerDevice(
            device_code="IT-003",
            device_name="服务器3",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=3001,
        )
        bad_device = PowerDevice(
            device_code="IT-004",
            device_name="服务器4",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=3002,
        )
        db_session.add_all([it_device, bad_device])
        await db_session.flush()

        rt_good = PointRealtime(
            point_id=3001,
            value=80.0,
            quality=0,
            updated_at=datetime.now(),
        )
        rt_bad = PointRealtime(
            point_id=3002,
            value=90.0,
            quality=2,  # 中断
            updated_at=datetime.now(),
        )
        db_session.add_all([rt_good, rt_bad])
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        # 只有 good 设备的 80kW 被计入
        assert result.it_power == 80.0
        assert result.total_power == 80.0

    @pytest.mark.anyio
    async def test_pue_unreliable_count(self, db_session):
        """quality==1 或数据过期的点位计入 unreliable_count"""
        it_device = PowerDevice(
            device_code="IT-005",
            device_name="服务器5",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=4001,
        )
        stale_device = PowerDevice(
            device_code="IT-006",
            device_name="服务器6",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=4002,
        )
        db_session.add_all([it_device, stale_device])
        await db_session.flush()

        rt_uncertain = PointRealtime(
            point_id=4001,
            value=80.0,
            quality=1,  # 不可靠
            updated_at=datetime.now(),
        )
        rt_stale = PointRealtime(
            point_id=4002,
            value=70.0,
            quality=0,
            updated_at=datetime.now() - timedelta(seconds=400),  # 过期
        )
        db_session.add_all([rt_uncertain, rt_stale])
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        assert result.unreliable_count == 2
        # 数据仍被计入功率
        assert result.it_power == 150.0

    @pytest.mark.anyio
    async def test_ups_loss_calculation(self, db_session):
        """UPS 损耗 = max(0, ups_total - it_power)"""
        it_device = PowerDevice(
            device_code="IT-007",
            device_name="服务器7",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=5001,
        )
        ups_device = PowerDevice(
            device_code="UPS-001",
            device_name="UPS1",
            device_type="UPS",
            rated_power=120.0,
            is_it_load=False,
            is_enabled=True,
            power_point_id=5002,
        )
        db_session.add_all([it_device, ups_device])
        await db_session.flush()

        rt_it = PointRealtime(
            point_id=5001,
            value=80.0,
            quality=0,
            updated_at=datetime.now(),
        )
        rt_ups = PointRealtime(
            point_id=5002,
            value=90.0,
            quality=0,
            updated_at=datetime.now(),
        )
        db_session.add_all([rt_it, rt_ups])
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        assert result.ups_loss == 10.0  # 90 - 80 = 10
        assert result.it_power == 80.0

    @pytest.mark.anyio
    async def test_no_power_point_id_skipped(self, db_session):
        """没有 power_point_id 的设备不参与计算"""
        device_no_point = PowerDevice(
            device_code="IT-008",
            device_name="服务器8",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=None,  # 无关联点位
        )
        db_session.add(device_no_point)
        await db_session.commit()

        result = await calculate_realtime_pue(db_session)

        assert result.it_power == 0
        assert result.current_pue is None


# ==================== PUE 历史写入测试 ====================


class TestWritePUEHistory:
    """测试 PUE 历史写入"""

    @pytest.mark.anyio
    async def test_write_pue_history_valid(self, db_session):
        """PUE 有效时正确写入 PUEHistory"""
        it_device = PowerDevice(
            device_code="IT-H01",
            device_name="服务器H1",
            device_type="IT",
            rated_power=100.0,
            is_it_load=True,
            is_enabled=True,
            power_point_id=6001,
        )
        ac_device = PowerDevice(
            device_code="AC-H01",
            device_name="空调H1",
            device_type="AC",
            rated_power=50.0,
            is_it_load=False,
            is_enabled=True,
            power_point_id=6002,
        )
        db_session.add_all([it_device, ac_device])
        await db_session.flush()

        rt_it = PointRealtime(
            point_id=6001,
            value=80.0,
            quality=0,
            updated_at=datetime.now(),
        )
        rt_ac = PointRealtime(
            point_id=6002,
            value=30.0,
            quality=0,
            updated_at=datetime.now(),
        )
        db_session.add_all([rt_it, rt_ac])
        await db_session.commit()

        await write_pue_history(db_session)

        # 验证写入
        from sqlalchemy import select

        result = await db_session.execute(select(PUEHistory))
        records = result.scalars().all()
        assert len(records) >= 1
        latest = records[-1]
        assert latest.pue == round(110.0 / 80.0, 3)
        assert latest.total_power == 110.0
        assert latest.it_power == 80.0
        assert latest.cooling_power == 30.0

    @pytest.mark.anyio
    async def test_write_pue_history_skip_when_invalid(self, db_session):
        """IT 负载为 0 时不写入 PUEHistory"""
        # 只有 AC 设备
        ac_device = PowerDevice(
            device_code="AC-H02",
            device_name="空调H2",
            device_type="AC",
            rated_power=50.0,
            is_it_load=False,
            is_enabled=True,
            power_point_id=7001,
        )
        db_session.add(ac_device)
        await db_session.flush()

        rt_ac = PointRealtime(
            point_id=7001,
            value=30.0,
            quality=0,
            updated_at=datetime.now(),
        )
        db_session.add(rt_ac)
        await db_session.commit()

        # 记录写入前的数量
        from sqlalchemy import select, func

        count_before = (await db_session.execute(select(func.count(PUEHistory.id)))).scalar()

        await write_pue_history(db_session)

        count_after = (await db_session.execute(select(func.count(PUEHistory.id)))).scalar()

        assert count_after == count_before


# ==================== PUEResult 数据类测试 ====================


class TestPUEResult:
    """测试 PUEResult 数据类"""

    def test_pue_result_fields(self):
        """PUEResult 应包含所有必要字段"""
        result = PUEResult(
            current_pue=1.5,
            total_power=100.0,
            it_power=66.7,
            cooling_power=20.0,
            ups_loss=5.0,
            data_source="realtime",
            unreliable_count=0,
        )
        assert result.current_pue == 1.5
        assert result.data_source == "realtime"
        assert result.unreliable_count == 0

    def test_pue_result_none_pue(self):
        """PUEResult 支持 current_pue=None"""
        result = PUEResult(
            current_pue=None,
            total_power=50.0,
            it_power=0,
            cooling_power=30.0,
            ups_loss=0,
            data_source="realtime",
            unreliable_count=1,
        )
        assert result.current_pue is None
