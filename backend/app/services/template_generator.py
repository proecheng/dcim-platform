"""
模板生成器服务
从6种模板生成节能方案，每个方案包含多个独立可选的措施

V3.1: 集成数据追溯链支持 (专利S1)
V3.2: 异步SQLAlchemy 2.0兼容版本
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from decimal import Decimal

from ..models.energy import EnergySavingProposal, ProposalMeasure
from .formula_calculator import FormulaCalculator
from .traced_formula_calculator import TracedFormulaCalculator


class TemplateGenerator:
    """模板生成器 - 从6种模板生成节能方案"""

    # 模板配置
    TEMPLATE_CONFIGS = {
        "A1": {
            "name": "峰谷套利优化方案",
            "type": "A",
            "description": "通过调整用电时段，避开尖峰高峰时段，降低电费"
        },
        "A2": {
            "name": "需量控制方案",
            "type": "A",
            "description": "优化申报需量，避免偶发性高峰，降低基本电费"
        },
        "A3": {
            "name": "设备运行优化方案",
            "type": "A",
            "description": "优化设备运行参数，提高运行效率，降低能耗"
        },
        "A4": {
            "name": "VPP需求响应方案",
            "type": "A",
            "description": "参与虚拟电厂需求响应市场，获得补贴收益"
        },
        "A5": {
            "name": "负荷调度优化方案",
            "type": "A",
            "description": "优化负荷曲线，提高负荷率，降低峰谷差"
        },
        "B1": {
            "name": "设备改造升级方案",
            "type": "B",
            "description": "改造老旧设备，提升能效水平"
        }
    }

    def __init__(self, db: AsyncSession, enable_trace: bool = True):
        self.db = db
        self.enable_trace = enable_trace
        self.calculator = FormulaCalculator(db)
        self._traced_calculator = None

    def _get_traced_calculator(self, proposal_id: int = None, measure_id: int = None) -> TracedFormulaCalculator:
        """获取带追溯功能的计算器"""
        if self._traced_calculator is None or self._traced_calculator.proposal_id != proposal_id:
            self._traced_calculator = TracedFormulaCalculator(
                self.db, proposal_id=proposal_id, measure_id=measure_id
            )
        else:
            self._traced_calculator.measure_id = measure_id
        return self._traced_calculator

    async def generate_proposal(
        self,
        template_id: str,
        analysis_days: int = 30
    ) -> EnergySavingProposal:
        """
        生成方案的主入口

        参数:
            template_id: 模板ID (A1/A2/A3/A4/A5/B1)
            analysis_days: 分析天数

        返回:
            EnergySavingProposal 对象（包含多个措施）
        """
        if template_id not in self.TEMPLATE_CONFIGS:
            raise ValueError(f"无效的模板ID: {template_id}")

        # 根据模板ID调用对应的生成方法
        generator_map = {
            "A1": self.generate_peak_valley_proposal,
            "A2": self.generate_demand_control_proposal,
            "A3": self.generate_equipment_optimization_proposal,
            "A4": self.generate_vpp_response_proposal,
            "A5": self.generate_load_scheduling_proposal,
            "B1": self.generate_equipment_upgrade_proposal
        }

        proposal = await generator_map[template_id](analysis_days)

        # V3.1: 写入追溯汇总信息
        if self.enable_trace and self._traced_calculator:
            proposal.trace_summary = self._traced_calculator.get_trace_summary()
            await self.db.flush()

        return proposal

    # ==================== A1: 峰谷套利优化方案 ====================

    async def generate_peak_valley_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成A1-峰谷套利优化方案

        方案结构:
        - 措施1: 热处理预热工序时段调整
        - 措施2: 辅助设备错峰运行
        - 措施3: 空压机储气罐充气策略优化

        每个措施包含:
        - regulation_object: 调节对象
        - current_state: 当前状态（尖峰用电量、时段等）
        - target_state: 目标状态（调整后时段、电量）
        - calculation_formula: 计算公式和步骤
        - annual_benefit: 年收益
        """
        # 1. 计算当前峰谷数据 (使用带追溯的计算器)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        if self.enable_trace:
            tc = self._get_traced_calculator()
            peak_valley_data = await tc.traced_peak_valley_data(start_date.date(), end_date.date())
        else:
            peak_valley_data = await self.calculator.calc_peak_valley_data(start_date.date(), end_date.date())

        # 2. 创建方案对象
        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("A1"),
            proposal_type="A",
            template_id="A1",
            template_name=self.TEMPLATE_CONFIGS["A1"]["name"],
            current_situation={
                "尖峰电量": float(peak_valley_data["尖峰电量"]),
                "尖峰占比": float(peak_valley_data["尖峰占比"]),
                "高峰电量": float(peak_valley_data["高峰电量"]),
                "高峰占比": float(peak_valley_data["高峰占比"]),
                "平段电量": float(peak_valley_data["平段电量"]),
                "平段占比": float(peak_valley_data["平段占比"]),
                "低谷电量": float(peak_valley_data["低谷电量"]),
                "低谷占比": float(peak_valley_data["低谷占比"]),
                "深谷电量": float(peak_valley_data["深谷电量"]),
                "深谷占比": float(peak_valley_data["深谷占比"]),
                "总电量": float(peak_valley_data["总电量"])
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 3. 生成措施列表
        measures = []

        # 措施1: 热处理预热工序时段调整
        measure1 = await self._generate_measure_heat_treatment_shift(proposal, analysis_days)
        measures.append(measure1)

        # 措施2: 辅助设备错峰运行
        measure2 = await self._generate_measure_auxiliary_equipment_shift(proposal, analysis_days)
        measures.append(measure2)

        # 措施3: 空压机储气罐充气策略优化
        measure3 = await self._generate_measure_compressor_optimization(proposal, analysis_days)
        measures.append(measure3)

        # 4. 计算总收益
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = Decimal("0")
        proposal.measures = measures

        return proposal

    async def _generate_measure_heat_treatment_shift(
        self,
        proposal: EnergySavingProposal,
        analysis_days: int
    ) -> ProposalMeasure:
        """生成措施1: 热处理预热工序时段调整"""

        # 参数设置
        shiftable_power = Decimal("2500")  # 可转移功率 2500kW
        shift_hours = Decimal("2")         # 每日转移2小时
        sharp_price = Decimal("1.1")       # 尖峰电价
        valley_price = Decimal("0.111")    # 低谷电价

        # 调用计算器 (带追溯)
        if self.enable_trace:
            tc = self._get_traced_calculator(proposal_id=None, measure_id=None)
            benefit = await tc.traced_peak_shift_benefit(
                shiftable_power, shift_hours, sharp_price, valley_price
            )
            measure_traces = benefit.get("_traces", {})
        else:
            benefit = await self.calculator.calc_peak_shift_benefit(
                shiftable_power, shift_hours, sharp_price, valley_price
            )
            measure_traces = {}

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="热处理生产线预热工序",
            regulation_description="将预热工序从尖峰时段(10:00-11:00, 13:00-14:00)调整至平段(11:00-13:00)",
            current_state={
                "预热时段": "10:00-11:00, 13:00-14:00（尖峰）",
                "预热功率": f"{shiftable_power} kW",
                "日耗电": f"{shiftable_power * shift_hours} kWh",
                "电价": f"{sharp_price} 元/kWh",
                "日电费": f"{float(shiftable_power * shift_hours * sharp_price)} 元"
            },
            target_state={
                "预热时段": "11:00-13:00（平段）",
                "预热功率": f"{shiftable_power} kW",
                "日耗电": f"{shiftable_power * shift_hours} kWh",
                "电价": f"{valley_price} 元/kWh",
                "日电费": f"{float(shiftable_power * shift_hours * valley_price)} 元"
            },
            calculation_formula=f"""
【计算步骤】
1. 日转移电量 = {shiftable_power} kW × {shift_hours} h = {benefit['日转移电量']} kWh
2. 价差 = {sharp_price} - {valley_price} = {sharp_price - valley_price} 元/kWh
3. 日收益 = {benefit['日转移电量']} kWh × {sharp_price - valley_price} 元/kWh = {benefit['日收益']} 元
4. 年收益 = {benefit['日收益']} 元 × 300天 = {benefit['年收益']} 万元
            """.strip(),
            calculation_basis=f"基于过去{analysis_days}天尖峰时段平均负荷数据，热处理预热工序功率约{shiftable_power}kW",
            annual_benefit=benefit["年收益"],
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and measure_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(measure_traces)

        return measure

    async def _generate_measure_auxiliary_equipment_shift(
        self,
        proposal: EnergySavingProposal,
        analysis_days: int
    ) -> ProposalMeasure:
        """生成措施2: 辅助设备错峰运行"""

        # 参数设置
        shiftable_power = Decimal("1200")  # 可转移功率 1200kW
        shift_hours = Decimal("3")         # 每日转移3小时
        peak_price = Decimal("0.68")       # 高峰电价
        flat_price = Decimal("0.425")      # 平段电价

        # 调用计算器 (带追溯)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            benefit = await tc.traced_peak_shift_benefit(
                shiftable_power, shift_hours, peak_price, flat_price
            )
            measure_traces = benefit.get("_traces", {})
        else:
            benefit = await self.calculator.calc_peak_shift_benefit(
                shiftable_power, shift_hours, peak_price, flat_price
            )
            measure_traces = {}

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="辅助生产设备（循环水泵、通风系统）",
            regulation_description="将部分辅助设备运行时段从高峰时段调整至平段运行",
            current_state={
                "运行时段": "8:00-11:00, 18:00-21:00（高峰）",
                "设备功率": f"{shiftable_power} kW",
                "日耗电": f"{shiftable_power * shift_hours} kWh",
                "电价": f"{peak_price} 元/kWh"
            },
            target_state={
                "运行时段": "11:00-14:00, 21:00-24:00（平段）",
                "设备功率": f"{shiftable_power} kW",
                "日耗电": f"{shiftable_power * shift_hours} kWh",
                "电价": f"{flat_price} 元/kWh"
            },
            calculation_formula=f"""
【计算步骤】
1. 日转移电量 = {shiftable_power} kW × {shift_hours} h = {benefit['日转移电量']} kWh
2. 价差 = {peak_price} - {flat_price} = {peak_price - flat_price} 元/kWh
3. 日收益 = {benefit['日转移电量']} kWh × {peak_price - flat_price} 元/kWh = {benefit['日收益']} 元
4. 年收益 = {benefit['日收益']} 元 × 300天 = {benefit['年收益']} 万元
            """.strip(),
            calculation_basis=f"基于过去{analysis_days}天高峰时段辅助设备运行数据",
            annual_benefit=benefit["年收益"],
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and measure_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(measure_traces)

        return measure

    async def _generate_measure_compressor_optimization(
        self,
        proposal: EnergySavingProposal,
        analysis_days: int
    ) -> ProposalMeasure:
        """生成措施3: 空压机储气罐充气策略优化"""

        # 参数设置
        shiftable_power = Decimal("800")   # 可转移功率 800kW
        shift_hours = Decimal("4")         # 每日转移4小时
        sharp_price = Decimal("1.1")       # 尖峰电价
        valley_price = Decimal("0.111")    # 低谷电价

        # 调用计算器 (带追溯)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            benefit = await tc.traced_peak_shift_benefit(
                shiftable_power, shift_hours, sharp_price, valley_price
            )
            measure_traces = benefit.get("_traces", {})
        else:
            benefit = await self.calculator.calc_peak_shift_benefit(
                shiftable_power, shift_hours, sharp_price, valley_price
            )
            measure_traces = {}

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="空压机系统储气罐",
            regulation_description="利用储气罐缓冲能力，在低谷时段提前充气，减少尖峰时段空压机启动",
            current_state={
                "充气策略": "随用随充（含尖峰时段）",
                "尖峰充气时长": f"{shift_hours} h/天",
                "充气功率": f"{shiftable_power} kW",
                "电价": f"{sharp_price} 元/kWh"
            },
            target_state={
                "充气策略": "低谷预充 + 平段补充",
                "低谷充气时长": f"{shift_hours} h/天",
                "充气功率": f"{shiftable_power} kW",
                "电价": f"{valley_price} 元/kWh"
            },
            calculation_formula=f"""
【计算步骤】
1. 日转移电量 = {shiftable_power} kW × {shift_hours} h = {benefit['日转移电量']} kWh
2. 价差 = {sharp_price} - {valley_price} = {sharp_price - valley_price} 元/kWh
3. 日收益 = {benefit['日转移电量']} kWh × {sharp_price - valley_price} 元/kWh = {benefit['日收益']} 元
4. 年收益 = {benefit['日收益']} 元 × 300天 = {benefit['年收益']} 万元

【技术说明】
- 现有储气罐容积可支持4小时缓冲
- 低谷时段(23:00-7:00)提前充气至满压
- 尖峰时段依靠储气罐供气，减少空压机启动
            """.strip(),
            calculation_basis=f"基于空压机系统运行数据和储气罐容积分析",
            annual_benefit=benefit["年收益"],
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and measure_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(measure_traces)

        return measure

    # ==================== A2: 需量控制方案 ====================

    async def generate_demand_control_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成A2-需量控制方案

        措施:
        - 措施1: 降低申报需量至合理水平
        - 措施2: 需量实时监控与预警
        - 措施3: 高峰时段负荷控制
        """
        # 1. 计算需量控制数据 (使用带追溯的计算器)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            demand_data = await tc.traced_demand_control_data()
            demand_traces = demand_data.get("_traces", {})
        else:
            demand_data = await self.calculator.calc_demand_control_data()
            demand_traces = {}

        # 2. 创建方案对象
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("A2"),
            proposal_type="A",
            template_id="A2",
            template_name=self.TEMPLATE_CONFIGS["A2"]["name"],
            current_situation={
                "当前申报需量": float(demand_data["当前申报需量"]),
                "历史95分位": float(demand_data["历史95分位"]),
                "建议申报需量": float(demand_data["建议申报需量"]),
                "需量电价": float(demand_data["需量电价"])
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 3. 生成措施列表
        measures = []

        # 措施1: 降低申报需量
        measure1 = await self._generate_measure_demand_reduction(proposal, demand_data, demand_traces)
        measures.append(measure1)

        # 措施2: 需量实时监控
        measure2 = await self._generate_measure_demand_monitoring(proposal, demand_data)
        measures.append(measure2)

        # 措施3: 高峰时段负荷控制
        measure3 = await self._generate_measure_peak_load_control(proposal, demand_data)
        measures.append(measure3)

        # 4. 计算总收益
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = Decimal("0")
        proposal.measures = measures

        return proposal

    async def _generate_measure_demand_reduction(
        self,
        proposal: EnergySavingProposal,
        demand_data: Dict[str, Decimal],
        demand_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施1: 降低申报需量至合理水平"""

        current_demand = demand_data["当前申报需量"]
        recommended_demand = demand_data["建议申报需量"]
        demand_price = demand_data["需量电价"]
        annual_saving = demand_data["年节省"]

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="申报需量调整",
            regulation_description=f"将申报需量从{current_demand}kW降低至{recommended_demand}kW",
            current_state={
                "申报需量": f"{current_demand} kW",
                "需量电价": f"{demand_price} 元/kW·月",
                "月基本电费": f"{float(current_demand * demand_price)} 元"
            },
            target_state={
                "申报需量": f"{recommended_demand} kW",
                "需量电价": f"{demand_price} 元/kW·月",
                "月基本电费": f"{float(recommended_demand * demand_price)} 元"
            },
            calculation_formula=f"""
【计算步骤】
1. 需量降低量 = {current_demand} - {recommended_demand} = {current_demand - recommended_demand} kW
2. 月节省 = {current_demand - recommended_demand} kW × {demand_price} 元/kW·月 = {demand_data['月节省']} 万元
3. 年节省 = {demand_data['月节省']} 万元 × 12月 = {annual_saving} 万元

【依据说明】
- 建议申报需量 = 历史95分位需量 × 1.05（安全余量）
- 历史95分位需量: {demand_data['历史95分位']} kW
- 安全余量5%可应对偶发性高峰
            """.strip(),
            calculation_basis="基于近3个月需量历史数据统计分析，95%的时间需量不会超过建议值",
            annual_benefit=annual_saving,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and demand_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(demand_traces)

        return measure

    async def _generate_measure_demand_monitoring(
        self,
        proposal: EnergySavingProposal,
        demand_data: Dict[str, Decimal]
    ) -> ProposalMeasure:
        """生成措施2: 需量实时监控与预警"""

        # 预警收益估算：避免超需量罚款
        recommended_demand = demand_data["建议申报需量"]
        estimated_benefit = Decimal("1.5")  # 估算年收益1.5万元

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="需量监控预警系统",
            regulation_description="建立需量实时监控机制，当接近申报需量80%时提前预警",
            current_state={
                "监控方式": "人工巡检（滞后）",
                "预警能力": "无",
                "超需量风险": "较高"
            },
            target_state={
                "监控方式": "实时自动监控",
                "预警阈值": f"{float(recommended_demand * Decimal('0.8'))} kW（80%申报需量）",
                "预警方式": "短信 + 邮件 + 系统推送",
                "超需量风险": "可控"
            },
            calculation_formula=f"""
【收益估算】
1. 避免超需量罚款：约1.0万元/年
2. 避免偶发性高峰导致的申报需量被动提升：约0.5万元/年
3. 合计年收益：{estimated_benefit} 万元

【实施方式】
- 利用现有能源管理系统功能
- 设置需量阈值报警
- 建立需量预警响应流程
            """.strip(),
            calculation_basis="基于历史超需量事件统计，年均2-3次偶发性高峰事件",
            annual_benefit=estimated_benefit,
            investment=Decimal("0")
        )

        return measure

    async def _generate_measure_peak_load_control(
        self,
        proposal: EnergySavingProposal,
        demand_data: Dict[str, Decimal]
    ) -> ProposalMeasure:
        """生成措施3: 高峰时段负荷控制"""

        # 负荷控制收益估算
        estimated_benefit = Decimal("2.0")  # 估算年收益2.0万元

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="高峰时段负荷管理",
            regulation_description="建立负荷控制策略，当需量预警时自动或手动削减非关键负荷",
            current_state={
                "负荷控制": "无自动化手段",
                "响应时间": "15-30分钟（人工）",
                "可控负荷": "未梳理"
            },
            target_state={
                "负荷控制": "分级自动控制",
                "响应时间": "< 1分钟",
                "可控负荷": "空调、照明、辅助设备等约800kW",
                "控制策略": "Ⅰ级预警：提示；Ⅱ级预警：自动削减非关键负荷"
            },
            calculation_formula=f"""
【收益估算】
1. 避免需量冲高导致全月需量电费增加：1.5万元/年
2. 优化负荷曲线带来的峰谷套利增益：0.5万元/年
3. 合计年收益：{estimated_benefit} 万元

【可控负荷清单】
- 空调系统温度上调：约400kW
- 非必要照明区域：约150kW
- 辅助生产设备暂停：约250kW
- 合计约800kW可控负荷

【控制逻辑】
- 90%阈值：短信提醒
- 95%阈值：自动削减Ⅰ级负荷（照明）
- 98%阈值：自动削减Ⅱ级负荷（空调+辅助设备）
            """.strip(),
            calculation_basis="基于可转移负荷梳理结果和需量电费单价计算",
            annual_benefit=estimated_benefit,
            investment=Decimal("0")
        )

        return measure

    # ==================== A3: 设备运行优化方案 ====================

    async def generate_equipment_optimization_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成A3-设备运行优化方案

        措施（针对不同设备类型）:
        - 措施1: 空压机负荷匹配优化
        - 措施2: 循环水泵变频调速
        - 措施3: 照明分区控制
        """
        # 1. 创建方案对象
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        # 计算各设备类型的负荷率 (使用带追溯的计算器)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            hvac_result = await tc.traced_equipment_load_rate("HVAC", start_date.date(), end_date.date())
            pump_result = await tc.traced_equipment_load_rate("PUMP", start_date.date(), end_date.date())
            hvac_load_rate = hvac_result["负荷率"]
            pump_load_rate = pump_result["负荷率"]
        else:
            hvac_load_rate = await self.calculator.calc_equipment_load_rate("HVAC", start_date.date(), end_date.date())
            pump_load_rate = await self.calculator.calc_equipment_load_rate("PUMP", start_date.date(), end_date.date())

        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("A3"),
            proposal_type="A",
            template_id="A3",
            template_name=self.TEMPLATE_CONFIGS["A3"]["name"],
            current_situation={
                "空调系统负荷率": float(hvac_load_rate),
                "水泵系统负荷率": float(pump_load_rate),
                "分析周期": f"{analysis_days}天"
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 2. 生成措施列表
        measures = []

        # 措施1: 空压机负荷匹配优化
        measure1 = await self._generate_measure_compressor_load_matching(proposal)
        measures.append(measure1)

        # 措施2: 循环水泵变频调速优化
        measure2 = await self._generate_measure_pump_frequency_control(proposal)
        measures.append(measure2)

        # 措施3: 照明分区控制
        measure3 = await self._generate_measure_lighting_zone_control(proposal)
        measures.append(measure3)

        # 3. 计算总收益
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = Decimal("0")
        proposal.measures = measures

        return proposal

    async def _generate_measure_compressor_load_matching(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施1: 空压机负荷匹配优化"""

        # 优化收益估算
        current_power = Decimal("320")  # 当前平均功率 kW
        optimized_power = Decimal("280")  # 优化后功率 kW
        saved_power = current_power - optimized_power
        annual_hours = Decimal("6000")
        avg_price = Decimal("0.436")

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="空压机系统",
            regulation_description="优化空压机组合运行策略，根据用气负荷动态调整运行台数，避免大马拉小车",
            current_state={
                "运行策略": "固定2台大功率空压机运行",
                "单台功率": "160kW",
                "平均负荷率": "60%",
                "平均功率": f"{current_power} kW"
            },
            target_state={
                "运行策略": "1台大功率 + 1台小功率组合",
                "组合功率": "110kW + 75kW",
                "平均负荷率": "75%",
                "平均功率": f"{optimized_power} kW"
            },
            calculation_formula=f"""
【计算步骤】
1. 节省功率 = {current_power} - {optimized_power} = {saved_power} kW
2. 年运行时间 = {annual_hours} 小时
3. 年节省电量 = {saved_power} kW × {annual_hours} h = {saved_power * annual_hours} kWh
4. 年节省金额 = {saved_power * annual_hours} kWh × {avg_price} 元/kWh = {annual_saving} 万元

【优化说明】
- 根据用气曲线分析，60%时段仅需185kW供气能力
- 采用大小搭配可提高整体负荷率至75%
- 减少空载损耗和频繁加卸载损耗
            """.strip(),
            calculation_basis="基于空压机运行数据和用气负荷曲线分析",
            annual_benefit=annual_saving,
            investment=Decimal("0")
        )

        return measure

    async def _generate_measure_pump_frequency_control(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施2: 循环水泵变频调速优化"""

        # 优化收益估算（假设节能20%）
        current_power = Decimal("150")
        optimization_ratio = Decimal("0.20")
        saved_power = (current_power * optimization_ratio).quantize(Decimal("0.01"))
        annual_hours = Decimal("7200")  # 水泵运行时间更长
        avg_price = Decimal("0.436")

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="循环水泵系统",
            regulation_description="优化循环水泵运行参数，根据冷却需求调整水泵转速，降低无效能耗",
            current_state={
                "运行方式": "工频恒速运行",
                "额定功率": f"{current_power} kW",
                "流量调节": "阀门节流",
                "能耗": "较高"
            },
            target_state={
                "运行方式": "根据温度需求调整转速",
                "调节方式": "优化控制策略",
                "预期节能": "20%",
                "节省功率": f"{saved_power} kW"
            },
            calculation_formula=f"""
【计算步骤】
1. 当前平均功率 = {current_power} kW
2. 优化节能比例 = {float(optimization_ratio * 100)}%
3. 节省功率 = {current_power} kW × {optimization_ratio} = {saved_power} kW
4. 年运行时间 = {annual_hours} 小时
5. 年节省电量 = {saved_power} kW × {annual_hours} h = {saved_power * annual_hours} kWh
6. 年节省金额 = {saved_power * annual_hours} kWh × {avg_price} 元/kWh = {annual_saving} 万元

【优化原理】
- 根据流体力学，流量与转速成正比，功率与转速三次方成正比
- 通过优化控制策略替代阀门节流，大幅降低能耗
- 冬季、过渡季节节能效果更明显
            """.strip(),
            calculation_basis="基于水泵运行数据和冷却负荷分析，参考行业经验值",
            annual_benefit=annual_saving,
            investment=Decimal("0")
        )

        return measure

    async def _generate_measure_lighting_zone_control(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施3: 照明分区控制"""

        # 优化收益估算
        current_power = Decimal("80")
        optimization_ratio = Decimal("0.30")
        saved_power = (current_power * optimization_ratio).quantize(Decimal("0.01"))
        annual_hours = Decimal("4000")  # 照明年运行时间
        avg_price = Decimal("0.436")

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="照明系统",
            regulation_description="实施照明分区精细化管理，根据人员活动和自然采光情况调整照明",
            current_state={
                "控制方式": "大区域统一开关",
                "控制精度": "粗放",
                "平均功率": f"{current_power} kW",
                "浪费现象": "无人区域常亮、自然采光区域开灯"
            },
            target_state={
                "控制方式": "分区控制 + 定时控制",
                "控制精度": "精细化",
                "预期节能": "30%",
                "节省功率": f"{saved_power} kW"
            },
            calculation_formula=f"""
【计算步骤】
1. 当前照明功率 = {current_power} kW
2. 优化节能比例 = {float(optimization_ratio * 100)}%
3. 节省功率 = {current_power} kW × {optimization_ratio} = {saved_power} kW
4. 年运行时间 = {annual_hours} 小时
5. 年节省电量 = {saved_power} kW × {annual_hours} h = {saved_power * annual_hours} kWh
6. 年节省金额 = {saved_power * annual_hours} kWh × {avg_price} 元/kWh = {annual_saving} 万元

【优化措施】
- 仓库区域：人来灯亮，人走延时5分钟关闭
- 办公区域：靠窗区域自然采光时段关闭照明
- 生产区域：按照工位使用情况分区控制
- 公共区域：定时控制 + 光感控制
            """.strip(),
            calculation_basis="基于照明系统现场调研和使用情况分析",
            annual_benefit=annual_saving,
            investment=Decimal("0")
        )

        return measure

    # ==================== A4: VPP需求响应方案 ====================

    async def generate_vpp_response_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成A4-VPP需求响应方案

        措施（按响应级别）:
        - 措施1: Ⅰ级快速响应资源
        - 措施2: Ⅱ级常规响应资源
        - 措施3: Ⅲ级计划响应资源
        """
        # 1. 计算VPP响应潜力 (使用带追溯的计算器)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            vpp_data = await tc.traced_vpp_response_potential()
            vpp_traces = vpp_data.get("_traces", {})
        else:
            vpp_data = await self.calculator.calc_vpp_response_potential()
            vpp_traces = {}

        # 2. 创建方案对象
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("A4"),
            proposal_type="A",
            template_id="A4",
            template_name=self.TEMPLATE_CONFIGS["A4"]["name"],
            current_situation={
                "Ⅰ级资源容量": float(vpp_data["Ⅰ级资源"]["容量"]),
                "Ⅱ级资源容量": float(vpp_data["Ⅱ级资源"]["容量"]),
                "Ⅲ级资源容量": float(vpp_data["Ⅲ级资源"]["容量"]),
                "总容量": float(vpp_data["总容量"]),
                "预期总收益": float(vpp_data["总年收益"])
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 3. 生成措施列表
        measures = []

        # 措施1: Ⅰ级快速响应资源
        measure1 = await self._generate_measure_vpp_level1(proposal, vpp_data, vpp_traces)
        measures.append(measure1)

        # 措施2: Ⅱ级常规响应资源
        measure2 = await self._generate_measure_vpp_level2(proposal, vpp_data, vpp_traces)
        measures.append(measure2)

        # 措施3: Ⅲ级计划响应资源
        measure3 = await self._generate_measure_vpp_level3(proposal, vpp_data, vpp_traces)
        measures.append(measure3)

        # 4. 计算总收益
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = Decimal("0")
        proposal.measures = measures

        return proposal

    async def _generate_measure_vpp_level1(
        self,
        proposal: EnergySavingProposal,
        vpp_data: Dict[str, Any],
        vpp_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施1: Ⅰ级快速响应资源"""

        level1_data = vpp_data["Ⅰ级资源"]
        capacity = level1_data["容量"]
        response_count = level1_data["年响应次数"]
        annual_benefit = level1_data["年收益"]

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="Ⅰ级快速响应资源（照明、空调）",
            regulation_description="注册Ⅰ级快速响应资源，响应时间≤5分钟，参与电网削峰填谷获得补贴",
            current_state={
                "响应能力": "未注册",
                "可响应容量": f"{capacity} kW",
                "市场参与": "否",
                "收益": "0元"
            },
            target_state={
                "响应能力": "已注册，响应时间≤5分钟",
                "注册容量": f"{capacity} kW",
                "响应设备": "办公照明、空调系统",
                "年响应次数": f"{response_count}次",
                "年收益": f"{annual_benefit}万元"
            },
            calculation_formula=f"""
【计算步骤】
1. 注册容量 = {capacity} kW = {capacity / Decimal('1000')} MW
2. 补偿标准 = 600 元/MW·次
3. 年响应次数 = {response_count} 次
4. 年收益 = {capacity / Decimal('1000')} MW × 600元/MW·次 × {response_count}次 = {annual_benefit} 万元

【响应机制】
- 接到指令后5分钟内完成负荷削减
- 每次响应持续时间：1-2小时
- 响应方式：办公区域照明降低30%、空调温度上调2℃

【资源清单】
- 办公照明系统：约{float(capacity * Decimal('0.4'))} kW
- 空调系统：约{float(capacity * Decimal('0.6'))} kW
            """.strip(),
            calculation_basis="基于虚拟电厂市场规则和补偿标准（上海、江苏等地市场数据）",
            annual_benefit=annual_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and vpp_traces:
            level_traces = {k: v for k, v in vpp_traces.items() if "Ⅰ级" in k}
            if level_traces:
                tc = self._get_traced_calculator()
                measure.trace_data = tc.get_measure_trace_data(level_traces)

        return measure

    async def _generate_measure_vpp_level2(
        self,
        proposal: EnergySavingProposal,
        vpp_data: Dict[str, Any],
        vpp_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施2: Ⅱ级常规响应资源"""

        level2_data = vpp_data["Ⅱ级资源"]
        capacity = level2_data["容量"]
        response_count = level2_data["年响应次数"]
        annual_benefit = level2_data["年收益"]

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="Ⅱ级常规响应资源（空压机、循环水泵）",
            regulation_description="注册Ⅱ级常规响应资源，响应时间≤15分钟，通过设备调度参与需求响应",
            current_state={
                "响应能力": "未注册",
                "可响应容量": f"{capacity} kW",
                "市场参与": "否",
                "收益": "0元"
            },
            target_state={
                "响应能力": "已注册，响应时间≤15分钟",
                "注册容量": f"{capacity} kW",
                "响应设备": "空压机、循环水泵",
                "年响应次数": f"{response_count}次",
                "年收益": f"{annual_benefit}万元"
            },
            calculation_formula=f"""
【计算步骤】
1. 注册容量 = {capacity} kW = {capacity / Decimal('1000')} MW
2. 补偿标准 = 300 元/MW·次
3. 年响应次数 = {response_count} 次
4. 年收益 = {capacity / Decimal('1000')} MW × 300元/MW·次 × {response_count}次 = {annual_benefit} 万元

【响应机制】
- 接到指令后15分钟内完成负荷调整
- 每次响应持续时间：2-4小时
- 响应方式：
  * 空压机：利用储气罐缓冲，暂停1-2台
  * 循环水泵：降低转速或暂停备用泵

【资源清单】
- 空压机系统：约{float(capacity * Decimal('0.6'))} kW
- 循环水泵：约{float(capacity * Decimal('0.4'))} kW
            """.strip(),
            calculation_basis="基于VPP市场Ⅱ级资源补偿标准",
            annual_benefit=annual_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and vpp_traces:
            level_traces = {k: v for k, v in vpp_traces.items() if "Ⅱ级" in k}
            if level_traces:
                tc = self._get_traced_calculator()
                measure.trace_data = tc.get_measure_trace_data(level_traces)

        return measure

    async def _generate_measure_vpp_level3(
        self,
        proposal: EnergySavingProposal,
        vpp_data: Dict[str, Any],
        vpp_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施3: Ⅲ级计划响应资源"""

        level3_data = vpp_data["Ⅲ级资源"]
        capacity = level3_data["容量"]
        response_count = level3_data["年响应次数"]
        annual_benefit = level3_data["年收益"]

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="Ⅲ级计划响应资源（生产负荷）",
            regulation_description="注册Ⅲ级计划响应资源，提前4小时通知，通过生产计划调整参与需求响应",
            current_state={
                "响应能力": "未注册",
                "可响应容量": f"{capacity} kW",
                "市场参与": "否",
                "收益": "0元"
            },
            target_state={
                "响应能力": "已注册，提前4小时通知",
                "注册容量": f"{capacity} kW",
                "响应设备": "热处理生产线、辅助生产设备",
                "年响应次数": f"{response_count}次",
                "年收益": f"{annual_benefit}万元"
            },
            calculation_formula=f"""
【计算步骤】
1. 注册容量 = {capacity} kW = {capacity / Decimal('1000')} MW
2. 补偿标准 = 200 元/MW·次
3. 年响应次数 = {response_count} 次
4. 年收益 = {capacity / Decimal('1000')} MW × 200元/MW·次 × {response_count}次 = {annual_benefit} 万元

【响应机制】
- 提前4小时接到通知
- 每次响应持续时间：4-8小时
- 响应方式：
  * 生产批次前移或后移
  * 非紧急订单生产时段调整
  * 设备维护保养窗口调整

【资源清单】
- 热处理生产线：约{float(capacity * Decimal('0.7'))} kW
- 辅助生产设备：约{float(capacity * Decimal('0.3'))} kW

【业务保障】
- 不影响紧急订单生产
- 通过排产优化消化时间调整
- 累计响应时间不超过年总时长的5%
            """.strip(),
            calculation_basis="基于VPP市场Ⅲ级资源补偿标准和生产计划灵活性分析",
            annual_benefit=annual_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and vpp_traces:
            level_traces = {k: v for k, v in vpp_traces.items() if "Ⅲ级" in k}
            if level_traces:
                tc = self._get_traced_calculator()
                measure.trace_data = tc.get_measure_trace_data(level_traces)

        return measure

    # ==================== A5: 负荷调度优化方案 ====================

    async def generate_load_scheduling_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成A5-负荷调度优化方案

        措施:
        - 措施1: 生产计划优化
        - 措施2: 设备启停时序优化
        - 措施3: 负荷曲线平滑化
        """
        # 1. 计算负荷曲线数据 (使用带追溯的计算器)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        # 使用昨天的数据作为示例
        yesterday = (datetime.now() - timedelta(days=1)).date()

        if self.enable_trace:
            tc = self._get_traced_calculator()
            load_curve = await tc.traced_load_curve_analysis(yesterday)
            load_traces = load_curve.get("_traces", {})
        else:
            load_curve = await self.calculator.calc_load_curve_analysis(yesterday)
            load_traces = {}

        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("A5"),
            proposal_type="A",
            template_id="A5",
            template_name=self.TEMPLATE_CONFIGS["A5"]["name"],
            current_situation={
                "最大负荷": float(load_curve["最大负荷"]),
                "最小负荷": float(load_curve["最小负荷"]),
                "平均负荷": float(load_curve["平均负荷"]),
                "峰谷差": float(load_curve["峰谷差"]),
                "负荷率": float(load_curve["负荷率"]),
                "峰谷比": float(load_curve["峰谷比"])
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 2. 生成措施列表
        measures = []

        # 措施1: 生产计划优化
        measure1 = await self._generate_measure_production_scheduling(proposal, load_curve, load_traces)
        measures.append(measure1)

        # 措施2: 设备启停时序优化
        measure2 = await self._generate_measure_equipment_sequencing(proposal, load_curve, load_traces)
        measures.append(measure2)

        # 措施3: 负荷曲线平滑化
        measure3 = await self._generate_measure_load_smoothing(proposal, load_curve, load_traces)
        measures.append(measure3)

        # 3. 计算总收益
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = Decimal("0")
        proposal.measures = measures

        return proposal

    async def _generate_measure_production_scheduling(
        self,
        proposal: EnergySavingProposal,
        load_curve: Dict[str, Decimal],
        load_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施1: 生产计划优化"""

        # 优化收益估算
        estimated_benefit = Decimal("3.5")  # 估算年收益3.5万元

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="生产计划排程",
            regulation_description="优化生产批次安排，将高能耗工序安排在低电价时段，降低用电成本",
            current_state={
                "排产依据": "订单交期优先",
                "能耗考虑": "较少",
                "负荷特征": f"峰谷差{load_curve['峰谷差']}kW，负荷率{load_curve['负荷率']}%",
                "优化空间": "较大"
            },
            target_state={
                "排产依据": "交期 + 能耗成本综合优化",
                "能耗考虑": "充分",
                "预期效果": "峰谷差降低15%，负荷率提升10%",
                "优化方式": "高能耗批次避开尖峰高峰时段"
            },
            calculation_formula=f"""
【收益估算】
1. 峰谷电价差收益：
   - 将500kW高能耗工序从尖峰(1.1元)调整至平段(0.425元)
   - 日转移2小时，价差0.675元/kWh
   - 年收益 = 500kW × 2h × 0.675元/kWh × 300天 ÷ 10000 = 2.0万元

2. 需量优化收益：
   - 削减偶发性峰值，降低申报需量100kW
   - 年收益 = 100kW × 42元/kW·月 × 12月 ÷ 10000 = 0.5万元

3. 负荷率提升带来的效率提升：
   - 设备利用率提升，分摊固定成本
   - 年收益约1.0万元

4. 合计年收益：{estimated_benefit}万元

【实施方式】
- 建立订单-能耗分析模型
- 在满足交期前提下，优先安排低电价时段生产
- 预留紧急订单快速插单能力
            """.strip(),
            calculation_basis="基于生产计划和负荷曲线分析，结合峰谷电价测算",
            annual_benefit=estimated_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and load_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(load_traces)

        return measure

    async def _generate_measure_equipment_sequencing(
        self,
        proposal: EnergySavingProposal,
        load_curve: Dict[str, Decimal],
        load_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施2: 设备启停时序优化"""

        # 优化收益估算
        estimated_benefit = Decimal("1.8")

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="设备启停时序",
            regulation_description="优化大功率设备启停时间，避免同时启动造成需量冲高",
            current_state={
                "启动方式": "集中启动（早8:00）",
                "峰值影响": "造成早高峰需量冲高",
                "启动功率": "约2000kW同时启动",
                "需量影响": "增加申报需量约200kW"
            },
            target_state={
                "启动方式": "梯次启动",
                "启动间隔": "每批次间隔15分钟",
                "峰值削减": "削减启动峰值约500kW",
                "需量影响": "降低需量冲高风险"
            },
            calculation_formula=f"""
【收益估算】
1. 需量削减收益：
   - 避免启动峰值，降低需量约150kW
   - 年收益 = 150kW × 42元/kW·月 × 12月 ÷ 10000 = 0.8万元

2. 启动优化节能：
   - 错峰启动避开尖峰时段，部分设备延后至平段启动
   - 每日转移300kW × 0.5h，价差0.675元/kWh
   - 年收益 = 300kW × 0.5h × 0.675元/kWh × 300天 ÷ 10000 = 0.3万元

3. 设备寿命延长：
   - 避免同时启动对电网和设备的冲击
   - 减少故障率，年节省维护成本约0.7万元

4. 合计年收益：{estimated_benefit}万元

【启动时序表】
- 7:45 空压机系统启动（避开尖峰）
- 8:00 照明、办公设备启动
- 8:15 循环水泵启动
- 8:30 生产线1启动
- 8:45 生产线2启动
            """.strip(),
            calculation_basis="基于设备启动功率统计和需量数据分析",
            annual_benefit=estimated_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and load_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(load_traces)

        return measure

    async def _generate_measure_load_smoothing(
        self,
        proposal: EnergySavingProposal,
        load_curve: Dict[str, Decimal],
        load_traces: Dict = None
    ) -> ProposalMeasure:
        """生成措施3: 负荷曲线平滑化"""

        # 优化收益估算
        estimated_benefit = Decimal("2.2")

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="整体负荷曲线",
            regulation_description="通过综合手段平滑负荷曲线，提高负荷率，降低峰谷差",
            current_state={
                "负荷率": f"{load_curve['负荷率']}%",
                "峰谷差": f"{load_curve['峰谷差']} kW",
                "峰谷比": f"{load_curve['峰谷比']}",
                "曲线特征": "峰谷明显，波动较大"
            },
            target_state={
                "目标负荷率": f"{float(load_curve['负荷率']) + 8}%",
                "目标峰谷差": f"{float(load_curve['峰谷差']) * 0.85} kW（降低15%）",
                "优化手段": "填谷 + 削峰",
                "曲线特征": "相对平滑"
            },
            calculation_formula=f"""
【收益估算】
1. 填谷收益：
   - 将部分可转移负荷转移至低谷时段
   - 增加低谷用电500kW × 4h，价差0.315元/kWh（平段→低谷）
   - 年收益 = 500kW × 4h × 0.315元/kWh × 300天 ÷ 10000 = 1.9万元

2. 削峰收益：
   - 降低需量申报50kW
   - 年收益 = 50kW × 42元/kW·月 × 12月 ÷ 10000 = 0.3万元

3. 合计年收益：{estimated_benefit}万元

【平滑化措施】
- 填谷：低谷时段安排设备维护、储气罐充气、蓄冷/蓄热
- 削峰：尖峰高峰时段减少非必要负荷、优化设备运行
- 负荷转移：灵活安排可转移负荷时段

【监控指标】
- 日负荷率目标：≥ {float(load_curve['负荷率']) + 8}%
- 峰谷差目标：≤ {float(load_curve['峰谷差']) * 0.85} kW
- 峰谷比目标：≤ {float(load_curve['峰谷比']) * 0.9}
            """.strip(),
            calculation_basis="基于负荷曲线特征分析和填谷削峰潜力评估",
            annual_benefit=estimated_benefit,
            investment=Decimal("0")
        )

        # V3.1: 写入追溯数据
        if self.enable_trace and load_traces:
            tc = self._get_traced_calculator()
            measure.trace_data = tc.get_measure_trace_data(load_traces)

        return measure

    async def generate_equipment_upgrade_proposal(self, analysis_days: int) -> EnergySavingProposal:
        """
        生成B1-设备改造升级方案（需要投资）

        措施:
        - 措施1: 老旧空压机更换为变频空压机
        - 措施2: 普通水泵加装变频器
        - 措施3: 传统照明改造为LED
        """
        # 1. 创建方案对象
        end_date = datetime.now()
        start_date = end_date - timedelta(days=analysis_days)

        # 计算设备能效对标 (使用带追溯的计算器)
        if self.enable_trace:
            tc = self._get_traced_calculator()
            pump_benchmark = await tc.traced_equipment_efficiency_benchmark("PUMP")
            benchmark_traces = pump_benchmark.get("_traces", {})
        else:
            pump_benchmark = await self.calculator.calc_equipment_efficiency_benchmark("PUMP")
            benchmark_traces = {}

        proposal = EnergySavingProposal(
            proposal_code=await self._generate_proposal_code("B1"),
            proposal_type="B",
            template_id="B1",
            template_name=self.TEMPLATE_CONFIGS["B1"]["name"],
            current_situation={
                "水泵系统当前能效": float(pump_benchmark["当前能效"]),
                "水泵系统行业先进能效": float(pump_benchmark["行业先进能效"]),
                "能效差距": float(pump_benchmark["能效差距"])
            },
            analysis_start_date=start_date.date(),
            analysis_end_date=end_date.date()
        )

        # 2. 生成措施列表
        measures = []

        # 措施1: 老旧空压机更换
        measure1 = await self._generate_measure_compressor_replacement(proposal)
        measures.append(measure1)

        # 措施2: 水泵加装变频器
        measure2 = await self._generate_measure_pump_vfd_installation(proposal)
        measures.append(measure2)

        # 措施3: LED照明改造
        measure3 = await self._generate_measure_led_retrofit(proposal)
        measures.append(measure3)

        # 3. 计算总收益和总投资
        proposal.total_benefit = sum(m.annual_benefit for m in measures)
        proposal.total_investment = sum(m.investment for m in measures)
        proposal.measures = measures

        return proposal

    async def _generate_measure_compressor_replacement(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施1: 老旧空压机更换为变频空压机"""

        # 参数设置
        old_power = Decimal("160")  # 老旧空压机额定功率
        new_power = Decimal("132")  # 变频空压机额定功率（效率更高）
        saved_power = old_power - new_power
        annual_hours = Decimal("6000")
        avg_price = Decimal("0.436")
        investment = Decimal("12")  # 投资12万元

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))
        payback_period = (investment / annual_saving).quantize(Decimal("0.1"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M001",
            regulation_object="1#空压机（使用年限15年）",
            regulation_description="将老旧工频空压机更换为永磁变频螺杆空压机，提升能效并实现按需供气",
            current_state={
                "设备型号": "工频螺杆空压机",
                "额定功率": f"{old_power} kW",
                "排气量": "30 m³/min",
                "能效等级": "3级（旧标准）",
                "调节方式": "加卸载",
                "平均功率": f"{old_power * Decimal('0.85')} kW"
            },
            target_state={
                "设备型号": "永磁变频螺杆空压机",
                "额定功率": f"{new_power} kW",
                "排气量": "30 m³/min",
                "能效等级": "1级（新标准）",
                "调节方式": "变频调速",
                "平均功率": f"{new_power * Decimal('0.75')} kW"
            },
            calculation_formula=f"""
【计算步骤】
1. 平均节省功率：
   - 老设备：{old_power} kW × 85% = {old_power * Decimal('0.85')} kW
   - 新设备：{new_power} kW × 75% = {new_power * Decimal('0.75')} kW
   - 节省功率 = {old_power * Decimal('0.85')} - {new_power * Decimal('0.75')} = {saved_power} kW

2. 年节省电量 = {saved_power} kW × {annual_hours} h = {saved_power * annual_hours} kWh

3. 年节省金额 = {saved_power * annual_hours} kWh × {avg_price} 元/kWh = {annual_saving} 万元

4. 投资回收期 = {investment} 万元 ÷ {annual_saving} 万元/年 = {payback_period} 年

【节能原理】
- 永磁电机效率更高（96% vs 92%）
- 变频调速替代加卸载，避免空载损耗
- 根据用气量自动调节转速，按需供气
- 综合节能率约30-35%
            """.strip(),
            calculation_basis="基于空压机运行数据和厂家技术参数",
            annual_benefit=annual_saving,
            investment=investment
        )

        return measure

    async def _generate_measure_pump_vfd_installation(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施2: 普通水泵加装变频器"""

        # 参数设置
        pump_power = Decimal("75")  # 水泵额定功率
        energy_saving_ratio = Decimal("0.35")  # 节能率35%
        saved_power = (pump_power * energy_saving_ratio).quantize(Decimal("0.01"))
        annual_hours = Decimal("7200")
        avg_price = Decimal("0.436")
        investment = Decimal("4.5")  # 投资4.5万元

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))
        payback_period = (investment / annual_saving).quantize(Decimal("0.1"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M002",
            regulation_object="2#、3#循环水泵",
            regulation_description="为2台循环水泵加装变频器，实现流量调节，降低节流损耗",
            current_state={
                "调节方式": "阀门节流",
                "额定功率": f"{pump_power} kW × 2台",
                "平均功率": f"{pump_power * Decimal('0.8')} kW/台",
                "效率": "低（节流损耗大）"
            },
            target_state={
                "调节方式": "变频调速",
                "额定功率": f"{pump_power} kW × 2台",
                "平均功率": f"{pump_power * Decimal('0.8') * (Decimal('1') - energy_saving_ratio)} kW/台",
                "效率": "高（按需调速）"
            },
            calculation_formula=f"""
【计算步骤】
1. 单台节省功率 = {pump_power} kW × 80%负载率 × {float(energy_saving_ratio * 100)}%节能率 = {saved_power} kW

2. 2台年节省电量 = {saved_power} kW × 2台 × {annual_hours} h = {saved_power * Decimal('2') * annual_hours} kWh

3. 年节省金额 = {saved_power * Decimal('2') * annual_hours} kWh × {avg_price} 元/kWh = {annual_saving} 万元

4. 投资回收期 = {investment} 万元 ÷ {annual_saving} 万元/年 = {payback_period} 年

【节能原理】
- 流体力学：流量∝转速，功率∝转速³
- 阀门节流是浪费能量，变频调速是减少输入
- 根据冷却需求调整转速，避免过度供水
- 冬季、过渡季节节能效果更明显

【投资明细】
- 变频器：2台 × 1.8万元 = 3.6万元
- 安装调试：0.6万元
- 控制改造：0.3万元
- 合计：{investment}万元
            """.strip(),
            calculation_basis="基于水泵运行曲线分析和变频改造节能测算",
            annual_benefit=annual_saving,
            investment=investment
        )

        return measure

    async def _generate_measure_led_retrofit(
        self,
        proposal: EnergySavingProposal
    ) -> ProposalMeasure:
        """生成措施3: 传统照明改造为LED"""

        # 参数设置
        old_power = Decimal("120")  # 传统照明总功率
        led_power = Decimal("50")   # LED照明总功率
        saved_power = old_power - led_power
        annual_hours = Decimal("4000")
        avg_price = Decimal("0.436")
        investment = Decimal("8")  # 投资8万元

        annual_saving = (saved_power * annual_hours * avg_price / Decimal("10000")).quantize(Decimal("0.01"))
        payback_period = (investment / annual_saving).quantize(Decimal("0.1"))

        measure = ProposalMeasure(
            measure_code=f"{proposal.proposal_code}-M003",
            regulation_object="车间及办公区照明系统",
            regulation_description="将传统荧光灯、金卤灯更换为LED灯具，降低照明能耗",
            current_state={
                "灯具类型": "荧光灯 + 金卤灯",
                "总功率": f"{old_power} kW",
                "照度": "300-500 lux",
                "光效": "60-80 lm/W",
                "使用寿命": "8000-10000小时"
            },
            target_state={
                "灯具类型": "LED灯具",
                "总功率": f"{led_power} kW",
                "照度": "300-500 lux（不变）",
                "光效": "120-150 lm/W",
                "使用寿命": "50000小时"
            },
            calculation_formula=f"""
【计算步骤】
1. 节省功率 = {old_power} - {led_power} = {saved_power} kW

2. 年节省电量 = {saved_power} kW × {annual_hours} h = {saved_power * annual_hours} kWh

3. 年节省电费 = {saved_power * annual_hours} kWh × {avg_price} 元/kWh = {float(saved_power * annual_hours * avg_price / Decimal('10000'))} 万元

4. 维护成本节省：
   - 传统灯具更换频次高，年维护约0.7万元
   - LED灯具寿命长，年维护约0.2万元
   - 年节省维护成本：0.5万元

5. 年总收益 = {float(saved_power * annual_hours * avg_price / Decimal('10000'))} + 0.5 = {annual_saving} 万元

6. 投资回收期 = {investment} 万元 ÷ {annual_saving} 万元/年 = {payback_period} 年

【改造明细】
- 车间金卤灯（400W）改为LED工矿灯（150W）：40盏
- 办公区荧光灯（40W×4）改为LED灯管（18W×4）：80套
- 走廊、仓库照明改造：若干

【附加收益】
- 照明质量提升（无频闪、显色性好）
- 维护工作量大幅降低
- 散热量减少，夏季降低空调负荷
            """.strip(),
            calculation_basis="基于照明系统现状调研和LED改造方案测算",
            annual_benefit=annual_saving,
            investment=investment
        )

        return measure

    # ==================== 辅助方法 ====================

    async def _generate_proposal_code(self, template_id: str) -> str:
        """
        生成方案编号
        格式: A1-20260125-001
        """
        date_str = datetime.now().strftime("%Y%m%d")

        # 查询今天已有的同类型方案数量 (异步查询)
        stmt = select(func.count(EnergySavingProposal.id)).where(
            EnergySavingProposal.proposal_code.like(f"{template_id}-{date_str}-%")
        )
        result = await self.db.execute(stmt)
        count = result.scalar() or 0

        seq = str(count + 1).zfill(3)
        return f"{template_id}-{date_str}-{seq}"
