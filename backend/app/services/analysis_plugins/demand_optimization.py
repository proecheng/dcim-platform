"""
需量优化分析插件
Demand Optimization Analysis Plugin

分析电力需量（最大功率），优化需量电费
Analyzes power demand and optimizes demand charges

Enhanced: 支持需量配置合理性分析、设备需量贡献分析、削峰措施建议

注: 核心计算逻辑已统一到 DemandAnalysisService，本插件调用该服务
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics
import math

from .base import (
    AnalysisPlugin,
    AnalysisContext,
    SuggestionResult,
    PluginConfig,
    PluginPriority,
    SuggestionType,
    DemandHistoryData,
    MeterPointData
)

# 导入统一的阈值配置
from ..demand_analysis_service import DemandThresholds


class DemandOptimizationPlugin(AnalysisPlugin):
    """
    需量优化分析插件

    分析内容:
    - 需量峰值分析
    - 需量配置合理性评估
    - 需量控制建议
    - 设备需量贡献分析
    - 削峰措施建议
    """

    @property
    def plugin_id(self) -> str:
        return "demand_optimization"

    @property
    def plugin_name(self) -> str:
        return "需量优化分析"

    @property
    def plugin_description(self) -> str:
        return "分析电力需量配置合理性，提供需量控制和削峰建议"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.DEMAND_OPTIMIZATION

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=20,
            min_data_days=30,
            thresholds={
                'low_utilization': 0.80,       # 低利用率阈值
                'high_utilization': 1.05,      # 高利用率阈值 (超申报)
                'optimal_utilization': 0.90,   # 最优利用率
                'safety_margin': 0.10,         # 安全裕度
                'demand_price': 38.0,          # 需量电价 元/kW·月
                'min_saving': 5000             # 最小年节省金额
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行需量优化分析"""
        results = []

        # 1. 需量配置合理性分析 (新增: 按计量点分析)
        if context.meter_points and context.demand_history:
            config_results = await self._analyze_demand_config(context)
            results.extend(config_results)
        else:
            # 使用传统分析方法
            legacy_results = await self._analyze_demand_legacy(context)
            results.extend(legacy_results)

        # 2. 设备需量贡献分析 (新增)
        if context.device_data:
            contribution_results = await self._analyze_device_contribution(context)
            results.extend(contribution_results)

        return results

    async def _analyze_demand_config(self, context: AnalysisContext) -> List[SuggestionResult]:
        """需量配置合理性分析 (按计量点)"""
        results = []
        thresholds = self._config.thresholds
        demand_price = context.pricing_config.get('demand_price', thresholds.get('demand_price', 38.0))

        for meter_point in context.meter_points:
            mp_id = meter_point.meter_point_id
            declared_demand = meter_point.declared_demand

            if not declared_demand or declared_demand <= 0:
                continue

            # 获取该计量点的需量历史
            demand_history = context.get_demand_history_for_meter(mp_id)
            if len(demand_history) < 3:
                continue

            # 计算统计数据
            max_demands = [d.max_demand for d in demand_history if d.max_demand > 0]
            if not max_demands:
                continue

            max_demand_12m = max(max_demands)
            avg_max_demand = statistics.mean(max_demands)
            std_dev = statistics.stdev(max_demands) if len(max_demands) > 1 else 0

            # 计算95%分位数
            sorted_demands = sorted(max_demands)
            idx_95 = int(len(sorted_demands) * 0.95)
            demand_95th = sorted_demands[min(idx_95, len(sorted_demands) - 1)]

            # 计算利用率
            utilization_rate = max_demand_12m / declared_demand

            # 计算超申报次数
            over_declared_count = sum(d.over_declared_times for d in demand_history)

            # ==================== 评估需量配置 ====================

            low_threshold = thresholds.get('low_utilization', 0.80)
            high_threshold = thresholds.get('high_utilization', 1.05)
            safety_margin = thresholds.get('safety_margin', 0.10)

            # 情况1: 需量配置过高 (利用率低)
            if utilization_rate < low_threshold:
                # 计算建议需量
                recommended_demand = self._calculate_optimal_demand(
                    demand_95th, safety_margin, meter_point.demand_type
                )

                # 计算节省
                demand_reduction = declared_demand - recommended_demand
                monthly_saving = demand_reduction * demand_price
                yearly_saving = monthly_saving * 12

                if yearly_saving >= thresholds.get('min_saving', 5000):
                    risk_level = 'low' if utilization_rate < 0.70 else 'medium'

                    results.append(self.create_suggestion(
                        title=f"降低计量点{meter_point.meter_code}申报需量",
                        description=f"当前申报需量{declared_demand:.0f}kW，实际利用率仅{utilization_rate:.1%}，建议降至{recommended_demand:.0f}kW",
                        detail=f"""
## 需量配置合理性分析

### 计量点信息
- 编码: {meter_point.meter_code}
- 名称: {meter_point.meter_name}
- 当前申报需量: {declared_demand:.0f} {meter_point.demand_type}
- 变压器: {meter_point.transformer_name or '未配置'}

### 历史需量统计 (近{len(demand_history)}月)
- 最大需量: {max_demand_12m:.1f} kW
- 平均最大需量: {avg_max_demand:.1f} kW
- 95%分位数需量: {demand_95th:.1f} kW
- 标准差: {std_dev:.1f} kW
- 需量利用率: {utilization_rate:.1%}

### 优化建议
- **建议申报需量**: {recommended_demand:.0f} {meter_point.demand_type}
- 安全裕度: {safety_margin*100:.0f}%
- 优化类型: 降低申报需量

### 效益分析
- 需量减少: {demand_reduction:.0f} {meter_point.demand_type}
- 月节省需量电费: ¥{monthly_saving:.0f}
- **年节省需量电费: ¥{yearly_saving:.0f}**

### 风险评估
- 风险等级: {'低' if risk_level == 'low' else '中'}
- 风险说明: {'需量利用率较低，降低申报风险较小' if risk_level == 'low' else '建议保留适当裕度'}

### 实施步骤
1. 向供电局提交需量变更申请
2. 提供近12个月用电数据作为依据
3. 等待审批通过（通常1-2周）
4. 新需量从下月生效
                        """.strip(),
                        estimated_saving=0,
                        estimated_cost_saving=yearly_saving,
                        implementation_difficulty=1,
                        priority=PluginPriority.HIGH if yearly_saving > 20000 else PluginPriority.MEDIUM,
                        payback_period=0,
                        analysis_data={
                            'meter_point_id': mp_id,
                            'meter_code': meter_point.meter_code,
                            'declared_demand': declared_demand,
                            'recommended_demand': recommended_demand,
                            'max_demand_12m': max_demand_12m,
                            'demand_95th': demand_95th,
                            'utilization_rate': utilization_rate,
                            'yearly_saving': yearly_saving,
                            'risk_level': risk_level,
                            'optimization_type': 'reduce'
                        },
                        confidence=90 if risk_level == 'low' else 80
                    ))

            # 情况2: 需量配置过低 (超申报风险)
            elif utilization_rate > high_threshold:
                # 计算建议需量
                recommended_demand = self._calculate_optimal_demand(
                    max_demand_12m, safety_margin * 1.5, meter_point.demand_type  # 更大裕度
                )

                # 计算超需量罚款风险
                over_amount = max_demand_12m - declared_demand
                penalty_estimate = over_amount * demand_price * 2 * 12  # 假设超出部分按2倍计费

                results.append(self.create_suggestion(
                    title=f"提高计量点{meter_point.meter_code}申报需量",
                    description=f"当前申报需量{declared_demand:.0f}kW，实际已超{(utilization_rate-1)*100:.1f}%，存在超需量罚款风险",
                    detail=f"""
## 需量超限预警

### 计量点信息
- 编码: {meter_point.meter_code}
- 名称: {meter_point.meter_name}
- 当前申报需量: {declared_demand:.0f} {meter_point.demand_type}

### 历史需量统计
- 最大需量: {max_demand_12m:.1f} kW
- 超出申报量: {over_amount:.1f} kW
- 超申报次数: {over_declared_count} 次

### 风险分析
- 需量利用率: {utilization_rate:.1%}
- 预估年超需量罚款: ¥{penalty_estimate:.0f}

### 优化建议
- **建议申报需量**: {recommended_demand:.0f} {meter_point.demand_type}
- 需量增加: {recommended_demand - declared_demand:.0f} {meter_point.demand_type}

### 或采取削峰措施
1. 安装需量控制系统
2. 优化大功率设备启动顺序
3. 实施负荷错峰调度
                    """.strip(),
                    estimated_saving=0,
                    estimated_cost_saving=-penalty_estimate,  # 负数表示避免损失
                    implementation_difficulty=1,
                    priority=PluginPriority.CRITICAL,
                    payback_period=0,
                    analysis_data={
                        'meter_point_id': mp_id,
                        'meter_code': meter_point.meter_code,
                        'declared_demand': declared_demand,
                        'recommended_demand': recommended_demand,
                        'max_demand_12m': max_demand_12m,
                        'utilization_rate': utilization_rate,
                        'over_amount': over_amount,
                        'over_declared_count': over_declared_count,
                        'optimization_type': 'increase_or_shave'
                    },
                    confidence=95
                ))

            # 情况3: 需量配置合理但有优化空间
            elif low_threshold <= utilization_rate <= 0.95:
                # 检查是否有削峰空间
                if std_dev > avg_max_demand * 0.15:  # 波动较大
                    peak_shave_target = max_demand_12m - demand_95th
                    potential_saving = peak_shave_target * demand_price * 12

                    if potential_saving > 5000:
                        results.append(self.create_suggestion(
                            title=f"实施计量点{meter_point.meter_code}需量削峰",
                            description=f"需量波动较大，通过削峰可降低{peak_shave_target:.1f}kW需量，年节省¥{potential_saving:.0f}",
                            detail=f"""
## 需量削峰分析

### 计量点信息
- 编码: {meter_point.meter_code}
- 当前申报需量: {declared_demand:.0f} {meter_point.demand_type}

### 需量波动分析
- 最大需量: {max_demand_12m:.1f} kW
- 95%分位数: {demand_95th:.1f} kW
- 需量波动: {std_dev:.1f} kW ({std_dev/avg_max_demand*100:.1f}%)

### 削峰建议
- 目标削减: {peak_shave_target:.1f} kW
- 削峰后需量: {demand_95th:.1f} kW
- 预计年节省: ¥{potential_saving:.0f}

### 削峰措施
1. **需量控制系统**: 实时监控，自动卸载非关键负荷
2. **设备启动优化**: 大功率设备分时启动
3. **储能削峰**: 考虑安装储能系统
                            """.strip(),
                            estimated_saving=0,
                            estimated_cost_saving=potential_saving,
                            implementation_difficulty=3,
                            priority=PluginPriority.MEDIUM,
                            payback_period=36,  # 约3年
                            analysis_data={
                                'meter_point_id': mp_id,
                                'peak_shave_target': peak_shave_target,
                                'demand_variation': std_dev / avg_max_demand,
                                'optimization_type': 'peak_shaving'
                            },
                            confidence=75
                        ))

        return results

    async def _analyze_demand_legacy(self, context: AnalysisContext) -> List[SuggestionResult]:
        """传统需量分析 (兼容无计量点数据的情况)"""
        results = []

        if not context.bill_data or len(context.bill_data) < 3:
            self._logger.warning("账单数据不足，跳过分析")
            return results

        # 提取需量数据
        demands = [b.max_demand for b in context.bill_data if b.max_demand > 0]
        if not demands:
            # 从功率数据估算
            if context.power_data:
                total_power = sum(p.active_power for p in context.power_data)
                demands = [total_power * 1.2]  # 估算峰值

        if not demands:
            return results

        avg_demand = statistics.mean(demands)
        max_demand = max(demands)
        min_demand = min(demands)

        thresholds = self._config.thresholds
        demand_price = context.pricing_config.get('demand_price', thresholds.get('demand_price', 38.0))

        # 分析需量波动
        if len(demands) >= 3:
            demand_variation = (max_demand - min_demand) / avg_demand if avg_demand > 0 else 0
            variation_threshold = 0.3

            if demand_variation > variation_threshold:
                target_demand = avg_demand * 1.1
                demand_reduction = max_demand - target_demand
                monthly_saving = demand_reduction * demand_price
                yearly_saving = monthly_saving * 12

                if yearly_saving > 5000:
                    results.append(self.create_suggestion(
                        title="降低需量峰值波动",
                        description=f"需量波动率 {demand_variation:.1%}，建议实施削峰措施",
                        detail=f"""
## 分析结果

### 当前状态
- 最大需量: {max_demand:.1f} kW
- 平均需量: {avg_demand:.1f} kW
- 最小需量: {min_demand:.1f} kW
- 波动率: {demand_variation:.1%}

### 需量电费分析
- 当前月均需量电费: ¥{max_demand * demand_price:.0f}
- 需量电价: ¥{demand_price}/kW·月

### 建议措施
1. **安装需量控制系统**: 实时监控功率，在接近限值时自动卸载非关键负荷
2. **负荷错峰启动**: 大功率设备采用顺序启动，避免同时启动造成需量峰值
3. **储能系统削峰**: 考虑安装储能系统在峰值时段放电削峰

### 预期效果
- 需量降低: {demand_reduction:.1f} kW
- 月节省: ¥{monthly_saving:.0f}
- 年节省: ¥{yearly_saving:.0f}
                        """.strip(),
                        estimated_saving=demand_reduction * 12,
                        estimated_cost_saving=yearly_saving,
                        implementation_difficulty=3,
                        priority=PluginPriority.HIGH if yearly_saving > 20000 else PluginPriority.MEDIUM,
                        payback_period=50000 / monthly_saving if monthly_saving > 0 else None,
                        analysis_data={
                            'max_demand': max_demand,
                            'avg_demand': avg_demand,
                            'demand_variation': demand_variation,
                            'target_demand': target_demand,
                            'demand_reduction': demand_reduction
                        },
                        confidence=80
                    ))

        return results

    async def _analyze_device_contribution(self, context: AnalysisContext) -> List[SuggestionResult]:
        """设备需量贡献分析"""
        results = []

        # 获取高功率设备
        high_power_devices = [
            d for d in context.device_data
            if d.rated_power and d.rated_power > 10
        ]

        if len(high_power_devices) < 3:
            return results

        # 按功率排序
        high_power_devices.sort(key=lambda d: d.rated_power or 0, reverse=True)

        total_rated = sum(d.rated_power for d in high_power_devices if d.rated_power)
        concurrent_start_power = total_rated * 1.5  # 启动电流约为额定1.5倍

        # 估算当前最大需量
        if context.bill_data:
            max_demand = max(b.max_demand for b in context.bill_data if b.max_demand > 0)
        else:
            max_demand = total_rated * 0.7

        if concurrent_start_power > max_demand * 1.2:
            demand_price = context.pricing_config.get('demand_price', 38.0)
            potential_saving = (concurrent_start_power - max_demand) * demand_price * 12 * 0.3

            # 生成设备贡献表
            device_table = "\n".join([
                f"| {d.device_name} | {d.device_type} | {d.rated_power:.1f} | {(d.rated_power/total_rated*100):.1f}% |"
                for d in high_power_devices[:8]
            ])

            # 分析可控设备
            controllable_devices = [
                d for d in high_power_devices
                if d.is_shiftable or d.device_type in ['HVAC', 'PUMP', 'LIGHTING']
            ]

            controllable_list = "\n".join([
                f"- {d.device_name}: {d.rated_power:.1f}kW"
                for d in controllable_devices[:5]
            ]) if controllable_devices else "暂无可控设备数据"

            results.append(self.create_suggestion(
                title="优化大功率设备启动策略",
                description=f"检测到{len(high_power_devices)}台大功率设备，建议错峰启动避免需量峰值",
                detail=f"""
## 设备需量贡献分析

### 大功率设备清单
| 设备名称 | 类型 | 额定功率(kW) | 占比 |
|---------|------|-------------|------|
{device_table}

### 风险分析
- 设备总额定功率: {total_rated:.1f} kW
- 同时启动峰值估算: {concurrent_start_power:.1f} kW
- 当前最大需量: {max_demand:.1f} kW

### 可调控设备
{controllable_list}

### 建议措施
1. **设置启动延时**: 为每台设备设置不同的启动延时，间隔30-60秒
2. **智能启动控制**: 安装智能控制系统，根据当前负载自动调节启动顺序
3. **软启动装置**: 为大功率电机配置软启动装置

### 预期效果
- 避免需量突增
- 潜在年节省: ¥{potential_saving:.0f}
                """.strip(),
                estimated_saving=0,
                estimated_cost_saving=potential_saving,
                implementation_difficulty=2,
                priority=PluginPriority.MEDIUM,
                related_devices=[d.device_name for d in high_power_devices[:5]],
                analysis_data={
                    'high_power_devices': len(high_power_devices),
                    'total_rated_power': total_rated,
                    'concurrent_start_power': concurrent_start_power,
                    'max_demand': max_demand,
                    'controllable_devices': len(controllable_devices),
                    'top_devices': [
                        {'name': d.device_name, 'power': d.rated_power, 'type': d.device_type}
                        for d in high_power_devices[:5]
                    ]
                },
                confidence=70
            ))

        return results

    def _calculate_optimal_demand(
        self,
        reference_demand: float,
        safety_margin: float,
        demand_type: str
    ) -> float:
        """计算最优申报需量"""
        # 添加安全裕度
        optimal = reference_demand * (1 + safety_margin)

        # 按照供电局要求取整 (通常5或10的倍数)
        if demand_type == 'kVA':
            # kVA通常按10取整
            optimal = math.ceil(optimal / 10) * 10
        else:
            # kW按5取整
            optimal = math.ceil(optimal / 5) * 5

        return optimal
