"""
测试公式计算器服务
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from app.services.formula_calculator import FormulaCalculator


class TestFormulaCalculator:
    """FormulaCalculator 测试类"""

    def test_calc_load_factor(self):
        """测试负荷率计算"""
        calc = FormulaCalculator(None)

        # 正常情况
        result = calc.calc_load_factor(
            avg_load=Decimal('14000'),
            max_demand=Decimal('22000')
        )
        assert result == Decimal('63.64')

        # 最大需量为0的边界情况
        result = calc.calc_load_factor(
            avg_load=Decimal('14000'),
            max_demand=Decimal('0')
        )
        assert result == Decimal('0')

    def test_calc_peak_shift_benefit(self):
        """测试峰谷转移收益计算"""
        calc = FormulaCalculator(None)

        result = calc.calc_peak_shift_benefit(
            shiftable_power=Decimal('1400'),
            shift_hours=Decimal('3'),
            sharp_price=Decimal('1.1'),
            valley_price=Decimal('0.111'),
            working_days=300
        )

        # 验证返回结构
        assert "日转移电量" in result
        assert "日收益" in result
        assert "年收益" in result

        # 验证计算结果
        # 日转移电量 = 1400 * 3 = 4200 kWh
        assert result["日转移电量"] == Decimal('4200.00')

        # 日收益 = 4200 * (1.1 - 0.111) = 4153.8 元
        assert result["日收益"] == Decimal('4153.80')

        # 年收益 = 4153.8 * 300 / 10000 = 124.61 万元
        assert result["年收益"] == Decimal('124.61')

    # 注：_get_electricity_price 需要数据库，移到集成测试部分

    def test_get_working_days(self):
        """测试工作日计算"""
        calc = FormulaCalculator(None)

        # 测试30天期间
        start = date(2026, 1, 1)
        end = date(2026, 1, 30)
        working_days = calc._get_working_days_in_period(start, end)

        # 30天 * 5/7 ≈ 21.4 → 21天
        assert working_days == 21

        # 测试7天期间
        start = date(2026, 1, 1)
        end = date(2026, 1, 7)
        working_days = calc._get_working_days_in_period(start, end)
        assert working_days == 5


@pytest.mark.integration
class TestFormulaCalculatorIntegration:
    """FormulaCalculator 集成测试（需要数据库）"""

    def test_calc_annual_energy(self, db_session):
        """测试年用电量计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        # 需要测试数据
        result = calc.calc_annual_energy(2026)
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')

    def test_calc_max_demand(self, db_session):
        """测试最大需量计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        # 测试年度最大需量
        result = calc.calc_max_demand(2026)
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')

        # 测试月度最大需量
        result = calc.calc_max_demand(2026, 1)
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')

    def test_calc_average_load(self, db_session):
        """测试平均负荷计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_average_load(2026)
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')

    def test_calc_peak_valley_data(self, db_session):
        """测试峰谷电量数据计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = calc.calc_peak_valley_data(start_date, end_date)

        # 验证返回结构
        assert "尖峰电量" in result
        assert "高峰电量" in result
        assert "平段电量" in result
        assert "低谷电量" in result
        assert "深谷电量" in result
        assert "总电量" in result

        # 验证数据类型
        assert isinstance(result["总电量"], Decimal)
        assert isinstance(result["尖峰占比"], Decimal)

    def test_calc_shiftable_load(self, db_session):
        """测试可转移负荷计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_shiftable_load()
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')

    def test_calc_demand_control_data(self, db_session):
        """测试需量控制数据计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_demand_control_data()

        # 验证返回结构
        assert "当前申报需量" in result
        assert "历史95分位" in result
        assert "建议申报需量" in result
        assert "需量电价" in result
        assert "月节省" in result
        assert "年节省" in result

        # 验证数据类型
        assert isinstance(result["当前申报需量"], Decimal)
        assert isinstance(result["年节省"], Decimal)

    def test_calc_equipment_load_rate(self, db_session):
        """测试设备负荷率计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = calc.calc_equipment_load_rate('HVAC', start_date, end_date)
        assert isinstance(result, Decimal)
        assert result >= Decimal('0')
        assert result <= Decimal('100')

    def test_calc_equipment_optimization_potential(self, db_session):
        """测试设备优化潜力计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_equipment_optimization_potential('HVAC')

        # 验证返回结构
        assert "当前功率" in result
        assert "优化后功率" in result
        assert "节省功率" in result
        assert "年运行小时" in result
        assert "年节省电量" in result
        assert "年节省金额" in result

    def test_calc_vpp_response_potential(self, db_session):
        """测试VPP需求响应潜力计算（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_vpp_response_potential()

        # 验证返回结构
        assert "Ⅰ级资源" in result
        assert "Ⅱ级资源" in result
        assert "Ⅲ级资源" in result
        assert "总容量" in result
        assert "总年收益" in result

        # 验证子结构
        assert "容量" in result["Ⅰ级资源"]
        assert "年响应次数" in result["Ⅰ级资源"]
        assert "年收益" in result["Ⅰ级资源"]

    def test_calc_load_curve_analysis(self, db_session):
        """测试负荷曲线分析（需要数据库）"""
        calc = FormulaCalculator(db_session)

        analysis_date = date.today() - timedelta(days=1)
        result = calc.calc_load_curve_analysis(analysis_date)

        # 验证返回结构
        assert "最大负荷" in result
        assert "最小负荷" in result
        assert "平均负荷" in result
        assert "峰谷差" in result
        assert "负荷率" in result
        assert "峰谷比" in result

    def test_calc_equipment_efficiency_benchmark(self, db_session):
        """测试设备能效对标分析（需要数据库）"""
        calc = FormulaCalculator(db_session)

        result = calc.calc_equipment_efficiency_benchmark('UPS')

        # 验证返回结构
        assert "当前能效" in result
        assert "行业先进能效" in result
        assert "能效差距" in result
        assert "改造投资" in result
        assert "年节省电量" in result
        assert "年节省金额" in result
        assert "投资回收期" in result

        # 验证数据类型
        assert isinstance(result["当前能效"], Decimal)
        assert isinstance(result["投资回收期"], Decimal)
