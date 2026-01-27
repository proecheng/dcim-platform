"""
功率因数分析插件
Power Factor Analysis Plugin

分析功率因数，提供无功补偿建议
Analyzes power factor and provides reactive power compensation suggestions
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


class PowerFactorPlugin(AnalysisPlugin):
    """
    功率因数分析插件

    分析内容:
    - 功率因数水平评估
    - 无功功率分析
    - 补偿容量计算
    """

    @property
    def plugin_id(self) -> str:
        return "power_factor"

    @property
    def plugin_name(self) -> str:
        return "功率因数分析"

    @property
    def plugin_description(self) -> str:
        return "分析系统功率因数，计算无功补偿需求，避免力调电费罚款"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.POWER_FACTOR

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=30,
            min_data_days=7,
            thresholds={
                'target_power_factor': 0.95,    # 目标功率因数
                'min_power_factor': 0.90,       # 最低允许功率因数
                'penalty_threshold': 0.90,      # 罚款阈值
                'reward_threshold': 0.95,       # 奖励阈值
                'penalty_rate': 0.005,          # 每0.01低于阈值罚款比例
                'reward_rate': 0.0075           # 每0.01高于阈值奖励比例
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行功率因数分析"""
        results = []

        if not context.power_data:
            self._logger.warning("无功率数据，跳过分析")
            return results

        # 计算系统平均功率因数
        power_factors = [p.power_factor for p in context.power_data if p.power_factor > 0]
        if not power_factors:
            return results

        avg_pf = statistics.mean(power_factors)
        min_pf = min(power_factors)
        max_pf = max(power_factors)

        thresholds = self._config.thresholds
        target_pf = thresholds.get('target_power_factor', 0.95)
        min_allowed_pf = thresholds.get('min_power_factor', 0.90)
        penalty_threshold = thresholds.get('penalty_threshold', 0.90)

        # 计算总功率
        total_active_power = sum(p.active_power for p in context.power_data)
        total_reactive_power = sum(p.reactive_power for p in context.power_data)
        total_apparent_power = sum(p.apparent_power for p in context.power_data)

        # 分析1: 功率因数偏低
        if avg_pf < target_pf:
            # 计算需要补偿的无功功率
            # Q_comp = P * (tan(arccos(pf_current)) - tan(arccos(pf_target)))
            import math
            current_tan = math.tan(math.acos(avg_pf))
            target_tan = math.tan(math.acos(target_pf))
            q_compensation = total_active_power * (current_tan - target_tan)

            # 计算电费影响
            # 假设月均电费 30000 元
            monthly_bill = sum(d.total_cost for d in context.energy_data) / len(context.energy_data) * 30 if context.energy_data else 30000

            if avg_pf < penalty_threshold:
                # 计算罚款
                penalty_points = int((penalty_threshold - avg_pf) * 100)
                penalty_rate = thresholds.get('penalty_rate', 0.005)
                monthly_penalty = monthly_bill * penalty_rate * penalty_points
                yearly_penalty = monthly_penalty * 12
            else:
                monthly_penalty = 0
                yearly_penalty = 0

            # 计算提升到目标后的奖励
            if target_pf > thresholds.get('reward_threshold', 0.95):
                reward_points = int((target_pf - thresholds.get('reward_threshold', 0.95)) * 100)
                reward_rate = thresholds.get('reward_rate', 0.0075)
                monthly_reward = monthly_bill * reward_rate * reward_points
                yearly_reward = monthly_reward * 12
            else:
                yearly_reward = 0

            total_benefit = yearly_penalty + yearly_reward

            # 补偿设备投资估算 (约 50-100 元/kVar)
            investment = q_compensation * 75

            priority = PluginPriority.CRITICAL if avg_pf < min_allowed_pf else (
                PluginPriority.HIGH if avg_pf < penalty_threshold else PluginPriority.MEDIUM
            )

            results.append(self.create_suggestion(
                title="提升系统功率因数",
                description=f"当前功率因数 {avg_pf:.3f}，建议提升至 {target_pf:.2f}",
                detail=f"""
## 分析结果

### 当前状态
- 平均功率因数: {avg_pf:.3f}
- 最低功率因数: {min_pf:.3f}
- 最高功率因数: {max_pf:.3f}
- 有功功率: {total_active_power:.1f} kW
- 无功功率: {total_reactive_power:.1f} kVar

### 电费影响分析
- 功率因数考核基准: {penalty_threshold}
- 当前状态: {'存在罚款风险' if avg_pf < penalty_threshold else '正常'}
- 月均罚款估算: ¥{monthly_penalty:.0f}
- 年罚款损失: ¥{yearly_penalty:.0f}

### 建议措施
1. **安装无功补偿装置**:
   - 补偿容量: {q_compensation:.1f} kVar
   - 建议采用自动投切电容器组
   - 投资估算: ¥{investment:.0f}

2. **分级补偿策略**:
   - 集中补偿: 在变压器低压侧安装集中补偿柜
   - 就地补偿: 在大功率设备处就地补偿

3. **监控与维护**:
   - 安装功率因数监测仪表
   - 定期检查补偿电容器状态

### 投资回报分析
- 设备投资: ¥{investment:.0f}
- 年节省电费: ¥{total_benefit:.0f}
- 投资回报期: {investment/total_benefit*12:.1f} 个月

### 功率因数低的设备
{chr(10).join([f"- {p.device_name}: PF={p.power_factor:.3f}" for p in sorted(context.power_data, key=lambda x: x.power_factor)[:5]])}
                """.strip(),
                estimated_saving=q_compensation,  # kVar
                estimated_cost_saving=total_benefit,
                implementation_difficulty=3,
                priority=priority,
                payback_period=investment / (total_benefit / 12) if total_benefit > 0 else None,
                related_devices=[p.device_name for p in sorted(context.power_data, key=lambda x: x.power_factor)[:5]],
                analysis_data={
                    'avg_power_factor': avg_pf,
                    'min_power_factor': min_pf,
                    'target_power_factor': target_pf,
                    'compensation_needed': q_compensation,
                    'yearly_penalty': yearly_penalty,
                    'investment': investment
                },
                confidence=85
            ))

        # 分析2: 个别设备功率因数异常低
        low_pf_devices = [p for p in context.power_data if p.power_factor < 0.85 and p.active_power > 5]
        if low_pf_devices:
            for device in low_pf_devices[:3]:  # 最多报告3个设备
                import math
                current_tan = math.tan(math.acos(device.power_factor))
                target_tan = math.tan(math.acos(0.95))
                device_q_comp = device.active_power * (current_tan - target_tan)

                results.append(self.create_suggestion(
                    title=f"设备 {device.device_name} 功率因数偏低",
                    description=f"功率因数 {device.power_factor:.3f}，建议就地补偿",
                    detail=f"""
## 设备分析

### 设备信息
- 设备名称: {device.device_name}
- 设备类型: {device.device_type}
- 有功功率: {device.active_power:.1f} kW
- 无功功率: {device.reactive_power:.1f} kVar
- 功率因数: {device.power_factor:.3f}

### 建议措施
- 就地补偿容量: {device_q_comp:.1f} kVar
- 可采用固定电容器补偿

### 注意事项
- 检查设备是否存在故障
- 确认无功负荷特性（感性/容性）
                    """.strip(),
                    estimated_saving=device_q_comp,
                    estimated_cost_saving=device_q_comp * 50,  # 简单估算
                    implementation_difficulty=2,
                    priority=PluginPriority.MEDIUM,
                    related_devices=[device.device_name],
                    analysis_data={
                        'device_name': device.device_name,
                        'power_factor': device.power_factor,
                        'compensation_needed': device_q_comp
                    },
                    confidence=80
                ))

        return results
