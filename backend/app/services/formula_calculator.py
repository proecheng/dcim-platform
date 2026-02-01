"""
公式计算器服务 (异步版本)
负责将所有 *** 占位符映射到实际数据源，并提供步骤化的计算公式

这是节能方案模板系统的核心服务，提供15+个计算方法用于6种模板类型

V2.0: 改为异步实现，使用 AsyncSession + select() 语法
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List
from decimal import Decimal

from ..models.energy import (
    EnergyMonthly,
    DemandHistory,
    EnergyDaily,
    MeterPoint,
    PowerCurveData,
    ElectricityPricing,
    PowerDevice,
    DeviceShiftConfig,
    LoadRegulationConfig,
    OverDemandEvent,
    EnergyHourly,
    DeviceLoadProfile
)


class FormulaCalculator:
    """公式计算器 - 将所有 *** 占位符映射到数据源 (异步版本)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== 通用数据方法 ====================

    async def calc_annual_energy(self, year: int) -> Decimal:
        """
        计算年度总用电量

        数据源: EnergyMonthly.total_energy
        公式: SUM(total_energy) WHERE stat_year = year

        参数:
            year: 统计年份

        返回:
            年用电量 (kWh)
        """
        stmt = select(func.sum(EnergyMonthly.total_energy)).where(
            EnergyMonthly.stat_year == year
        )
        result = await self.db.execute(stmt)
        value = result.scalar()

        return Decimal(str(value)) if value else Decimal('0')

    async def calc_max_demand(self, year: int, month: Optional[int] = None) -> Decimal:
        """
        计算年度或月度最大需量

        数据源: DemandHistory.max_demand
        公式: MAX(max_demand) WHERE stat_year = year [AND stat_month = month]

        参数:
            year: 统计年份
            month: 统计月份（可选，不传则计算全年）

        返回:
            最大需量 (kW)
        """
        stmt = select(func.max(DemandHistory.max_demand)).where(
            DemandHistory.stat_year == year
        )

        if month is not None:
            stmt = stmt.where(DemandHistory.stat_month == month)

        result = await self.db.execute(stmt)
        value = result.scalar()
        return Decimal(str(value)) if value else Decimal('0')

    async def calc_average_load(self, year: int) -> Decimal:
        """
        计算年度平均负荷

        公式: 年用电量 ÷ 8760 小时

        参数:
            year: 统计年份

        返回:
            平均负荷 (kW)
        """
        annual_energy = await self.calc_annual_energy(year)
        if annual_energy == 0:
            return Decimal('0')

        # 8760 = 365 天 × 24 小时
        average_load = annual_energy / Decimal('8760')
        return average_load.quantize(Decimal('0.01'))

    def calc_load_factor(self, avg_load: Decimal, max_demand: Decimal) -> Decimal:
        """
        计算负荷率

        公式: (平均负荷 / 最大需量) × 100

        参数:
            avg_load: 平均负荷 (kW)
            max_demand: 最大需量 (kW)

        返回:
            负荷率 (%)
        """
        if max_demand == 0:
            return Decimal('0')

        load_factor = (avg_load / max_demand) * Decimal('100')
        return load_factor.quantize(Decimal('0.01'))

    # ==================== A1: 峰谷套利相关方法 ====================

    async def calc_peak_valley_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        计算峰谷电量数据（分尖峰、高峰、平段、低谷、深谷）

        数据源: EnergyDaily 表按时段统计

        参数:
            start_date: 分析起始日期
            end_date: 分析结束日期

        返回格式:
        {
            "尖峰电量": Decimal,  # kWh
            "尖峰占比": Decimal,  # %
            "高峰电量": Decimal,
            "高峰占比": Decimal,
            "平段电量": Decimal,
            "平段占比": Decimal,
            "低谷电量": Decimal,
            "低谷占比": Decimal,
            "深谷电量": Decimal,
            "深谷占比": Decimal,
            "总电量": Decimal
        }
        """
        # 统计总电量
        stmt = select(func.sum(EnergyDaily.total_energy)).where(
            EnergyDaily.stat_date >= start_date,
            EnergyDaily.stat_date <= end_date
        )
        result = await self.db.execute(stmt)
        total_energy_result = result.scalar()
        total_energy = Decimal(str(total_energy_result)) if total_energy_result else Decimal('0')

        # 统计各时段电量
        stmt = select(func.sum(EnergyDaily.peak_energy)).where(
            EnergyDaily.stat_date >= start_date,
            EnergyDaily.stat_date <= end_date
        )
        result = await self.db.execute(stmt)
        peak_energy_result = result.scalar()
        peak_energy = Decimal(str(peak_energy_result)) if peak_energy_result else Decimal('0')

        stmt = select(func.sum(EnergyDaily.normal_energy)).where(
            EnergyDaily.stat_date >= start_date,
            EnergyDaily.stat_date <= end_date
        )
        result = await self.db.execute(stmt)
        normal_energy_result = result.scalar()
        normal_energy = Decimal(str(normal_energy_result)) if normal_energy_result else Decimal('0')

        stmt = select(func.sum(EnergyDaily.valley_energy)).where(
            EnergyDaily.stat_date >= start_date,
            EnergyDaily.stat_date <= end_date
        )
        result = await self.db.execute(stmt)
        valley_energy_result = result.scalar()
        valley_energy = Decimal(str(valley_energy_result)) if valley_energy_result else Decimal('0')

        # 计算占比
        def calc_ratio(energy: Decimal, total: Decimal) -> Decimal:
            if total == 0:
                return Decimal('0')
            return ((energy / total) * Decimal('100')).quantize(Decimal('0.01'))

        # 简化处理：假设尖峰占高峰电量30%，高峰占70%
        sharp_energy = (peak_energy * Decimal('0.3')).quantize(Decimal('0.01'))
        high_peak_energy = (peak_energy * Decimal('0.7')).quantize(Decimal('0.01'))

        # 假设深谷占低谷电量40%，低谷占60%
        deep_valley_energy = (valley_energy * Decimal('0.4')).quantize(Decimal('0.01'))
        low_valley_energy = (valley_energy * Decimal('0.6')).quantize(Decimal('0.01'))

        return {
            "尖峰电量": sharp_energy,
            "尖峰占比": calc_ratio(sharp_energy, total_energy),
            "高峰电量": high_peak_energy,
            "高峰占比": calc_ratio(high_peak_energy, total_energy),
            "平段电量": normal_energy,
            "平段占比": calc_ratio(normal_energy, total_energy),
            "低谷电量": low_valley_energy,
            "低谷占比": calc_ratio(low_valley_energy, total_energy),
            "深谷电量": deep_valley_energy,
            "深谷占比": calc_ratio(deep_valley_energy, total_energy),
            "总电量": total_energy
        }

    async def calc_shiftable_load(self, meter_point_id: Optional[int] = None) -> Decimal:
        """
        计算可从尖峰高峰转移的负荷

        业务规则:
        - 空压机系统: 50% 可转移
        - 循环水泵: 30% 可转移
        - 照明空调: 40% 可转移
        - 辅助设备: 60% 可转移

        数据源: PowerDevice + DeviceShiftConfig

        参数:
            meter_point_id: 计量点ID（可选，不传则计算全部）

        返回:
            可转移负荷 (kW)
        """
        stmt = select(
            func.sum(PowerDevice.rated_power * DeviceShiftConfig.shiftable_power_ratio)
        ).select_from(PowerDevice).join(
            DeviceShiftConfig,
            PowerDevice.id == DeviceShiftConfig.device_id
        ).where(
            DeviceShiftConfig.is_shiftable == True,
            PowerDevice.is_enabled == True
        )

        result = await self.db.execute(stmt)
        value = result.scalar()
        return Decimal(str(value)) if value else Decimal('0')

    def calc_peak_shift_benefit(
        self,
        shiftable_power: Decimal,  # 可转移功率 kW
        shift_hours: Decimal,      # 转移时长 h/天
        sharp_price: Decimal,      # 尖峰电价 元/kWh
        valley_price: Decimal,     # 低谷电价 元/kWh
        working_days: int = 300    # 年工作日
    ) -> Dict[str, Decimal]:
        """
        计算峰谷转移收益

        公式:
        日转移电量 = shiftable_power × shift_hours
        日价差 = sharp_price - valley_price
        日收益 = 日转移电量 × 日价差
        年收益 = 日收益 × working_days ÷ 10000  # 转换为万元

        返回:
        {
            "日转移电量": Decimal,  # kWh
            "日收益": Decimal,      # 元
            "年收益": Decimal       # 万元
        }
        """
        # 日转移电量 (kWh)
        daily_shifted_energy = shiftable_power * shift_hours

        # 价差 (元/kWh)
        price_diff = sharp_price - valley_price

        # 日收益 (元)
        daily_benefit = daily_shifted_energy * price_diff

        # 年收益 (万元)
        annual_benefit = (daily_benefit * Decimal(str(working_days)) / Decimal('10000')).quantize(Decimal('0.01'))

        return {
            "日转移电量": daily_shifted_energy.quantize(Decimal('0.01')),
            "日收益": daily_benefit.quantize(Decimal('0.01')),
            "年收益": annual_benefit
        }

    # ==================== A2: 需量控制相关方法 ====================

    async def calc_demand_control_data(self, meter_point_id: Optional[int] = None) -> Dict[str, Any]:
        """
        计算需量控制相关数据

        步骤:
        1. 获取当前申报需量 (from MeterPoint.declared_demand)
        2. 统计历史需量分布，计算 95 分位值
        3. 建议申报需量 = 95 分位值 × 1.05 (安全余量)
        4. 计算可节省金额

        返回格式:
        {
            "当前申报需量": Decimal,  # kW
            "历史95分位": Decimal,    # kW
            "建议申报需量": Decimal,  # kW
            "需量电价": Decimal,      # 元/kW·月
            "月节省": Decimal,        # 万元
            "年节省": Decimal         # 万元
        }
        """
        # 获取计量点
        if meter_point_id is None:
            stmt = select(MeterPoint).where(MeterPoint.is_enabled == True).limit(1)
            result = await self.db.execute(stmt)
            meter_point = result.scalar_one_or_none()
        else:
            stmt = select(MeterPoint).where(MeterPoint.id == meter_point_id)
            result = await self.db.execute(stmt)
            meter_point = result.scalar_one_or_none()

        if not meter_point:
            return {
                "当前申报需量": Decimal('0'),
                "历史95分位": Decimal('0'),
                "建议申报需量": Decimal('0'),
                "需量电价": Decimal('42'),
                "月节省": Decimal('0'),
                "年节省": Decimal('0')
            }

        current_declared = Decimal(str(meter_point.declared_demand)) if meter_point.declared_demand else Decimal('0')

        # 获取最近一个月的需量历史
        current_year = datetime.now().year
        current_month = datetime.now().month

        stmt = select(DemandHistory).where(
            DemandHistory.meter_point_id == meter_point.id,
            DemandHistory.stat_year == current_year,
            DemandHistory.stat_month == current_month
        ).limit(1)
        result = await self.db.execute(stmt)
        demand_history = result.scalar_one_or_none()

        if not demand_history or not demand_history.demand_95th:
            # 如果没有当月数据，查询上个月
            prev_month = current_month - 1 if current_month > 1 else 12
            prev_year = current_year if current_month > 1 else current_year - 1

            stmt = select(DemandHistory).where(
                DemandHistory.meter_point_id == meter_point.id,
                DemandHistory.stat_year == prev_year,
                DemandHistory.stat_month == prev_month
            ).limit(1)
            result = await self.db.execute(stmt)
            demand_history = result.scalar_one_or_none()

        demand_95th = Decimal(str(demand_history.demand_95th)) if demand_history and demand_history.demand_95th else Decimal('0')

        # 建议申报需量 = 95分位 × 1.05
        recommended_demand = (demand_95th * Decimal('1.05')).quantize(Decimal('0.1'))

        # 需量电价 (元/kW·月) - 固定值或从配置获取
        demand_price = Decimal('42')

        # 计算节省
        if current_declared > recommended_demand:
            monthly_saving = ((current_declared - recommended_demand) * demand_price / Decimal('10000')).quantize(Decimal('0.01'))
            annual_saving = (monthly_saving * Decimal('12')).quantize(Decimal('0.01'))
        else:
            monthly_saving = Decimal('0')
            annual_saving = Decimal('0')

        return {
            "当前申报需量": current_declared,
            "历史95分位": demand_95th,
            "建议申报需量": recommended_demand,
            "需量电价": demand_price,
            "月节省": monthly_saving,
            "年节省": annual_saving
        }

    # ==================== A3: 设备运行优化相关方法 ====================

    async def calc_equipment_load_rate(self, equipment_type: str, start_date: date, end_date: date) -> Decimal:
        """
        计算设备平均负荷率

        数据源: EnergyHourly 表 + PowerDevice 表
        公式: AVG(avg_power / rated_power) × 100

        参数:
        - equipment_type: "HVAC", "PUMP", "UPS", etc.
        - start_date: 统计起始日期
        - end_date: 统计结束日期

        返回: 负荷率 (%)
        """
        stmt = select(
            func.avg(EnergyHourly.avg_power / PowerDevice.rated_power * 100)
        ).select_from(EnergyHourly).join(
            PowerDevice,
            EnergyHourly.device_id == PowerDevice.id
        ).where(
            PowerDevice.device_type == equipment_type,
            PowerDevice.is_enabled == True,
            EnergyHourly.stat_time >= start_date,
            EnergyHourly.stat_time <= end_date,
            PowerDevice.rated_power > 0  # 避免除零
        )

        result = await self.db.execute(stmt)
        value = result.scalar()
        return Decimal(str(value)).quantize(Decimal('0.01')) if value else Decimal('0')

    async def calc_equipment_optimization_potential(self, equipment_type: str) -> Dict[str, Decimal]:
        """
        计算设备优化潜力

        业务规则:
        - 空压机: 负荷率 < 70% 时，优化潜力 = (70% - 实际负荷率) × 额定功率 × 运行时间
        - 循环水泵: 温度调节可节省 20-30%
        - 热处理炉: 批次优化可节省 10-15%

        返回:
        {
            "当前功率": Decimal,     # kW
            "优化后功率": Decimal,   # kW
            "节省功率": Decimal,     # kW
            "年运行小时": Decimal,
            "年节省电量": Decimal,   # kWh
            "年节省金额": Decimal    # 万元
        }
        """
        stmt = select(
            func.avg(PowerDevice.rated_power).label('avg_rated_power'),
            func.avg(PowerDevice.avg_load_rate).label('avg_load_rate'),
            func.count(PowerDevice.id).label('device_count')
        ).where(
            PowerDevice.device_type == equipment_type,
            PowerDevice.is_enabled == True
        )

        result = await self.db.execute(stmt)
        device_stats = result.first()

        if not device_stats or not device_stats.avg_rated_power:
            return {
                "当前功率": Decimal('0'),
                "优化后功率": Decimal('0'),
                "节省功率": Decimal('0'),
                "年运行小时": Decimal('0'),
                "年节省电量": Decimal('0'),
                "年节省金额": Decimal('0')
            }

        avg_rated_power = Decimal(str(device_stats.avg_rated_power))
        current_load_rate = Decimal(str(device_stats.avg_load_rate)) if device_stats.avg_load_rate else Decimal('70')
        device_count = device_stats.device_count

        # 当前功率
        current_power = (avg_rated_power * current_load_rate / Decimal('100')).quantize(Decimal('0.01'))

        # 根据设备类型设置优化潜力
        optimization_ratio = Decimal('0')
        if equipment_type == 'HVAC':
            optimization_ratio = Decimal('0.25')  # 25% 优化潜力
        elif equipment_type == 'PUMP':
            optimization_ratio = Decimal('0.20')  # 20% 优化潜力
        elif equipment_type in ['UPS', 'IT_SERVER']:
            optimization_ratio = Decimal('0.10')  # 10% 优化潜力

        # 优化后功率
        optimized_power = (current_power * (Decimal('1') - optimization_ratio)).quantize(Decimal('0.01'))
        saved_power = current_power - optimized_power

        # 年运行小时 (假设 6000 小时/年)
        annual_hours = Decimal('6000')

        # 年节省电量
        annual_energy_saving = (saved_power * annual_hours * Decimal(str(device_count))).quantize(Decimal('0.01'))

        # 年节省金额 (假设平均电价 0.436 元/kWh)
        avg_price = Decimal('0.436')
        annual_cost_saving = (annual_energy_saving * avg_price / Decimal('10000')).quantize(Decimal('0.01'))

        return {
            "当前功率": current_power,
            "优化后功率": optimized_power,
            "节省功率": saved_power,
            "年运行小时": annual_hours,
            "年节省电量": annual_energy_saving,
            "年节省金额": annual_cost_saving
        }

    # ==================== A4: VPP 需求响应相关方法 ====================

    async def calc_vpp_response_potential(self) -> Dict[str, Any]:
        """
        计算 VPP 需求响应潜力

        分级资源:
        - Ⅰ级快速响应: 照明、空调 (响应时间 ≤ 1 分钟)
        - Ⅱ级常规响应: 空压机、循环水泵 (响应时间 ≤ 10 分钟)
        - Ⅲ级计划响应: 热处理生产批次调整 (响应时间 ≥ 4 小时)

        返回:
        {
            "Ⅰ级资源": {"容量": Decimal, "年响应次数": int, "年收益": Decimal},
            "Ⅱ级资源": {"容量": Decimal, "年响应次数": int, "年收益": Decimal},
            "Ⅲ级资源": {"容量": Decimal, "年响应次数": int, "年收益": Decimal},
            "总容量": Decimal,
            "总年收益": Decimal
        }
        """
        # Ⅰ级快速响应 (响应时间 ≤ 5 分钟)
        stmt = select(
            func.sum(PowerDevice.rated_power * DeviceShiftConfig.shiftable_power_ratio)
        ).select_from(PowerDevice).join(
            DeviceShiftConfig,
            PowerDevice.id == DeviceShiftConfig.device_id
        ).where(
            DeviceShiftConfig.is_shiftable == True,
            DeviceShiftConfig.shift_notice_time <= 5,
            PowerDevice.is_enabled == True
        )
        result = await self.db.execute(stmt)
        level1_capacity_result = result.scalar()
        level1_capacity = Decimal(str(level1_capacity_result)) if level1_capacity_result else Decimal('0')

        # Ⅱ级常规响应 (响应时间 ≤ 15 分钟)
        stmt = select(
            func.sum(PowerDevice.rated_power * DeviceShiftConfig.shiftable_power_ratio)
        ).select_from(PowerDevice).join(
            DeviceShiftConfig,
            PowerDevice.id == DeviceShiftConfig.device_id
        ).where(
            DeviceShiftConfig.is_shiftable == True,
            DeviceShiftConfig.shift_notice_time > 5,
            DeviceShiftConfig.shift_notice_time <= 15,
            PowerDevice.is_enabled == True
        )
        result = await self.db.execute(stmt)
        level2_capacity_result = result.scalar()
        level2_capacity = Decimal(str(level2_capacity_result)) if level2_capacity_result else Decimal('0')

        # Ⅲ级计划响应 (响应时间 > 240 分钟)
        stmt = select(
            func.sum(PowerDevice.rated_power * DeviceShiftConfig.shiftable_power_ratio)
        ).select_from(PowerDevice).join(
            DeviceShiftConfig,
            PowerDevice.id == DeviceShiftConfig.device_id
        ).where(
            DeviceShiftConfig.is_shiftable == True,
            DeviceShiftConfig.shift_notice_time > 240,
            PowerDevice.is_enabled == True
        )
        result = await self.db.execute(stmt)
        level3_capacity_result = result.scalar()
        level3_capacity = Decimal(str(level3_capacity_result)) if level3_capacity_result else Decimal('0')

        # 响应次数和补偿标准 (基于市场数据)
        level1_response_count = 50  # 次/年
        level1_compensation = Decimal('600')  # 元/MW·次

        level2_response_count = 80  # 次/年
        level2_compensation = Decimal('300')  # 元/MW·次

        level3_response_count = 100  # 次/年
        level3_compensation = Decimal('200')  # 元/MW·次

        # 计算收益 (容量单位转换为 MW)
        level1_revenue = (level1_capacity / Decimal('1000') * Decimal(str(level1_response_count)) * level1_compensation / Decimal('10000')).quantize(Decimal('0.01'))
        level2_revenue = (level2_capacity / Decimal('1000') * Decimal(str(level2_response_count)) * level2_compensation / Decimal('10000')).quantize(Decimal('0.01'))
        level3_revenue = (level3_capacity / Decimal('1000') * Decimal(str(level3_response_count)) * level3_compensation / Decimal('10000')).quantize(Decimal('0.01'))

        total_capacity = level1_capacity + level2_capacity + level3_capacity
        total_revenue = level1_revenue + level2_revenue + level3_revenue

        return {
            "Ⅰ级资源": {
                "容量": level1_capacity.quantize(Decimal('0.01')),
                "年响应次数": level1_response_count,
                "年收益": level1_revenue
            },
            "Ⅱ级资源": {
                "容量": level2_capacity.quantize(Decimal('0.01')),
                "年响应次数": level2_response_count,
                "年收益": level2_revenue
            },
            "Ⅲ级资源": {
                "容量": level3_capacity.quantize(Decimal('0.01')),
                "年响应次数": level3_response_count,
                "年收益": level3_revenue
            },
            "总容量": total_capacity.quantize(Decimal('0.01')),
            "总年收益": total_revenue
        }

    # ==================== A5: 负荷调度优化相关方法 ====================

    async def calc_load_curve_analysis(self, analysis_date: date) -> Dict[str, Any]:
        """
        分析负荷曲线特征

        计算指标:
        - 峰谷差 = 最大负荷 - 最小负荷
        - 负荷率 = 平均负荷 / 最大负荷 × 100%
        - 峰谷比 = 最大负荷 / 最小负荷

        返回:
        {
            "最大负荷": Decimal,
            "最小负荷": Decimal,
            "平均负荷": Decimal,
            "峰谷差": Decimal,
            "负荷率": Decimal,
            "峰谷比": Decimal
        }
        """
        stmt = select(
            func.max(PowerCurveData.active_power).label('max_power'),
            func.min(PowerCurveData.active_power).label('min_power'),
            func.avg(PowerCurveData.active_power).label('avg_power')
        ).where(
            func.date(PowerCurveData.timestamp) == analysis_date
        )

        result = await self.db.execute(stmt)
        stats = result.first()

        if not stats or not stats.max_power:
            return {
                "最大负荷": Decimal('0'),
                "最小负荷": Decimal('0'),
                "平均负荷": Decimal('0'),
                "峰谷差": Decimal('0'),
                "负荷率": Decimal('0'),
                "峰谷比": Decimal('0')
            }

        max_load = Decimal(str(stats.max_power))
        min_load = Decimal(str(stats.min_power)) if stats.min_power else Decimal('0')
        avg_load = Decimal(str(stats.avg_power)) if stats.avg_power else Decimal('0')

        # 峰谷差
        peak_valley_diff = max_load - min_load

        # 负荷率
        load_rate = (avg_load / max_load * Decimal('100')).quantize(Decimal('0.01')) if max_load > 0 else Decimal('0')

        # 峰谷比
        peak_valley_ratio = (max_load / min_load).quantize(Decimal('0.01')) if min_load > 0 else Decimal('0')

        return {
            "最大负荷": max_load.quantize(Decimal('0.01')),
            "最小负荷": min_load.quantize(Decimal('0.01')),
            "平均负荷": avg_load.quantize(Decimal('0.01')),
            "峰谷差": peak_valley_diff.quantize(Decimal('0.01')),
            "负荷率": load_rate,
            "峰谷比": peak_valley_ratio
        }

    # ==================== B1: 设备改造升级相关方法 ====================

    async def calc_equipment_efficiency_benchmark(self, equipment_type: str) -> Dict[str, Any]:
        """
        设备能效对标分析

        对比:
        - 当前能效水平 vs 行业先进水平
        - 计算改造收益

        返回:
        {
            "当前能效": Decimal,
            "行业先进能效": Decimal,
            "能效差距": Decimal,
            "改造投资": Decimal,
            "年节省电量": Decimal,
            "年节省金额": Decimal,
            "投资回收期": Decimal
        }
        """
        # 获取设备当前能效
        stmt = select(func.avg(PowerDevice.efficiency)).where(
            PowerDevice.device_type == equipment_type,
            PowerDevice.is_enabled == True
        )
        result = await self.db.execute(stmt)
        current_efficiency_result = result.scalar()
        current_efficiency = Decimal(str(current_efficiency_result)) if current_efficiency_result else Decimal('90')

        # 行业先进能效水平 (基于设备类型)
        industry_benchmarks = {
            'UPS': Decimal('98'),
            'HVAC': Decimal('95'),
            'PUMP': Decimal('92'),
            'IT_SERVER': Decimal('96'),
            'LIGHTING': Decimal('90')
        }
        industry_efficiency = industry_benchmarks.get(equipment_type, Decimal('95'))

        # 能效差距
        efficiency_gap = industry_efficiency - current_efficiency

        # 获取设备额定功率和年运行时间
        stmt = select(
            func.sum(PowerDevice.rated_power).label('total_rated_power'),
            func.count(PowerDevice.id).label('device_count')
        ).where(
            PowerDevice.device_type == equipment_type,
            PowerDevice.is_enabled == True
        )
        result = await self.db.execute(stmt)
        device_stats = result.first()

        if not device_stats or not device_stats.total_rated_power:
            total_rated_power = Decimal('0')
            device_count = 0
        else:
            total_rated_power = Decimal(str(device_stats.total_rated_power))
            device_count = device_stats.device_count

        # 年运行时间 (假设 6000 小时)
        annual_hours = Decimal('6000')

        # 计算年节省电量
        # 节省电量 = 额定功率 × 运行时间 × (1/当前效率 - 1/行业先进效率)
        if current_efficiency > 0 and industry_efficiency > 0:
            energy_saving = (
                total_rated_power * annual_hours *
                (Decimal('1') / current_efficiency - Decimal('1') / industry_efficiency) *
                Decimal('100')
            ).quantize(Decimal('0.01'))
        else:
            energy_saving = Decimal('0')

        # 年节省金额 (假设平均电价 0.436 元/kWh)
        avg_price = Decimal('0.436')
        cost_saving = (energy_saving * avg_price / Decimal('10000')).quantize(Decimal('0.01'))

        # 改造投资估算 (基于设备类型和功率)
        investment_per_kw = Decimal('300')  # 元/kW
        total_investment = (total_rated_power * investment_per_kw / Decimal('10000')).quantize(Decimal('0.01'))

        # 投资回收期 (年)
        payback_period = (total_investment / cost_saving).quantize(Decimal('0.1')) if cost_saving > 0 else Decimal('0')

        return {
            "当前能效": current_efficiency.quantize(Decimal('0.01')),
            "行业先进能效": industry_efficiency,
            "能效差距": efficiency_gap.quantize(Decimal('0.01')),
            "改造投资": total_investment,
            "年节省电量": energy_saving,
            "年节省金额": cost_saving,
            "投资回收期": payback_period
        }

    # ==================== 辅助方法 ====================

    async def _get_electricity_price(self, time_slot: str) -> Decimal:
        """
        获取电价（尖峰/高峰/平段/低谷/深谷）

        参数:
            time_slot: 时段类型 "sharp"/"peak"/"normal"/"valley"/"deep_valley"

        返回:
            电价 (元/kWh)
        """
        stmt = select(ElectricityPricing).where(
            ElectricityPricing.period_type == time_slot,
            ElectricityPricing.is_enabled == True
        ).limit(1)

        result = await self.db.execute(stmt)
        pricing = result.scalar_one_or_none()

        if pricing:
            return Decimal(str(pricing.price))

        # 默认电价
        default_prices = {
            'sharp': Decimal('1.1'),
            'peak': Decimal('0.68'),
            'normal': Decimal('0.425'),
            'valley': Decimal('0.111'),
            'deep_valley': Decimal('0.08')
        }
        return default_prices.get(time_slot, Decimal('0.436'))

    def _get_working_days_in_period(self, start: date, end: date) -> int:
        """
        计算期间工作日数量

        参数:
            start: 起始日期
            end: 结束日期

        返回:
            工作日数量
        """
        total_days = (end - start).days + 1
        # 简化处理：假设工作日占比 5/7
        working_days = int(total_days * 5 / 7)
        return working_days
