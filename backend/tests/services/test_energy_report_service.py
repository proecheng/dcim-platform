"""
能效报告服务测试

覆盖:
  - _period_range: 月份时间范围
  - _date_range: 月份日期范围
  - _prev_month: 上月计算
  - _change_rate: 变化率计算
  - EnergyReportService._cost_dict: 成本字典构建
  - EnergyReportService._sum_energy_json: JSON能耗求和
  - EnergyReportService._calc_saving_kwh: 节能电量计算
  - EnergyReportService.generate_report_data: 报告数据生成
"""

import pytest
import json
from datetime import datetime, date

from app.services.energy_report_service import (
    _period_range,
    _date_range,
    _prev_month,
    _change_rate,
    EnergyReportService,
)


class TestPeriodRange:
    """月份时间范围测试"""

    def test_normal_month(self):
        """普通月份"""
        start, end = _period_range(2026, 6)
        assert start == datetime(2026, 6, 1)
        assert end == datetime(2026, 7, 1)

    def test_december(self):
        """12月跨年"""
        start, end = _period_range(2026, 12)
        assert start == datetime(2026, 12, 1)
        assert end == datetime(2027, 1, 1)

    def test_january(self):
        """1月"""
        start, end = _period_range(2026, 1)
        assert start == datetime(2026, 1, 1)
        assert end == datetime(2026, 2, 1)


class TestDateRange:
    """月份日期范围测试"""

    def test_normal_month(self):
        start, end = _date_range(2026, 3)
        assert start == date(2026, 3, 1)
        assert end == date(2026, 4, 1)

    def test_december(self):
        start, end = _date_range(2026, 12)
        assert start == date(2026, 12, 1)
        assert end == date(2027, 1, 1)


class TestPrevMonth:
    """上月计算测试"""

    def test_normal(self):
        assert _prev_month(2026, 6) == (2026, 5)

    def test_january(self):
        """1月的上月是去年12月"""
        assert _prev_month(2026, 1) == (2025, 12)


class TestChangeRate:
    """变化率计算测试"""

    def test_normal_increase(self):
        """正常增长"""
        rate = _change_rate(110, 100)
        assert rate == 10.0

    def test_normal_decrease(self):
        """正常下降"""
        rate = _change_rate(90, 100)
        assert rate == -10.0

    def test_previous_zero(self):
        """前值为0返回None"""
        assert _change_rate(100, 0) is None

    def test_previous_none(self):
        """前值为None返回None"""
        assert _change_rate(100, None) is None

    def test_current_none(self):
        """当前值为None返回None"""
        assert _change_rate(None, 100) is None


class TestCostDict:
    """成本字典构建测试"""

    def test_normal_row(self):
        """正常数据行"""
        row = (1000.0, 500.0, 400.0, 200.0, 300.0, 150.0, 300.0, 150.0)
        result = EnergyReportService._cost_dict(row)
        assert result["total_energy"] == 1000.0
        assert result["total_cost"] == 500.0
        assert result["peak_energy"] == 400.0

    def test_null_values(self):
        """空值处理"""
        row = (None, None, None, None, None, None, None, None)
        result = EnergyReportService._cost_dict(row)
        assert result["total_energy"] == 0.0
        assert result["total_cost"] == 0.0


class TestSumEnergyJson:
    """JSON能耗求和测试"""

    def test_list_of_dicts(self):
        """字典列表求和"""
        data = [{"energy": 100}, {"energy": 200}, {"energy": 300}]
        assert EnergyReportService._sum_energy_json(data) == 600

    def test_json_string(self):
        """JSON字符串解析后求和"""
        data = json.dumps([{"energy": 50}, {"energy": 75}])
        assert EnergyReportService._sum_energy_json(data) == 125

    def test_none_input(self):
        """None输入返回0"""
        assert EnergyReportService._sum_energy_json(None) == 0.0

    def test_invalid_json_string(self):
        """无效JSON字符串返回0"""
        assert EnergyReportService._sum_energy_json("not json") == 0.0

    def test_empty_list(self):
        """空列表返回0"""
        assert EnergyReportService._sum_energy_json([]) == 0.0

    def test_mixed_items(self):
        """混合项（含非字典）"""
        data = [{"energy": 100}, "invalid", {"energy": 200}]
        assert EnergyReportService._sum_energy_json(data) == 300


class TestCalcSavingKwh:
    """节能电量计算测试"""

    def test_normal_saving(self):
        """正常节能"""
        before = [{"energy": 500}, {"energy": 300}]
        after = [{"energy": 400}, {"energy": 200}]
        result = EnergyReportService._calc_saving_kwh(before, after)
        assert result == 200  # (500+300) - (400+200)

    def test_no_saving(self):
        """无节能"""
        data = [{"energy": 100}]
        result = EnergyReportService._calc_saving_kwh(data, data)
        assert result == 0

    def test_none_inputs(self):
        """空输入"""
        result = EnergyReportService._calc_saving_kwh(None, None)
        assert result == 0.0


class TestGenerateReportData:
    """报告数据生成集成测试"""

    @pytest.mark.asyncio
    async def test_empty_database(self, async_db):
        """空数据库生成报告"""
        result = await EnergyReportService.generate_report_data(async_db, 2026, 1)
        assert result["year"] == 2026
        assert result["month"] == 1
        assert "pue_trend" in result
        assert "cost_comparison" in result
        assert "energy_saving" in result
        assert "energy_overview" in result

    @pytest.mark.asyncio
    async def test_report_structure(self, async_db):
        """报告数据结构完整性"""
        result = await EnergyReportService.generate_report_data(async_db, 2026, 6)
        # PUE 趋势
        pue = result["pue_trend"]
        assert "daily_values" in pue
        assert "month_avg_pue" in pue
        # 成本对比
        cost = result["cost_comparison"]
        assert "current_month" in cost
        assert "last_month" in cost
        # 节能
        saving = result["energy_saving"]
        assert "total_saving_kwh" in saving
        assert "opportunities_count" in saving
        # 能耗概览
        overview = result["energy_overview"]
        assert "daily_energy" in overview
        assert "total_energy" in overview
