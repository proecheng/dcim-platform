"""
电价配置服务 - 完整电价体系支持
V2.5 扩展版本 - 新增基本电费、功率因数调整、固定费用支持
"""
from datetime import date
from typing import Dict, List, Optional, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import ElectricityPricing, PricingConfig


class PricingService:
    """电价配置服务 - 从数据库查询真实电价配置"""

    # 时段类型标签映射
    PERIOD_LABELS = {
        "sharp": "尖峰",
        "peak": "高峰",
        "normal": "平段",
        "valley": "低谷",
        "deep_valley": "深谷"
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_current_pricing(self) -> Dict[str, List[Dict]]:
        """
        获取当前有效的电价配置，按时段类型分组

        Returns:
            Dict: 按时段类型分组的电价配置
            {
                "sharp": [{"start_time": "10:00", "end_time": "11:00", "price": 1.1, "name": "尖峰电价"}],
                "peak": [...],
                "normal": [...],
                "valley": [...],
                "deep_valley": [...]
            }
        """
        today = date.today()

        # 查询当前有效的电价配置
        result = await self.db.execute(
            select(ElectricityPricing).where(
                and_(
                    ElectricityPricing.is_enabled == True,
                    ElectricityPricing.effective_date <= today,
                    or_(
                        ElectricityPricing.expire_date >= today,
                        ElectricityPricing.expire_date == None
                    )
                )
            ).order_by(ElectricityPricing.start_time)
        )
        pricing_records = result.scalars().all()

        # 按时段类型分组
        pricing_map: Dict[str, List[Dict]] = {
            "sharp": [],
            "peak": [],
            "normal": [],
            "valley": [],
            "deep_valley": []
        }

        for p in pricing_records:
            period_type = p.period_type.lower()
            if period_type not in pricing_map:
                # 处理可能的别名
                if period_type in ["high", "high_peak"]:
                    period_type = "peak"
                elif period_type in ["flat", "mid"]:
                    period_type = "normal"
                elif period_type in ["low", "off_peak"]:
                    period_type = "valley"
                else:
                    period_type = "normal"  # 默认归类

            pricing_map[period_type].append({
                "id": p.id,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "price": float(p.price),
                "name": p.pricing_name
            })

        return pricing_map

    async def get_price_for_period(self, period_type: str) -> float:
        """
        获取指定时段的电价

        Args:
            period_type: 时段类型 (sharp/peak/normal/valley/deep_valley)

        Returns:
            float: 电价（元/kWh），如果未找到返回0.0
        """
        pricing = await self.get_current_pricing()
        periods = pricing.get(period_type.lower(), [])
        if periods:
            return periods[0]["price"]
        return 0.0

    async def get_all_prices(self) -> Dict[str, float]:
        """
        获取所有时段的电价

        Returns:
            Dict: 各时段电价
            {
                "sharp_price": 1.1,
                "peak_price": 0.68,
                "normal_price": 0.425,
                "valley_price": 0.111,
                "deep_valley_price": 0.08
            }
        """
        pricing = await self.get_current_pricing()

        result = {}
        for period_type in ["sharp", "peak", "normal", "valley", "deep_valley"]:
            periods = pricing.get(period_type, [])
            if periods:
                result[f"{period_type}_price"] = periods[0]["price"]
            else:
                result[f"{period_type}_price"] = 0.0

        return result

    async def get_time_periods_for_display(self) -> List[Dict]:
        """
        获取所有时段信息，用于前端下拉选择

        Returns:
            List[Dict]: 时段信息列表，包含标签和时间范围
            [
                {
                    "type": "sharp",
                    "label": "尖峰(10:00-11:00, 13:00-15:00)",
                    "price": 1.1,
                    "time_ranges": [{"start_time": "10:00", "end_time": "11:00", ...}]
                },
                ...
            ]
        """
        pricing = await self.get_current_pricing()
        result = []

        for period_type, periods in pricing.items():
            if periods:
                # 合并时间段显示
                time_ranges = ", ".join([
                    f"{p['start_time']}-{p['end_time']}"
                    for p in periods
                ])
                result.append({
                    "type": period_type,
                    "label": f"{self._get_period_label(period_type)}({time_ranges})",
                    "display_name": self._get_period_label(period_type),
                    "price": periods[0]["price"],
                    "time_ranges": periods
                })

        # 按电价从高到低排序
        result.sort(key=lambda x: x["price"], reverse=True)
        return result

    async def get_price_diff(self, source_period: str, target_period: str) -> float:
        """
        计算两个时段之间的电价差

        Args:
            source_period: 源时段类型
            target_period: 目标时段类型

        Returns:
            float: 电价差（元/kWh）
        """
        source_price = await self.get_price_for_period(source_period)
        target_price = await self.get_price_for_period(target_period)
        return source_price - target_price

    async def get_peak_valley_spread(self) -> Dict[str, Any]:
        """
        获取峰谷电价差分析

        Returns:
            Dict: 峰谷电价差信息
        """
        prices = await self.get_all_prices()

        sharp = prices.get("sharp_price", 0)
        peak = prices.get("peak_price", 0)
        normal = prices.get("normal_price", 0)
        valley = prices.get("valley_price", 0)
        deep_valley = prices.get("deep_valley_price", 0)

        # 计算各种价差
        return {
            "sharp_price": sharp,
            "peak_price": peak,
            "normal_price": normal,
            "valley_price": valley,
            "deep_valley_price": deep_valley,
            "sharp_valley_diff": sharp - valley if sharp and valley else 0,
            "peak_valley_diff": peak - valley if peak and valley else 0,
            "sharp_deep_valley_diff": sharp - deep_valley if sharp and deep_valley else 0,
            "has_sharp": sharp > 0,
            "has_deep_valley": deep_valley > 0,
            "avg_price": (peak + normal + valley) / 3 if (peak and normal and valley) else 0
        }

    async def get_pricing_data_source(self) -> Dict[str, Any]:
        """
        获取电价数据来源信息（用于前端显示数据溯源）

        Returns:
            Dict: 数据来源信息
        """
        today = date.today()

        # 查询有效配置数量
        result = await self.db.execute(
            select(ElectricityPricing).where(
                and_(
                    ElectricityPricing.is_enabled == True,
                    ElectricityPricing.effective_date <= today,
                    or_(
                        ElectricityPricing.expire_date >= today,
                        ElectricityPricing.expire_date == None
                    )
                )
            )
        )
        records = result.scalars().all()

        if not records:
            return {
                "source": "electricity_pricing表",
                "status": "empty",
                "message": "未配置电价数据，请在系统设置中配置电价",
                "config_count": 0,
                "effective_date": None
            }

        # 获取最早生效日期
        earliest_date = min(r.effective_date for r in records)

        return {
            "source": "electricity_pricing表",
            "status": "active",
            "message": "数据来源：系统设置 → 电价配置",
            "config_count": len(records),
            "effective_date": earliest_date.isoformat(),
            "period_types": list(set(r.period_type for r in records))
        }

    def _get_period_label(self, period_type: str) -> str:
        """获取时段类型的中文标签"""
        return self.PERIOD_LABELS.get(period_type, period_type)

    async def calculate_cost_for_energy(
        self,
        energy_kwh: float,
        period_type: str
    ) -> float:
        """
        计算指定时段的电费

        Args:
            energy_kwh: 电量（kWh）
            period_type: 时段类型

        Returns:
            float: 电费（元）
        """
        price = await self.get_price_for_period(period_type)
        return energy_kwh * price

    async def calculate_savings(
        self,
        power_kw: float,
        hours: float,
        source_period: str,
        target_period: str,
        working_days: int = 300
    ) -> Dict[str, float]:
        """
        计算负荷转移的节省金额

        Args:
            power_kw: 转移功率（kW）
            hours: 转移时长（小时）
            source_period: 源时段（高价时段）
            target_period: 目标时段（低价时段）
            working_days: 年工作日数

        Returns:
            Dict: 节省金额详情
        """
        source_price = await self.get_price_for_period(source_period)
        target_price = await self.get_price_for_period(target_period)
        price_diff = source_price - target_price

        daily_energy = power_kw * hours
        daily_saving = daily_energy * price_diff
        annual_saving = daily_saving * working_days

        return {
            "source_price": source_price,
            "target_price": target_price,
            "price_diff": price_diff,
            "daily_energy_kwh": daily_energy,
            "daily_saving_yuan": round(daily_saving, 2),
            "annual_saving_yuan": round(annual_saving, 2),
            "annual_saving_wan": round(annual_saving / 10000, 4)
        }

    # ========== V2.5 完整电价配置（新增）==========

    async def get_current_global_config(self) -> Optional[PricingConfig]:
        """获取当前有效的全局电价配置"""
        today = date.today()
        result = await self.db.execute(
            select(PricingConfig)
            .where(
                and_(
                    PricingConfig.is_enabled == True,
                    PricingConfig.effective_date <= today,
                    or_(
                        PricingConfig.expire_date == None,
                        PricingConfig.expire_date >= today
                    )
                )
            )
            .order_by(PricingConfig.effective_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_full_pricing_config(self) -> Dict[str, Any]:
        """
        获取完整的电价配置（时段电价 + 全局配置）

        返回:
        {
            "time_period_prices": {...},  # 时段电价（兼容旧接口）
            "global_config": {...},        # 全局配置（基本电费、功率因数、固定费用）
            "summary": {...}               # 配置摘要
        }
        """
        # 获取时段电价
        time_prices = await self.get_current_pricing()

        # 获取全局配置
        global_config = await self.get_current_global_config()

        # 构建摘要
        summary = {
            "has_time_prices": any(len(v) > 0 for v in time_prices.values()),
            "has_global_config": global_config is not None,
            "billing_mode": global_config.billing_mode if global_config else None,
            "time_periods_count": sum(len(v) for v in time_prices.values())
        }

        result = {
            "time_period_prices": time_prices,
            "global_config": None,
            "summary": summary
        }

        if global_config:
            result["global_config"] = {
                "id": global_config.id,
                "config_name": global_config.config_name,
                "billing_mode": global_config.billing_mode,
                "demand_price": global_config.demand_price,
                "declared_demand": global_config.declared_demand,
                "over_demand_multiplier": global_config.over_demand_multiplier,
                "capacity_price": global_config.capacity_price,
                "transformer_capacity": global_config.transformer_capacity,
                "power_factor_baseline": global_config.power_factor_baseline,
                "power_factor_rules": global_config.power_factor_rules or [],
                "transmission_fee": global_config.transmission_fee,
                "government_fund": global_config.government_fund,
                "auxiliary_fee": global_config.auxiliary_fee,
                "other_fee": global_config.other_fee,
                "effective_date": global_config.effective_date.isoformat() if global_config.effective_date else None,
                "expire_date": global_config.expire_date.isoformat() if global_config.expire_date else None,
                "description": global_config.description
            }

        return result

    async def update_pricing_config(
        self,
        config_id: Optional[int] = None,
        config_data: Optional[Dict[str, Any]] = None
    ) -> PricingConfig:
        """
        更新或创建全局电价配置

        Args:
            config_id: 配置ID（如果为None则创建新配置）
            config_data: 配置数据

        Returns:
            PricingConfig: 更新/创建后的配置
        """
        if config_id:
            # 更新现有配置
            result = await self.db.execute(
                select(PricingConfig).where(PricingConfig.id == config_id)
            )
            config = result.scalar_one_or_none()
            if not config:
                raise ValueError(f"配置ID {config_id} 不存在")

            # 更新字段
            for key, value in (config_data or {}).items():
                if hasattr(config, key) and value is not None:
                    setattr(config, key, value)

            await self.db.commit()
            await self.db.refresh(config)
            return config
        else:
            # 创建新配置
            config = PricingConfig(**(config_data or {}))
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
            return config

    async def calculate_electricity_bill(
        self,
        energy_by_period: Dict[str, float],
        max_demand: float = 0.0,
        avg_power_factor: float = 0.9,
        include_fixed_fees: bool = True
    ) -> Dict[str, Any]:
        """
        计算完整电费账单

        Args:
            energy_by_period: 各时段用电量 {"sharp": 100, "peak": 200, "normal": 300, "valley": 150}
            max_demand: 当月最大需量 kW
            avg_power_factor: 平均功率因数
            include_fixed_fees: 是否包含固定费用

        Returns:
            {
                "energy_charge": {...},           # 电度电费
                "basic_charge": {...},            # 基本电费
                "power_factor_adjustment": {...}, # 功率因数调整
                "fixed_fees": {...},              # 固定费用
                "total": {...}                    # 汇总
            }
        """
        # 1. 计算电度电费
        prices = await self.get_all_prices()
        energy_charge_detail = {}
        total_energy = 0.0
        total_energy_charge = 0.0

        period_mapping = {
            "sharp": "sharp_price",
            "peak": "peak_price",
            "normal": "normal_price",
            "valley": "valley_price",
            "deep_valley": "deep_valley_price"
        }

        for period, energy in energy_by_period.items():
            price_key = period_mapping.get(period, f"{period}_price")
            price = prices.get(price_key, 0.0)
            charge = energy * price
            energy_charge_detail[period] = {
                "energy_kwh": round(energy, 2),
                "price": price,
                "charge": round(charge, 2)
            }
            total_energy += energy
            total_energy_charge += charge

        energy_charge = {
            "detail": energy_charge_detail,
            "total_energy_kwh": round(total_energy, 2),
            "total_charge": round(total_energy_charge, 2)
        }

        # 2. 获取全局配置
        global_config = await self.get_current_global_config()

        # 3. 计算基本电费
        basic_charge = {"charge": 0.0, "detail": {}}
        if global_config and max_demand > 0:
            if global_config.billing_mode == "demand":
                # 按需量计费
                declared = global_config.declared_demand or 0
                demand_price = global_config.demand_price or 0
                over_multiplier = global_config.over_demand_multiplier or 2.0

                if max_demand <= declared:
                    # 未超需量
                    basic_charge_amount = declared * demand_price
                    basic_charge["detail"] = {
                        "mode": "demand",
                        "declared_demand": declared,
                        "actual_demand": round(max_demand, 2),
                        "demand_price": demand_price,
                        "over_demand": 0,
                        "over_charge": 0
                    }
                else:
                    # 超需量
                    over_demand = max_demand - declared
                    normal_charge = declared * demand_price
                    over_charge = over_demand * demand_price * over_multiplier
                    basic_charge_amount = normal_charge + over_charge
                    basic_charge["detail"] = {
                        "mode": "demand",
                        "declared_demand": declared,
                        "actual_demand": round(max_demand, 2),
                        "demand_price": demand_price,
                        "over_demand": round(over_demand, 2),
                        "over_multiplier": over_multiplier,
                        "normal_charge": round(normal_charge, 2),
                        "over_charge": round(over_charge, 2)
                    }
                basic_charge["charge"] = round(basic_charge_amount, 2)

            elif global_config.billing_mode == "capacity":
                # 按容量计费
                capacity = global_config.transformer_capacity or 0
                capacity_price = global_config.capacity_price or 0
                basic_charge_amount = capacity * capacity_price
                basic_charge["charge"] = round(basic_charge_amount, 2)
                basic_charge["detail"] = {
                    "mode": "capacity",
                    "transformer_capacity": capacity,
                    "capacity_price": capacity_price
                }

        # 4. 计算功率因数调整
        pf_adjustment = {"adjustment_rate": 0.0, "adjustment_amount": 0.0}
        if global_config and global_config.power_factor_rules:
            rules = global_config.power_factor_rules
            adjustment_rate = 0.0

            # 查找适用的功率因数规则
            for rule in rules:
                rule_min = rule.get("min", 0)
                rule_max = rule.get("max", 1.0)
                if rule_min <= avg_power_factor < rule_max:
                    adjustment_rate = rule.get("adjustment", 0)
                    break

            # 功率因数调整基数 = 电度电费 + 基本电费
            adjustment_base = total_energy_charge + basic_charge["charge"]
            adjustment_amount = adjustment_base * (adjustment_rate / 100)

            pf_adjustment = {
                "power_factor": round(avg_power_factor, 3),
                "baseline": global_config.power_factor_baseline,
                "adjustment_rate": adjustment_rate,
                "adjustment_base": round(adjustment_base, 2),
                "adjustment_amount": round(adjustment_amount, 2)
            }

        # 5. 计算固定费用
        fixed_fees = {"total": 0.0, "detail": {}}
        if include_fixed_fees and global_config:
            transmission = total_energy * (global_config.transmission_fee or 0)
            government = total_energy * (global_config.government_fund or 0)
            auxiliary = total_energy * (global_config.auxiliary_fee or 0)
            other = total_energy * (global_config.other_fee or 0)
            fixed_total = transmission + government + auxiliary + other

            fixed_fees = {
                "total": round(fixed_total, 2),
                "detail": {
                    "transmission_fee": round(transmission, 2),
                    "government_fund": round(government, 2),
                    "auxiliary_fee": round(auxiliary, 2),
                    "other_fee": round(other, 2)
                },
                "rates": {
                    "transmission_fee": global_config.transmission_fee or 0,
                    "government_fund": global_config.government_fund or 0,
                    "auxiliary_fee": global_config.auxiliary_fee or 0,
                    "other_fee": global_config.other_fee or 0
                },
                "note": "固定费用不参与优化，仅用于成本统计"
            }

        # 6. 汇总
        optimizable_total = (
            total_energy_charge +
            basic_charge["charge"] +
            pf_adjustment.get("adjustment_amount", 0)
        )
        grand_total = optimizable_total + fixed_fees["total"]

        total = {
            "energy_charge": round(total_energy_charge, 2),
            "basic_charge": round(basic_charge["charge"], 2),
            "power_factor_adjustment": round(pf_adjustment.get("adjustment_amount", 0), 2),
            "fixed_fees": round(fixed_fees["total"], 2),
            "optimizable_total": round(optimizable_total, 2),
            "grand_total": round(grand_total, 2),
            "unit_price": round(grand_total / total_energy, 4) if total_energy > 0 else 0
        }

        return {
            "energy_charge": energy_charge,
            "basic_charge": basic_charge,
            "power_factor_adjustment": pf_adjustment,
            "fixed_fees": fixed_fees,
            "total": total
        }

    async def estimate_savings(
        self,
        current_energy_by_period: Dict[str, float],
        current_max_demand: float,
        optimized_energy_by_period: Dict[str, float],
        optimized_max_demand: float,
        avg_power_factor: float = 0.9
    ) -> Dict[str, Any]:
        """
        估算优化后的节省金额

        Args:
            current_energy_by_period: 当前各时段用电量
            current_max_demand: 当前最大需量
            optimized_energy_by_period: 优化后各时段用电量
            optimized_max_demand: 优化后最大需量
            avg_power_factor: 平均功率因数

        Returns:
            节省金额详情
        """
        # 计算当前电费（不含固定费用）
        current_bill = await self.calculate_electricity_bill(
            current_energy_by_period,
            current_max_demand,
            avg_power_factor,
            include_fixed_fees=False
        )

        # 计算优化后电费
        optimized_bill = await self.calculate_electricity_bill(
            optimized_energy_by_period,
            optimized_max_demand,
            avg_power_factor,
            include_fixed_fees=False
        )

        # 计算节省
        savings = {
            "energy_charge": round(
                current_bill["total"]["energy_charge"] - optimized_bill["total"]["energy_charge"],
                2
            ),
            "basic_charge": round(
                current_bill["total"]["basic_charge"] - optimized_bill["total"]["basic_charge"],
                2
            ),
            "power_factor_adjustment": round(
                current_bill["total"]["power_factor_adjustment"] -
                optimized_bill["total"]["power_factor_adjustment"],
                2
            ),
            "total": round(
                current_bill["total"]["optimizable_total"] - optimized_bill["total"]["optimizable_total"],
                2
            )
        }

        # 计算节省比例
        savings["percentage"] = round(
            (savings["total"] / current_bill["total"]["optimizable_total"] * 100)
            if current_bill["total"]["optimizable_total"] > 0 else 0,
            2
        )

        return {
            "current_bill": current_bill["total"],
            "optimized_bill": optimized_bill["total"],
            "savings": savings
        }

