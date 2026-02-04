"""
Demo 数据提供服务 - 统一的模拟数据生成入口

所有需要模拟数据的地方都应通过此服务获取，而非直接使用 random。
可通过配置 SIMULATION_ENABLED 控制是否启用模拟数据。

使用方式：
    from app.services.demo_data_provider import demo_provider

    # 获取实时需量状态（自动判断是否使用模拟数据）
    status = await demo_provider.get_realtime_demand_status(db, declared_demand)
"""
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from ..core.config import get_settings


class DemoDataProvider:
    """Demo 数据提供服务

    集中管理所有模拟数据的生成，便于：
    1. 统一控制是否启用 Demo 模式
    2. 生成一致的、可预测的模拟数据
    3. 便于切换到真实数据源
    """

    def __init__(self):
        self._settings = None

    @property
    def settings(self):
        """延迟获取配置"""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def is_demo_mode(self) -> bool:
        """是否处于 Demo 模式"""
        return self.settings.simulation_enabled

    def _get_deterministic_value(self, seed_value: float, min_val: float, max_val: float,
                                  variation: float = 0.1) -> float:
        """基于种子值生成确定性数值（避免使用 random）

        使用正弦函数产生周期性波动，确保相同输入产生相同输出
        """
        # 使用时间戳的小数部分作为相位
        phase = (seed_value * 1000) % (2 * math.pi)
        normalized = (math.sin(phase) + 1) / 2  # 0-1 范围

        # 计算中心值和波动范围
        center = (min_val + max_val) / 2
        range_half = (max_val - min_val) / 2 * variation

        return center + (normalized - 0.5) * 2 * range_half

    def _get_time_factor(self, dt: datetime) -> float:
        """根据时间获取负荷因子

        模拟典型数据中心的日负荷曲线:
        - 尖峰时段 (10-12, 14-17): 负荷最高
        - 高峰时段 (8-10, 12-14, 17-21): 负荷较高
        - 平段 (7-8, 21-23): 负荷中等
        - 低谷 (23-7): 负荷最低
        """
        hour = dt.hour
        minute = dt.minute

        # 平滑的时间因子（避免阶跃变化）
        hour_decimal = hour + minute / 60.0

        # 基于24小时周期的负荷曲线
        # 使用组合正弦波模拟真实负荷曲线
        base_factor = 0.6

        # 日间高峰（中心在12点和17点）
        day_peak = 0.25 * (
            math.exp(-((hour_decimal - 11) ** 2) / 8) +  # 午间高峰
            math.exp(-((hour_decimal - 17) ** 2) / 6)    # 傍晚高峰
        )

        # 夜间低谷
        if hour_decimal < 6 or hour_decimal > 22:
            base_factor = 0.35
            day_peak = 0

        return min(0.98, base_factor + day_peak)

    def get_demo_demand_status(self, declared_demand: float,
                                timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """生成 Demo 模式下的需量状态数据

        Args:
            declared_demand: 申报需量 kW
            timestamp: 时间戳，默认为当前时间

        Returns:
            需量状态数据字典
        """
        if timestamp is None:
            timestamp = datetime.now()

        # 获取时间相关的负荷因子
        time_factor = self._get_time_factor(timestamp)

        # 基于时间戳生成确定性波动
        seed = timestamp.timestamp()
        variation = self._get_deterministic_value(seed, -0.03, 0.03, 1.0)

        # 计算当前功率和平均功率
        base_power = declared_demand * time_factor
        current_power = base_power * (1 + variation)
        window_avg_power = base_power * (1 + variation * 0.5)  # 平均功率波动较小

        # 计算利用率
        utilization_ratio = (window_avg_power / declared_demand) * 100 if declared_demand > 0 else 0
        remaining_capacity = declared_demand - window_avg_power

        # 判断预警级别
        if utilization_ratio >= 100:
            alert_level = "critical"
        elif utilization_ratio >= 90:
            alert_level = "warning"
        else:
            alert_level = "normal"

        # 趋势判断
        if current_power > window_avg_power * 1.05:
            trend = "up"
        elif current_power < window_avg_power * 0.95:
            trend = "down"
        else:
            trend = "stable"

        # 本月最大需量（基于月份的确定性值）
        month_seed = timestamp.year * 12 + timestamp.month
        month_max_factor = 0.85 + self._get_deterministic_value(month_seed, 0, 0.13, 1.0)
        month_max_demand = declared_demand * month_max_factor

        # 最大需量时间（月内某一天）
        day_offset = int(self._get_deterministic_value(month_seed + 1, 1, min(15, timestamp.day), 1.0))
        month_max_time = (timestamp.replace(day=max(1, timestamp.day - day_offset), hour=11, minute=30)).strftime("%Y-%m-%d %H:%M")

        return {
            "current_power": round(current_power, 1),
            "window_avg_power": round(window_avg_power, 1),
            "demand_target": round(declared_demand, 1),
            "declared_demand": round(declared_demand, 1),
            "utilization_ratio": round(utilization_ratio, 1),
            "remaining_capacity": round(max(0, remaining_capacity), 1),
            "alert_level": alert_level,
            "month_max_demand": round(month_max_demand, 1),
            "month_max_time": month_max_time,
            "trend": trend,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "is_demo_data": True
        }

    def get_demo_realtime_curve(self, declared_demand: float, hours: int = 4,
                                  end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """生成 Demo 模式下的实时功率曲线数据

        Args:
            declared_demand: 申报需量 kW
            hours: 获取最近几小时数据
            end_time: 结束时间，默认为当前时间

        Returns:
            功率曲线数据列表（按时间正序）
        """
        if end_time is None:
            end_time = datetime.now()

        data_points = []

        # 生成数据点（每5分钟一个点）
        for i in range(hours * 12):
            ts = end_time - timedelta(minutes=i * 5)

            # 使用时间因子生成功率
            time_factor = self._get_time_factor(ts)
            seed = ts.timestamp()
            variation = self._get_deterministic_value(seed, -0.03, 0.03, 1.0)

            power = declared_demand * time_factor * (1 + variation)
            utilization = power / declared_demand * 100 if declared_demand > 0 else 0

            # 判断预警级别
            if utilization >= 100:
                alert = "critical"
            elif utilization >= 90:
                alert = "warning"
            else:
                alert = "normal"

            data_points.append({
                "timestamp": ts.strftime("%H:%M"),
                "full_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "power": round(power, 1),
                "demand_target": declared_demand,
                "utilization": round(utilization, 1),
                "alert_level": alert,
                "is_demo_data": True
            })

        # 按时间正序排列
        data_points.reverse()
        return data_points

    def get_demo_monthly_summary(self, declared_demand: float, demand_price: float,
                                   target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """生成 Demo 模式下的月度电费汇总

        Args:
            declared_demand: 申报需量 kW
            demand_price: 需量单价 元/kW
            target_date: 目标日期，默认为当前日期

        Returns:
            月度电费汇总数据字典
        """
        if target_date is None:
            target_date = datetime.now()

        year_month = target_date.strftime("%Y-%m")
        days_in_month = target_date.day
        month_seed = target_date.year * 12 + target_date.month

        # 基础参数（确定性计算）
        daily_energy_base = declared_demand * 24 * 0.65  # 假设平均负载率65%
        daily_energy = daily_energy_base * (1 + self._get_deterministic_value(month_seed, -0.1, 0.1, 1.0))
        total_energy = daily_energy * days_in_month

        # 最大需量
        max_demand_factor = 0.85 + self._get_deterministic_value(month_seed + 1, 0, 0.13, 1.0)
        max_demand = declared_demand * max_demand_factor

        # 分时电量分布
        sharp_ratio = 0.08
        peak_ratio = 0.30
        flat_ratio = 0.35
        valley_ratio = 0.20
        deep_valley_ratio = 0.07

        # 电价
        prices = {
            "sharp": 1.20,
            "peak": 0.95,
            "flat": 0.65,
            "valley": 0.35,
            "deep_valley": 0.20
        }

        # 计算电量电费
        energy_cost = (
            total_energy * sharp_ratio * prices["sharp"] +
            total_energy * peak_ratio * prices["peak"] +
            total_energy * flat_ratio * prices["flat"] +
            total_energy * valley_ratio * prices["valley"] +
            total_energy * deep_valley_ratio * prices["deep_valley"]
        )

        # 计算需量电费
        billable_demand = max(max_demand, declared_demand * 0.4)
        if max_demand > declared_demand:
            demand_cost = declared_demand * demand_price + (max_demand - declared_demand) * demand_price * 2
        else:
            demand_cost = billable_demand * demand_price

        # 力调电费
        base_cost = energy_cost + demand_cost
        power_factor_adjustment = -base_cost * 0.005

        total_cost = energy_cost + demand_cost + power_factor_adjustment

        # 优化节省（确定性计算）
        saving_factor = 0.03 + self._get_deterministic_value(month_seed + 2, 0, 0.05, 1.0)
        optimized_saving = total_cost * saving_factor

        return {
            "year_month": year_month,
            "total_energy": round(total_energy, 1),
            "max_demand": round(max_demand, 1),
            "demand_target": round(declared_demand, 1),
            "energy_cost": round(energy_cost, 2),
            "demand_cost": round(demand_cost, 2),
            "power_factor_adjustment": round(power_factor_adjustment, 2),
            "total_cost": round(total_cost, 2),
            "optimized_saving": round(optimized_saving, 2),
            "cost_breakdown": {
                "energy_by_period": {
                    "sharp": round(total_energy * sharp_ratio, 1),
                    "peak": round(total_energy * peak_ratio, 1),
                    "flat": round(total_energy * flat_ratio, 1),
                    "valley": round(total_energy * valley_ratio, 1),
                    "deep_valley": round(total_energy * deep_valley_ratio, 1)
                },
                "cost_by_period": {
                    "sharp": round(total_energy * sharp_ratio * prices["sharp"], 2),
                    "peak": round(total_energy * peak_ratio * prices["peak"], 2),
                    "flat": round(total_energy * flat_ratio * prices["flat"], 2),
                    "valley": round(total_energy * valley_ratio * prices["valley"], 2),
                    "deep_valley": round(total_energy * deep_valley_ratio * prices["deep_valley"], 2)
                }
            },
            "is_demo_data": True
        }

    def get_demo_daily_demand_trend(self, declared_demand: float,
                                      target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """生成 Demo 模式下的日需量趋势数据

        Args:
            declared_demand: 申报需量 kW
            target_date: 目标日期

        Returns:
            日需量趋势数据
        """
        if target_date is None:
            target_date = datetime.now()

        day_seed = target_date.toordinal()

        data_points = []
        max_demand = 0
        max_demand_time = None

        for hour in range(24):
            for quarter in range(4):
                time_str = f"{hour:02d}:{quarter*15:02d}"
                ts = target_date.replace(hour=hour, minute=quarter*15, second=0, microsecond=0)

                # 使用时间因子生成功率
                time_factor = self._get_time_factor(ts)
                seed = day_seed * 96 + hour * 4 + quarter
                variation = self._get_deterministic_value(seed, -0.02, 0.02, 1.0)

                demand = declared_demand * time_factor * (1 + variation)

                if demand > max_demand:
                    max_demand = demand
                    max_demand_time = time_str

                # 时段类型
                if hour in [10, 11, 14, 15, 16]:
                    period = "sharp"
                elif hour in [8, 9, 12, 13, 17, 18, 19, 20]:
                    period = "peak"
                elif hour in [7, 21, 22]:
                    period = "flat"
                elif hour in [23, 0, 1, 2, 3, 4, 5, 6]:
                    period = "valley" if hour in [23, 6] else "deep_valley"
                else:
                    period = "flat"

                data_points.append({
                    "time": time_str,
                    "demand": round(demand, 1),
                    "period": period
                })

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "declared_demand": declared_demand,
            "max_demand": round(max_demand, 1),
            "max_demand_time": max_demand_time,
            "avg_demand": round(sum(p["demand"] for p in data_points) / len(data_points), 1),
            "data": data_points,
            "is_demo_data": True
        }

    def get_demo_monthly_history(self, declared_demand: float, months: int = 12,
                                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """生成 Demo 模式下的历史月度电费数据

        Args:
            declared_demand: 申报需量 kW
            months: 获取最近几个月
            end_date: 结束日期

        Returns:
            历史月度数据列表
        """
        if end_date is None:
            end_date = datetime.now()

        history = []

        for i in range(months):
            target_date = end_date - timedelta(days=30 * i)
            year_month = target_date.strftime("%Y-%m")
            month_seed = target_date.year * 12 + target_date.month

            # 季节性系数
            month = target_date.month
            if month in [7, 8]:  # 夏季高峰
                season_factor = 1.3
            elif month in [1, 2, 12]:  # 冬季
                season_factor = 1.1
            else:
                season_factor = 1.0

            # 基础能耗（确定性计算）
            base_energy = declared_demand * 24 * 30 * 0.65  # 月均基础电量
            energy_variation = self._get_deterministic_value(month_seed, -0.08, 0.08, 1.0)
            total_energy = base_energy * season_factor * (1 + energy_variation)

            # 电费（简化计算）
            avg_price = 0.7  # 平均电价
            total_cost = total_energy * avg_price

            # 最大需量
            max_demand_factor = 0.85 + self._get_deterministic_value(month_seed + 1, 0, 0.13, 1.0)
            max_demand = declared_demand * max_demand_factor * season_factor

            history.append({
                "year_month": year_month,
                "total_energy": round(total_energy, 1),
                "total_cost": round(total_cost, 2),
                "energy_cost": round(total_cost * 0.65, 2),
                "demand_cost": round(total_cost * 0.30, 2),
                "other_cost": round(total_cost * 0.05, 2),
                "max_demand": round(max_demand, 1),
                "is_demo_data": True
            })

        return history


# 全局 Demo 数据提供实例
demo_provider = DemoDataProvider()
