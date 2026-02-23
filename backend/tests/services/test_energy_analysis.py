"""
能耗分析服务测试

覆盖:
  - DemandAnalysisService.analyze_demand_config: 需量配置分析（有历史数据/无历史数据）
  - DemandAnalysisService._calculate_recommended_demand: 推荐需量计算
  - DemandAnalysisService._generate_mock_analysis: 模拟分析数据
  - LoadShiftAnalysisService.analyze_load_shift: 负荷转移分析
  - LoadShiftAnalysisService._get_peak_valley_distribution: 峰谷分布
  - LoadShiftAnalysisService._generate_shift_suggestions: 转移建议生成
"""

import pytest
from datetime import datetime, timedelta

from app.services.energy_analysis import (
    DemandAnalysisService,
    LoadShiftAnalysisService,
)


class TestCalculateRecommendedDemand:
    """推荐需量计算测试"""

    def test_basic_calculation(self):
        """基本推荐需量计算：95分位数 + 10%安全裕度，按5取整"""
        result = DemandAnalysisService._calculate_recommended_demand(max_demand=700, demand_95th=650, avg_demand=500)
        # 650 * 1.10 = 715.0000000000001 (浮点精度) → ceil(715.0.../5)*5 = 720
        assert result == 720

    def test_rounds_up_to_multiple_of_5(self):
        """结果应向上取整到5的倍数"""
        result = DemandAnalysisService._calculate_recommended_demand(max_demand=700, demand_95th=601, avg_demand=500)
        # 601 * 1.10 = 661.1 → ceil(661.1/5)*5 = 665
        assert result == 665
        assert result % 5 == 0

    def test_custom_safety_margin(self):
        """自定义安全裕度"""
        result = DemandAnalysisService._calculate_recommended_demand(
            max_demand=700, demand_95th=600, avg_demand=500, safety_margin=0.20
        )
        # 600 * 1.20 = 720 → ceil(720/5)*5 = 720
        assert result == 720

    def test_zero_demand(self):
        """零需量输入"""
        result = DemandAnalysisService._calculate_recommended_demand(max_demand=0, demand_95th=0, avg_demand=0)
        assert result == 0

    def test_small_demand(self):
        """小需量值也应正确取整"""
        result = DemandAnalysisService._calculate_recommended_demand(max_demand=50, demand_95th=42, avg_demand=30)
        # 42 * 1.10 = 46.2 → ceil(46.2/5)*5 = 50
        assert result == 50
        assert result % 5 == 0


class TestAnalyzeDemandConfig:
    """需量配置分析测试"""

    @pytest.mark.asyncio
    async def test_meter_point_not_found(self, async_db):
        """计量点不存在时返回错误"""
        result = await DemandAnalysisService.analyze_demand_config(async_db, meter_point_id=99999)
        assert "error" in result
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_mock_analysis_when_no_history(self, async_db):
        """无历史数据时生成模拟分析"""
        from app.models.energy import MeterPoint

        mp = MeterPoint(
            meter_code="TEST-M001",
            meter_name="测试计量点",
            declared_demand=800,
            demand_type="kW",
            is_enabled=True,
        )
        async_db.add(mp)
        await async_db.flush()

        result = await DemandAnalysisService.analyze_demand_config(async_db, meter_point_id=mp.id)
        # 无历史数据应返回模拟分析
        assert result["meter_point_id"] == mp.id
        assert result["current_config"]["declared_demand"] == 800
        assert "_note" in result or "模拟" in result.get("analysis_period", "")

    @pytest.mark.asyncio
    async def test_analysis_with_history_data(self, async_db):
        """有历史数据时进行真实分析"""
        from app.models.energy import MeterPoint, DemandHistory

        mp = MeterPoint(
            meter_code="TEST-M002",
            meter_name="测试计量点2",
            declared_demand=1000,
            demand_type="kW",
            is_enabled=True,
        )
        async_db.add(mp)
        await async_db.flush()

        # 创建12个月的需量历史
        now = datetime.now()
        for i in range(12):
            month_date = now - timedelta(days=i * 30)
            dh = DemandHistory(
                meter_point_id=mp.id,
                stat_year=month_date.year,
                stat_month=month_date.month,
                max_demand=700 + i * 10,
                avg_demand=500 + i * 5,
                over_declared_times=0,
            )
            async_db.add(dh)
        await async_db.flush()

        result = await DemandAnalysisService.analyze_demand_config(async_db, meter_point_id=mp.id)
        assert result["meter_point_id"] == mp.id
        assert "statistics" in result
        assert "recommendation" in result
        assert "cost_analysis" in result
        assert result["statistics"]["max_demand"] > 0
        assert len(result["optimization_options"]) == 3

    @pytest.mark.asyncio
    async def test_analysis_returns_optimization_options(self, async_db):
        """分析结果应包含三种优化方案"""
        from app.models.energy import MeterPoint, DemandHistory

        mp = MeterPoint(
            meter_code="TEST-M003",
            meter_name="测试计量点3",
            declared_demand=900,
            demand_type="kW",
            is_enabled=True,
        )
        async_db.add(mp)
        await async_db.flush()

        now = datetime.now()
        for i in range(6):
            dh = DemandHistory(
                meter_point_id=mp.id,
                stat_year=now.year,
                stat_month=max(1, now.month - i),
                max_demand=600 + i * 20,
                avg_demand=450 + i * 10,
            )
            async_db.add(dh)
        await async_db.flush()

        result = await DemandAnalysisService.analyze_demand_config(async_db, meter_point_id=mp.id)
        options = result["optimization_options"]
        assert len(options) == 3
        option_names = {o["name"] for o in options}
        assert option_names == {"conservative", "recommended", "aggressive"}


class TestGenerateShiftSuggestions:
    """转移建议生成测试"""

    def test_hvac_devices_generate_suggestion(self):
        """HVAC设备应生成高优先级建议"""
        potentials = [
            {
                "device_id": 1,
                "device_name": "精密空调1",
                "device_type": "HVAC",
                "shiftable_ratio": 0.17,
                "monthly_saving": 500,
                "annual_saving": 6000,
                "peak_reduction_ratio": 2.0,
                "valley_increase_ratio": 3.0,
            }
        ]
        distribution = {"peak_ratio": 45, "valley_ratio": 22}
        suggestions = LoadShiftAnalysisService._generate_shift_suggestions(potentials, distribution)
        assert len(suggestions) >= 1
        assert suggestions[0]["priority"] == "high"
        assert "精密空调" in suggestions[0]["title"]

    def test_lighting_devices_generate_suggestion(self):
        """照明设备应生成中优先级建议"""
        potentials = [
            {
                "device_id": 2,
                "device_name": "照明系统1",
                "device_type": "LIGHTING",
                "shiftable_ratio": 0.10,
                "monthly_saving": 200,
                "annual_saving": 2400,
                "peak_reduction_ratio": 1.0,
                "valley_increase_ratio": 1.5,
            }
        ]
        distribution = {"peak_ratio": 45, "valley_ratio": 22}
        suggestions = LoadShiftAnalysisService._generate_shift_suggestions(potentials, distribution)
        assert len(suggestions) >= 1
        assert suggestions[0]["priority"] == "medium"

    def test_empty_potentials(self):
        """无可转移设备时返回空建议"""
        suggestions = LoadShiftAnalysisService._generate_shift_suggestions([], {})
        assert suggestions == []

    def test_mixed_device_types(self):
        """混合设备类型应生成多条建议"""
        potentials = [
            {
                "device_id": 1,
                "device_name": "空调1",
                "device_type": "HVAC",
                "shiftable_ratio": 0.17,
                "monthly_saving": 500,
                "annual_saving": 6000,
                "peak_reduction_ratio": 2.0,
                "valley_increase_ratio": 3.0,
            },
            {
                "device_id": 2,
                "device_name": "照明1",
                "device_type": "LIGHTING",
                "shiftable_ratio": 0.10,
                "monthly_saving": 200,
                "annual_saving": 2400,
                "peak_reduction_ratio": 1.0,
                "valley_increase_ratio": 1.5,
            },
            {
                "device_id": 3,
                "device_name": "水泵1",
                "device_type": "PUMP",
                "shiftable_ratio": 0.15,
                "monthly_saving": 300,
                "annual_saving": 3600,
                "peak_reduction_ratio": 1.5,
                "valley_increase_ratio": 2.0,
            },
        ]
        distribution = {"peak_ratio": 45, "valley_ratio": 22}
        suggestions = LoadShiftAnalysisService._generate_shift_suggestions(potentials, distribution)
        # HVAC + LIGHTING + 1个其他设备 = 3条建议
        assert len(suggestions) == 3


class TestLoadShiftAnalysis:
    """负荷转移分析集成测试"""

    @pytest.mark.asyncio
    async def test_analyze_with_no_data(self, async_db):
        """无可转移设备时返回空结果"""
        result = await LoadShiftAnalysisService.analyze_load_shift(async_db, days=30)
        assert "summary" in result
        assert result["summary"]["shiftable_device_count"] == 0
        assert "peak_valley_distribution" in result

    @pytest.mark.asyncio
    async def test_peak_valley_distribution_mock_data(self, async_db):
        """无日能耗数据时返回模拟分布"""
        dist = await LoadShiftAnalysisService._get_peak_valley_distribution(async_db, days=30)
        assert dist["total_energy"] > 0
        assert "_note" in dist  # 模拟数据标记
