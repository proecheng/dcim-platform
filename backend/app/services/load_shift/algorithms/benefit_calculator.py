"""
Benefit Calculator - Calculate cost and energy savings for shift plans
效益计算器 - 计算转移计划的成本和节能效益
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, time, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import PowerDevice, ElectricityPricing
from app.schemas.load_shift import (
    FeasibilityAnalysisRequest,
    BenefitAnalysisResponse,
    ShiftPeriodType
)


class BenefitCalculator:
    """Benefit calculator - 效益计算器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_benefits(
        self,
        request: FeasibilityAnalysisRequest,
        device_ids: List[int],
        shift_duration_hours: float = 1.0
    ) -> BenefitAnalysisResponse:
        """
        Calculate benefits for shift plan - 计算转移计划效益
        
        Args:
            request: Feasibility analysis request
            device_ids: List of device IDs
            shift_duration_hours: Shift duration in hours
            
        Returns:
            Benefit analysis response
        """
        # Load devices
        devices = await self._load_devices(device_ids)
        
        # Load electricity pricing
        pricing = await self._load_pricing()
        
        # Calculate total shift power
        total_shift_power = sum(d.rated_power or 0 for d in devices)
        actual_shift_power = min(total_shift_power, request.target_shift_power)
        
        # Calculate energy saving
        energy_saving = actual_shift_power * shift_duration_hours  # kWh
        
        # Calculate cost saving
        cost_saving = await self._calculate_cost_saving(
            request.shift_from_period,
            request.shift_to_period,
            energy_saving,
            pricing
        )
        
        # Calculate peak reduction and valley filling
        peak_reduction = 0.0
        valley_filling = 0.0
        
        if request.shift_from_period in [ShiftPeriodType.PEAK, ShiftPeriodType.SHARP]:
            peak_reduction = actual_shift_power
        
        if request.shift_to_period == ShiftPeriodType.VALLEY:
            valley_filling = actual_shift_power
        
        # Calculate ROI (if investment data available)
        # For Phase 1, we assume no additional investment
        payback_period_days = None
        roi = None
        
        # Build benefit details
        benefit_details = {
            "total_shift_power": actual_shift_power,
            "shift_duration_hours": shift_duration_hours,
            "energy_saving_kwh": energy_saving,
            "cost_saving_yuan": cost_saving,
            "peak_reduction_kw": peak_reduction,
            "valley_filling_kw": valley_filling,
            "from_period": request.shift_from_period.value,
            "to_period": request.shift_to_period.value,
            "from_period_price": await self._get_period_price(request.shift_from_period, pricing),
            "to_period_price": await self._get_period_price(request.shift_to_period, pricing),
            "device_count": len(devices),
            "calculation_method": "simple_price_difference"
        }
        
        return BenefitAnalysisResponse(
            cost_saving=cost_saving,
            energy_saving=energy_saving,
            peak_reduction=peak_reduction,
            valley_filling=valley_filling,
            payback_period_days=payback_period_days,
            roi=roi,
            benefit_details=benefit_details
        )

    async def _load_devices(self, device_ids: List[int]) -> List[PowerDevice]:
        """Load device information - 加载设备信息"""
        result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id.in_(device_ids))
        )
        return result.scalars().all()

    async def _load_pricing(self) -> Optional[ElectricityPricing]:
        """
        Load electricity pricing - 加载电价配置
        
        Returns:
            Latest active pricing or None
        """
        result = await self.db.execute(
            select(ElectricityPricing)
            .where(ElectricityPricing.is_active == True)
            .order_by(ElectricityPricing.effective_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _calculate_cost_saving(
        self,
        from_period: ShiftPeriodType,
        to_period: ShiftPeriodType,
        energy_kwh: float,
        pricing: Optional[ElectricityPricing]
    ) -> float:
        """
        Calculate cost saving - 计算成本节省
        
        Args:
            from_period: Shift from period
            to_period: Shift to period
            energy_kwh: Energy amount in kWh
            pricing: Electricity pricing
            
        Returns:
            Cost saving in yuan
        """
        if not pricing:
            # Use default prices if no pricing configured
            default_prices = {
                ShiftPeriodType.SHARP: 1.2,    # 尖峰 1.2元/kWh
                ShiftPeriodType.PEAK: 1.0,     # 高峰 1.0元/kWh
                ShiftPeriodType.FLAT: 0.6,     # 平段 0.6元/kWh
                ShiftPeriodType.VALLEY: 0.3    # 谷段 0.3元/kWh
            }
            from_price = default_prices.get(from_period, 0.6)
            to_price = default_prices.get(to_period, 0.6)
        else:
            from_price = self._get_price_from_pricing(from_period, pricing)
            to_price = self._get_price_from_pricing(to_period, pricing)
        
        # Cost saving = (from_price - to_price) * energy_kwh
        cost_saving = (from_price - to_price) * energy_kwh
        
        return max(0, cost_saving)  # Ensure non-negative

    def _get_price_from_pricing(
        self,
        period: ShiftPeriodType,
        pricing: ElectricityPricing
    ) -> float:
        """
        Get price for period from pricing - 从电价配置获取时段价格
        
        Args:
            period: Shift period type
            pricing: Electricity pricing
            
        Returns:
            Price in yuan/kWh
        """
        period_map = {
            ShiftPeriodType.SHARP: pricing.sharp_price,
            ShiftPeriodType.PEAK: pricing.peak_price,
            ShiftPeriodType.FLAT: pricing.flat_price,
            ShiftPeriodType.VALLEY: pricing.valley_price
        }
        return period_map.get(period, pricing.flat_price or 0.6)

    async def _get_period_price(
        self,
        period: ShiftPeriodType,
        pricing: Optional[ElectricityPricing]
    ) -> float:
        """
        Get period price - 获取时段价格
        
        Args:
            period: Shift period type
            pricing: Electricity pricing
            
        Returns:
            Price in yuan/kWh
        """
        if not pricing:
            default_prices = {
                ShiftPeriodType.SHARP: 1.2,
                ShiftPeriodType.PEAK: 1.0,
                ShiftPeriodType.FLAT: 0.6,
                ShiftPeriodType.VALLEY: 0.3
            }
            return default_prices.get(period, 0.6)
        
        return self._get_price_from_pricing(period, pricing)

    async def calculate_monthly_benefits(
        self,
        year: int,
        month: int,
        total_shift_power: float,
        total_energy_saving: float,
        total_cost_saving: float,
        plan_count: int
    ) -> Dict[str, Any]:
        """
        Calculate monthly benefits summary - 计算月度效益汇总
        
        Args:
            year: Year
            month: Month
            total_shift_power: Total shift power in kW
            total_energy_saving: Total energy saving in kWh
            total_cost_saving: Total cost saving in yuan
            plan_count: Number of plans
            
        Returns:
            Monthly benefits summary
        """
        # Calculate average per plan
        avg_shift_power = total_shift_power / plan_count if plan_count > 0 else 0
        avg_energy_saving = total_energy_saving / plan_count if plan_count > 0 else 0
        avg_cost_saving = total_cost_saving / plan_count if plan_count > 0 else 0
        
        # Calculate equivalent CO2 reduction (0.785 kg CO2/kWh)
        co2_reduction_kg = total_energy_saving * 0.785
        co2_reduction_tons = co2_reduction_kg / 1000
        
        # Calculate equivalent coal saving (0.4 kg coal/kWh)
        coal_saving_kg = total_energy_saving * 0.4
        coal_saving_tons = coal_saving_kg / 1000
        
        return {
            "year": year,
            "month": month,
            "plan_count": plan_count,
            "total_shift_power_kw": total_shift_power,
            "total_energy_saving_kwh": total_energy_saving,
            "total_cost_saving_yuan": total_cost_saving,
            "avg_shift_power_kw": avg_shift_power,
            "avg_energy_saving_kwh": avg_energy_saving,
            "avg_cost_saving_yuan": avg_cost_saving,
            "co2_reduction_tons": co2_reduction_tons,
            "coal_saving_tons": coal_saving_tons,
            "environmental_benefits": {
                "co2_reduction_kg": co2_reduction_kg,
                "coal_saving_kg": coal_saving_kg,
                "equivalent_trees_planted": int(co2_reduction_tons * 50)  # 1 ton CO2 = 50 trees
            }
        }

    async def calculate_yearly_benefits(
        self,
        year: int,
        monthly_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate yearly benefits summary - 计算年度效益汇总
        
        Args:
            year: Year
            monthly_data: List of monthly benefit data
            
        Returns:
            Yearly benefits summary
        """
        total_plans = sum(m["plan_count"] for m in monthly_data)
        total_shift_power = sum(m["total_shift_power_kw"] for m in monthly_data)
        total_energy_saving = sum(m["total_energy_saving_kwh"] for m in monthly_data)
        total_cost_saving = sum(m["total_cost_saving_yuan"] for m in monthly_data)
        total_co2_reduction = sum(m["co2_reduction_tons"] for m in monthly_data)
        total_coal_saving = sum(m["coal_saving_tons"] for m in monthly_data)
        
        # Calculate monthly averages
        months_with_data = len([m for m in monthly_data if m["plan_count"] > 0])
        avg_monthly_plans = total_plans / months_with_data if months_with_data > 0 else 0
        avg_monthly_saving = total_cost_saving / months_with_data if months_with_data > 0 else 0
        
        # Find best and worst months
        best_month = max(monthly_data, key=lambda m: m["total_cost_saving_yuan"]) if monthly_data else None
        worst_month = min(monthly_data, key=lambda m: m["total_cost_saving_yuan"]) if monthly_data else None
        
        return {
            "year": year,
            "total_plans": total_plans,
            "total_shift_power_kw": total_shift_power,
            "total_energy_saving_kwh": total_energy_saving,
            "total_cost_saving_yuan": total_cost_saving,
            "total_co2_reduction_tons": total_co2_reduction,
            "total_coal_saving_tons": total_coal_saving,
            "avg_monthly_plans": avg_monthly_plans,
            "avg_monthly_saving_yuan": avg_monthly_saving,
            "best_month": {
                "month": best_month["month"],
                "cost_saving": best_month["total_cost_saving_yuan"]
            } if best_month else None,
            "worst_month": {
                "month": worst_month["month"],
                "cost_saving": worst_month["total_cost_saving_yuan"]
            } if worst_month else None,
            "environmental_impact": {
                "co2_reduction_tons": total_co2_reduction,
                "coal_saving_tons": total_coal_saving,
                "equivalent_trees_planted": int(total_co2_reduction * 50),
                "equivalent_cars_off_road": int(total_co2_reduction / 2.3)  # 1 car = 2.3 tons CO2/year
            }
        }
