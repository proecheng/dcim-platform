"""
设备效率分析插件
Equipment Efficiency Analysis Plugin

分析设备运行效率，识别低效设备
Analyzes equipment operating efficiency and identifies inefficient devices
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


class EquipmentEfficiencyPlugin(AnalysisPlugin):
    """
    设备效率分析插件

    分析内容:
    - 设备负载率分析
    - 设备效率评估
    - 设备更换建议
    """

    @property
    def plugin_id(self) -> str:
        return "equipment_efficiency"

    @property
    def plugin_name(self) -> str:
        return "设备效率分析"

    @property
    def plugin_description(self) -> str:
        return "分析设备运行效率和负载率，识别优化机会"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.EQUIPMENT_EFFICIENCY

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=60,
            min_data_days=7,
            thresholds={
                'min_load_rate': 0.30,          # 最低负载率
                'optimal_load_rate_min': 0.40,  # 最佳负载率下限
                'optimal_load_rate_max': 0.80,  # 最佳负载率上限
                'min_efficiency': 0.85,         # 最低效率阈值
                'ups_target_efficiency': 0.95,  # UPS目标效率
                'old_equipment_years': 8        # 老旧设备年限
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行设备效率分析"""
        results = []

        if not context.device_data and not context.power_data:
            self._logger.warning("无设备数据，跳过分析")
            return results

        thresholds = self._config.thresholds
        min_load_rate = thresholds.get('min_load_rate', 0.30)
        optimal_min = thresholds.get('optimal_load_rate_min', 0.40)
        optimal_max = thresholds.get('optimal_load_rate_max', 0.80)
        min_efficiency = thresholds.get('min_efficiency', 0.85)

        # 使用power_data获取负载率信息
        devices_with_load = []
        for p in context.power_data:
            devices_with_load.append({
                'name': p.device_name,
                'type': p.device_type,
                'load_rate': p.load_rate / 100 if p.load_rate > 1 else p.load_rate,
                'power': p.active_power,
                'power_factor': p.power_factor
            })

        # 补充device_data中的信息
        for d in context.device_data:
            found = False
            for item in devices_with_load:
                if item['name'] == d.device_name:
                    item['efficiency'] = d.efficiency / 100 if d.efficiency > 1 else d.efficiency
                    item['rated_power'] = d.rated_power
                    found = True
                    break
            if not found:
                load_rate = d.current_power / d.rated_power if d.rated_power > 0 else 0
                devices_with_load.append({
                    'name': d.device_name,
                    'type': d.device_type,
                    'load_rate': load_rate,
                    'power': d.current_power,
                    'rated_power': d.rated_power,
                    'efficiency': d.efficiency / 100 if d.efficiency > 1 else d.efficiency
                })

        if not devices_with_load:
            return results

        # 分析1: 低负载率设备
        low_load_devices = [d for d in devices_with_load
                          if d.get('load_rate', 0) < min_load_rate and d.get('load_rate', 0) > 0]

        if low_load_devices:
            total_wasted_capacity = sum(
                (d.get('rated_power', 0) * (min_load_rate - d['load_rate']))
                for d in low_load_devices if d.get('rated_power', 0) > 0
            )

            # 低负载运行的效率损失
            efficiency_loss = 0
            for d in low_load_devices:
                # UPS在低负载时效率下降
                if d['type'] == 'UPS':
                    # 假设UPS在30%负载时效率为90%，在10%负载时效率为80%
                    actual_efficiency = 0.8 + 0.2 * (d['load_rate'] / 0.5) if d['load_rate'] < 0.5 else 0.92
                    target_efficiency = 0.92
                    efficiency_loss += d.get('power', 0) * (target_efficiency - actual_efficiency) / actual_efficiency

            yearly_loss = efficiency_loss * 24 * 365 * 0.8

            results.append(self.create_suggestion(
                title="优化低负载率设备",
                description=f"发现 {len(low_load_devices)} 台设备负载率低于 {min_load_rate:.0%}",
                detail=f"""
## 低负载率设备分析

### 低负载设备清单
| 设备名称 | 类型 | 负载率 | 功率(kW) |
|----------|------|--------|----------|
{chr(10).join([f"| {d['name']} | {d['type']} | {d['load_rate']:.1%} | {d.get('power', 0):.1f} |" for d in low_load_devices[:10]])}

### 问题分析
设备长期低负载运行的问题:
1. **能效降低**: UPS/变压器在低负载时效率下降
2. **投资浪费**: 设备容量未充分利用
3. **维护成本**: 相同的维护成本，产出效益低

### 优化建议
1. **负载整合**
   - 将负载集中到部分设备
   - 关停冗余的低载设备

2. **容量规划**
   - 评估实际需求
   - 下次更新时选择合适容量

3. **UPS优化**
   - 多台UPS考虑N+1模式运行
   - 使用ECO模式提升效率

### 预期效果
- 减少闲置容量: {total_wasted_capacity:.1f} kW
- 年节省电费: ¥{yearly_loss:.0f}
                """.strip(),
                estimated_saving=efficiency_loss * 24 * 365,
                estimated_cost_saving=yearly_loss,
                implementation_difficulty=3,
                priority=PluginPriority.MEDIUM,
                related_devices=[d['name'] for d in low_load_devices[:5]],
                analysis_data={
                    'low_load_count': len(low_load_devices),
                    'wasted_capacity': total_wasted_capacity,
                    'efficiency_loss': efficiency_loss
                },
                confidence=80
            ))

        # 分析2: 高负载率设备（过载风险）
        high_load_devices = [d for d in devices_with_load
                           if d.get('load_rate', 0) > optimal_max]

        if high_load_devices:
            overload_risk_devices = [d for d in high_load_devices if d['load_rate'] > 0.90]

            results.append(self.create_suggestion(
                title="关注高负载率设备",
                description=f"发现 {len(high_load_devices)} 台设备负载率超过 {optimal_max:.0%}",
                detail=f"""
## 高负载率设备分析

### 高负载设备清单
| 设备名称 | 类型 | 负载率 | 功率(kW) | 风险等级 |
|----------|------|--------|----------|----------|
{chr(10).join([f"| {d['name']} | {d['type']} | {d['load_rate']:.1%} | {d.get('power', 0):.1f} | {'🔴 高' if d['load_rate'] > 0.9 else '🟡 中'} |" for d in high_load_devices[:10]])}

### 风险分析
1. **过载风险**: 负载率 > 90% 存在过载保护触发风险
2. **寿命影响**: 长期高负载运行加速设备老化
3. **冗余不足**: 高负载状态下冗余切换能力受限

### 建议措施
1. **短期措施**
   - 密切监控高负载设备
   - 制定应急预案

2. **中期措施**
   - 负载均衡调整
   - 评估扩容需求

3. **长期措施**
   - 容量规划升级
   - 增加冗余设备

### 优先处理
{chr(10).join([f"- ⚠️ {d['name']}: 负载率 {d['load_rate']:.1%}" for d in overload_risk_devices[:3]])}
                """.strip(),
                estimated_saving=0,
                estimated_cost_saving=0,
                implementation_difficulty=3,
                priority=PluginPriority.HIGH if overload_risk_devices else PluginPriority.MEDIUM,
                related_devices=[d['name'] for d in high_load_devices[:5]],
                analysis_data={
                    'high_load_count': len(high_load_devices),
                    'overload_risk_count': len(overload_risk_devices)
                },
                confidence=90
            ))

        # 分析3: 低效率设备
        low_efficiency_devices = [d for d in devices_with_load
                                 if d.get('efficiency', 1) < min_efficiency and d.get('efficiency', 0) > 0]

        if low_efficiency_devices:
            total_loss = sum(
                d.get('power', 0) * (min_efficiency - d['efficiency']) / d['efficiency']
                for d in low_efficiency_devices
            )
            yearly_loss = total_loss * 24 * 365 * 0.8

            results.append(self.create_suggestion(
                title="更换低效率设备",
                description=f"发现 {len(low_efficiency_devices)} 台设备效率低于 {min_efficiency:.0%}",
                detail=f"""
## 低效率设备分析

### 低效率设备清单
| 设备名称 | 类型 | 当前效率 | 目标效率 | 功率损耗(kW) |
|----------|------|----------|----------|--------------|
{chr(10).join([f"| {d['name']} | {d['type']} | {d.get('efficiency', 0):.1%} | {min_efficiency:.0%} | {d.get('power', 0) * (min_efficiency - d['efficiency']) / max(d['efficiency'], 0.01):.2f} |" for d in low_efficiency_devices[:10]])}

### 效率损失分析
- 总功率损耗: {total_loss:.2f} kW
- 年电量损失: {total_loss * 24 * 365:.0f} kWh
- 年电费损失: ¥{yearly_loss:.0f}

### 优化建议
1. **设备维护**
   - 检查设备是否需要维护保养
   - 清洁散热系统，改善运行环境

2. **设备更换**
   - 评估更换高效设备的经济性
   - 优先更换效率最低的设备

3. **运行优化**
   - 调整运行参数
   - 优化负载分配

### 投资建议
| 设备类型 | 新设备效率 | 投资回报期 |
|----------|------------|------------|
| UPS | 95-97% | 3-5年 |
| 精密空调 | COP > 4.0 | 4-6年 |
| 变压器 | 99% | 8-10年 |
                """.strip(),
                estimated_saving=total_loss * 24 * 365,
                estimated_cost_saving=yearly_loss,
                implementation_difficulty=4,
                priority=PluginPriority.MEDIUM if yearly_loss > 10000 else PluginPriority.LOW,
                related_devices=[d['name'] for d in low_efficiency_devices[:5]],
                analysis_data={
                    'low_efficiency_count': len(low_efficiency_devices),
                    'total_power_loss': total_loss,
                    'yearly_loss': yearly_loss
                },
                confidence=75
            ))

        # 分析4: 设备整体健康度评估
        if devices_with_load:
            avg_load_rate = statistics.mean([d.get('load_rate', 0) for d in devices_with_load if d.get('load_rate', 0) > 0])
            optimal_devices = [d for d in devices_with_load
                             if optimal_min <= d.get('load_rate', 0) <= optimal_max]
            optimal_ratio = len(optimal_devices) / len(devices_with_load)

            if optimal_ratio < 0.5:
                results.append(self.create_suggestion(
                    title="改善设备整体负载分布",
                    description=f"仅 {optimal_ratio:.0%} 设备在最佳负载区间运行",
                    detail=f"""
## 设备负载分布分析

### 负载分布统计
| 负载区间 | 设备数量 | 占比 | 状态 |
|----------|----------|------|------|
| < 30% (低载) | {len([d for d in devices_with_load if d.get('load_rate', 0) < 0.3])} | {len([d for d in devices_with_load if d.get('load_rate', 0) < 0.3])/len(devices_with_load)*100:.0f}% | ⚠️ 效率低 |
| 30-40% | {len([d for d in devices_with_load if 0.3 <= d.get('load_rate', 0) < 0.4])} | {len([d for d in devices_with_load if 0.3 <= d.get('load_rate', 0) < 0.4])/len(devices_with_load)*100:.0f}% | 一般 |
| 40-80% (最佳) | {len(optimal_devices)} | {optimal_ratio*100:.0f}% | ✅ 最佳 |
| > 80% (高载) | {len([d for d in devices_with_load if d.get('load_rate', 0) > 0.8])} | {len([d for d in devices_with_load if d.get('load_rate', 0) > 0.8])/len(devices_with_load)*100:.0f}% | ⚠️ 风险 |

### 整体指标
- 平均负载率: {avg_load_rate:.1%}
- 最佳区间设备比例: {optimal_ratio:.1%}
- 目标: > 60%

### 优化方向
1. 整合低负载设备的负载
2. 分散高负载设备的负载
3. 合理规划容量配置
                    """.strip(),
                    estimated_saving=0,
                    estimated_cost_saving=0,
                    implementation_difficulty=3,
                    priority=PluginPriority.LOW,
                    analysis_data={
                        'avg_load_rate': avg_load_rate,
                        'optimal_ratio': optimal_ratio,
                        'device_count': len(devices_with_load)
                    },
                    confidence=85
                ))

        return results
