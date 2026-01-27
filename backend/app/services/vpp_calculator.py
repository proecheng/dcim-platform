"""
VPP Calculator Service
虚拟电厂指标计算服务

This service implements all VPP calculation methods with:
- Clear formulas for each metric
- Data source tracking
- Proper async/await patterns
- Comprehensive docstrings
"""
from typing import List, Dict, Optional
from datetime import date, datetime
from decimal import Decimal
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.vpp_data import (
    ElectricityBill,
    LoadCurve,
    ElectricityPrice,
    AdjustableLoad,
    VPPConfig,
    TimePeriodType
)


class VPPCalculator:
    """VPP方案计算器 - 所有指标均有明确数据来源和计算公式"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== A. 用电规模指标 ====================

    async def calc_average_price(self, month: str) -> Dict:
        """A1. 计算平均电价

        公式: average_price = total_cost / total_consumption
        数据来源: electricity_bills表

        Args:
            month: 月份 (YYYY-MM格式)

        Returns:
            {
                "value": 计算值,
                "unit": "元/kWh",
                "formula": "total_cost / total_consumption",
                "data_source": {源数据字典}
            }
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {
                "value": 0,
                "unit": "元/kWh",
                "formula": "total_cost / total_consumption",
                "data_source": {"error": "无数据", "month": month}
            }

        value = bill.total_cost / bill.total_consumption if bill.total_consumption > 0 else 0
        return {
            "value": round(value, 4),
            "unit": "元/kWh",
            "formula": "total_cost / total_consumption",
            "data_source": {
                "total_cost": bill.total_cost,
                "total_consumption": bill.total_consumption,
                "month": month
            }
        }

    async def calc_fluctuation_rate(self, months: List[str]) -> Dict:
        """A2. 计算月度用电波动率

        公式: (max - min) / avg * 100
        数据来源: electricity_bills表 (多月数据)

        Args:
            months: 月份列表 ["2025-01", "2025-02", ...]

        Returns:
            波动率指标字典
        """
        result = await self.db.execute(
            select(ElectricityBill.total_consumption)
            .where(ElectricityBill.month.in_(months))
        )
        consumptions = [r[0] for r in result.fetchall()]

        if len(consumptions) < 2:
            return {
                "value": 0,
                "unit": "%",
                "formula": "(max - min) / avg * 100",
                "data_source": {"error": "数据不足", "months_count": len(consumptions)}
            }

        max_val = max(consumptions)
        min_val = min(consumptions)
        avg_val = statistics.mean(consumptions)
        rate = (max_val - min_val) / avg_val * 100 if avg_val > 0 else 0

        return {
            "value": round(rate, 2),
            "unit": "%",
            "formula": "(max(consumption) - min(consumption)) / avg(consumption) * 100",
            "data_source": {
                "max_consumption": max_val,
                "min_consumption": min_val,
                "avg_consumption": round(avg_val, 2),
                "months_count": len(consumptions),
                "months": months
            }
        }

    async def calc_peak_ratio(self, month: str) -> Dict:
        """A3. 计算峰段用电占比

        公式: peak_consumption / total_consumption * 100
        数据来源: electricity_bills表

        Args:
            month: 月份 (YYYY-MM格式)

        Returns:
            峰段占比指标字典
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {
                "value": 0,
                "unit": "%",
                "formula": "peak_consumption / total_consumption * 100",
                "data_source": {"error": "无数据", "month": month}
            }

        ratio = bill.peak_consumption / bill.total_consumption * 100 if bill.total_consumption > 0 else 0
        return {
            "value": round(ratio, 2),
            "unit": "%",
            "formula": "peak_consumption / total_consumption * 100",
            "data_source": {
                "peak_consumption": bill.peak_consumption,
                "total_consumption": bill.total_consumption,
                "month": month
            }
        }

    async def calc_valley_ratio(self, month: str) -> Dict:
        """A4. 计算谷段用电占比

        公式: valley_consumption / total_consumption * 100
        数据来源: electricity_bills表

        Args:
            month: 月份 (YYYY-MM格式)

        Returns:
            谷段占比指标字典
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {
                "value": 0,
                "unit": "%",
                "formula": "valley_consumption / total_consumption * 100",
                "data_source": {"error": "无数据", "month": month}
            }

        ratio = bill.valley_consumption / bill.total_consumption * 100 if bill.total_consumption > 0 else 0
        return {
            "value": round(ratio, 2),
            "unit": "%",
            "formula": "valley_consumption / total_consumption * 100",
            "data_source": {
                "valley_consumption": bill.valley_consumption,
                "total_consumption": bill.total_consumption,
                "month": month
            }
        }

    # ==================== B. 负荷特性指标 ====================

    async def calc_load_metrics(self, start_date: date, end_date: date) -> Dict:
        """B1-B6. 计算所有负荷特性指标

        包括:
        - B1. P_max: 最大负荷
        - B2. P_avg: 平均负荷
        - B3. P_min: 最小负荷
        - B4. load_rate: 日负荷率 (η = P_avg / P_max)
        - B5. peak_valley_diff: 峰谷差 (ΔP = P_max - P_min)
        - B6. load_std: 负荷标准差

        数据来源: load_curves表

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            负荷特性指标字典
        """
        result = await self.db.execute(
            select(LoadCurve.load_value)
            .where(LoadCurve.date >= start_date)
            .where(LoadCurve.date <= end_date)
        )
        loads = [r[0] for r in result.fetchall() if r[0] is not None]

        if not loads:
            return {
                "error": "无负荷数据",
                "data_source": {
                    "date_range": f"{start_date} to {end_date}",
                    "data_points": 0
                }
            }

        P_max = max(loads)
        P_min = min(loads)
        P_avg = statistics.mean(loads)
        load_rate = P_avg / P_max if P_max > 0 else 0
        peak_valley_diff = P_max - P_min
        load_std = statistics.stdev(loads) if len(loads) > 1 else 0

        return {
            "P_max": {
                "value": round(P_max, 2),
                "unit": "kW",
                "formula": "max(load_value)",
                "description": "最大负荷"
            },
            "P_avg": {
                "value": round(P_avg, 2),
                "unit": "kW",
                "formula": "sum(load_value) / count(load_value)",
                "description": "平均负荷"
            },
            "P_min": {
                "value": round(P_min, 2),
                "unit": "kW",
                "formula": "min(load_value)",
                "description": "最小负荷"
            },
            "load_rate": {
                "value": round(load_rate, 4),
                "unit": "-",
                "formula": "P_avg / P_max",
                "description": "日负荷率",
                "typical_range": "0.65-0.85"
            },
            "peak_valley_diff": {
                "value": round(peak_valley_diff, 2),
                "unit": "kW",
                "formula": "P_max - P_min",
                "description": "峰谷差"
            },
            "load_std": {
                "value": round(load_std, 2),
                "unit": "kW",
                "formula": "sqrt(sum((load - P_avg)^2) / n)",
                "description": "负荷标准差"
            },
            "data_source": {
                "table": "load_curves",
                "date_range": f"{start_date} to {end_date}",
                "data_points": len(loads)
            }
        }

    # ==================== C. 电费结构指标 ====================

    async def calc_cost_structure(self, month: str) -> Dict:
        """C1-C3. 计算电费结构占比

        包括:
        - C1. 市场化购电占比
        - C2. 输配电费占比
        - C3. 基本电费占比
        - 系统运行费占比
        - 政府性基金占比

        数据来源: electricity_bills表

        Args:
            month: 月份 (YYYY-MM格式)

        Returns:
            电费结构指标字典
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {
                "error": "无电费数据",
                "data_source": {"month": month}
            }

        total = bill.total_cost
        return {
            "market_ratio": {
                "value": round(bill.market_purchase_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "market_purchase_fee / total_cost * 100",
                "typical_range": "65%-72%"
            },
            "transmission_ratio": {
                "value": round(bill.transmission_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "transmission_fee / total_cost * 100",
                "typical_range": "22%-25%"
            },
            "basic_fee_ratio": {
                "value": round(bill.basic_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "basic_fee / total_cost * 100"
            },
            "system_operation_ratio": {
                "value": round(bill.system_operation_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "system_operation_fee / total_cost * 100",
                "typical_range": "3%-5%"
            },
            "government_fund_ratio": {
                "value": round(bill.government_fund / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "government_fund / total_cost * 100",
                "typical_range": "3%-4%"
            },
            "data_source": {
                "table": "electricity_bills",
                "month": month,
                "total_cost": total
            }
        }

    # ==================== D. 峰谷转移潜力指标 ====================

    async def calc_transfer_potential(self) -> Dict:
        """D1-D3. 计算峰谷转移潜力

        包括:
        - D1. 可转移负荷量
        - D2. 峰谷电价差
        - D3. 峰谷转移年收益潜力

        数据来源: adjustable_loads表, electricity_prices表, vpp_configs表

        Returns:
            峰谷转移潜力指标字典
        """
        # D1. 获取可调节负荷
        result = await self.db.execute(
            select(AdjustableLoad).where(AdjustableLoad.is_active == True)
        )
        loads = result.scalars().all()

        transferable_load = sum(
            load.rated_power * load.adjustable_ratio / 100
            for load in loads
        )

        # D2. 获取峰谷电价差
        price_result = await self.db.execute(select(ElectricityPrice))
        prices = {p.period_type.value: p.price for p in price_result.scalars().all()}

        peak_price = prices.get("peak", 0.85)  # 默认值
        valley_price = prices.get("valley", 0.35)  # 默认值
        price_spread = peak_price - valley_price

        # 获取配置参数
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key == "daily_shift_hours")
        )
        config = config_result.scalar_one_or_none()
        daily_shift_hours = config.config_value if config else 4  # 默认4小时

        # D3. 计算年收益潜力
        annual_benefit = transferable_load * daily_shift_hours * 365 * price_spread

        return {
            "transferable_load": {
                "value": round(transferable_load, 2),
                "unit": "kW",
                "formula": "sum(rated_power * adjustable_ratio / 100)",
                "description": "可转移负荷量"
            },
            "price_spread": {
                "value": round(price_spread, 4),
                "unit": "元/kWh",
                "formula": "peak_price - valley_price",
                "data_source": {
                    "peak_price": peak_price,
                    "valley_price": valley_price
                }
            },
            "annual_transfer_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年",
                "formula": "transferable_load * daily_shift_hours * 365 * price_spread",
                "parameters": {
                    "daily_shift_hours": daily_shift_hours
                }
            },
            "data_source": {
                "adjustable_loads_count": len(loads),
                "price_table": "electricity_prices"
            }
        }

    # ==================== E. 需量优化指标 ====================

    async def calc_demand_optimization(self, P_max: float) -> Dict:
        """E1-E2. 计算需量优化潜力

        包括:
        - E1. 削峰空间
        - E2. 需量优化年收益

        数据来源: vpp_configs表

        Args:
            P_max: 最大负荷 (kW)

        Returns:
            需量优化指标字典
        """
        # 获取配置参数
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key.in_(["target_demand_ratio", "demand_price"]))
        )
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        target_ratio = configs.get("target_demand_ratio", 0.9)  # 默认削减10%
        demand_price = configs.get("demand_price", 40)  # 默认40元/kW/月

        target_demand = P_max * target_ratio
        peak_reduction = P_max - target_demand
        annual_benefit = peak_reduction * demand_price * 12

        return {
            "peak_reduction_potential": {
                "value": round(peak_reduction, 2),
                "unit": "kW",
                "formula": "P_max - target_demand",
                "description": "削峰空间"
            },
            "demand_optimization_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年",
                "formula": "peak_reduction * demand_price * 12",
                "description": "需量优化年收益"
            },
            "parameters": {
                "P_max": P_max,
                "target_demand": round(target_demand, 2),
                "target_ratio": target_ratio,
                "demand_price": demand_price
            }
        }

    # ==================== F. 虚拟电厂收益指标 ====================

    async def calc_vpp_revenue(self, adjustable_capacity: float) -> Dict:
        """F1-F4. 计算VPP各类收益

        包括:
        - F1. 需求响应收益
        - F2. 辅助服务收益
        - F3. 现货市场套利收益
        - F4. VPP年总收益

        数据来源: vpp_configs表

        Args:
            adjustable_capacity: 可调节容量 (kW)

        Returns:
            VPP收益指标字典
        """
        # 获取配置参数
        config_result = await self.db.execute(select(VPPConfig))
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        # F1. 需求响应收益
        response_count = configs.get("response_count", 20)  # 年响应次数
        response_price = configs.get("response_price", 4)  # 响应补贴 元/kW
        demand_response_revenue = adjustable_capacity * response_count * response_price

        # F2. 辅助服务收益
        service_hours = configs.get("service_hours", 200)  # 年服务小时数
        service_price = configs.get("service_price", 0.75)  # 服务价格 元/kW·h
        ancillary_service_revenue = adjustable_capacity * service_hours * service_price

        # F3. 现货市场套利
        arbitrage_hours = configs.get("arbitrage_hours", 500)  # 年套利小时数
        price_spread_spot = configs.get("price_spread_spot", 0.3)  # 现货价差
        spot_arbitrage_revenue = adjustable_capacity * arbitrage_hours * price_spread_spot

        # F4. VPP总收益
        total_vpp_revenue = demand_response_revenue + ancillary_service_revenue + spot_arbitrage_revenue

        return {
            "demand_response_revenue": {
                "value": round(demand_response_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * response_count * response_price",
                "parameters": {
                    "adjustable_capacity": adjustable_capacity,
                    "response_count": response_count,
                    "response_price": response_price
                }
            },
            "ancillary_service_revenue": {
                "value": round(ancillary_service_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * service_hours * service_price",
                "parameters": {
                    "service_hours": service_hours,
                    "service_price": service_price
                }
            },
            "spot_arbitrage_revenue": {
                "value": round(spot_arbitrage_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * arbitrage_hours * price_spread_spot",
                "parameters": {
                    "arbitrage_hours": arbitrage_hours,
                    "price_spread_spot": price_spread_spot
                }
            },
            "total_vpp_revenue": {
                "value": round(total_vpp_revenue, 2),
                "unit": "元/年",
                "formula": "demand_response + ancillary_service + spot_arbitrage"
            }
        }

    # ==================== G. 投资回报指标 ====================

    async def calc_roi(self, annual_benefit: float) -> Dict:
        """G1-G4. 计算投资回报指标

        包括:
        - G1. 总投资额
        - G2. 年总收益
        - G3. 静态投资回收期
        - G4. 投资收益率 (ROI)

        数据来源: vpp_configs表

        Args:
            annual_benefit: 年总收益 (元)

        Returns:
            投资回报指标字典
        """
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key.in_([
                "monitoring_system_cost", "control_system_cost",
                "platform_cost", "other_cost"
            ]))
        )
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        monitoring_cost = configs.get("monitoring_system_cost", 500000)
        control_cost = configs.get("control_system_cost", 800000)
        platform_cost = configs.get("platform_cost", 200000)
        other_cost = configs.get("other_cost", 100000)

        total_investment = monitoring_cost + control_cost + platform_cost + other_cost
        payback_period = total_investment / annual_benefit if annual_benefit > 0 else float('inf')
        roi = annual_benefit / total_investment * 100 if total_investment > 0 else 0

        return {
            "total_investment": {
                "value": round(total_investment, 2),
                "unit": "元",
                "formula": "monitoring + control + platform + other",
                "breakdown": {
                    "monitoring_system": monitoring_cost,
                    "control_system": control_cost,
                    "platform": platform_cost,
                    "other": other_cost
                }
            },
            "annual_total_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年"
            },
            "payback_period": {
                "value": round(payback_period, 2) if payback_period != float('inf') else 0,
                "unit": "年",
                "formula": "total_investment / annual_benefit"
            },
            "roi": {
                "value": round(roi, 2),
                "unit": "%",
                "formula": "annual_benefit / total_investment * 100"
            }
        }

    # ==================== H. 综合分析报告 ====================

    async def generate_full_analysis(
        self,
        months: List[str],
        start_date: date,
        end_date: date
    ) -> Dict:
        """生成完整的VPP方案分析报告

        汇总所有指标及其数据来源和计算公式

        Args:
            months: 月份列表 ["2025-01", "2025-02", ...]
            start_date: 负荷数据开始日期
            end_date: 负荷数据结束日期

        Returns:
            完整分析报告字典
        """
        # 获取负荷指标
        load_metrics = await self.calc_load_metrics(start_date, end_date)
        P_max = load_metrics.get("P_max", {}).get("value", 0)

        # 获取峰谷转移潜力
        transfer = await self.calc_transfer_potential()
        transferable_load = transfer.get("transferable_load", {}).get("value", 0)

        # 获取需量优化
        demand_opt = await self.calc_demand_optimization(P_max)

        # 获取VPP收益
        vpp_revenue = await self.calc_vpp_revenue(transferable_load)

        # 计算年总收益
        annual_transfer_benefit = transfer.get("annual_transfer_benefit", {}).get("value", 0)
        demand_benefit = demand_opt.get("demand_optimization_benefit", {}).get("value", 0)
        total_vpp = vpp_revenue.get("total_vpp_revenue", {}).get("value", 0)
        annual_total_benefit = annual_transfer_benefit + demand_benefit + total_vpp

        # 计算ROI
        roi = await self.calc_roi(annual_total_benefit)

        # 电费结构 (使用最近月份)
        cost_structure = await self.calc_cost_structure(months[-1]) if months else {}

        return {
            "analysis_period": {
                "months": months,
                "load_data_range": f"{start_date} to {end_date}"
            },
            "electricity_usage": {
                "average_price": await self.calc_average_price(months[-1]) if months else {},
                "fluctuation_rate": await self.calc_fluctuation_rate(months),
                "peak_ratio": await self.calc_peak_ratio(months[-1]) if months else {},
                "valley_ratio": await self.calc_valley_ratio(months[-1]) if months else {}
            },
            "load_characteristics": load_metrics,
            "cost_structure": cost_structure,
            "transfer_potential": transfer,
            "demand_optimization": demand_opt,
            "vpp_revenue": vpp_revenue,
            "investment_return": roi,
            "summary": {
                "annual_total_benefit": {
                    "value": round(annual_total_benefit, 2),
                    "unit": "元/年",
                    "formula": "transfer_benefit + demand_benefit + vpp_revenue",
                    "breakdown": {
                        "峰谷转移收益": annual_transfer_benefit,
                        "需量优化收益": demand_benefit,
                        "VPP参与收益": total_vpp
                    }
                },
                "payback_period": roi.get("payback_period"),
                "roi": roi.get("roi")
            }
        }
