"""
电价配置服务测试

覆盖:
  - PricingService.get_current_pricing: 获取当前电价配置
  - PricingService.get_price_for_period: 获取指定时段电价
  - PricingService.get_all_prices: 获取所有时段电价
  - PricingService.get_price_diff: 计算电价差
  - PricingService.get_peak_valley_spread: 峰谷价差分析
  - PricingService.calculate_cost_for_energy: 电费计算
  - PricingService.calculate_savings: 负荷转移节省计算
  - PricingService._get_period_label: 时段标签
"""

import pytest
from datetime import date, timedelta

from app.services.pricing_service import PricingService
from app.models.energy import ElectricityPricing


class TestGetPeriodLabel:
    """时段标签测试"""

    def test_known_period_types(self):
        """已知时段类型应返回中文标签"""
        svc = PricingService(None)
        assert svc._get_period_label("sharp") == "尖峰"
        assert svc._get_period_label("peak") == "高峰"
        assert svc._get_period_label("normal") == "平段"
        assert svc._get_period_label("valley") == "低谷"
        assert svc._get_period_label("deep_valley") == "深谷"

    def test_unknown_period_type(self):
        """未知时段类型应返回原始值"""
        svc = PricingService(None)
        assert svc._get_period_label("unknown") == "unknown"


class TestGetCurrentPricing:
    """获取当前电价配置测试"""

    @pytest.mark.asyncio
    async def test_empty_pricing(self, async_db):
        """无电价配置时返回空分组"""
        svc = PricingService(async_db)
        result = await svc.get_current_pricing()
        assert isinstance(result, dict)
        for period_type in ["sharp", "peak", "normal", "valley", "deep_valley"]:
            assert period_type in result
            assert result[period_type] == []

    @pytest.mark.asyncio
    async def test_with_pricing_records(self, async_db):
        """有电价记录时正确分组"""
        today = date.today()
        pricing = ElectricityPricing(
            pricing_name="尖峰电价",
            period_type="sharp",
            start_time="10:00",
            end_time="12:00",
            price=1.20,
            effective_date=today - timedelta(days=30),
            is_enabled=True,
        )
        async_db.add(pricing)
        await async_db.flush()

        svc = PricingService(async_db)
        result = await svc.get_current_pricing()
        assert len(result["sharp"]) == 1
        assert result["sharp"][0]["price"] == 1.20

    @pytest.mark.asyncio
    async def test_expired_pricing_excluded(self, async_db):
        """过期电价不应被返回"""
        today = date.today()
        pricing = ElectricityPricing(
            pricing_name="过期电价",
            period_type="peak",
            start_time="08:00",
            end_time="10:00",
            price=0.95,
            effective_date=today - timedelta(days=365),
            expire_date=today - timedelta(days=30),
            is_enabled=True,
        )
        async_db.add(pricing)
        await async_db.flush()

        svc = PricingService(async_db)
        result = await svc.get_current_pricing()
        assert result["peak"] == []

    @pytest.mark.asyncio
    async def test_period_type_alias_mapping(self, async_db):
        """时段类型别名应正确映射"""
        today = date.today()
        # "high" 应映射到 "peak"
        pricing = ElectricityPricing(
            pricing_name="高峰电价",
            period_type="high",
            start_time="08:00",
            end_time="10:00",
            price=0.95,
            effective_date=today - timedelta(days=30),
            is_enabled=True,
        )
        async_db.add(pricing)
        await async_db.flush()

        svc = PricingService(async_db)
        result = await svc.get_current_pricing()
        assert len(result["peak"]) == 1


class TestGetPriceForPeriod:
    """获取指定时段电价测试"""

    @pytest.mark.asyncio
    async def test_no_pricing_returns_zero(self, async_db):
        """无电价配置时返回0.0"""
        svc = PricingService(async_db)
        price = await svc.get_price_for_period("sharp")
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_returns_first_price(self, async_db):
        """返回第一条匹配的电价"""
        today = date.today()
        pricing = ElectricityPricing(
            pricing_name="尖峰电价",
            period_type="sharp",
            start_time="10:00",
            end_time="12:00",
            price=1.35,
            effective_date=today - timedelta(days=10),
            is_enabled=True,
        )
        async_db.add(pricing)
        await async_db.flush()

        svc = PricingService(async_db)
        price = await svc.get_price_for_period("sharp")
        assert price == 1.35


class TestGetAllPrices:
    """获取所有时段电价测试"""

    @pytest.mark.asyncio
    async def test_all_zero_when_empty(self, async_db):
        """无配置时所有电价为0"""
        svc = PricingService(async_db)
        prices = await svc.get_all_prices()
        assert prices["sharp_price"] == 0.0
        assert prices["peak_price"] == 0.0
        assert prices["normal_price"] == 0.0
        assert prices["valley_price"] == 0.0
        assert prices["deep_valley_price"] == 0.0


class TestCalculateCostForEnergy:
    """电费计算测试"""

    @pytest.mark.asyncio
    async def test_zero_energy(self, async_db):
        """零电量应返回零电费"""
        svc = PricingService(async_db)
        cost = await svc.calculate_cost_for_energy(0, "peak")
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_cost_calculation(self, async_db):
        """电费 = 电量 × 电价"""
        today = date.today()
        pricing = ElectricityPricing(
            pricing_name="高峰电价",
            period_type="peak",
            start_time="08:00",
            end_time="12:00",
            price=0.95,
            effective_date=today - timedelta(days=10),
            is_enabled=True,
        )
        async_db.add(pricing)
        await async_db.flush()

        svc = PricingService(async_db)
        cost = await svc.calculate_cost_for_energy(1000, "peak")
        assert cost == 950.0


class TestCalculateSavings:
    """负荷转移节省计算测试"""

    @pytest.mark.asyncio
    async def test_savings_with_no_pricing(self, async_db):
        """无电价配置时节省为0"""
        svc = PricingService(async_db)
        result = await svc.calculate_savings(power_kw=100, hours=4, source_period="peak", target_period="valley")
        assert result["daily_saving_yuan"] == 0.0
        assert result["annual_saving_yuan"] == 0.0

    @pytest.mark.asyncio
    async def test_savings_calculation(self, async_db):
        """正确计算负荷转移节省"""
        today = date.today()
        for period, price in [("peak", 0.95), ("valley", 0.35)]:
            p = ElectricityPricing(
                pricing_name=f"{period}电价",
                period_type=period,
                start_time="00:00",
                end_time="23:59",
                price=price,
                effective_date=today - timedelta(days=10),
                is_enabled=True,
            )
            async_db.add(p)
        await async_db.flush()

        svc = PricingService(async_db)
        result = await svc.calculate_savings(
            power_kw=100, hours=4, source_period="peak", target_period="valley", working_days=250
        )
        # 日转移电量 = 100 * 4 = 400 kWh
        assert result["daily_energy_kwh"] == 400
        # 价差 = 0.95 - 0.35 = 0.60
        assert result["price_diff"] == pytest.approx(0.60, abs=0.01)
        # 日节省 = 400 * 0.60 = 240
        assert result["daily_saving_yuan"] == 240.0
        # 年节省 = 240 * 250 = 60000
        assert result["annual_saving_yuan"] == 60000.0


class TestGetPriceDiff:
    """电价差计算测试"""

    @pytest.mark.asyncio
    async def test_price_diff_no_data(self, async_db):
        """无数据时价差为0"""
        svc = PricingService(async_db)
        diff = await svc.get_price_diff("sharp", "valley")
        assert diff == 0.0


class TestGetPeakValleySpread:
    """峰谷价差分析测试"""

    @pytest.mark.asyncio
    async def test_spread_no_data(self, async_db):
        """无数据时所有价差为0"""
        svc = PricingService(async_db)
        spread = await svc.get_peak_valley_spread()
        assert spread["sharp_valley_diff"] == 0
        assert spread["peak_valley_diff"] == 0
        assert spread["has_sharp"] is False
        assert spread["has_deep_valley"] is False
