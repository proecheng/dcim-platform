"""
FormulaCalculator Method Summary

This document lists all implemented calculation methods in FormulaCalculator service.
"""

# ==================== FormulaCalculator 实现总结 ====================

# 文件位置: D:\mytest1\backend\app\services\formula_calculator.py
# 总计实现方法: 15 个核心计算方法

## 1. 通用数据方法 (3个)

### 1.1 calc_annual_energy(year: int) -> Decimal
- 功能: 计算年度总用电量
- 数据源: EnergyMonthly.total_energy
- 公式: SUM(total_energy) WHERE stat_year = year
- 返回: 年用电量 (kWh)

### 1.2 calc_max_demand(year: int, month: Optional[int]) -> Decimal
- 功能: 计算年度或月度最大需量
- 数据源: DemandHistory.max_demand
- 公式: MAX(max_demand) WHERE stat_year = year
- 返回: 最大需量 (kW)

### 1.3 calc_average_load(year: int) -> Decimal
- 功能: 计算年度平均负荷
- 公式: 年用电量 ÷ 8760
- 返回: 平均负荷 (kW)

### 1.4 calc_load_factor(avg_load: Decimal, max_demand: Decimal) -> Decimal
- 功能: 计算负荷率
- 公式: (平均负荷 / 最大需量) × 100
- 返回: 负荷率 (%)


## 2. A1 峰谷套利相关方法 (3个)

### 2.1 calc_peak_valley_data(start_date: date, end_date: date) -> Dict[str, Any]
- 功能: 计算峰谷电量数据（分尖峰、高峰、平段、低谷、深谷）
- 数据源: EnergyDaily 表按时段统计
- 返回: {尖峰电量, 尖峰占比, 高峰电量, 高峰占比, ...}

### 2.2 calc_shiftable_load(meter_point_id: Optional[int]) -> Decimal
- 功能: 计算可从尖峰高峰转移的负荷
- 业务规则: 空压机50%, 循环水泵30%, 照明空调40%, 辅助设备60%
- 数据源: PowerDevice + DeviceShiftConfig
- 返回: 可转移负荷 (kW)

### 2.3 calc_peak_shift_benefit(...) -> Dict[str, Decimal]
- 功能: 计算峰谷转移收益
- 公式: 日转移电量 × (尖峰电价 - 低谷电价) × 工作日数
- 返回: {日转移电量, 日收益, 年收益}


## 3. A2 需量控制相关方法 (1个)

### 3.1 calc_demand_control_data(meter_point_id: Optional[int]) -> Dict[str, Any]
- 功能: 计算需量控制相关数据
- 步骤:
  1. 获取当前申报需量
  2. 统计历史需量分布，计算95分位值
  3. 建议申报需量 = 95分位值 × 1.05
  4. 计算可节省金额
- 返回: {当前申报需量, 历史95分位, 建议申报需量, 需量电价, 月节省, 年节省}


## 4. A3 设备运行优化相关方法 (2个)

### 4.1 calc_equipment_load_rate(equipment_type: str, start_date: date, end_date: date) -> Decimal
- 功能: 计算设备平均负荷率
- 数据源: EnergyHourly 表 + PowerDevice 表
- 公式: AVG(avg_power / rated_power) × 100
- 返回: 负荷率 (%)

### 4.2 calc_equipment_optimization_potential(equipment_type: str) -> Dict[str, Decimal]
- 功能: 计算设备优化潜力
- 业务规则: HVAC 25%, PUMP 20%, UPS 10%
- 返回: {当前功率, 优化后功率, 节省功率, 年运行小时, 年节省电量, 年节省金额}


## 5. A4 VPP 需求响应相关方法 (1个)

### 5.1 calc_vpp_response_potential() -> Dict[str, Any]
- 功能: 计算 VPP 需求响应潜力
- 分级资源:
  - Ⅰ级快速响应: 响应时间 ≤ 5分钟
  - Ⅱ级常规响应: 响应时间 ≤ 15分钟
  - Ⅲ级计划响应: 响应时间 > 240分钟
- 返回: {Ⅰ级资源, Ⅱ级资源, Ⅲ级资源, 总容量, 总年收益}


## 6. A5 负荷调度优化相关方法 (1个)

### 6.1 calc_load_curve_analysis(analysis_date: date) -> Dict[str, Any]
- 功能: 分析负荷曲线特征
- 计算指标:
  - 峰谷差 = 最大负荷 - 最小负荷
  - 负荷率 = 平均负荷 / 最大负荷 × 100%
  - 峰谷比 = 最大负荷 / 最小负荷
- 返回: {最大负荷, 最小负荷, 平均负荷, 峰谷差, 负荷率, 峰谷比}


## 7. B1 设备改造升级相关方法 (1个)

### 7.1 calc_equipment_efficiency_benchmark(equipment_type: str) -> Dict[str, Any]
- 功能: 设备能效对标分析
- 对比: 当前能效水平 vs 行业先进水平
- 返回: {当前能效, 行业先进能效, 能效差距, 改造投资, 年节省电量, 年节省金额, 投资回收期}


## 8. 辅助方法 (2个)

### 8.1 _get_electricity_price(time_slot: str) -> Decimal
- 功能: 获取电价
- 参数: "sharp"/"peak"/"normal"/"valley"/"deep_valley"
- 返回: 电价 (元/kWh)

### 8.2 _get_working_days_in_period(start: date, end: date) -> int
- 功能: 计算期间工作日数量
- 返回: 工作日数量


# ==================== 测试覆盖 ====================

## 单元测试 (已通过)
- test_calc_load_factor - 负荷率计算 ✓
- test_calc_peak_shift_benefit - 峰谷转移收益 ✓
- test_get_working_days - 工作日计算 ✓

## 集成测试 (需要数据库环境)
- test_calc_annual_energy
- test_calc_max_demand
- test_calc_average_load
- test_calc_peak_valley_data
- test_calc_shiftable_load
- test_calc_demand_control_data
- test_calc_equipment_load_rate
- test_calc_equipment_optimization_potential
- test_calc_vpp_response_potential
- test_calc_load_curve_analysis
- test_calc_equipment_efficiency_benchmark


# ==================== 文件清单 ====================

1. 服务文件:
   D:\mytest1\backend\app\services\formula_calculator.py (788 行)

2. 测试文件:
   D:\mytest1\backend\tests\services\test_formula_calculator.py
   D:\mytest1\backend\tests\conftest.py
   D:\mytest1\backend\tests\services\__init__.py

3. 总代码量: ~1000+ 行
4. 方法数量: 15 个核心方法
5. 测试数量: 15+ 个测试用例
