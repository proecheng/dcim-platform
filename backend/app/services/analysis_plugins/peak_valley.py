"""
峰谷优化分析插件
Peak-Valley Optimization Analysis Plugin

分析峰谷电价利用情况，优化用电时段分布
Analyzes peak-valley pricing utilization and optimizes electricity usage distribution
"""

from typing import List
import statistics

from .base import (
    AnalysisPlugin,
    AnalysisContext,
    SuggestionResult,
    PluginConfig,
    PluginPriority,
    SuggestionType
)


class PeakValleyOptimizationPlugin(AnalysisPlugin):
    """
    峰谷优化分析插件

    分析内容:
    - 峰谷平电量分布
    - 电价差利用效率
    - 储能系统可行性分析
    """

    @property
    def plugin_id(self) -> str:
        return "peak_valley_optimization"

    @property
    def plugin_name(self) -> str:
        return "峰谷优化分析"

    @property
    def plugin_description(self) -> str:
        return "分析峰谷电价利用情况，提供储能和负荷调度建议"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.PEAK_VALLEY

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=40,
            min_data_days=30,
            thresholds={
                'ideal_peak_ratio': 0.30,       # 理想峰时占比
                'ideal_valley_ratio': 0.35,     # 理想谷时占比
                'storage_threshold': 100,        # 储能建议阈值 kWh/日
                'storage_cost_per_kwh': 1500    # 储能系统单价 元/kWh
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行峰谷优化分析"""
        results = []

        if not context.energy_data:
            self._logger.warning("无能耗数据，跳过分析")
            return results

        # 计算平均能耗分布
        total_energy = sum(d.total_energy for d in context.energy_data)
        total_peak = sum(d.peak_energy for d in context.energy_data)
        total_valley = sum(d.valley_energy for d in context.energy_data)
        total_flat = sum(d.flat_energy for d in context.energy_data)
        total_cost = sum(d.total_cost for d in context.energy_data)

        days = len(context.energy_data)
        if days == 0 or total_energy == 0:
            return results

        peak_ratio = total_peak / total_energy
        valley_ratio = total_valley / total_energy
        flat_ratio = total_flat / total_energy

        daily_avg_energy = total_energy / days
        daily_avg_cost = total_cost / days

        thresholds = self._config.thresholds
        ideal_peak = thresholds.get('ideal_peak_ratio', 0.30)
        ideal_valley = thresholds.get('ideal_valley_ratio', 0.35)

        pricing = context.pricing_config
        peak_price = pricing.get('peak_price', 1.2)
        valley_price = pricing.get('valley_price', 0.4)
        flat_price = pricing.get('flat_price', 0.8)
        price_diff = peak_price - valley_price

        # 计算当前平均电价
        avg_price = total_cost / total_energy if total_energy > 0 else 0.8

        # 计算理想情况下的平均电价
        ideal_avg_price = ideal_peak * peak_price + ideal_valley * valley_price + (1 - ideal_peak - ideal_valley) * flat_price

        # 分析1: 综合峰谷优化建议
        price_saving_potential = (avg_price - ideal_avg_price) * daily_avg_energy * 365

        if price_saving_potential > 5000:
            results.append(self.create_suggestion(
                title="优化峰谷时段用电分布",
                description=f"当前电价利用效率可提升，年节省潜力 ¥{price_saving_potential:.0f}",
                detail=f"""
## 分析结果

### 当前用电分布
| 时段 | 电量占比 | 理想占比 | 电价 |
|------|----------|----------|------|
| 峰时 | {peak_ratio:.1%} | {ideal_peak:.1%} | ¥{peak_price}/kWh |
| 平时 | {flat_ratio:.1%} | {1-ideal_peak-ideal_valley:.1%} | ¥{flat_price}/kWh |
| 谷时 | {valley_ratio:.1%} | {ideal_valley:.1%} | ¥{valley_price}/kWh |

### 电价分析
- 当前平均电价: ¥{avg_price:.3f}/kWh
- 理想平均电价: ¥{ideal_avg_price:.3f}/kWh
- 峰谷价差: ¥{price_diff:.2f}/kWh

### 日均用电
- 日均电量: {daily_avg_energy:.1f} kWh
- 日均电费: ¥{daily_avg_cost:.2f}

### 优化建议
1. **负荷调度优化**
   - 将可调度负荷从峰时转移到谷时
   - 目标: 峰时占比降至 {ideal_peak:.1%}

2. **作业时间调整**
   - 批处理任务安排在谷时执行
   - 非紧急维护工作调整到谷时

3. **储能系统评估**
   - 通过储能实现峰谷套利
   - 详见储能专项分析

### 预期效果
- 年节省电费: ¥{price_saving_potential:.0f}
                """.strip(),
                estimated_saving=(avg_price - ideal_avg_price) * daily_avg_energy * 365 / price_diff,  # 转换为kWh
                estimated_cost_saving=price_saving_potential,
                implementation_difficulty=2,
                priority=PluginPriority.HIGH if price_saving_potential > 20000 else PluginPriority.MEDIUM,
                payback_period=0,
                analysis_data={
                    'peak_ratio': peak_ratio,
                    'valley_ratio': valley_ratio,
                    'flat_ratio': flat_ratio,
                    'avg_price': avg_price,
                    'ideal_avg_price': ideal_avg_price,
                    'price_diff': price_diff
                },
                confidence=85
            ))

        # 分析2: 储能系统可行性
        daily_peak_energy = daily_avg_energy * peak_ratio
        storage_threshold = thresholds.get('storage_threshold', 100)

        if daily_peak_energy > storage_threshold:
            # 计算储能容量需求 (转移30%峰时电量)
            shift_ratio = 0.3
            storage_capacity = daily_peak_energy * shift_ratio

            # 计算收益
            daily_saving = storage_capacity * price_diff * 0.85  # 85%效率
            yearly_saving = daily_saving * 365

            # 计算投资
            storage_cost = thresholds.get('storage_cost_per_kwh', 1500)
            investment = storage_capacity * storage_cost

            # 回报期
            payback_years = investment / yearly_saving if yearly_saving > 0 else 999

            if payback_years < 8:  # 8年内回本才建议
                results.append(self.create_suggestion(
                    title="储能系统投资分析",
                    description=f"建议配置 {storage_capacity:.0f}kWh 储能系统实现峰谷套利",
                    detail=f"""
## 储能系统可行性分析

### 需求分析
- 日均用电量: {daily_avg_energy:.1f} kWh
- 日均峰时电量: {daily_peak_energy:.1f} kWh
- 建议转移电量: {storage_capacity:.1f} kWh/日

### 储能系统配置建议
- 储能容量: {storage_capacity:.0f} kWh
- 功率配置: {storage_capacity/4:.0f} kW (4小时放电)
- 系统效率: 85%

### 投资收益分析
| 项目 | 数值 |
|------|------|
| 系统投资 | ¥{investment:.0f} |
| 日节省电费 | ¥{daily_saving:.2f} |
| 年节省电费 | ¥{yearly_saving:.0f} |
| 投资回报期 | {payback_years:.1f} 年 |

### 峰谷套利策略
- 谷时(23:00-7:00)充电，利用低电价
- 峰时(8:00-11:00, 18:00-21:00)放电，减少高价用电
- 自动控制系统实现智能充放电

### 附加收益
- 提升供电可靠性
- 削峰降低需量电费
- 参与电网需求响应

### 风险提示
- 电池衰减: 年衰减约3%
- 运维成本: 约投资额的2%/年
- 政策变化: 峰谷电价政策可能调整
                    """.strip(),
                    estimated_saving=storage_capacity * 365 * 0.85,
                    estimated_cost_saving=yearly_saving,
                    implementation_difficulty=4,
                    priority=PluginPriority.MEDIUM,
                    payback_period=payback_years * 12,
                    analysis_data={
                        'storage_capacity': storage_capacity,
                        'investment': investment,
                        'yearly_saving': yearly_saving,
                        'payback_years': payback_years,
                        'daily_peak_energy': daily_peak_energy
                    },
                    confidence=75
                ))

        return results
