"""能耗统计端点测试 — Story 6-2"""

import pytest
from datetime import datetime, date

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.energy import PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly, ElectricityPricing
from app.utils.deterministic import _deterministic_ratio, _deterministic_offset, _device_seed, _time_seed, _date_seed


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
        await session.execute(delete(EnergyDaily))
        await session.execute(delete(EnergyMonthly))
        await session.execute(delete(EnergyHourly))
        await session.execute(delete(ElectricityPricing))
        await session.execute(delete(PowerDevice))
        await session.commit()
        yield session


# ==================== 确定性辅助函数测试 ====================


class TestDeterministicFunctions:
    """测试确定性模拟辅助函数"""

    def test_deterministic_ratio_range(self):
        """比率值应在 [min_val, max_val] 范围内"""
        for seed in range(100):
            val = _deterministic_ratio(seed, 0.3, 0.9)
            assert 0.3 <= val <= 0.9

    def test_deterministic_ratio_reproducible(self):
        """相同种子应产生相同结果"""
        a = _deterministic_ratio(42, 0.5, 0.9)
        b = _deterministic_ratio(42, 0.5, 0.9)
        assert a == b

    def test_deterministic_offset_range(self):
        """偏移值应在 [-amplitude, +amplitude] 范围内"""
        for seed in range(100):
            val = _deterministic_offset(seed, 10.0)
            assert -10.0 <= val <= 10.0

    def test_deterministic_offset_reproducible(self):
        """相同种子应产生相同偏移"""
        a = _deterministic_offset(99, 5.0)
        b = _deterministic_offset(99, 5.0)
        assert a == b

    def test_device_seed_unique(self):
        """不同设备ID应产生不同种子"""
        s1 = _device_seed(1, 0)
        s2 = _device_seed(2, 0)
        assert s1 != s2

    def test_time_seed_unique(self):
        """不同时间应产生不同种子"""
        dt1 = datetime(2026, 1, 1, 10)
        dt2 = datetime(2026, 1, 1, 11)
        assert _time_seed(dt1) != _time_seed(dt2)

    def test_date_seed_unique(self):
        """不同日期应产生不同种子"""
        d1 = date(2026, 1, 1)
        d2 = date(2026, 1, 2)
        assert _date_seed(d1) != _date_seed(d2)


# ==================== Schema data_source 字段测试 ====================


class TestSchemaDataSource:
    """测试 Schema 新增的 data_source 字段"""

    def test_energy_stat_data_source_optional(self):
        """EnergyStat.data_source 应为可选字段"""
        from app.schemas.energy import EnergyStat

        stat = EnergyStat(
            total_energy=1000,
            peak_energy=400,
            normal_energy=350,
            valley_energy=250,
            total_cost=800,
            peak_cost=480,
            normal_cost=280,
            valley_cost=100,
            avg_power=42,
            max_power=50,
        )
        assert stat.data_source is None

    def test_energy_stat_data_source_set(self):
        """EnergyStat.data_source 可设置为 'real'"""
        from app.schemas.energy import EnergyStat

        stat = EnergyStat(
            total_energy=1000,
            peak_energy=400,
            normal_energy=350,
            valley_energy=250,
            total_cost=800,
            peak_cost=480,
            normal_cost=280,
            valley_cost=100,
            avg_power=42,
            max_power=50,
            data_source="real",
        )
        assert stat.data_source == "real"

    def test_energy_trend_data_source(self):
        """EnergyTrend.data_source 应为可选字段"""
        from app.schemas.energy import EnergyTrend

        trend = EnergyTrend(granularity="daily", data=[], total_energy=0, total_cost=0)
        assert trend.data_source is None

    def test_energy_comparison_data_source(self):
        """EnergyComparison.data_source 应为可选字段"""
        from app.schemas.energy import EnergyComparison, EnergyStat

        stat = EnergyStat(
            total_energy=1000,
            peak_energy=400,
            normal_energy=350,
            valley_energy=250,
            total_cost=800,
            peak_cost=480,
            normal_cost=280,
            valley_cost=100,
            avg_power=42,
            max_power=50,
        )
        comp = EnergyComparison(
            current_period=stat,
            previous_period=stat,
            energy_change=0,
            energy_change_rate=0,
            cost_change=0,
            cost_change_rate=0,
        )
        assert comp.data_source is None


# ==================== PricingService 集成测试 ====================


class TestPricingServiceIntegration:
    """测试 PricingService 在统计端点中的使用"""

    @pytest.mark.anyio
    async def test_get_all_prices_returns_dict(self, db_session):
        """get_all_prices 应返回包含各时段电价的字典"""
        from app.services.pricing_service import PricingService

        # 插入电价配置
        pricing = ElectricityPricing(
            pricing_name="高峰电价",
            period_type="peak",
            start_time="10:00",
            end_time="12:00",
            price=1.05,
            effective_date=date(2025, 1, 1),
            is_enabled=True,
        )
        db_session.add(pricing)
        await db_session.commit()

        service = PricingService(db_session)
        prices = await service.get_all_prices()

        assert isinstance(prices, dict)
        assert "peak_price" in prices
        assert prices["peak_price"] == 1.05

    @pytest.mark.anyio
    async def test_get_all_prices_empty(self, db_session):
        """无电价配置时返回全零"""
        from app.services.pricing_service import PricingService

        service = PricingService(db_session)
        prices = await service.get_all_prices()

        assert prices.get("peak_price") == 0.0
        assert prices.get("normal_price") == 0.0
        assert prices.get("valley_price") == 0.0


# ==================== EnergyDaily 查询测试 ====================


class TestEnergyDailyQuery:
    """测试日能耗数据查询"""

    @pytest.mark.anyio
    async def test_query_daily_with_data(self, db_session):
        """有数据时应返回真实记录"""
        from sqlalchemy import select

        device = PowerDevice(
            device_code="DEV-D01", device_name="测试设备1", device_type="IT", rated_power=100.0, is_enabled=True
        )
        db_session.add(device)
        await db_session.flush()

        daily = EnergyDaily(
            device_id=device.id,
            stat_date=date(2026, 1, 15),
            total_energy=1200.5,
            peak_energy=480.2,
            normal_energy=420.1,
            valley_energy=300.2,
            max_power=55.0,
            avg_power=50.0,
            energy_cost=960.4,
        )
        db_session.add(daily)
        await db_session.commit()

        result = await db_session.execute(select(EnergyDaily).where(EnergyDaily.stat_date == date(2026, 1, 15)))
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].total_energy == 1200.5

    @pytest.mark.anyio
    async def test_query_daily_empty(self, db_session):
        """无数据时查询应返回空列表"""
        from sqlalchemy import select

        result = await db_session.execute(select(EnergyDaily).where(EnergyDaily.stat_date == date(2099, 12, 31)))
        records = result.scalars().all()
        assert len(records) == 0


# ==================== EnergyMonthly 查询测试 ====================


class TestEnergyMonthlyQuery:
    """测试月能耗数据查询"""

    @pytest.mark.anyio
    async def test_query_monthly_with_data(self, db_session):
        """有数据时应返回真实记录"""
        from sqlalchemy import select

        device = PowerDevice(
            device_code="DEV-M01", device_name="测试设备M1", device_type="IT", rated_power=100.0, is_enabled=True
        )
        db_session.add(device)
        await db_session.flush()

        monthly = EnergyMonthly(
            device_id=device.id,
            stat_year=2026,
            stat_month=1,
            total_energy=36000.0,
            peak_energy=14400.0,
            normal_energy=12600.0,
            valley_energy=9000.0,
            max_power=60.0,
            avg_power=50.0,
            energy_cost=28800.0,
            peak_cost=17280.0,
            normal_cost=10080.0,
            valley_cost=3600.0,
        )
        db_session.add(monthly)
        await db_session.commit()

        result = await db_session.execute(
            select(EnergyMonthly).where(EnergyMonthly.stat_year == 2026, EnergyMonthly.stat_month == 1)
        )
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].total_energy == 36000.0
        assert records[0].peak_cost == 17280.0
