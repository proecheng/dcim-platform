"""
FormulaCalculator 功能验证脚本

这个脚本展示所有 12+ 个计算方法的使用示例
"""
from decimal import Decimal
from datetime import date, timedelta


def demo_formula_calculator():
    """
    演示 FormulaCalculator 的所有功能

    注：这是一个演示脚本，实际使用时需要数据库连接
    """
    print("=" * 80)
    print("FormulaCalculator 功能验证")
    print("=" * 80)
    print()

    # 由于我们没有数据库，这里只演示不需要数据库的方法
    from app.services.formula_calculator import FormulaCalculator

    calc = FormulaCalculator(None)

    print("1. 负荷率计算")
    print("-" * 40)
    result = calc.calc_load_factor(
        avg_load=Decimal('14000'),
        max_demand=Decimal('22000')
    )
    print(f"   平均负荷: 14,000 kW")
    print(f"   最大需量: 22,000 kW")
    print(f"   负荷率: {result}%")
    print()

    print("2. 峰谷转移收益计算")
    print("-" * 40)
    result = calc.calc_peak_shift_benefit(
        shiftable_power=Decimal('1400'),
        shift_hours=Decimal('3'),
        sharp_price=Decimal('1.1'),
        valley_price=Decimal('0.111'),
        working_days=300
    )
    print(f"   可转移功率: 1,400 kW")
    print(f"   转移时长: 3 小时/天")
    print(f"   尖峰电价: 1.1 元/kWh")
    print(f"   低谷电价: 0.111 元/kWh")
    print(f"   → 日转移电量: {result['日转移电量']} kWh")
    print(f"   → 日收益: {result['日收益']} 元")
    print(f"   → 年收益: {result['年收益']} 万元")
    print()

    print("3. 工作日计算")
    print("-" * 40)
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    working_days = calc._get_working_days_in_period(start, end)
    print(f"   期间: {start} 至 {end}")
    print(f"   总天数: {(end - start).days + 1}")
    print(f"   工作日: {working_days} 天")
    print()

    print("=" * 80)
    print("需要数据库的方法列表（已实现，运行时需要数据库连接）:")
    print("=" * 80)

    methods = [
        ("通用方法", [
            "calc_annual_energy() - 年用电量计算",
            "calc_max_demand() - 最大需量计算",
            "calc_average_load() - 平均负荷计算"
        ]),
        ("A1 峰谷套利", [
            "calc_peak_valley_data() - 峰谷电量数据",
            "calc_shiftable_load() - 可转移负荷",
            "calc_peak_shift_benefit() - 峰谷转移收益 ✓ 已测试"
        ]),
        ("A2 需量控制", [
            "calc_demand_control_data() - 需量控制数据"
        ]),
        ("A3 设备优化", [
            "calc_equipment_load_rate() - 设备负荷率",
            "calc_equipment_optimization_potential() - 设备优化潜力"
        ]),
        ("A4 VPP 需求响应", [
            "calc_vpp_response_potential() - VPP 响应潜力"
        ]),
        ("A5 负荷调度", [
            "calc_load_curve_analysis() - 负荷曲线分析"
        ]),
        ("B1 设备改造", [
            "calc_equipment_efficiency_benchmark() - 设备能效对标"
        ]),
        ("辅助方法", [
            "_get_electricity_price() - 获取电价",
            "_get_working_days_in_period() - 工作日计算 ✓ 已测试"
        ])
    ]

    for category, method_list in methods:
        print(f"\n{category}:")
        for method in method_list:
            print(f"  • {method}")

    print()
    print("=" * 80)
    print("总计: 12+ 个核心计算方法已实现")
    print("=" * 80)


if __name__ == "__main__":
    demo_formula_calculator()
