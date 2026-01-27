"""
MILP优化器模块
使用混合整数线性规划优化电费成本
"""
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False
    pulp = None


class DeviceType(Enum):
    """设备类型枚举"""
    SHIFTABLE = 'shiftable'      # 时移型
    CURTAILABLE = 'curtailable'  # 削减型
    MODULATING = 'modulating'    # 调节型
    GENERATION = 'generation'    # 发电型
    STORAGE = 'storage'          # 储能型
    RIGID = 'rigid'              # 刚性型


class PeriodType(Enum):
    """时段类型"""
    SHARP = 'sharp'              # 尖峰
    PEAK = 'peak'                # 峰
    FLAT = 'flat'                # 平
    VALLEY = 'valley'            # 谷
    DEEP_VALLEY = 'deep_valley'  # 深谷


@dataclass
class PricingConfig:
    """电价配置"""
    demand_price: float = 40.0           # 需量单价 (元/kW·月)
    capacity_price: float = 23.0         # 容量单价 (元/kVA·月)
    declared_demand: float = 800.0       # 申报需量 (kW)
    transformer_capacity: float = 1000.0 # 变压器容量 (kVA)
    over_demand_penalty: float = 2.0     # 超需量惩罚系数
    pricing_type: str = 'demand'         # 'demand' or 'capacity'

    # 分时电价 (元/kWh)
    period_prices: Dict[str, float] = None

    def __post_init__(self):
        if self.period_prices is None:
            self.period_prices = {
                'sharp': 1.20,
                'peak': 0.95,
                'flat': 0.65,
                'valley': 0.35,
                'deep_valley': 0.20,
            }


@dataclass
class StorageConfig:
    """储能配置"""
    capacity: float = 500.0              # 容量 (kWh)
    max_charge_power: float = 100.0      # 最大充电功率 (kW)
    max_discharge_power: float = 100.0   # 最大放电功率 (kW)
    charge_efficiency: float = 0.95      # 充电效率
    discharge_efficiency: float = 0.95   # 放电效率
    min_soc: float = 0.10                # 最小SOC
    max_soc: float = 0.90                # 最大SOC
    initial_soc: float = 0.50            # 初始SOC
    cycle_cost: float = 0.10             # 循环成本 (元/kWh)


@dataclass
class DispatchableDevice:
    """可调度设备"""
    id: int
    name: str
    device_type: DeviceType
    rated_power: float                   # 额定功率 (kW)
    min_power: float = 0.0               # 最小功率 (kW)
    max_power: float = None              # 最大功率 (kW)

    # 时移型参数
    run_duration: float = 2.0            # 单次运行时长 (h)
    daily_runs: int = 1                  # 每日运行次数
    allowed_periods: List[int] = None    # 允许时段 (小时列表)
    forbidden_periods: List[int] = None  # 禁止时段

    # 削减型参数
    curtail_ratio: float = 0.5           # 可削减比例
    max_curtail_duration: float = 2.0    # 最大削减时长 (h)

    # 调节型参数
    ramp_rate: float = 10.0              # 调节速率 (kW/min)

    priority: int = 5                    # 优先级 (1-10)

    def __post_init__(self):
        if self.max_power is None:
            self.max_power = self.rated_power
        if self.allowed_periods is None:
            self.allowed_periods = list(range(24))
        if self.forbidden_periods is None:
            self.forbidden_periods = []


class MILPOptimizer:
    """MILP优化器"""

    # 时段划分 (小时 -> 时段类型)
    HOUR_TO_PERIOD = {
        0: 'deep_valley', 1: 'deep_valley', 2: 'deep_valley', 3: 'deep_valley',
        4: 'valley', 5: 'valley', 6: 'valley', 7: 'valley',
        8: 'flat', 9: 'peak', 10: 'peak', 11: 'sharp',
        12: 'peak', 13: 'flat', 14: 'flat', 15: 'flat',
        16: 'flat', 17: 'peak', 18: 'sharp', 19: 'peak',
        20: 'peak', 21: 'flat', 22: 'valley', 23: 'valley',
    }

    def __init__(
        self,
        pricing: PricingConfig,
        storage: Optional[StorageConfig] = None,
        devices: Optional[List[DispatchableDevice]] = None,
        time_slots: int = 96,  # 96个15分钟时段
        time_limit: int = 30   # 求解时间限制（秒）
    ):
        self.pricing = pricing
        self.storage = storage
        self.devices = devices or []
        self.time_slots = time_slots
        self.time_limit = time_limit
        self.slot_duration = 0.25  # 15分钟 = 0.25小时

        # 构建时段到电价的映射
        self.slot_prices = self._build_slot_prices()

    def _build_slot_prices(self) -> List[float]:
        """构建每个时段的电价"""
        prices = []
        for slot in range(self.time_slots):
            hour = slot // 4
            period = self.HOUR_TO_PERIOD.get(hour, 'flat')
            price = self.pricing.period_prices.get(period, 0.65)
            prices.append(price)
        return prices

    def _get_slot_period(self, slot: int) -> str:
        """获取时段类型"""
        hour = slot // 4
        return self.HOUR_TO_PERIOD.get(hour, 'flat')

    def optimize(
        self,
        base_load: List[float],
        demand_target: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        执行优化

        Args:
            base_load: 基础负荷曲线 (96个时段的功率值，kW)
            demand_target: 需量目标 (kW)，默认使用申报需量

        Returns:
            优化结果字典
        """
        if not PULP_AVAILABLE:
            return self._optimize_heuristic(base_load, demand_target)

        if demand_target is None:
            demand_target = self.pricing.declared_demand

        try:
            return self._optimize_milp(base_load, demand_target)
        except Exception as e:
            print(f"MILP优化失败，使用启发式方法: {e}")
            return self._optimize_heuristic(base_load, demand_target)

    def _optimize_milp(
        self,
        base_load: List[float],
        demand_target: float
    ) -> Dict[str, Any]:
        """MILP优化实现"""
        T = self.time_slots
        dt = self.slot_duration

        # 创建优化问题
        prob = pulp.LpProblem("Electricity_Cost_Optimization", pulp.LpMinimize)

        # ========== 决策变量 ==========

        # 最大需量变量
        D_max = pulp.LpVariable("D_max", lowBound=0)

        # 储能变量
        if self.storage:
            P_charge = [pulp.LpVariable(f"P_charge_{t}", lowBound=0,
                                        upBound=self.storage.max_charge_power)
                       for t in range(T)]
            P_discharge = [pulp.LpVariable(f"P_discharge_{t}", lowBound=0,
                                           upBound=self.storage.max_discharge_power)
                          for t in range(T)]
            SOC = [pulp.LpVariable(f"SOC_{t}", lowBound=self.storage.min_soc,
                                   upBound=self.storage.max_soc)
                  for t in range(T + 1)]
            # 充放电互斥二进制变量
            z_charge = [pulp.LpVariable(f"z_charge_{t}", cat='Binary') for t in range(T)]
        else:
            P_charge = [0] * T
            P_discharge = [0] * T
            SOC = None

        # 可调度设备变量
        device_vars = {}
        for d_idx, device in enumerate(self.devices):
            if device.device_type == DeviceType.SHIFTABLE:
                # 时移型：开关状态
                device_vars[d_idx] = {
                    'on': [pulp.LpVariable(f"dev_{d_idx}_on_{t}", cat='Binary')
                          for t in range(T)]
                }
            elif device.device_type == DeviceType.CURTAILABLE:
                # 削减型：削减比例
                device_vars[d_idx] = {
                    'curtail': [pulp.LpVariable(f"dev_{d_idx}_curtail_{t}",
                                               lowBound=0, upBound=device.curtail_ratio)
                               for t in range(T)]
                }
            elif device.device_type == DeviceType.MODULATING:
                # 调节型：功率输出
                device_vars[d_idx] = {
                    'power': [pulp.LpVariable(f"dev_{d_idx}_power_{t}",
                                             lowBound=device.min_power,
                                             upBound=device.max_power)
                             for t in range(T)]
                }

        # ========== 目标函数 ==========

        # 电量电费
        energy_cost = pulp.lpSum([
            self.slot_prices[t] * base_load[t] * dt
            for t in range(T)
        ])

        # 储能相关成本
        if self.storage:
            # 储能放电收益（高价时段放电）
            storage_benefit = pulp.lpSum([
                self.slot_prices[t] * P_discharge[t] * dt * self.storage.discharge_efficiency
                for t in range(T)
            ])
            # 储能充电成本（低价时段充电）
            storage_cost = pulp.lpSum([
                self.slot_prices[t] * P_charge[t] * dt / self.storage.charge_efficiency
                for t in range(T)
            ])
            # 循环成本
            cycle_cost = pulp.lpSum([
                self.storage.cycle_cost * (P_charge[t] + P_discharge[t]) * dt
                for t in range(T)
            ])
            storage_total = storage_cost - storage_benefit + cycle_cost
        else:
            storage_total = 0

        # 需量电费
        demand_cost = D_max * self.pricing.demand_price

        # 总目标：最小化总电费
        prob += energy_cost + storage_total + demand_cost

        # ========== 约束条件 ==========

        # 1. 需量约束：任意时段净功率 <= D_max
        for t in range(T):
            # 计算净功率
            net_power = base_load[t]

            # 加上储能影响
            if self.storage:
                net_power += P_charge[t] - P_discharge[t]

            # 加上可调度设备影响
            for d_idx, device in enumerate(self.devices):
                if d_idx not in device_vars:
                    continue

                if device.device_type == DeviceType.SHIFTABLE:
                    # 时移型：开启时增加功率
                    net_power += device.rated_power * device_vars[d_idx]['on'][t]
                elif device.device_type == DeviceType.CURTAILABLE:
                    # 削减型：削减时减少功率
                    net_power -= device.rated_power * device_vars[d_idx]['curtail'][t]
                elif device.device_type == DeviceType.MODULATING:
                    # 调节型：直接使用功率变量
                    pass  # 已在base_load中

            prob += D_max >= net_power, f"demand_constraint_{t}"

        # 2. 需量目标软约束（尽量不超过申报需量）
        prob += D_max <= demand_target * 1.05, "demand_target_soft"

        # 3. 储能约束
        if self.storage:
            # 初始SOC
            prob += SOC[0] == self.storage.initial_soc, "initial_soc"

            # SOC演化
            for t in range(T):
                prob += SOC[t + 1] == (
                    SOC[t] +
                    (P_charge[t] * self.storage.charge_efficiency -
                     P_discharge[t] / self.storage.discharge_efficiency) *
                    dt / self.storage.capacity
                ), f"soc_evolution_{t}"

            # 充放电互斥
            for t in range(T):
                prob += P_charge[t] <= self.storage.max_charge_power * z_charge[t]
                prob += P_discharge[t] <= self.storage.max_discharge_power * (1 - z_charge[t])

        # 4. 时移型设备约束
        for d_idx, device in enumerate(self.devices):
            if device.device_type != DeviceType.SHIFTABLE:
                continue
            if d_idx not in device_vars:
                continue

            vars_on = device_vars[d_idx]['on']

            # 每日运行时长约束
            total_run_slots = int(device.run_duration * 4 * device.daily_runs)
            prob += pulp.lpSum(vars_on) == total_run_slots, f"dev_{d_idx}_run_duration"

            # 禁止时段约束
            for hour in device.forbidden_periods:
                for q in range(4):
                    slot = hour * 4 + q
                    if slot < T:
                        prob += vars_on[slot] == 0, f"dev_{d_idx}_forbidden_{slot}"

        # ========== 求解 ==========
        solver = pulp.PULP_CBC_CMD(timeLimit=self.time_limit, msg=0)
        status = prob.solve(solver)

        # ========== 结果解析 ==========
        if pulp.LpStatus[status] not in ['Optimal', 'Not Solved']:
            return {
                'status': 'failed',
                'message': f'Solver status: {pulp.LpStatus[status]}',
                'optimal_value': None
            }

        # 提取结果
        result = {
            'status': 'success',
            'solve_status': pulp.LpStatus[status],
            'optimal_value': pulp.value(prob.objective),
            'max_demand': pulp.value(D_max),
            'demand_target': demand_target,
            'schedule': [],
            'storage_schedule': [],
            'cost_breakdown': {},
        }

        # 计算各项成本
        energy_cost_val = sum(self.slot_prices[t] * base_load[t] * dt for t in range(T))
        demand_cost_val = pulp.value(D_max) * self.pricing.demand_price

        result['cost_breakdown'] = {
            'energy_cost': round(energy_cost_val, 2),
            'demand_cost': round(demand_cost_val, 2),
            'total_cost': round(energy_cost_val + demand_cost_val, 2),
        }

        # 提取储能调度计划
        if self.storage:
            storage_benefit_val = 0
            storage_cost_val = 0

            for t in range(T):
                charge_val = pulp.value(P_charge[t]) or 0
                discharge_val = pulp.value(P_discharge[t]) or 0
                soc_val = pulp.value(SOC[t]) or 0

                result['storage_schedule'].append({
                    'time_slot': t,
                    'hour': t // 4,
                    'minute': (t % 4) * 15,
                    'charge_power': round(charge_val, 2),
                    'discharge_power': round(discharge_val, 2),
                    'soc': round(soc_val, 3),
                    'period': self._get_slot_period(t),
                })

                storage_benefit_val += self.slot_prices[t] * discharge_val * dt
                storage_cost_val += self.slot_prices[t] * charge_val * dt

            result['cost_breakdown']['storage_benefit'] = round(storage_benefit_val, 2)
            result['cost_breakdown']['storage_cost'] = round(storage_cost_val, 2)
            result['cost_breakdown']['storage_net'] = round(storage_cost_val - storage_benefit_val, 2)

        # 提取设备调度计划
        for d_idx, device in enumerate(self.devices):
            if d_idx not in device_vars:
                continue

            device_schedule = {
                'device_id': device.id,
                'device_name': device.name,
                'device_type': device.device_type.value,
                'actions': []
            }

            if device.device_type == DeviceType.SHIFTABLE:
                for t in range(T):
                    on_val = pulp.value(device_vars[d_idx]['on'][t]) or 0
                    if on_val > 0.5:
                        device_schedule['actions'].append({
                            'time_slot': t,
                            'hour': t // 4,
                            'minute': (t % 4) * 15,
                            'action': 'on',
                            'power': device.rated_power,
                        })

            elif device.device_type == DeviceType.CURTAILABLE:
                for t in range(T):
                    curtail_val = pulp.value(device_vars[d_idx]['curtail'][t]) or 0
                    if curtail_val > 0.01:
                        device_schedule['actions'].append({
                            'time_slot': t,
                            'hour': t // 4,
                            'minute': (t % 4) * 15,
                            'action': 'curtail',
                            'curtail_ratio': round(curtail_val, 2),
                            'power_reduction': round(device.rated_power * curtail_val, 2),
                        })

            result['schedule'].append(device_schedule)

        # 计算节省金额
        baseline_cost = self._calculate_baseline_cost(base_load, demand_target)
        result['baseline_cost'] = round(baseline_cost, 2)
        result['expected_saving'] = round(baseline_cost - result['optimal_value'], 2)
        result['saving_ratio'] = round(
            (baseline_cost - result['optimal_value']) / baseline_cost * 100
            if baseline_cost > 0 else 0, 2
        )

        return result

    def _calculate_baseline_cost(
        self,
        base_load: List[float],
        demand_target: float
    ) -> float:
        """计算基线成本（不优化的情况）"""
        dt = self.slot_duration

        # 电量电费
        energy_cost = sum(self.slot_prices[t] * base_load[t] * dt for t in range(len(base_load)))

        # 需量电费（使用最大负荷）
        max_load = max(base_load)
        demand_cost = max_load * self.pricing.demand_price

        return energy_cost + demand_cost

    def _optimize_heuristic(
        self,
        base_load: List[float],
        demand_target: float
    ) -> Dict[str, Any]:
        """
        启发式优化（当MILP不可用时使用）

        简单策略：
        1. 储能在谷时段充电，峰时段放电
        2. 时移型设备移到谷时段运行
        """
        T = len(base_load)
        dt = self.slot_duration

        # 复制负荷曲线
        optimized_load = list(base_load)

        # 储能调度
        storage_schedule = []
        if self.storage:
            soc = self.storage.initial_soc

            for t in range(T):
                period = self._get_slot_period(t)
                charge = 0
                discharge = 0

                # 谷时段充电
                if period in ['valley', 'deep_valley'] and soc < self.storage.max_soc:
                    charge = min(
                        self.storage.max_charge_power,
                        (self.storage.max_soc - soc) * self.storage.capacity / dt
                    )
                    soc += charge * dt * self.storage.charge_efficiency / self.storage.capacity
                    optimized_load[t] += charge

                # 峰时段放电
                elif period in ['peak', 'sharp'] and soc > self.storage.min_soc:
                    discharge = min(
                        self.storage.max_discharge_power,
                        (soc - self.storage.min_soc) * self.storage.capacity / dt,
                        optimized_load[t]  # 不要放电超过负荷
                    )
                    soc -= discharge * dt / self.storage.discharge_efficiency / self.storage.capacity
                    optimized_load[t] -= discharge

                storage_schedule.append({
                    'time_slot': t,
                    'hour': t // 4,
                    'minute': (t % 4) * 15,
                    'charge_power': round(charge, 2),
                    'discharge_power': round(discharge, 2),
                    'soc': round(soc, 3),
                    'period': period,
                })

        # 计算成本
        energy_cost = sum(self.slot_prices[t] * optimized_load[t] * dt for t in range(T))
        max_demand = max(optimized_load)
        demand_cost = max_demand * self.pricing.demand_price
        total_cost = energy_cost + demand_cost

        # 基线成本
        baseline_cost = self._calculate_baseline_cost(base_load, demand_target)

        return {
            'status': 'success',
            'solve_status': 'Heuristic',
            'optimal_value': total_cost,
            'max_demand': max_demand,
            'demand_target': demand_target,
            'schedule': [],
            'storage_schedule': storage_schedule,
            'cost_breakdown': {
                'energy_cost': round(energy_cost, 2),
                'demand_cost': round(demand_cost, 2),
                'total_cost': round(total_cost, 2),
            },
            'baseline_cost': round(baseline_cost, 2),
            'expected_saving': round(baseline_cost - total_cost, 2),
            'saving_ratio': round((baseline_cost - total_cost) / baseline_cost * 100 if baseline_cost > 0 else 0, 2),
        }


def run_day_ahead_optimization(
    forecast_data: Dict,
    pricing_config: Dict,
    storage_config: Optional[Dict] = None,
    devices: Optional[List[Dict]] = None,
    demand_target: Optional[float] = None
) -> Dict:
    """
    执行日前调度优化

    Args:
        forecast_data: 负荷预测数据
        pricing_config: 电价配置
        storage_config: 储能配置（可选）
        devices: 可调度设备列表（可选）
        demand_target: 需量目标（可选）

    Returns:
        优化结果
    """
    # 构建配置对象
    pricing = PricingConfig(
        demand_price=pricing_config.get('demand_price', 40.0),
        declared_demand=pricing_config.get('declared_demand', 800.0),
        over_demand_penalty=pricing_config.get('over_demand_penalty', 2.0),
        period_prices=pricing_config.get('period_prices', None),
    )

    storage = None
    if storage_config:
        storage = StorageConfig(
            capacity=storage_config.get('capacity', 500.0),
            max_charge_power=storage_config.get('max_charge_power', 100.0),
            max_discharge_power=storage_config.get('max_discharge_power', 100.0),
            charge_efficiency=storage_config.get('charge_efficiency', 0.95),
            discharge_efficiency=storage_config.get('discharge_efficiency', 0.95),
            min_soc=storage_config.get('min_soc', 0.10),
            max_soc=storage_config.get('max_soc', 0.90),
            initial_soc=storage_config.get('initial_soc', 0.50),
            cycle_cost=storage_config.get('cycle_cost', 0.10),
        )

    device_list = []
    if devices:
        for d in devices:
            device_list.append(DispatchableDevice(
                id=d.get('id', 0),
                name=d.get('name', 'Unknown'),
                device_type=DeviceType(d.get('device_type', 'rigid')),
                rated_power=d.get('rated_power', 0),
                min_power=d.get('min_power', 0),
                max_power=d.get('max_power'),
                run_duration=d.get('run_duration', 2.0),
                daily_runs=d.get('daily_runs', 1),
                allowed_periods=d.get('allowed_periods'),
                forbidden_periods=d.get('forbidden_periods'),
                curtail_ratio=d.get('curtail_ratio', 0.5),
                max_curtail_duration=d.get('max_curtail_duration', 2.0),
                priority=d.get('priority', 5),
            ))

    # 提取基础负荷
    base_load = [f['predicted_power'] for f in forecast_data.get('forecasts', [])]
    if len(base_load) != 96:
        # 如果数据点不是96个，进行插值或截断
        if len(base_load) < 96:
            base_load = base_load + [base_load[-1]] * (96 - len(base_load))
        else:
            base_load = base_load[:96]

    # 创建优化器并执行
    optimizer = MILPOptimizer(
        pricing=pricing,
        storage=storage,
        devices=device_list,
    )

    result = optimizer.optimize(base_load, demand_target)

    # 添加预测信息
    result['forecast_date'] = forecast_data.get('date')
    result['base_load_summary'] = forecast_data.get('statistics', {})

    return result
