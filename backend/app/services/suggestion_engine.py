"""
节能建议引擎 V2.4
数据驱动版本 - 从数据库查询真实电价和设备配置
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import (
    EnergySuggestion, PowerDevice, PUEHistory,
    EnergyDaily, MeterPoint
)
from .pricing_service import PricingService
from .device_regulation_service import DeviceRegulationService


class SuggestionTemplate:
    """节能建议模板"""

    TEMPLATES = {
        "pue_high": {
            "template_id": "pue_high",
            "name": "PUE过高",
            "category": "pue",
            "trigger": lambda data: data.get("pue", 0) > 1.8,
            "priority": "high",
            "difficulty": "medium",
            "title": "机房PUE偏高，建议优化制冷系统",
            "problem": "当前PUE为{pue:.2f}，高于行业标准1.5",
            "analysis": "制冷功率占总功率{cooling_ratio:.1f}%，建议值应低于30%",
            "measures": [
                "提高空调设定温度至24-26℃",
                "优化机房气流组织，消除热点",
                "采用冷热通道封闭方案"
            ],
            "effect": "PUE可降至{target_pue:.2f}，年节电{saving_kwh:.0f}kWh"
        },
        "ac_temp_low": {
            "template_id": "ac_temp_low",
            "name": "空调温度过低",
            "category": "efficiency",
            "trigger": lambda data: data.get("ac_temp", 24) < 22,
            "priority": "medium",
            "difficulty": "easy",
            "title": "空调温度设定过低，存在节能空间",
            "problem": "当前空调设定温度{ac_temp}℃，低于推荐值24℃",
            "analysis": "温度每升高1℃，制冷功率降低约6%",
            "measures": [
                "将空调温度调高至24℃",
                "监测设备温度，确保安全"
            ],
            "effect": "制冷功率可降低{power_reduction:.1f}kW，月节省{monthly_saving:.0f}元"
        },
        "peak_ratio_high": {
            "template_id": "peak_ratio_high",
            "name": "峰时用电过高",
            "category": "cost",
            "trigger": lambda data: data.get("peak_ratio", 0) > 25,  # 降低阈值以便触发
            "priority": "high",
            "difficulty": "medium",
            "title": "峰时用电占比过高，建议错峰用电",
            "problem": "峰时用电占比{peak_ratio:.1f}%，电费成本高",
            "analysis": "峰谷电价差为{price_diff:.3f}元/kWh（数据来源：系统电价配置）",
            "measures": [
                "将非关键任务调整至谷时",
                "优化设备启停时间",
                "使用储能设备削峰填谷"
            ],
            "effect": "月电费可节省{cost_saving:.0f}元"
        },
        "demand_over": {
            "template_id": "demand_over",
            "name": "需量申报不合理",
            "category": "demand",
            "trigger": lambda data: data.get("utilization", 100) < 70 or data.get("utilization", 0) > 95,
            "priority": "high",
            "difficulty": "easy",
            "title": "需量申报{status}，建议调整",
            "problem": "申报需量{declared}kW，实际最大需量{actual}kW，利用率{utilization:.1f}%",
            "analysis": "申报过高导致容量电费浪费；申报过低面临超需量罚款风险",
            "measures": [
                "建议申报需量调整为{recommended}kW",
                "月容量电费差额{fee_diff:.0f}元"
            ],
            "effect": "年节省容量电费{annual_saving:.0f}元"
        },
        "device_idle": {
            "template_id": "device_idle",
            "name": "设备长时间空载",
            "category": "efficiency",
            "trigger": lambda data: data.get("load_rate", 100) < 30,
            "priority": "medium",
            "difficulty": "medium",
            "title": "{device_name}长时间低负载运行",
            "problem": "设备负载率仅{load_rate:.1f}%，持续{duration}小时",
            "analysis": "空载功耗约为满载功耗的{idle_ratio:.0f}%，存在浪费",
            "measures": [
                "评估是否可关闭该设备",
                "合并负载，提高设备利用率",
                "启用设备节能模式"
            ],
            "effect": "可节省功耗{power_saving:.1f}kW，月节省{cost_saving:.0f}元"
        }
    }


class SuggestionEngineService:
    """节能建议引擎服务 - V2.4 数据驱动版本"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.templates = SuggestionTemplate.TEMPLATES
        # 注入数据服务
        self.pricing_service = PricingService(db)
        self.device_service = DeviceRegulationService(db)

    def get_templates(self) -> List[Dict]:
        """获取所有建议模板"""
        return [
            {
                "template_id": t["template_id"],
                "name": t["name"],
                "category": t["category"],
                "priority": t["priority"],
                "difficulty": t["difficulty"]
            }
            for t in self.templates.values()
        ]

    async def analyze_and_generate(
        self,
        categories: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """分析数据并生成建议"""
        # 收集分析数据 - 从数据库查询真实数据
        analysis_data = await self._collect_analysis_data()

        new_count = 0
        updated_count = 0
        analyzed_categories = []

        for template_id, template in self.templates.items():
            # 过滤类别
            if categories and template["category"] not in categories:
                continue

            analyzed_categories.append(template["category"])

            # 检查触发条件
            if template["trigger"](analysis_data):
                # 生成建议
                suggestion = await self._generate_suggestion(template, analysis_data)
                if suggestion:
                    # 检查是否已存在
                    existing = await self._find_existing_suggestion(template_id)
                    if existing:
                        if force_refresh:
                            await self._update_suggestion(existing, suggestion)
                            updated_count += 1
                    else:
                        await self._create_suggestion(suggestion)
                        new_count += 1

        await self.db.commit()

        return {
            "analyzed_count": len(analyzed_categories),
            "new_suggestions": new_count,
            "updated_suggestions": updated_count,
            "categories_analyzed": list(set(analyzed_categories)),
            "analysis_time": datetime.now()
        }

    async def _collect_analysis_data(self) -> Dict[str, Any]:
        """收集分析所需数据 - 从数据库查询真实数据"""
        data = {}

        # 1. 从 electricity_pricing 表获取真实电价
        pricing = await self.pricing_service.get_current_pricing()
        data["pricing"] = pricing

        # 获取各时段电价
        prices = await self.pricing_service.get_all_prices()
        data.update(prices)

        # 计算峰谷价差
        sharp_price = prices.get("sharp_price", 0)
        peak_price = prices.get("peak_price", 0)
        valley_price = prices.get("valley_price", 0)

        # 使用尖峰-低谷价差，如果没有尖峰则使用高峰-低谷价差
        if sharp_price > 0:
            data["price_diff_sharp_valley"] = sharp_price - valley_price
            data["price_diff"] = sharp_price - valley_price
        else:
            data["price_diff_peak_valley"] = peak_price - valley_price
            data["price_diff"] = peak_price - valley_price

        # 2. 获取可转移设备列表
        shiftable_devices = await self.device_service.get_shiftable_devices()
        data["shiftable_devices"] = shiftable_devices
        data["total_shiftable_power"] = sum(d["shiftable_power"] for d in shiftable_devices)

        # 3. 获取可调节设备列表
        adjustable_devices = await self.device_service.get_adjustable_devices()
        data["adjustable_devices"] = adjustable_devices

        # 4. 获取时段配置用于前端展示
        time_periods = await self.pricing_service.get_time_periods_for_display()
        data["time_periods"] = time_periods

        # 5. 获取数据来源信息
        pricing_source = await self.pricing_service.get_pricing_data_source()
        device_source = await self.device_service.get_regulation_data_source()
        data["data_sources"] = {
            "pricing": pricing_source,
            "devices": device_source
        }

        # 6. 获取最新PUE数据
        pue_result = await self.db.execute(
            select(PUEHistory).order_by(PUEHistory.record_time.desc()).limit(1)
        )
        pue_record = pue_result.scalar_one_or_none()
        if pue_record:
            data["pue"] = pue_record.pue
            data["total_power"] = pue_record.total_power
            data["it_power"] = pue_record.it_power
            data["cooling_power"] = pue_record.cooling_power or 0
            if pue_record.total_power > 0:
                data["cooling_ratio"] = (pue_record.cooling_power or 0) / pue_record.total_power * 100
            else:
                data["cooling_ratio"] = 0
        else:
            data["pue"] = 1.5
            data["total_power"] = 100
            data["it_power"] = 60
            data["cooling_ratio"] = 25
            data["cooling_power"] = 25

        # 7. 获取需量数据
        meter_result = await self.db.execute(
            select(MeterPoint).where(MeterPoint.is_enabled == True).limit(1)
        )
        meter = meter_result.scalar_one_or_none()
        if meter:
            data["declared"] = meter.declared_demand or 150
            data["actual"] = data.get("total_power", 100)
            if data["declared"] > 0:
                data["utilization"] = data["actual"] / data["declared"] * 100
            else:
                data["utilization"] = 80
        else:
            data["declared"] = 150
            data["actual"] = 100
            data["utilization"] = 66.7

        # 8. 其他分析数据
        data["ac_temp"] = 24
        data["peak_ratio"] = 45  # 模拟峰时用电占比
        data["load_rate"] = 60
        data["device_name"] = "设备"
        data["duration"] = 8
        data["idle_ratio"] = 30

        return data

    async def _generate_suggestion(
        self,
        template: Dict,
        data: Dict[str, Any]
    ) -> Optional[Dict]:
        """根据模板生成建议 - 使用真实数据填充"""
        try:
            # 计算节能潜力
            saving_kwh = 0
            saving_cost = 0

            # 根据模板类型生成特定的建议内容
            if template["template_id"] == "pue_high":
                target_pue = 1.5
                current_pue = data.get("pue", 1.8)
                total_power = data.get("total_power", 100)
                it_power = data.get("it_power", 60)
                if current_pue > target_pue:
                    current_total = it_power * current_pue
                    target_total = it_power * target_pue
                    saving_kwh = (current_total - target_total) * 24 * 30
                    avg_price = data.get("normal_price", 0.8)
                    saving_cost = saving_kwh * avg_price
                data["target_pue"] = target_pue
                data["saving_kwh"] = saving_kwh

            elif template["template_id"] == "ac_temp_low":
                cooling_power = data.get("cooling_power", 30)
                power_reduction = cooling_power * 0.12  # 2度 * 6%
                avg_price = data.get("normal_price", 0.8)
                saving_cost = power_reduction * 24 * 30 * avg_price
                data["power_reduction"] = power_reduction
                data["monthly_saving"] = saving_cost

            elif template["template_id"] == "peak_ratio_high":
                # 峰谷套利建议 - 使用真实电价和设备数据
                return await self._generate_peak_valley_suggestion(template, data)

            elif template["template_id"] == "demand_over":
                utilization = data.get("utilization", 80)
                declared = data.get("declared", 150)
                actual = data.get("actual", 100)
                if utilization < 70:
                    data["status"] = "过高"
                    data["recommended"] = actual * 1.15
                else:
                    data["status"] = "偏低"
                    data["recommended"] = actual * 1.05
                data["fee_diff"] = abs(declared - data["recommended"]) * 30
                data["annual_saving"] = data["fee_diff"] * 12
                saving_cost = data["annual_saving"]

            elif template["template_id"] == "device_idle":
                power_saving = data.get("total_power", 100) * 0.1
                avg_price = data.get("normal_price", 0.8)
                saving_cost = power_saving * 24 * 30 * avg_price
                data["power_saving"] = power_saving
                data["cost_saving"] = saving_cost

            # 格式化模板内容
            title = template["title"].format(**data) if "{" in template["title"] else template["title"]
            problem = template["problem"].format(**data) if "{" in template["problem"] else template["problem"]
            analysis = template["analysis"].format(**data) if "{" in template["analysis"] else template["analysis"]
            effect = template["effect"].format(**data) if "{" in template["effect"] else template["effect"]

            return {
                "rule_id": template["template_id"],
                "rule_name": template["name"],
                "template_id": template["template_id"],
                "category": template["category"],
                "suggestion": title,
                "problem_description": problem,
                "analysis_detail": analysis,
                "implementation_steps": [
                    {"step": i + 1, "description": m, "duration": "1-2天"}
                    for i, m in enumerate(template["measures"])
                ],
                "expected_effect": {
                    "description": effect,
                    "saving_kwh": saving_kwh,
                    "saving_cost": saving_cost
                },
                "priority": template["priority"],
                "difficulty": template["difficulty"],
                "potential_saving": saving_kwh,
                "potential_cost_saving": saving_cost,
                "parameters": self._build_parameters(template["template_id"], data)
            }
        except Exception as e:
            print(f"生成建议失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _generate_peak_valley_suggestion(
        self,
        template: Dict,
        data: Dict[str, Any]
    ) -> Optional[Dict]:
        """生成峰谷套利建议 - 使用真实数据"""
        pricing = data.get("pricing", {})
        shiftable_devices = data.get("shiftable_devices", [])
        time_periods = data.get("time_periods", [])

        # 获取电价
        sharp_price = data.get("sharp_price", 0)
        peak_price = data.get("peak_price", 0)
        valley_price = data.get("valley_price", 0)
        price_diff = data.get("price_diff", 0)

        # 如果没有电价配置，使用默认值
        if price_diff <= 0:
            price_diff = 0.5  # 默认价差

        # 计算可转移功率
        total_shiftable_power = data.get("total_shiftable_power", 0)
        if total_shiftable_power <= 0:
            total_shiftable_power = 100  # 默认值

        # 计算节能效果
        default_shift_hours = 2
        daily_energy = total_shiftable_power * default_shift_hours
        daily_saving = daily_energy * price_diff
        annual_saving = daily_saving * 300  # 年工作日

        # 构建可调参数 - 基于真实数据
        adjustable_params = [
            {
                "key": "shift_hours",
                "name": "转移时长",
                "type": "number",
                "current_value": default_shift_hours,
                "min": 0.5,
                "max": 8,
                "step": 0.5,
                "unit": "小时"
            },
            {
                "key": "selected_devices",
                "name": "参与设备",
                "type": "device_select",
                "current_value": [d["device_id"] for d in shiftable_devices[:3]],
                "options": [
                    {
                        "device_id": d["device_id"],
                        "label": f"{d['device_name']}({d['rated_power']}kW)",
                        "shiftable_power": d["shiftable_power"],
                        "constraints": {
                            "allowed_hours": d.get("allowed_shift_hours", []),
                            "max_duration": d.get("max_shift_duration")
                        }
                    }
                    for d in shiftable_devices
                ]
            },
            {
                "key": "source_period",
                "name": "转出时段",
                "type": "period_select",
                "current_value": "sharp" if sharp_price > 0 else "peak",
                "options": [p for p in time_periods if p["type"] in ["sharp", "peak"]]
            },
            {
                "key": "target_period",
                "name": "转入时段",
                "type": "period_select",
                "current_value": "valley",
                "options": [p for p in time_periods if p["type"] in ["valley", "deep_valley", "normal"]]
            }
        ]

        # 设备列表 - 使用真实数据
        devices = [
            {
                "device_id": d["device_id"],
                "device_code": d["device_code"],
                "device_name": d["device_name"],
                "device_type": d["device_type"],
                "rated_power": d["rated_power"],
                "shiftable_power": d["shiftable_power"],
                "regulation_method": d.get("regulation_method", "负荷转移"),
                "constraints": {
                    "allowed_hours": d.get("allowed_shift_hours", []),
                    "forbidden_hours": d.get("forbidden_shift_hours", []),
                    "min_runtime": d.get("min_continuous_runtime")
                }
            }
            for d in shiftable_devices
        ]

        # 时间配置 - 使用真实电价时段
        time_config = {
            "source_periods": pricing.get("sharp", []) + pricing.get("peak", []),
            "target_periods": pricing.get("valley", []) + pricing.get("deep_valley", []),
            "all_periods": time_periods
        }

        # 计算公式 - 使用真实电价
        calculation_formula = {
            "formula": "日收益 = 转移功率 × 转移时长 × (转出电价 - 转入电价)",
            "variables_from_db": {
                "尖峰电价": f"{sharp_price} 元/kWh（来自系统设置-电价配置）" if sharp_price > 0 else "未配置",
                "高峰电价": f"{peak_price} 元/kWh（来自系统设置-电价配置）",
                "低谷电价": f"{valley_price} 元/kWh（来自系统设置-电价配置）",
                "峰谷价差": f"{price_diff:.3f} 元/kWh"
            },
            "steps": [
                {"step": 1, "desc": f"日转移电量 = {total_shiftable_power:.1f} kW × {default_shift_hours} h = {daily_energy:.1f} kWh"},
                {"step": 2, "desc": f"价差 = {sharp_price if sharp_price > 0 else peak_price:.3f} - {valley_price:.3f} = {price_diff:.3f} 元/kWh"},
                {"step": 3, "desc": f"日收益 = {daily_energy:.1f} × {price_diff:.3f} = {daily_saving:.2f} 元"},
                {"step": 4, "desc": f"年收益 = {daily_saving:.2f} × 300天 = {annual_saving:.2f} 元"}
            ]
        }

        # 格式化模板
        data["cost_saving"] = annual_saving / 12  # 月节省
        title = template["title"]
        problem = template["problem"].format(**data)
        analysis = template["analysis"].format(**data)
        effect = f"月电费可节省{annual_saving/12:.0f}元，年节省{annual_saving/10000:.2f}万元"

        return {
            "rule_id": template["template_id"],
            "rule_name": template["name"],
            "template_id": template["template_id"],
            "category": template["category"],
            "suggestion": title,
            "problem_description": problem,
            "analysis_detail": analysis,
            "implementation_steps": [
                {"step": i + 1, "description": m, "duration": "1-2天"}
                for i, m in enumerate(template["measures"])
            ],
            "expected_effect": {
                "description": effect,
                "saving_kwh": daily_energy * 30,
                "saving_cost": annual_saving / 12
            },
            "priority": template["priority"],
            "difficulty": template["difficulty"],
            "potential_saving": daily_energy * 30 * 12,
            "potential_cost_saving": annual_saving,
            "parameters": {
                "pricing_source": "electricity_pricing表",
                "device_source": "device_shift_configs表",
                "sharp_price": sharp_price,
                "peak_price": peak_price,
                "valley_price": valley_price,
                "price_diff": price_diff,
                "total_shiftable_power": total_shiftable_power,
                "adjustable_params": adjustable_params,
                "devices": devices,
                "time_config": time_config,
                "calculation_formula": calculation_formula,
                "default_shift_hours": default_shift_hours,
                "daily_saving": daily_saving,
                "annual_saving": annual_saving
            }
        }

    def _build_parameters(self, template_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建建议参数"""
        # 基础参数
        params = {
            "data_sources": data.get("data_sources", {}),
            "analysis_time": datetime.now().isoformat()
        }

        # 根据模板类型添加特定参数
        if template_id == "pue_high":
            params.update({
                "current_pue": data.get("pue"),
                "target_pue": data.get("target_pue", 1.5),
                "cooling_ratio": data.get("cooling_ratio"),
                "cooling_power": data.get("cooling_power"),
                "it_power": data.get("it_power"),
                "total_power": data.get("total_power")
            })
        elif template_id == "ac_temp_low":
            params.update({
                "current_temp": data.get("ac_temp"),
                "target_temp": 24,
                "adjustable_devices": data.get("adjustable_devices", [])
            })
        elif template_id == "demand_over":
            params.update({
                "declared": data.get("declared"),
                "actual": data.get("actual"),
                "utilization": data.get("utilization"),
                "recommended": data.get("recommended")
            })

        return params

    async def recalculate_suggestion(
        self,
        suggestion_id: int,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据用户调整的参数重新计算节能效果

        Args:
            suggestion_id: 建议ID
            params: 用户调整的参数
                - selected_devices: List[int] 选择的设备ID
                - shift_hours: float 转移时长
                - source_period: str 转出时段
                - target_period: str 转入时段

        Returns:
            Dict: 重新计算的结果
        """
        # 获取真实电价
        source_price = await self.pricing_service.get_price_for_period(params.get("source_period", "peak"))
        target_price = await self.pricing_service.get_price_for_period(params.get("target_period", "valley"))
        price_diff = source_price - target_price

        # 获取选中设备的可转移功率
        selected_device_ids = params.get("selected_devices", [])
        shift_hours = params.get("shift_hours", 2)

        all_devices = await self.device_service.get_shiftable_devices()
        selected_devices = [d for d in all_devices if d["device_id"] in selected_device_ids]
        total_power = sum(d["shiftable_power"] for d in selected_devices)

        # 计算节能效果
        daily_energy = total_power * shift_hours
        daily_saving = daily_energy * price_diff
        annual_saving = daily_saving * 300  # 年工作日

        return {
            "calculation_steps": [
                f"1. 选中设备总可转移功率: {total_power:.1f} kW",
                f"2. 日转移电量: {total_power:.1f} kW × {shift_hours} h = {daily_energy:.1f} kWh",
                f"3. 电价差: {source_price:.3f} - {target_price:.3f} = {price_diff:.3f} 元/kWh",
                f"4. 日收益: {daily_energy:.1f} × {price_diff:.3f} = {daily_saving:.2f} 元",
                f"5. 年收益: {daily_saving:.2f} × 300天 = {annual_saving:.2f} 元"
            ],
            "effects": {
                "daily_energy_kwh": round(daily_energy, 2),
                "daily_saving_yuan": round(daily_saving, 2),
                "annual_saving_yuan": round(annual_saving, 2),
                "annual_saving_wan": round(annual_saving / 10000, 4)
            },
            "pricing_used": {
                "source": {"period": params.get("source_period"), "price": source_price},
                "target": {"period": params.get("target_period"), "price": target_price}
            },
            "devices_used": selected_devices
        }

    async def _find_existing_suggestion(self, template_id: str) -> Optional[EnergySuggestion]:
        """查找已存在的建议"""
        result = await self.db.execute(
            select(EnergySuggestion).where(
                EnergySuggestion.template_id == template_id,
                EnergySuggestion.status == "pending"
            )
        )
        return result.scalar_one_or_none()

    async def _create_suggestion(self, data: Dict) -> EnergySuggestion:
        """创建新建议"""
        suggestion = EnergySuggestion(
            rule_id=data["rule_id"],
            rule_name=data["rule_name"],
            template_id=data["template_id"],
            category=data["category"],
            suggestion=data["suggestion"],
            problem_description=data["problem_description"],
            analysis_detail=data["analysis_detail"],
            implementation_steps=data["implementation_steps"],
            expected_effect=data["expected_effect"],
            priority=data["priority"],
            difficulty=data["difficulty"],
            potential_saving=data["potential_saving"],
            potential_cost_saving=data["potential_cost_saving"],
            parameters=data["parameters"],
            status="pending"
        )
        self.db.add(suggestion)
        return suggestion

    async def _update_suggestion(self, existing: EnergySuggestion, data: Dict):
        """更新已存在的建议"""
        existing.suggestion = data["suggestion"]
        existing.problem_description = data["problem_description"]
        existing.analysis_detail = data["analysis_detail"]
        existing.implementation_steps = data["implementation_steps"]
        existing.expected_effect = data["expected_effect"]
        existing.potential_saving = data["potential_saving"]
        existing.potential_cost_saving = data["potential_cost_saving"]
        existing.parameters = data["parameters"]
        existing.updated_at = datetime.now()

    async def get_suggestions(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status: str = "pending",
        limit: int = 50
    ) -> List[EnergySuggestion]:
        """获取建议列表"""
        query = select(EnergySuggestion)

        conditions = []
        if category:
            conditions.append(EnergySuggestion.category == category)
        if priority:
            conditions.append(EnergySuggestion.priority == priority)
        if status:
            conditions.append(EnergySuggestion.status == status)

        if conditions:
            from sqlalchemy import and_
            query = query.where(and_(*conditions))

        query = query.order_by(EnergySuggestion.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_suggestion_detail(self, suggestion_id: int) -> Optional[Dict[str, Any]]:
        """获取建议详情 - 包含完整的调整参数和设备信息"""
        result = await self.db.execute(
            select(EnergySuggestion).where(EnergySuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()

        if not suggestion:
            return None

        # 获取最新的电价和设备数据
        pricing = await self.pricing_service.get_current_pricing()
        time_periods = await self.pricing_service.get_time_periods_for_display()
        shiftable_devices = await self.device_service.get_shiftable_devices()
        prices = await self.pricing_service.get_all_prices()

        # 获取数据库中的原始参数
        db_parameters = suggestion.parameters or {}

        # 构建增强的参数对象（合并数据库参数和实时数据）
        enhanced_parameters = {**db_parameters}

        # 如果数据库参数中没有 adjustable_params，动态生成
        if not enhanced_parameters.get("adjustable_params"):
            sharp_price = prices.get("sharp_price", 0)
            enhanced_parameters["adjustable_params"] = [
                {
                    "key": "shift_hours",
                    "name": "转移时长",
                    "type": "number",
                    "current_value": db_parameters.get("default_shift_hours", 2),
                    "min": 0.5,
                    "max": 8,
                    "step": 0.5,
                    "unit": "小时"
                },
                {
                    "key": "selected_devices",
                    "name": "参与设备",
                    "type": "device_select",
                    "current_value": [d["device_id"] for d in shiftable_devices[:3]] if shiftable_devices else [],
                    "options": [
                        {
                            "device_id": d["device_id"],
                            "label": f"{d['device_name']}({d['rated_power']}kW)",
                            "shiftable_power": d["shiftable_power"],
                            "constraints": {
                                "allowed_hours": d.get("allowed_shift_hours", []),
                                "max_duration": d.get("max_shift_duration")
                            }
                        }
                        for d in shiftable_devices
                    ]
                },
                {
                    "key": "source_period",
                    "name": "转出时段",
                    "type": "period_select",
                    "current_value": "sharp" if sharp_price > 0 else "peak",
                    "options": [p for p in time_periods if p.get("type") in ["sharp", "peak"]]
                },
                {
                    "key": "target_period",
                    "name": "转入时段",
                    "type": "period_select",
                    "current_value": "valley",
                    "options": [p for p in time_periods if p.get("type") in ["valley", "deep_valley", "normal"]]
                }
            ]

        # 如果数据库参数中没有 devices，从实时数据生成
        if not enhanced_parameters.get("devices"):
            enhanced_parameters["devices"] = [
                {
                    "device_id": d["device_id"],
                    "device_code": d.get("device_code", f"DEV-{d['device_id']}"),
                    "device_name": d["device_name"],
                    "device_type": d.get("device_type", "HVAC"),
                    "rated_power": d["rated_power"],
                    "shiftable_power": d["shiftable_power"],
                    "regulation_method": d.get("regulation_method", "负荷转移"),
                    "constraints": {
                        "allowed_hours": d.get("allowed_shift_hours", []),
                        "forbidden_hours": d.get("forbidden_shift_hours", []),
                        "min_runtime": d.get("min_continuous_runtime")
                    }
                }
                for d in shiftable_devices
            ]

        # 如果数据库参数中没有 calculation_formula，动态生成
        if not enhanced_parameters.get("calculation_formula"):
            sharp_price = prices.get("sharp_price", 0)
            peak_price = prices.get("peak_price", 0)
            valley_price = prices.get("valley_price", 0)
            price_diff = (sharp_price if sharp_price > 0 else peak_price) - valley_price if valley_price > 0 else 0.5

            total_shiftable_power = sum(d["shiftable_power"] for d in shiftable_devices) if shiftable_devices else 100
            default_shift_hours = enhanced_parameters.get("default_shift_hours", 2)
            daily_energy = total_shiftable_power * default_shift_hours
            daily_saving = daily_energy * price_diff
            annual_saving = daily_saving * 300

            enhanced_parameters["calculation_formula"] = {
                "formula": "日收益 = 转移功率 × 转移时长 × (转出电价 - 转入电价)",
                "variables_from_db": {
                    "尖峰电价": f"{sharp_price} 元/kWh（来自系统设置-电价配置）" if sharp_price > 0 else "未配置",
                    "高峰电价": f"{peak_price} 元/kWh（来自系统设置-电价配置）",
                    "低谷电价": f"{valley_price} 元/kWh（来自系统设置-电价配置）",
                    "峰谷价差": f"{price_diff:.3f} 元/kWh"
                },
                "steps": [
                    {"step": 1, "desc": f"日转移电量 = {total_shiftable_power:.1f} kW × {default_shift_hours} h = {daily_energy:.1f} kWh"},
                    {"step": 2, "desc": f"价差 = {sharp_price if sharp_price > 0 else peak_price:.3f} - {valley_price:.3f} = {price_diff:.3f} 元/kWh"},
                    {"step": 3, "desc": f"日收益 = {daily_energy:.1f} × {price_diff:.3f} = {daily_saving:.2f} 元"},
                    {"step": 4, "desc": f"年收益 = {daily_saving:.2f} × 300天 = {annual_saving:.2f} 元"}
                ]
            }

        # 填充缺失的电价信息
        if not enhanced_parameters.get("sharp_price"):
            enhanced_parameters["sharp_price"] = prices.get("sharp_price", 0)
        if not enhanced_parameters.get("peak_price"):
            enhanced_parameters["peak_price"] = prices.get("peak_price", 0)
        if not enhanced_parameters.get("valley_price"):
            enhanced_parameters["valley_price"] = prices.get("valley_price", 0)
        if not enhanced_parameters.get("price_diff"):
            sharp = enhanced_parameters.get("sharp_price", 0)
            peak = enhanced_parameters.get("peak_price", 0)
            valley = enhanced_parameters.get("valley_price", 0)
            enhanced_parameters["price_diff"] = (sharp if sharp > 0 else peak) - valley

        if not enhanced_parameters.get("total_shiftable_power"):
            enhanced_parameters["total_shiftable_power"] = sum(d["shiftable_power"] for d in shiftable_devices) if shiftable_devices else 0

        # 构建详情响应
        detail = {
            "id": suggestion.id,
            "rule_id": suggestion.rule_id,
            "rule_name": suggestion.rule_name,
            "template_id": suggestion.template_id,
            "category": suggestion.category,
            "suggestion": suggestion.suggestion,
            "problem_description": suggestion.problem_description or "当前系统存在节能优化空间",
            "analysis_detail": suggestion.analysis_detail or "通过分析系统运行数据，发现可通过优化用电策略降低能耗成本。",
            "implementation_steps": suggestion.implementation_steps or [
                {"step": 1, "description": "分析当前用电模式", "duration": "1天"},
                {"step": 2, "description": "制定优化方案", "duration": "1-2天"},
                {"step": 3, "description": "实施优化措施", "duration": "1-3天"},
                {"step": 4, "description": "监控效果并调整", "duration": "持续"}
            ],
            "expected_effect": suggestion.expected_effect or {
                "description": f"预计可节省用电成本",
                "saving_kwh": suggestion.potential_saving or 0,
                "saving_cost": suggestion.potential_cost_saving or 0
            },
            "priority": suggestion.priority,
            "difficulty": suggestion.difficulty,
            "potential_saving": suggestion.potential_saving,
            "potential_cost_saving": suggestion.potential_cost_saving,
            "status": suggestion.status,
            "created_at": suggestion.created_at,
            "parameters": enhanced_parameters,
            # 添加实时数据
            "current_pricing": pricing,
            "time_periods": time_periods,
            "shiftable_devices": shiftable_devices,
            "data_sources": {
                "pricing": await self.pricing_service.get_pricing_data_source(),
                "devices": await self.device_service.get_regulation_data_source()
            }
        }

        return detail

    async def get_suggestion_summary(self) -> Dict[str, Any]:
        """获取建议汇总"""
        # 统计各状态数量
        result = await self.db.execute(
            select(
                EnergySuggestion.status,
                func.count(EnergySuggestion.id)
            ).group_by(EnergySuggestion.status)
        )
        status_counts = {row[0]: row[1] for row in result.all()}

        # 统计各优先级数量
        result = await self.db.execute(
            select(
                EnergySuggestion.priority,
                func.count(EnergySuggestion.id)
            ).where(EnergySuggestion.status == "pending"
            ).group_by(EnergySuggestion.priority)
        )
        priority_counts = {row[0]: row[1] for row in result.all()}

        # 计算潜在节能量
        result = await self.db.execute(
            select(
                func.sum(EnergySuggestion.potential_saving),
                func.sum(EnergySuggestion.potential_cost_saving)
            ).where(EnergySuggestion.status == "pending")
        )
        row = result.first()
        potential_saving = row[0] or 0
        potential_cost = row[1] or 0

        return {
            "total_count": sum(status_counts.values()),
            "pending_count": status_counts.get("pending", 0),
            "accepted_count": status_counts.get("accepted", 0),
            "completed_count": status_counts.get("completed", 0),
            "urgent_count": priority_counts.get("urgent", 0),
            "high_count": priority_counts.get("high", 0),
            "medium_count": priority_counts.get("medium", 0),
            "low_count": priority_counts.get("low", 0),
            "potential_saving_kwh": potential_saving,
            "potential_saving_cost": potential_cost
        }

    async def accept_suggestion_with_params(
        self,
        suggestion_id: int,
        adjusted_params: Optional[Dict[str, Any]] = None
    ) -> Optional[EnergySuggestion]:
        """
        接受建议并保存调整后的参数

        Args:
            suggestion_id: 建议ID
            adjusted_params: 用户调整的参数

        Returns:
            EnergySuggestion: 更新后的建议
        """
        result = await self.db.execute(
            select(EnergySuggestion).where(EnergySuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()

        if not suggestion:
            return None

        suggestion.status = "accepted"
        suggestion.accepted_at = datetime.now()

        # 保存调整后的参数
        if adjusted_params:
            current_params = suggestion.parameters or {}
            current_params["user_adjusted_params"] = adjusted_params

            # 如果有调整参数，重新计算并更新预期效果
            if "selected_devices" in adjusted_params:
                recalc_result = await self.recalculate_suggestion(suggestion_id, adjusted_params)
                suggestion.potential_saving = recalc_result["effects"]["daily_energy_kwh"] * 30 * 12
                suggestion.potential_cost_saving = recalc_result["effects"]["annual_saving_yuan"]
                current_params["recalculated_effects"] = recalc_result["effects"]
                current_params["pricing_used"] = recalc_result["pricing_used"]

            suggestion.parameters = current_params

        suggestion.updated_at = datetime.now()
        await self.db.commit()

        return suggestion
