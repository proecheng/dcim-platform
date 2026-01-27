"""
PUE优化分析插件
PUE Optimization Analysis Plugin

分析数据中心PUE，提供能效优化建议
Analyzes data center PUE and provides energy efficiency optimization suggestions
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


class PUEOptimizationPlugin(AnalysisPlugin):
    """
    PUE优化分析插件

    分析内容:
    - PUE趋势分析
    - 制冷效率分析
    - PUE优化建议
    """

    @property
    def plugin_id(self) -> str:
        return "pue_optimization"

    @property
    def plugin_name(self) -> str:
        return "PUE优化分析"

    @property
    def plugin_description(self) -> str:
        return "分析数据中心PUE指标，识别能效提升机会"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.PUE_OPTIMIZATION

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=50,
            min_data_days=7,
            thresholds={
                'target_pue': 1.4,              # 目标PUE
                'excellent_pue': 1.2,           # 优秀PUE
                'poor_pue': 1.8,                # 较差PUE
                'cooling_efficiency_threshold': 0.4  # 制冷占比阈值
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行PUE优化分析"""
        results = []

        if not context.environment_data:
            self._logger.warning("无环境数据，跳过分析")
            return results

        # 计算PUE统计
        pue_values = [e.pue for e in context.environment_data if e.pue > 0]
        if not pue_values:
            return results

        avg_pue = statistics.mean(pue_values)
        min_pue = min(pue_values)
        max_pue = max(pue_values)
        pue_std = statistics.stdev(pue_values) if len(pue_values) > 1 else 0

        # 计算功率统计
        it_powers = [e.it_power for e in context.environment_data if e.it_power > 0]
        cooling_powers = [e.cooling_power for e in context.environment_data if e.cooling_power > 0]
        total_powers = [e.total_power for e in context.environment_data if e.total_power > 0]

        avg_it_power = statistics.mean(it_powers) if it_powers else 0
        avg_cooling_power = statistics.mean(cooling_powers) if cooling_powers else 0
        avg_total_power = statistics.mean(total_powers) if total_powers else 0

        cooling_ratio = avg_cooling_power / avg_total_power if avg_total_power > 0 else 0.3

        thresholds = self._config.thresholds
        target_pue = thresholds.get('target_pue', 1.4)
        excellent_pue = thresholds.get('excellent_pue', 1.2)
        poor_pue = thresholds.get('poor_pue', 1.8)

        # 分析1: PUE水平评估
        if avg_pue > target_pue:
            # 计算PUE改善后的节能量
            # 降低0.1 PUE约节省 IT负载的10%
            pue_reduction = avg_pue - target_pue
            energy_saving_ratio = pue_reduction / avg_pue
            daily_saving_kwh = avg_total_power * 24 * energy_saving_ratio

            # 假设平均电价0.8元/kWh
            daily_saving_cost = daily_saving_kwh * 0.8
            yearly_saving = daily_saving_cost * 365

            pue_level = "较差" if avg_pue > poor_pue else "一般" if avg_pue > target_pue else "良好"

            results.append(self.create_suggestion(
                title="降低数据中心PUE",
                description=f"当前PUE {avg_pue:.2f} ({pue_level})，建议优化至 {target_pue:.1f}",
                detail=f"""
## PUE分析报告

### 当前PUE状态
| 指标 | 数值 | 评价 |
|------|------|------|
| 平均PUE | {avg_pue:.2f} | {pue_level} |
| 最低PUE | {min_pue:.2f} | - |
| 最高PUE | {max_pue:.2f} | - |
| PUE波动 | ±{pue_std:.2f} | {'稳定' if pue_std < 0.1 else '波动较大'} |

### 功率分布
| 类别 | 功率(kW) | 占比 |
|------|----------|------|
| IT负载 | {avg_it_power:.1f} | {avg_it_power/avg_total_power*100:.1f}% |
| 制冷系统 | {avg_cooling_power:.1f} | {cooling_ratio*100:.1f}% |
| 其他 | {avg_total_power-avg_it_power-avg_cooling_power:.1f} | {(1-avg_it_power/avg_total_power-cooling_ratio)*100:.1f}% |
| 总功率 | {avg_total_power:.1f} | 100% |

### PUE等级标准
| 等级 | PUE范围 | 说明 |
|------|---------|------|
| 优秀 | < {excellent_pue} | 高效数据中心 |
| 良好 | {excellent_pue} - {target_pue} | 行业先进水平 |
| 一般 | {target_pue} - {poor_pue} | 有优化空间 |
| 较差 | > {poor_pue} | 亟需改善 |

### 优化建议
1. **提升制冷效率**
   - 优化送风温度和气流组织
   - 采用热通道/冷通道封闭
   - 提高冷冻水供水温度

2. **降低制冷负荷**
   - 服务器进风温度可提高至27°C
   - 安装热交换器利用自然冷却
   - 优化机柜布局减少热点

3. **减少配电损耗**
   - 提高UPS运行效率
   - 优化配电路径

### 预期效果
- PUE目标: {target_pue}
- PUE降低: {pue_reduction:.2f}
- 日节省电量: {daily_saving_kwh:.1f} kWh
- 年节省电费: ¥{yearly_saving:.0f}
                """.strip(),
                estimated_saving=daily_saving_kwh * 365,
                estimated_cost_saving=yearly_saving,
                implementation_difficulty=3,
                priority=PluginPriority.HIGH if avg_pue > poor_pue else PluginPriority.MEDIUM,
                payback_period=6,  # 大部分措施6个月内见效
                analysis_data={
                    'avg_pue': avg_pue,
                    'min_pue': min_pue,
                    'max_pue': max_pue,
                    'target_pue': target_pue,
                    'pue_reduction': pue_reduction,
                    'cooling_ratio': cooling_ratio,
                    'daily_saving_kwh': daily_saving_kwh
                },
                confidence=85
            ))

        # 分析2: 制冷效率分析
        cooling_threshold = thresholds.get('cooling_efficiency_threshold', 0.4)
        if cooling_ratio > cooling_threshold:
            excess_cooling_ratio = cooling_ratio - cooling_threshold
            potential_saving = avg_cooling_power * excess_cooling_ratio / cooling_ratio
            yearly_saving = potential_saving * 24 * 365 * 0.8

            results.append(self.create_suggestion(
                title="优化制冷系统能耗",
                description=f"制冷占比 {cooling_ratio:.1%}，高于建议值 {cooling_threshold:.1%}",
                detail=f"""
## 制冷系统分析

### 当前状态
- 制冷功率: {avg_cooling_power:.1f} kW
- IT负载功率: {avg_it_power:.1f} kW
- 制冷占比: {cooling_ratio:.1%}
- 建议占比: < {cooling_threshold:.1%}

### 问题分析
制冷系统能耗偏高可能原因:
1. 送风温度设置过低
2. 气流组织不合理，存在热点或短循环
3. 制冷设备效率下降
4. 冷却方式不够节能

### 优化建议
1. **提高送风温度**
   - 当前机房温度如低于24°C，可适当提高
   - 每提高1°C可节能约4%

2. **优化气流组织**
   - 封闭冷/热通道
   - 安装盲板封堵空置机柜位置
   - 调整出风口方向

3. **变频改造**
   - 精密空调变频改造
   - 冷冻水泵变频控制

4. **自然冷却**
   - 室外温度低于18°C时利用新风
   - 考虑间接蒸发冷却系统

### 预期效果
- 可节省制冷功率: {potential_saving:.1f} kW
- 年节省电费: ¥{yearly_saving:.0f}
                """.strip(),
                estimated_saving=potential_saving * 24 * 365,
                estimated_cost_saving=yearly_saving,
                implementation_difficulty=3,
                priority=PluginPriority.MEDIUM,
                analysis_data={
                    'cooling_power': avg_cooling_power,
                    'it_power': avg_it_power,
                    'cooling_ratio': cooling_ratio,
                    'target_ratio': cooling_threshold,
                    'potential_saving': potential_saving
                },
                confidence=80
            ))

        # 分析3: PUE波动分析
        if pue_std > 0.15:
            results.append(self.create_suggestion(
                title="改善PUE稳定性",
                description=f"PUE波动较大 (标准差 {pue_std:.2f})，建议优化控制",
                detail=f"""
## PUE波动分析

### 当前状态
- PUE范围: {min_pue:.2f} ~ {max_pue:.2f}
- 标准差: {pue_std:.2f}
- 波动幅度: {(max_pue-min_pue)/avg_pue*100:.1f}%

### 可能原因
1. IT负载波动大
2. 制冷系统响应滞后
3. 温度控制精度不足
4. 季节性因素影响

### 优化建议
1. **优化制冷控制策略**
   - 采用预测性控制算法
   - 缩短控制响应时间

2. **平滑IT负载波动**
   - 负载均衡优化
   - 虚拟化资源动态调度

3. **分区温度控制**
   - 根据负载分布调整制冷
   - 热点区域重点保障

### 预期效果
- 降低PUE波动至 ±0.05
- 提升运行稳定性
- 间接节能约5%
                """.strip(),
                estimated_saving=avg_total_power * 24 * 0.05 * 365,
                estimated_cost_saving=avg_total_power * 24 * 0.05 * 365 * 0.8,
                implementation_difficulty=3,
                priority=PluginPriority.LOW,
                analysis_data={
                    'pue_std': pue_std,
                    'pue_range': max_pue - min_pue
                },
                confidence=70
            ))

        return results
