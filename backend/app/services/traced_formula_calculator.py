"""
带追溯功能的公式计算器
在 FormulaCalculator 基础上增加数据追溯链支持

每次计算自动生成追溯记录，记录:
- 数据来源 (源表、字段)
- 计算公式
- 中间结果
- 追溯树结构
"""
import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal
from sqlalchemy.orm import Session

from .formula_calculator import FormulaCalculator
from ..models.trace import TraceRecord, MappingType, AggregationType


class TracedValue:
    """带追溯信息的值"""

    def __init__(self, value: Decimal, trace: TraceRecord, unit: str = ""):
        self.value = value
        self.trace = trace
        self.unit = unit

    @property
    def trace_id(self) -> str:
        return self.trace.trace_id

    def __repr__(self):
        return f"TracedValue({self.value}, {self.unit}, trace={self.trace_id})"


class TracedFormulaCalculator(FormulaCalculator):
    """
    带追溯功能的公式计算器

    继承 FormulaCalculator，重写每个计算方法:
    1. 调用父类方法获取计算结果
    2. 创建追溯记录
    3. 返回 TracedValue (包含值+追溯信息)
    """

    def __init__(self, db: Session, proposal_id: int = None, measure_id: int = None):
        super().__init__(db)
        self.proposal_id = proposal_id
        self.measure_id = measure_id
        self._traces: List[TraceRecord] = []
        self._trace_map: Dict[str, TraceRecord] = {}

    # ==================== 追溯ID生成 ====================

    @staticmethod
    def _gen_trace_id(prefix: str = "TR") -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        unique_part = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{date_str}-{unique_part}"

    @staticmethod
    def _format_value(value: Decimal, unit: str = "") -> str:
        v = float(value)
        if abs(v) >= 10000:
            formatted = f"{v:,.0f}"
        elif abs(v) >= 1:
            formatted = f"{v:,.2f}"
        else:
            formatted = f"{v:.4f}"
        return f"{formatted} {unit}" if unit else formatted

    # ==================== 追溯记录创建 ====================

    def _create_direct_trace(
        self,
        param_code: str,
        param_name: str,
        source_table: str,
        source_field: str,
        value: Decimal,
        value_unit: str = "",
        filter_condition: str = None,
        query_sql: str = None,
        parent_trace_id: str = None
    ) -> TraceRecord:
        """创建直接映射追溯记录"""
        trace_id = self._gen_trace_id()
        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=self.proposal_id,
            measure_id=self.measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.DIRECT.value,
            source_table=source_table,
            source_field=source_field,
            filter_condition=filter_condition,
            raw_value=value,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=0 if parent_trace_id is None else 1,
            query_sql=query_sql,
            calculated_at=datetime.now()
        )
        self.db.add(trace)
        self._traces.append(trace)
        self._trace_map[trace_id] = trace
        return trace

    def _create_aggregate_trace(
        self,
        param_code: str,
        param_name: str,
        source_table: str,
        source_field: str,
        aggregation_type: str,
        value: Decimal,
        value_unit: str = "",
        filter_condition: str = None,
        aggregation_params: Dict = None,
        time_range_start: datetime = None,
        time_range_end: datetime = None,
        query_sql: str = None,
        parent_trace_id: str = None
    ) -> TraceRecord:
        """创建聚合映射追溯记录"""
        trace_id = self._gen_trace_id()
        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=self.proposal_id,
            measure_id=self.measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.AGGREGATE.value,
            source_table=source_table,
            source_field=source_field,
            filter_condition=filter_condition,
            aggregation_type=aggregation_type,
            aggregation_params=aggregation_params,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            raw_value=value,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=0 if parent_trace_id is None else 1,
            query_sql=query_sql,
            calculated_at=datetime.now()
        )
        self.db.add(trace)
        self._traces.append(trace)
        self._trace_map[trace_id] = trace
        return trace

    def _create_composite_trace(
        self,
        param_code: str,
        param_name: str,
        formula: str,
        formula_display: str,
        child_traces: List[TraceRecord],
        value: Decimal,
        value_unit: str = "",
        parent_trace_id: str = None
    ) -> TraceRecord:
        """创建复合映射追溯记录"""
        trace_id = self._gen_trace_id()
        child_trace_ids = [t.trace_id for t in child_traces]
        max_child_depth = max([t.depth for t in child_traces], default=0)

        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=self.proposal_id,
            measure_id=self.measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.COMPOSITE.value,
            formula=formula,
            formula_display=formula_display,
            child_trace_ids=child_trace_ids,
            raw_value=value,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=max_child_depth + 1,
            calculated_at=datetime.now()
        )

        # 设置子节点的父ID
        for child in child_traces:
            if child.parent_trace_id is None:
                child.parent_trace_id = trace_id

        self.db.add(trace)
        self._traces.append(trace)
        self._trace_map[trace_id] = trace
        return trace

    # ==================== 带追溯的计算方法 ====================

    def traced_annual_energy(self, year: int) -> TracedValue:
        """带追溯的年用电量计算"""
        value = self.calc_annual_energy(year)
        trace = self._create_aggregate_trace(
            param_code="annual_energy",
            param_name="年用电量",
            source_table="energy_monthly",
            source_field="total_energy",
            aggregation_type="sum",
            value=value,
            value_unit="kWh",
            filter_condition=f"stat_year = {year}",
            query_sql=f"SELECT SUM(total_energy) FROM energy_monthly WHERE stat_year = {year}",
            time_range_start=datetime(year, 1, 1),
            time_range_end=datetime(year, 12, 31)
        )
        return TracedValue(value, trace, "kWh")

    def traced_max_demand(self, year: int, month: Optional[int] = None) -> TracedValue:
        """带追溯的最大需量计算"""
        value = self.calc_max_demand(year, month)
        filter_cond = f"stat_year = {year}"
        sql = f"SELECT MAX(max_demand) FROM demand_history WHERE stat_year = {year}"
        if month:
            filter_cond += f" AND stat_month = {month}"
            sql += f" AND stat_month = {month}"

        trace = self._create_aggregate_trace(
            param_code="max_demand",
            param_name="最大需量",
            source_table="demand_history",
            source_field="max_demand",
            aggregation_type="max",
            value=value,
            value_unit="kW",
            filter_condition=filter_cond,
            query_sql=sql,
            time_range_start=datetime(year, month or 1, 1),
            time_range_end=datetime(year, month or 12, 28)
        )
        return TracedValue(value, trace, "kW")

    def traced_average_load(self, year: int) -> TracedValue:
        """带追溯的平均负荷计算"""
        energy_tv = self.traced_annual_energy(year)
        value = self.calc_average_load(year)

        trace = self._create_composite_trace(
            param_code="avg_load",
            param_name="平均负荷",
            formula="{annual_energy} / 8760",
            formula_display=f"{energy_tv.value} / 8760 = {value}",
            child_traces=[energy_tv.trace],
            value=value,
            value_unit="kW"
        )
        return TracedValue(value, trace, "kW")

    def traced_load_factor(self, avg_load_tv: TracedValue, max_demand_tv: TracedValue) -> TracedValue:
        """带追溯的负荷率计算"""
        value = self.calc_load_factor(avg_load_tv.value, max_demand_tv.value)

        trace = self._create_composite_trace(
            param_code="load_factor",
            param_name="负荷率",
            formula="({avg_load} / {max_demand}) × 100",
            formula_display=f"({avg_load_tv.value} / {max_demand_tv.value}) × 100 = {value}%",
            child_traces=[avg_load_tv.trace, max_demand_tv.trace],
            value=value,
            value_unit="%"
        )
        return TracedValue(value, trace, "%")

    def traced_peak_valley_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """带追溯的峰谷电量数据"""
        data = self.calc_peak_valley_data(start_date, end_date)
        traces = {}

        # 为每个数据项创建追溯记录
        for key, value in data.items():
            if "电量" in key:
                param_code = key.replace("电量", "_energy")
                trace = self._create_aggregate_trace(
                    param_code=f"pv_{param_code}",
                    param_name=key,
                    source_table="energy_daily",
                    source_field="peak_energy/normal_energy/valley_energy",
                    aggregation_type="sum",
                    value=value,
                    value_unit="kWh",
                    filter_condition=f"stat_date BETWEEN '{start_date}' AND '{end_date}'",
                    time_range_start=datetime.combine(start_date, datetime.min.time()),
                    time_range_end=datetime.combine(end_date, datetime.max.time())
                )
                traces[key] = trace

        data["_traces"] = traces
        return data

    def traced_demand_control_data(self, meter_point_id: Optional[int] = None) -> Dict[str, Any]:
        """带追溯的需量控制数据"""
        data = self.calc_demand_control_data(meter_point_id)
        traces = {}

        # 当前申报需量 - 直接映射
        t_declared = self._create_direct_trace(
            param_code="declared_demand",
            param_name="当前申报需量",
            source_table="meter_points",
            source_field="declared_demand",
            value=data["当前申报需量"],
            value_unit="kW",
            filter_condition=f"meter_point_id = {meter_point_id}" if meter_point_id else "first enabled"
        )
        traces["当前申报需量"] = t_declared

        # 95分位需量 - 聚合映射
        t_95th = self._create_aggregate_trace(
            param_code="demand_95th",
            param_name="历史95分位需量",
            source_table="demand_history",
            source_field="demand_95th",
            aggregation_type="percentile",
            aggregation_params={"percentile": 95},
            value=data["历史95分位"],
            value_unit="kW"
        )
        traces["历史95分位"] = t_95th

        # 需量电价 - 直接映射
        t_price = self._create_direct_trace(
            param_code="demand_price",
            param_name="需量电价",
            source_table="pricing_configs",
            source_field="demand_price",
            value=data["需量电价"],
            value_unit="元/kW·月"
        )
        traces["需量电价"] = t_price

        # 建议申报需量 - 复合映射
        safety_factor = Decimal("1.05")
        t_recommended = self._create_composite_trace(
            param_code="recommended_demand",
            param_name="建议申报需量",
            formula="{demand_95th} × {safety_factor}",
            formula_display=f"{data['历史95分位']} × {safety_factor} = {data['建议申报需量']}",
            child_traces=[t_95th],
            value=data["建议申报需量"],
            value_unit="kW"
        )
        traces["建议申报需量"] = t_recommended

        # 年节省 - 复合映射
        if data["年节省"] > 0:
            t_saving = self._create_composite_trace(
                param_code="demand_annual_saving",
                param_name="需量优化年节省",
                formula="({declared_demand} - {recommended_demand}) × {demand_price} × 12 / 10000",
                formula_display=(
                    f"({data['当前申报需量']} - {data['建议申报需量']}) × "
                    f"{data['需量电价']} × 12 / 10000 = {data['年节省']} 万元"
                ),
                child_traces=[t_declared, t_recommended, t_price],
                value=data["年节省"],
                value_unit="万元/年"
            )
            traces["年节省"] = t_saving

        data["_traces"] = traces
        return data

    def traced_peak_shift_benefit(
        self,
        shiftable_power: Decimal,
        shift_hours: Decimal,
        sharp_price: Decimal,
        valley_price: Decimal,
        working_days: int = 300,
        shiftable_power_trace: TraceRecord = None
    ) -> Dict[str, Any]:
        """带追溯的峰谷转移收益计算"""
        data = self.calc_peak_shift_benefit(
            shiftable_power, shift_hours, sharp_price, valley_price, working_days
        )
        traces = {}

        # 可转移功率追溯 (如果未传入，则创建新追溯)
        if shiftable_power_trace is None:
            shiftable_power_trace = self._create_aggregate_trace(
                param_code="shiftable_power",
                param_name="可转移功率",
                source_table="device_shift_configs",
                source_field="shiftable_power_ratio × rated_power",
                aggregation_type="sum",
                value=shiftable_power,
                value_unit="kW"
            )
        traces["可转移功率"] = shiftable_power_trace

        # 电价追溯
        t_sharp = self._create_direct_trace(
            param_code="sharp_price",
            param_name="尖峰电价",
            source_table="electricity_pricing",
            source_field="price",
            value=sharp_price,
            value_unit="元/kWh",
            filter_condition="period_type = 'sharp'"
        )
        t_valley = self._create_direct_trace(
            param_code="valley_price",
            param_name="低谷电价",
            source_table="electricity_pricing",
            source_field="price",
            value=valley_price,
            value_unit="元/kWh",
            filter_condition="period_type = 'valley'"
        )

        # 价差 - 复合
        price_diff = sharp_price - valley_price
        t_price_diff = self._create_composite_trace(
            param_code="price_diff",
            param_name="峰谷价差",
            formula="{sharp_price} - {valley_price}",
            formula_display=f"{sharp_price} - {valley_price} = {price_diff}",
            child_traces=[t_sharp, t_valley],
            value=price_diff,
            value_unit="元/kWh"
        )
        traces["峰谷价差"] = t_price_diff

        # 年收益 - 复合
        t_annual = self._create_composite_trace(
            param_code="peak_valley_annual_saving",
            param_name="峰谷套利年收益",
            formula="{shiftable_power} × {shift_hours} × {price_diff} × {working_days} / 10000",
            formula_display=(
                f"{shiftable_power} × {shift_hours} × {price_diff} × "
                f"{working_days} / 10000 = {data['年收益']} 万元"
            ),
            child_traces=[shiftable_power_trace, t_price_diff],
            value=data["年收益"],
            value_unit="万元/年"
        )
        traces["年收益"] = t_annual

        data["_traces"] = traces
        return data

    def traced_vpp_response_potential(self) -> Dict[str, Any]:
        """带追溯的VPP需求响应潜力计算"""
        data = self.calc_vpp_response_potential()
        traces = {}

        # 为每个资源级别创建追溯记录
        for level_name, level_key in [("Ⅰ级资源", "Ⅰ级资源"), ("Ⅱ级资源", "Ⅱ级资源"), ("Ⅲ级资源", "Ⅲ级资源")]:
            level_data = data[level_key]
            capacity = level_data["容量"]
            annual_benefit = level_data["年收益"]

            t_capacity = self._create_aggregate_trace(
                param_code=f"vpp_{level_key}_capacity",
                param_name=f"VPP{level_name}容量",
                source_table="load_regulation_configs",
                source_field="adjustable_capacity",
                aggregation_type="sum",
                value=capacity,
                value_unit="kW",
                filter_condition=f"vpp_level = '{level_key[:2]}'"
            )

            t_benefit = self._create_composite_trace(
                param_code=f"vpp_{level_key}_benefit",
                param_name=f"VPP{level_name}年收益",
                formula=f"{{capacity}} × {{rate}} × {{times}} / 10000",
                formula_display=f"{capacity}kW × 补贴标准 × 年响应次数 = {annual_benefit}万元",
                child_traces=[t_capacity],
                value=annual_benefit,
                value_unit="万元/年"
            )
            traces[f"{level_key}_容量"] = t_capacity
            traces[f"{level_key}_收益"] = t_benefit

        # 总收益追溯
        total_benefit = data["总年收益"]
        child_benefit_traces = [traces[f"{k}_收益"] for k in ["Ⅰ级资源", "Ⅱ级资源", "Ⅲ级资源"]]
        t_total = self._create_composite_trace(
            param_code="vpp_total_benefit",
            param_name="VPP总年收益",
            formula="{Ⅰ级收益} + {Ⅱ级收益} + {Ⅲ级收益}",
            formula_display=f"{data['Ⅰ级资源']['年收益']} + {data['Ⅱ级资源']['年收益']} + {data['Ⅲ级资源']['年收益']} = {total_benefit}万元",
            child_traces=child_benefit_traces,
            value=total_benefit,
            value_unit="万元/年"
        )
        traces["总收益"] = t_total

        data["_traces"] = traces
        return data

    def traced_load_curve_analysis(self, analysis_date: date) -> Dict[str, Any]:
        """带追溯的负荷曲线分析"""
        data = self.calc_load_curve_analysis(analysis_date)
        traces = {}

        # 最大负荷追溯
        t_max = self._create_aggregate_trace(
            param_code="max_load",
            param_name="最大负荷",
            source_table="power_curve_data",
            source_field="power",
            aggregation_type="max",
            value=data["最大负荷"],
            value_unit="kW",
            filter_condition=f"curve_date = '{analysis_date}'"
        )
        traces["最大负荷"] = t_max

        # 最小负荷追溯
        t_min = self._create_aggregate_trace(
            param_code="min_load",
            param_name="最小负荷",
            source_table="power_curve_data",
            source_field="power",
            aggregation_type="min",
            value=data["最小负荷"],
            value_unit="kW",
            filter_condition=f"curve_date = '{analysis_date}'"
        )
        traces["最小负荷"] = t_min

        # 平均负荷追溯
        t_avg = self._create_aggregate_trace(
            param_code="avg_load",
            param_name="平均负荷",
            source_table="power_curve_data",
            source_field="power",
            aggregation_type="avg",
            value=data["平均负荷"],
            value_unit="kW",
            filter_condition=f"curve_date = '{analysis_date}'"
        )
        traces["平均负荷"] = t_avg

        # 峰谷差追溯
        t_diff = self._create_composite_trace(
            param_code="peak_valley_diff",
            param_name="峰谷差",
            formula="{最大负荷} - {最小负荷}",
            formula_display=f"{data['最大负荷']} - {data['最小负荷']} = {data['峰谷差']}",
            child_traces=[t_max, t_min],
            value=data["峰谷差"],
            value_unit="kW"
        )
        traces["峰谷差"] = t_diff

        # 负荷率追溯
        t_load_rate = self._create_composite_trace(
            param_code="load_rate",
            param_name="负荷率",
            formula="({平均负荷} / {最大负荷}) × 100",
            formula_display=f"({data['平均负荷']} / {data['最大负荷']}) × 100 = {data['负荷率']}%",
            child_traces=[t_avg, t_max],
            value=data["负荷率"],
            value_unit="%"
        )
        traces["负荷率"] = t_load_rate

        # 峰谷比追溯
        t_ratio = self._create_composite_trace(
            param_code="peak_valley_ratio",
            param_name="峰谷比",
            formula="{最大负荷} / {最小负荷}",
            formula_display=f"{data['最大负荷']} / {data['最小负荷']} = {data['峰谷比']}",
            child_traces=[t_max, t_min],
            value=data["峰谷比"],
            value_unit=""
        )
        traces["峰谷比"] = t_ratio

        data["_traces"] = traces
        return data

    def traced_equipment_load_rate(self, equipment_type: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """带追溯的设备负荷率计算"""
        value = self.calc_equipment_load_rate(equipment_type, start_date, end_date)

        trace = self._create_aggregate_trace(
            param_code=f"equipment_{equipment_type.lower()}_load_rate",
            param_name=f"{equipment_type}设备负荷率",
            source_table="device_load_profiles",
            source_field="load_rate",
            aggregation_type="avg",
            value=value,
            value_unit="%",
            filter_condition=f"device_type = '{equipment_type}'",
            time_range_start=datetime.combine(start_date, datetime.min.time()),
            time_range_end=datetime.combine(end_date, datetime.max.time())
        )

        return {
            "负荷率": value,
            "_traces": {"设备负荷率": trace}
        }

    def traced_equipment_efficiency_benchmark(self, equipment_type: str) -> Dict[str, Any]:
        """带追溯的设备能效对标"""
        data = self.calc_equipment_efficiency_benchmark(equipment_type)
        traces = {}

        # 当前能效追溯
        t_current = self._create_aggregate_trace(
            param_code=f"equipment_{equipment_type.lower()}_efficiency",
            param_name=f"{equipment_type}当前能效",
            source_table="power_devices",
            source_field="efficiency_rating",
            aggregation_type="avg",
            value=data["当前能效"],
            value_unit="%",
            filter_condition=f"device_type = '{equipment_type}'"
        )
        traces["当前能效"] = t_current

        # 行业先进能效 (直接映射)
        t_benchmark = self._create_direct_trace(
            param_code=f"equipment_{equipment_type.lower()}_benchmark",
            param_name=f"{equipment_type}行业先进能效",
            source_table="efficiency_benchmarks",
            source_field="benchmark_value",
            value=data["行业先进能效"],
            value_unit="%",
            filter_condition=f"device_type = '{equipment_type}'"
        )
        traces["行业先进能效"] = t_benchmark

        # 能效差距 (复合映射)
        t_gap = self._create_composite_trace(
            param_code=f"equipment_{equipment_type.lower()}_gap",
            param_name=f"{equipment_type}能效差距",
            formula="{行业先进能效} - {当前能效}",
            formula_display=f"{data['行业先进能效']} - {data['当前能效']} = {data['能效差距']}",
            child_traces=[t_benchmark, t_current],
            value=data["能效差距"],
            value_unit="%"
        )
        traces["能效差距"] = t_gap

        data["_traces"] = traces
        return data

    def get_trace_summary(self) -> Dict[str, Any]:
        """获取所有追溯记录的汇总信息"""
        data_sources = set()
        root_trace_ids = []

        for trace in self._traces:
            if trace.source_table:
                data_sources.add(trace.source_table)
            if trace.parent_trace_id is None:
                root_trace_ids.append(trace.trace_id)

        # 获取时间范围
        time_starts = [t.time_range_start for t in self._traces if t.time_range_start]
        time_ends = [t.time_range_end for t in self._traces if t.time_range_end]

        return {
            "total_traces": len(self._traces),
            "data_sources": list(data_sources),
            "time_range": {
                "start": min(time_starts).isoformat() if time_starts else None,
                "end": max(time_ends).isoformat() if time_ends else None,
            },
            "root_trace_ids": root_trace_ids
        }

    def get_measure_trace_data(self, traces_dict: Dict[str, TraceRecord]) -> Dict[str, Any]:
        """
        生成措施追溯数据 (存入 ProposalMeasure.trace_data)

        参数:
            traces_dict: 参数名 -> TraceRecord 映射
        """
        # 找到根追溯
        root_traces = [t for t in traces_dict.values() if t.parent_trace_id is None]
        root_trace_id = root_traces[0].trace_id if root_traces else None

        # 构建 traces 映射
        trace_ids = {name: trace.trace_id for name, trace in traces_dict.items()}

        # 构建计算步骤
        steps = []
        for i, (name, trace) in enumerate(traces_dict.items(), 1):
            step = {
                "step": i,
                "description": f"{trace.param_name}: {trace.formatted_value}",
                "trace_id": trace.trace_id,
            }
            if trace.formula:
                step["formula"] = trace.formula
            if trace.raw_value is not None:
                step["result"] = float(trace.raw_value)
            step["unit"] = trace.value_unit or ""
            steps.append(step)

        return {
            "root_trace_id": root_trace_id,
            "traces": trace_ids,
            "calculation_steps": steps
        }

    @property
    def all_traces(self) -> List[TraceRecord]:
        """获取所有追溯记录"""
        return self._traces
