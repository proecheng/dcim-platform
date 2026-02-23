"""
需量分析服务测试

覆盖:
  - subtract_months: 月份减法
  - DemandThresholds: 阈值配置
  - DemandAnalysisService.calculate_optimal_demand: 建议需量计算
  - DemandAnalysisService.generate_recommendation: 优化建议生成
  - DemandAnalysisService.analyze: 完整分析入口
  - DemandAnalysisService.generate_mock_demand_curve: 模拟需量曲线
  - DemandAnalysisService.generate_mock_hourly_load: 模拟小时负荷
  - DemandAnalysisService.generate_mock_power_factor: 模拟功率因数
"""

import pytest
from datetime import datetime

from app.services.demand_analysis_service import (
    subtract_months,
    DemandThresholds,
    DemandStatistics,
    DemandAnalysisService,
)


class TestSubtractMonths:
    """月份减法测试"""

    def test_basic_subtraction(self):
        """基本月份减法"""
        dt = datetime(2026, 6, 15)
        result = subtract_months(dt, 3)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15

    def test_cross_year(self):
        """跨年减法"""
        dt = datetime(2026, 2, 15)
        result = subtract_months(dt, 3)
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 15

    def test_month_end_adjustment(self):
        """月末日期调整（如3月31日减1个月应为2月28日）"""
        dt = datetime(2026, 3, 31)
        result = subtract_months(dt, 1)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 28

    def test_leap_year(self):
        """闰年2月29日"""
        dt = datetime(2024, 3, 31)
        result = subtract_months(dt, 1)
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29

    def test_subtract_12_months(self):
        """减12个月等于去年同月"""
        dt = datetime(2026, 6, 15)
        result = subtract_months(dt, 12)
        assert result.year == 2025
        assert result.month == 6

    def test_subtract_zero(self):
        """减0个月不变"""
        dt = datetime(2026, 6, 15)
        result = subtract_months(dt, 0)
        assert result == dt


class TestDemandThresholds:
    """阈值配置测试"""

    def test_default_values(self):
        """默认阈值"""
        t = DemandThresholds()
        assert t.low_utilization == 0.80
        assert t.high_utilization == 1.05
        assert t.optimal_utilization == 0.90
        assert t.safety_margin == 0.10
        assert t.min_saving == 5000


class TestCalculateOptimalDemand:
    """建议需量计算测试"""

    def test_kw_rounds_to_5(self):
        """kW类型按5取整"""
        svc = DemandAnalysisService.__new__(DemandAnalysisService)
        svc.thresholds = DemandThresholds()
        result = svc.calculate_optimal_demand(600, demand_type="kW")
        # 600 * 1.10 = 660 → ceil(660/5)*5 = 660
        assert result == 660
        assert result % 5 == 0

    def test_kva_rounds_to_10(self):
        """kVA类型按10取整"""
        svc = DemandAnalysisService.__new__(DemandAnalysisService)
        svc.thresholds = DemandThresholds()
        result = svc.calculate_optimal_demand(600, demand_type="KVA")
        # 600 * 1.10 = 660 → ceil(660/10)*10 = 660
        assert result == 660
        assert result % 10 == 0

    def test_custom_safety_margin(self):
        """自定义安全裕度"""
        svc = DemandAnalysisService.__new__(DemandAnalysisService)
        svc.thresholds = DemandThresholds()
        result = svc.calculate_optimal_demand(600, safety_margin=0.20)
        # 600 * 1.20 = 720 → ceil(720/5)*5 = 720
        assert result == 720

    def test_non_round_value(self):
        """非整数值向上取整"""
        svc = DemandAnalysisService.__new__(DemandAnalysisService)
        svc.thresholds = DemandThresholds()
        result = svc.calculate_optimal_demand(601)
        # 601 * 1.10 = 661.1 → ceil(661.1/5)*5 = 665
        assert result == 665


class TestGenerateRecommendation:
    """优化建议生成测试"""

    @pytest.mark.asyncio
    async def test_reduce_recommendation(self, async_db):
        """利用率低于80%时建议降低需量"""
        svc = DemandAnalysisService(async_db)
        stats = DemandStatistics(
            meter_point_id=1,
            meter_code="M001",
            meter_name="测试",
            declared_demand=1000,
            demand_type="kW",
            max_demand_12m=600,
            avg_demand_12m=500,
            demand_95th=580,
            std_dev=50,
            utilization_rate=0.60,  # 低于 0.80
            over_declared_count=0,
            transformer_name=None,
        )
        rec = await svc.generate_recommendation(stats)
        assert rec.recommendation_type == "reduce"
        assert rec.suggested_demand < 1000
        assert rec.annual_saving > 0

    @pytest.mark.asyncio
    async def test_increase_recommendation(self, async_db):
        """利用率超过105%时建议增加需量"""
        svc = DemandAnalysisService(async_db)
        stats = DemandStatistics(
            meter_point_id=1,
            meter_code="M001",
            meter_name="测试",
            declared_demand=500,
            demand_type="kW",
            max_demand_12m=600,
            avg_demand_12m=550,
            demand_95th=580,
            std_dev=30,
            utilization_rate=1.20,  # 超过 1.05
            over_declared_count=5,
            transformer_name=None,
        )
        rec = await svc.generate_recommendation(stats)
        assert rec.recommendation_type == "increase"
        assert rec.risk_level == "high"

    @pytest.mark.asyncio
    async def test_none_recommendation(self, async_db):
        """利用率合理且波动小时无需调整"""
        svc = DemandAnalysisService(async_db)
        stats = DemandStatistics(
            meter_point_id=1,
            meter_code="M001",
            meter_name="测试",
            declared_demand=800,
            demand_type="kW",
            max_demand_12m=720,
            avg_demand_12m=680,
            demand_95th=710,
            std_dev=20,  # std_dev < avg * 0.15 = 102
            utilization_rate=0.90,  # 在 0.80-1.05 之间
            over_declared_count=0,
            transformer_name=None,
        )
        rec = await svc.generate_recommendation(stats)
        assert rec.recommendation_type == "none"
        assert rec.annual_saving == 0


class TestAnalyze:
    """完整分析入口测试"""

    @pytest.mark.asyncio
    async def test_insufficient_data(self, async_db):
        """数据不足时返回无机会"""
        svc = DemandAnalysisService(async_db)
        result = await svc.analyze(meter_point_id=99999)
        assert result["has_opportunity"] is False
        assert result["statistics"] is None


class TestMockDataGeneration:
    """模拟数据生成测试"""

    def test_generate_mock_demand_curve(self):
        """生成需量曲线模拟数据"""
        data = DemandAnalysisService.generate_mock_demand_curve(meter_point_id=1, months=12)
        assert len(data) == 12
        for item in data:
            assert "month" in item
            assert "max_demand" in item
            assert "avg_demand" in item
            assert item["max_demand"] > 0

    def test_generate_mock_hourly_load(self):
        """生成24小时负荷模拟数据"""
        from datetime import date

        period_map = {h: "flat" for h in range(24)}
        data = DemandAnalysisService.generate_mock_hourly_load(
            meter_point_id=1, target_date=date(2026, 1, 15), period_map=period_map
        )
        assert len(data) == 24
        for item in data:
            assert "hour" in item
            assert "power" in item
            assert "period" in item

    def test_generate_mock_power_factor(self):
        """生成功率因数趋势模拟数据"""
        data = DemandAnalysisService.generate_mock_power_factor(meter_point_id=1, days=30)
        assert len(data) == 30
        for item in data:
            assert "date" in item
            assert "power_factor" in item
            assert 0.85 <= item["power_factor"] <= 1.0
            assert item["status"] in ["good", "warning", "bad"]

    def test_deterministic_output(self):
        """相同参数应产生相同结果"""
        data1 = DemandAnalysisService.generate_mock_demand_curve(meter_point_id=5, months=6)
        data2 = DemandAnalysisService.generate_mock_demand_curve(meter_point_id=5, months=6)
        assert data1 == data2
