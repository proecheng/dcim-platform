"""能耗数据聚合服务测试 — Story 6-2"""
import pytest
from datetime import datetime, date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, select

from app.core.database import Base
from app.models.energy import (
    PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly, ElectricityPricing
)
from app.models.history import PointHistory
from app.services.energy_aggregator import (
    aggregate_hourly, aggregate_daily, aggregate_monthly, _get_period_type_for_hour
)


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
        await session.execute(delete(EnergyMonthly))
        await session.execute(delete(EnergyDaily))
        await session.execute(delete(EnergyHourly))
        await session.execute(delete(PointHistory))
        await session.execute(delete(ElectricityPricing))
        await session.execute(delete(PowerDevice))
        await session.commit()
        yield session


# ==================== 时段分类辅助函数测试 ====================


class TestGetPeriodTypeForHour:
    """测试时段分类辅助函数"""

    def test_peak_period(self):
        """高峰时段应返回 'peak'"""

        class MockPricing:
            period_type = "peak"
            start_time = "10:00"
            end_time = "12:00"

        result = _get_period_type_for_hour(10, [MockPricing()])
        assert result == "peak"

    def test_valley_period(self):
        """低谷时段应返回 'valley'"""

        class MockPricing:
            period_type = "valley"
            start_time = "23:00"
            end_time = "07:00"

        result = _get_period_type_for_hour(0, [MockPricing()])
        assert result == "valley"

    def test_default_normal(self):
        """无匹配时段应返回 'normal'"""
        result = _get_period_type_for_hour(15, [])
        assert result == "normal"

    def test_sharp_maps_to_peak(self):
        """尖峰时段应映射为 'peak'"""

        class MockPricing:
            period_type = "sharp"
            start_time = "13:00"
            end_time = "15:00"

        result = _get_period_type_for_hour(14, [MockPricing()])
        assert result == "peak"

    def test_deep_valley_maps_to_valley(self):
        """深谷时段应映射为 'valley'"""

        class MockPricing:
            period_type = "deep_valley"
            start_time = "01:00"
            end_time = "05:00"

        result = _get_period_type_for_hour(3, [MockPricing()])
        assert result == "valley"


# ==================== 小时聚合测试 ====================


class TestAggregateHourly:
    """测试小时聚合"""

    @pytest.mark.anyio
    async def test_hourly_aggregation_basic(self, db_session):
        """基本小时聚合：从 PointHistory 计算平均功率和电量"""
        device = PowerDevice(
            device_code="AGG-H01", device_name="聚合测试设备1",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9001
        )
        db_session.add(device)
        await db_session.flush()

        # 在 10:00-11:00 之间插入功率数据
        target_time = datetime(2026, 1, 15, 10, 0, 0)
        for i in range(12):  # 每5分钟一条
            ph = PointHistory(
                point_id=9001,
                value=50.0 + i,  # 50-61 kW
                quality=0,
                recorded_at=target_time + timedelta(minutes=i * 5)
            )
            db_session.add(ph)
        await db_session.commit()

        await aggregate_hourly(db_session, target_time=target_time)

        result = await db_session.execute(
            select(EnergyHourly).where(
                EnergyHourly.device_id == device.id,
                EnergyHourly.stat_time == target_time
            )
        )
        hourly = result.scalar_one_or_none()
        assert hourly is not None
        assert hourly.avg_power > 0
        assert hourly.max_power == 61.0
        assert hourly.min_power == 50.0
        # total_energy = avg_power * 1h
        assert abs(hourly.total_energy - hourly.avg_power) < 0.01

    @pytest.mark.anyio
    async def test_hourly_idempotent(self, db_session):
        """幂等性：重复聚合不应产生重复记录"""
        device = PowerDevice(
            device_code="AGG-H02", device_name="聚合测试设备2",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9002
        )
        db_session.add(device)
        await db_session.flush()

        target_time = datetime(2026, 1, 15, 11, 0, 0)
        ph = PointHistory(
            point_id=9002, value=60.0, quality=0,
            recorded_at=target_time + timedelta(minutes=15)
        )
        db_session.add(ph)
        await db_session.commit()

        await aggregate_hourly(db_session, target_time=target_time)
        await aggregate_hourly(db_session, target_time=target_time)

        result = await db_session.execute(
            select(EnergyHourly).where(
                EnergyHourly.device_id == device.id,
                EnergyHourly.stat_time == target_time
            )
        )
        records = result.scalars().all()
        assert len(records) == 1

    @pytest.mark.anyio
    async def test_hourly_skip_bad_quality(self, db_session):
        """quality != 0 的数据不参与聚合"""
        device = PowerDevice(
            device_code="AGG-H03", device_name="聚合测试设备3",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9003
        )
        db_session.add(device)
        await db_session.flush()

        target_time = datetime(2026, 1, 15, 12, 0, 0)
        # 只有 quality=2 的数据
        ph = PointHistory(
            point_id=9003, value=60.0, quality=2,
            recorded_at=target_time + timedelta(minutes=15)
        )
        db_session.add(ph)
        await db_session.commit()

        await aggregate_hourly(db_session, target_time=target_time)

        result = await db_session.execute(
            select(EnergyHourly).where(
                EnergyHourly.device_id == device.id,
                EnergyHourly.stat_time == target_time
            )
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.anyio
    async def test_hourly_skip_no_power_point(self, db_session):
        """无 power_point_id 的设备不参与聚合"""
        device = PowerDevice(
            device_code="AGG-H04", device_name="无点位设备",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=None
        )
        db_session.add(device)
        await db_session.commit()

        target_time = datetime(2026, 1, 15, 13, 0, 0)
        await aggregate_hourly(db_session, target_time=target_time)

        result = await db_session.execute(
            select(EnergyHourly).where(
                EnergyHourly.stat_time == target_time
            )
        )
        records = result.scalars().all()
        # 不应有该设备的记录
        assert all(r.device_id != device.id for r in records)


# ==================== 日聚合测试 ====================


class TestAggregateDaily:
    """测试日聚合"""

    @pytest.mark.anyio
    async def test_daily_aggregation_basic(self, db_session):
        """基本日聚合：从 EnergyHourly 聚合到 EnergyDaily"""
        device = PowerDevice(
            device_code="AGG-D01", device_name="日聚合测试设备",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9101
        )
        db_session.add(device)
        await db_session.flush()

        # 插入电价配置
        pricing_peak = ElectricityPricing(
            pricing_name="高峰", period_type="peak",
            start_time="10:00", end_time="15:00",
            price=1.05, effective_date=date(2025, 1, 1),
            is_enabled=True
        )
        pricing_valley = ElectricityPricing(
            pricing_name="低谷", period_type="valley",
            start_time="23:00", end_time="07:00",
            price=0.3, effective_date=date(2025, 1, 1),
            is_enabled=True
        )
        db_session.add_all([pricing_peak, pricing_valley])
        await db_session.flush()

        # 插入24小时的 EnergyHourly 数据
        target_date = date(2026, 1, 20)
        for hour in range(24):
            hourly = EnergyHourly(
                device_id=device.id,
                stat_time=datetime(2026, 1, 20, hour, 0, 0),
                total_energy=50.0,  # 每小时 50 kWh
                avg_power=50.0,
                max_power=55.0 + hour,
                min_power=45.0
            )
            db_session.add(hourly)
        await db_session.commit()

        await aggregate_daily(db_session, target_date=target_date)

        result = await db_session.execute(
            select(EnergyDaily).where(
                EnergyDaily.device_id == device.id,
                EnergyDaily.stat_date == target_date
            )
        )
        daily = result.scalar_one_or_none()
        assert daily is not None
        assert daily.total_energy == 24 * 50.0  # 1200 kWh
        assert daily.peak_energy > 0
        assert daily.valley_energy > 0
        assert daily.max_power > 0

    @pytest.mark.anyio
    async def test_daily_idempotent(self, db_session):
        """幂等性：重复日聚合不应产生重复记录"""
        device = PowerDevice(
            device_code="AGG-D02", device_name="日聚合幂等测试",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9102
        )
        db_session.add(device)
        await db_session.flush()

        target_date = date(2026, 1, 21)
        hourly = EnergyHourly(
            device_id=device.id,
            stat_time=datetime(2026, 1, 21, 10, 0, 0),
            total_energy=50.0, avg_power=50.0,
            max_power=55.0, min_power=45.0
        )
        db_session.add(hourly)
        await db_session.commit()

        await aggregate_daily(db_session, target_date=target_date)
        await aggregate_daily(db_session, target_date=target_date)

        result = await db_session.execute(
            select(EnergyDaily).where(
                EnergyDaily.device_id == device.id,
                EnergyDaily.stat_date == target_date
            )
        )
        records = result.scalars().all()
        assert len(records) == 1


# ==================== 月聚合测试 ====================


class TestAggregateMonthly:
    """测试月聚合"""

    @pytest.mark.anyio
    async def test_monthly_aggregation_basic(self, db_session):
        """基本月聚合：从 EnergyDaily 聚合到 EnergyMonthly"""
        device = PowerDevice(
            device_code="AGG-M01", device_name="月聚合测试设备",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9201
        )
        db_session.add(device)
        await db_session.flush()

        # 插入电价配置
        pricing = ElectricityPricing(
            pricing_name="高峰", period_type="peak",
            start_time="10:00", end_time="15:00",
            price=1.05, effective_date=date(2025, 1, 1),
            is_enabled=True
        )
        db_session.add(pricing)
        await db_session.flush()

        # 插入30天的 EnergyDaily 数据
        for day in range(1, 31):
            daily = EnergyDaily(
                device_id=device.id,
                stat_date=date(2026, 1, day),
                total_energy=1200.0,
                peak_energy=480.0,
                normal_energy=420.0,
                valley_energy=300.0,
                max_power=55.0,
                avg_power=50.0,
                energy_cost=960.0
            )
            db_session.add(daily)
        await db_session.commit()

        await aggregate_monthly(db_session, target_year=2026, target_month=1)

        result = await db_session.execute(
            select(EnergyMonthly).where(
                EnergyMonthly.device_id == device.id,
                EnergyMonthly.stat_year == 2026,
                EnergyMonthly.stat_month == 1
            )
        )
        monthly = result.scalar_one_or_none()
        assert monthly is not None
        assert monthly.total_energy == 30 * 1200.0
        assert monthly.peak_energy == 30 * 480.0
        assert monthly.peak_cost > 0  # 使用 PricingService 计算

    @pytest.mark.anyio
    async def test_monthly_idempotent(self, db_session):
        """幂等性：重复月聚合不应产生重复记录"""
        device = PowerDevice(
            device_code="AGG-M02", device_name="月聚合幂等测试",
            device_type="IT", rated_power=100.0,
            is_enabled=True, power_point_id=9202
        )
        db_session.add(device)
        await db_session.flush()

        daily = EnergyDaily(
            device_id=device.id,
            stat_date=date(2026, 2, 15),
            total_energy=1200.0,
            peak_energy=480.0, normal_energy=420.0, valley_energy=300.0,
            max_power=55.0, avg_power=50.0, energy_cost=960.0
        )
        db_session.add(daily)
        await db_session.commit()

        await aggregate_monthly(db_session, target_year=2026, target_month=2)
        await aggregate_monthly(db_session, target_year=2026, target_month=2)

        result = await db_session.execute(
            select(EnergyMonthly).where(
                EnergyMonthly.device_id == device.id,
                EnergyMonthly.stat_year == 2026,
                EnergyMonthly.stat_month == 2
            )
        )
        records = result.scalars().all()
        assert len(records) == 1
