"""
负荷转移分析插件
Load Shifting Analysis Plugin

分析用电负荷分布，识别可转移到谷时的负荷
Analyzes electricity load distribution and identifies loads that can be shifted to valley periods

Enhanced: 支持设备级负荷转移分析、计量点关联、功率曲线分析
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from .base import (
    AnalysisPlugin,
    AnalysisContext,
    SuggestionResult,
    PluginConfig,
    PluginPriority,
    SuggestionType,
    DeviceShiftInfo,
    MeterPointData,
    PowerCurvePoint,
    EnergyData
)


class LoadShiftingPlugin(AnalysisPlugin):
    """
    负荷转移分析插件

    分析内容:
    - 峰时用电占比分析
    - 可转移负荷识别 (设备级)
    - 转移效益计算
    - 按计量点分组分析
    - 功率曲线分析
    """

    @property
    def plugin_id(self) -> str:
        return "load_shifting"

    @property
    def plugin_name(self) -> str:
        return "负荷转移分析"

    @property
    def plugin_description(self) -> str:
        return "分析用电负荷分布，识别可转移到谷时的负荷，支持设备级分析，计算节省潜力"

    @property
    def suggestion_type(self) -> SuggestionType:
        return SuggestionType.LOAD_SHIFTING

    def get_default_config(self) -> PluginConfig:
        return PluginConfig(
            plugin_id=self.plugin_id,
            name=self.plugin_name,
            enabled=True,
            execution_order=10,
            min_data_days=7,
            thresholds={
                'peak_ratio_threshold': 0.35,  # 峰时占比阈值
                'min_shift_amount': 50,        # 最小转移电量 kWh
                'shift_efficiency': 0.7,       # 转移效率（可实际转移的比例）
                'device_min_power': 5,         # 设备最小功率阈值 kW
                'min_device_shift_saving': 100 # 单设备最小年节省金额
            }
        )

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """执行负荷转移分析"""
        results = []

        if not context.energy_data:
            self._logger.warning("无能耗数据，跳过分析")
            return results

        # 1. 整体峰谷分析
        overall_results = await self._analyze_overall_peak_valley(context)
        results.extend(overall_results)

        # 2. 设备级负荷转移分析 (新增)
        device_results = await self._analyze_device_shift_potential(context)
        results.extend(device_results)

        # 3. 按计量点分组分析 (新增)
        if context.meter_points:
            meter_results = await self._analyze_by_meter_point(context)
            results.extend(meter_results)

        return results

    async def _analyze_overall_peak_valley(self, context: AnalysisContext) -> List[SuggestionResult]:
        """整体峰谷分析"""
        results = []

        # 计算平均峰时占比
        total_energy = sum(d.total_energy for d in context.energy_data)
        total_peak = sum(d.peak_energy for d in context.energy_data)
        total_valley = sum(d.valley_energy for d in context.energy_data)
        total_sharp = sum(d.sharp_energy for d in context.energy_data)

        if total_energy == 0:
            return results

        peak_ratio = (total_peak + total_sharp) / total_energy
        valley_ratio = total_valley / total_energy

        thresholds = self._config.thresholds
        peak_threshold = thresholds.get('peak_ratio_threshold', 0.35)

        # 分析1: 峰时用电占比过高
        if peak_ratio > peak_threshold:
            # 计算可转移电量
            target_peak_ratio = 0.30  # 目标峰时占比
            shiftable_energy = (peak_ratio - target_peak_ratio) * total_energy / len(context.energy_data)
            shift_efficiency = thresholds.get('shift_efficiency', 0.7)
            actual_shift = shiftable_energy * shift_efficiency

            # 计算年化节省
            peak_price = context.pricing_config.get('peak_price', 1.2)
            sharp_price = context.pricing_config.get('sharp_price', 1.5)
            valley_price = context.pricing_config.get('valley_price', 0.4)
            avg_peak_price = (peak_price + sharp_price) / 2
            price_diff = avg_peak_price - valley_price
            daily_saving = actual_shift * price_diff
            yearly_saving = daily_saving * 365

            if actual_shift >= thresholds.get('min_shift_amount', 50):
                # 获取可转移设备列表
                shiftable_devices = context.get_shiftable_devices()
                device_list = "\n".join([
                    f"- {d.device_name} ({d.device_type}): {d.rated_power:.1f}kW, 可转移{d.shiftable_power_ratio*100:.0f}%"
                    for d in shiftable_devices[:5]
                ]) if shiftable_devices else "暂无设备数据"

                results.append(self.create_suggestion(
                    title="优化峰时用电负荷",
                    description=f"当前峰时用电占比 {peak_ratio:.1%}，高于建议值 {peak_threshold:.1%}",
                    detail=f"""
## 分析结果

### 当前状态
- 峰时+尖峰用电占比: {peak_ratio:.1%}
- 谷时用电占比: {valley_ratio:.1%}
- 日均峰时电量: {(total_peak+total_sharp)/len(context.energy_data):.1f} kWh

### 可转移设备清单
{device_list}

### 建议措施
1. **批量作业调度优化**: 将数据备份、报表生成等批量任务调整到谷时(0:00-7:00)执行
2. **UPS充电时间调整**: 将UPS电池充电时间调整到谷时
3. **空调预冷策略**: 谷时降低温度设定点，利用建筑热惯性
4. **非关键设备错峰**: 将测试服务器、开发环境等非关键设备在峰时降低负载

### 预期效果
- 可转移电量: {actual_shift:.1f} kWh/日
- 日节省电费: ¥{daily_saving:.2f}
- 年节省电费: ¥{yearly_saving:.0f}

### 实施建议
- 优先调整可灵活调度的批量任务
- 制定详细的负荷转移计划表
- 监控转移后的系统稳定性
                    """.strip(),
                    estimated_saving=actual_shift * 365,
                    estimated_cost_saving=yearly_saving,
                    implementation_difficulty=2,
                    priority=PluginPriority.HIGH if yearly_saving > 10000 else PluginPriority.MEDIUM,
                    payback_period=0,  # 无需投资
                    related_devices=[d.device_name for d in shiftable_devices[:5]],
                    analysis_data={
                        'peak_ratio': peak_ratio,
                        'valley_ratio': valley_ratio,
                        'target_peak_ratio': target_peak_ratio,
                        'daily_shift_amount': actual_shift,
                        'daily_saving': daily_saving,
                        'price_diff': price_diff,
                        'shiftable_device_count': len(shiftable_devices)
                    },
                    confidence=85
                ))

        # 分析2: 谷时利用率低
        valley_target = 0.30  # 目标谷时占比
        if valley_ratio < valley_target * 0.8:  # 谷时利用率低于目标80%
            potential_shift = (valley_target - valley_ratio) * total_energy / len(context.energy_data)
            peak_price = context.pricing_config.get('peak_price', 1.2)
            valley_price = context.pricing_config.get('valley_price', 0.4)
            price_diff = peak_price - valley_price
            daily_saving = potential_shift * price_diff * 0.5  # 保守估计
            yearly_saving = daily_saving * 365

            if yearly_saving > 5000:
                results.append(self.create_suggestion(
                    title="提高谷时电力利用率",
                    description=f"谷时用电占比仅 {valley_ratio:.1%}，存在优化空间",
                    detail=f"""
## 分析结果

### 当前状态
- 谷时用电占比: {valley_ratio:.1%}
- 建议谷时占比: {valley_target:.1%}
- 谷时电价优势: ¥{price_diff:.2f}/kWh

### 建议措施
1. **调整定时任务**: 将系统维护、数据同步等任务调整到谷时
2. **UPS策略优化**: 在谷时进行UPS充电和电池均衡
3. **制冷预冷策略**: 在谷时适当降低温度设定点，利用建筑热惯性

### 预期效果
- 潜在转移电量: {potential_shift:.1f} kWh/日
- 预计年节省: ¥{yearly_saving:.0f}

### 注意事项
- 确保转移后不影响业务系统可用性
- 分阶段实施，逐步增加谷时负荷
                    """.strip(),
                    estimated_saving=potential_shift * 365 * 0.5,
                    estimated_cost_saving=yearly_saving,
                    implementation_difficulty=2,
                    priority=PluginPriority.MEDIUM,
                    payback_period=0,
                    analysis_data={
                        'valley_ratio': valley_ratio,
                        'target_valley_ratio': valley_target,
                        'potential_shift': potential_shift
                    },
                    confidence=75
                ))

        return results

    async def _analyze_device_shift_potential(self, context: AnalysisContext) -> List[SuggestionResult]:
        """设备级负荷转移分析"""
        results = []

        if not context.device_shift_info:
            return results

        thresholds = self._config.thresholds
        min_device_power = thresholds.get('device_min_power', 5)
        min_saving = thresholds.get('min_device_shift_saving', 100)

        # 按设备分析转移潜力
        device_shift_analysis = []

        for device in context.device_shift_info:
            if not device.is_shiftable or device.is_critical:
                continue

            if device.rated_power < min_device_power:
                continue

            # 计算峰时用电量
            peak_energy_daily = device.rated_power * device.peak_energy_ratio * 24 * 0.7  # 假设70%负载率
            valley_capacity = device.rated_power * (1 - device.valley_energy_ratio) * 8  # 8小时谷时

            # 可转移电量 (取峰时电量和谷时容量的较小值)
            shiftable_energy = min(
                peak_energy_daily * device.shiftable_power_ratio,
                valley_capacity
            )

            if shiftable_energy < 10:  # 忽略太小的转移量
                continue

            # 计算节省
            peak_price = context.pricing_config.get('peak_price', 1.2)
            valley_price = context.pricing_config.get('valley_price', 0.4)
            daily_saving = shiftable_energy * (peak_price - valley_price)
            yearly_saving = daily_saving * 365

            if yearly_saving >= min_saving:
                device_shift_analysis.append({
                    'device': device,
                    'shiftable_energy': shiftable_energy,
                    'daily_saving': daily_saving,
                    'yearly_saving': yearly_saving
                })

        # 按年节省金额排序
        device_shift_analysis.sort(key=lambda x: x['yearly_saving'], reverse=True)

        # 生成设备级转移建议 (Top 5)
        for analysis in device_shift_analysis[:5]:
            device = analysis['device']
            yearly_saving = analysis['yearly_saving']
            shiftable_energy = analysis['shiftable_energy']

            # 生成转移时段建议
            from_hours = [h for h in range(8, 22) if h not in device.forbidden_shift_hours]
            to_hours = [h for h in device.allowed_shift_hours if h in range(0, 8)]

            from_str = self._format_hours(from_hours[:4])
            to_str = self._format_hours(to_hours[:4])

            results.append(self.create_suggestion(
                title=f"转移{device.device_name}部分负荷至谷时",
                description=f"{device.device_name}峰时用电占比{device.peak_energy_ratio:.1%}，建议将{device.shiftable_power_ratio*100:.0f}%负荷转移至谷时",
                detail=f"""
## 设备负荷转移分析

### 设备信息
- 设备名称: {device.device_name}
- 设备类型: {device.device_type}
- 额定功率: {device.rated_power:.1f} kW
- 当前功率: {device.current_power:.1f} kW

### 用电分布
- 峰时用电占比: {device.peak_energy_ratio:.1%}
- 谷时用电占比: {device.valley_energy_ratio:.1%}
- 可转移功率比例: {device.shiftable_power_ratio*100:.0f}%

### 转移建议
- 从时段: {from_str}
- 转移至: {to_str}
- 日转移电量: {shiftable_energy:.1f} kWh

### 预期效果
- 日节省电费: ¥{analysis['daily_saving']:.2f}
- 年节省电费: ¥{yearly_saving:.0f}

### 实施步骤
1. 评估设备运行时间灵活性
2. 设置定时启停或调度策略
3. 监控转移后的运行状态
4. 验证节能效果
                """.strip(),
                estimated_saving=shiftable_energy * 365,
                estimated_cost_saving=yearly_saving,
                implementation_difficulty=2 if device.shiftable_power_ratio >= 0.5 else 3,
                priority=PluginPriority.HIGH if yearly_saving > 2000 else PluginPriority.MEDIUM,
                payback_period=0,
                related_devices=[device.device_name],
                analysis_data={
                    'device_id': device.device_id,
                    'device_type': device.device_type,
                    'rated_power': device.rated_power,
                    'peak_energy_ratio': device.peak_energy_ratio,
                    'shiftable_power_ratio': device.shiftable_power_ratio,
                    'shiftable_energy': shiftable_energy,
                    'from_hours': from_hours[:4],
                    'to_hours': to_hours[:4]
                },
                confidence=80
            ))

        # 生成设备转移汇总建议
        if len(device_shift_analysis) >= 3:
            total_yearly_saving = sum(a['yearly_saving'] for a in device_shift_analysis)
            total_shiftable = sum(a['shiftable_energy'] for a in device_shift_analysis)

            device_summary = "\n".join([
                f"| {a['device'].device_name} | {a['device'].device_type} | {a['shiftable_energy']:.1f} | ¥{a['yearly_saving']:.0f} |"
                for a in device_shift_analysis[:10]
            ])

            results.append(self.create_suggestion(
                title="设备负荷转移综合优化方案",
                description=f"识别出{len(device_shift_analysis)}台可转移设备，年节省潜力¥{total_yearly_saving:.0f}",
                detail=f"""
## 设备负荷转移综合分析

### 分析汇总
- 可转移设备数量: {len(device_shift_analysis)} 台
- 日可转移电量: {total_shiftable:.1f} kWh
- 年节省潜力: ¥{total_yearly_saving:.0f}

### 设备清单
| 设备名称 | 类型 | 日转移量(kWh) | 年节省(元) |
|---------|------|--------------|-----------|
{device_summary}

### 实施优先级
建议按年节省金额从高到低顺序实施，优先处理节省效益最高的设备。

### 风险提示
- 确保关键负荷不受影响
- 分阶段实施，每次调整1-2台设备
- 保留回退方案
                """.strip(),
                estimated_saving=total_shiftable * 365,
                estimated_cost_saving=total_yearly_saving,
                implementation_difficulty=3,
                priority=PluginPriority.HIGH if total_yearly_saving > 10000 else PluginPriority.MEDIUM,
                payback_period=0,
                related_devices=[a['device'].device_name for a in device_shift_analysis[:10]],
                analysis_data={
                    'device_count': len(device_shift_analysis),
                    'total_shiftable_energy': total_shiftable,
                    'total_yearly_saving': total_yearly_saving,
                    'top_devices': [
                        {'name': a['device'].device_name, 'saving': a['yearly_saving']}
                        for a in device_shift_analysis[:5]
                    ]
                },
                confidence=85
            ))

        return results

    async def _analyze_by_meter_point(self, context: AnalysisContext) -> List[SuggestionResult]:
        """按计量点分组分析"""
        results = []

        for meter_point in context.meter_points:
            mp_id = meter_point.meter_point_id

            # 获取该计量点下的设备
            devices = context.get_devices_by_meter_point(mp_id)
            if not devices:
                continue

            # 获取该计量点的能耗数据
            mp_energy = context.device_energy_data.get(mp_id, [])
            if not mp_energy:
                continue

            # 计算峰谷比例
            total_energy = sum(e.total_energy for e in mp_energy)
            if total_energy == 0:
                continue

            peak_energy = sum(e.peak_energy + e.sharp_energy for e in mp_energy)
            valley_energy = sum(e.valley_energy for e in mp_energy)

            peak_ratio = peak_energy / total_energy
            valley_ratio = valley_energy / total_energy

            # 如果峰时占比较高，生成计量点级别建议
            if peak_ratio > 0.40:
                shiftable_devices = [d for d in devices if d.is_shiftable and not d.is_critical]

                if shiftable_devices:
                    shiftable_power = sum(d.rated_power for d in shiftable_devices if d.rated_power)

                    # 估算转移效益
                    peak_price = context.pricing_config.get('peak_price', 1.2)
                    valley_price = context.pricing_config.get('valley_price', 0.4)
                    price_diff = peak_price - valley_price

                    # 假设可转移30%的峰时电量
                    daily_shift = (peak_energy / len(mp_energy)) * 0.3
                    yearly_saving = daily_shift * price_diff * 365

                    if yearly_saving > 5000:
                        device_list = "\n".join([
                            f"- {d.device_name}: {d.rated_power or 0:.1f}kW"
                            for d in shiftable_devices[:5]
                        ])

                        results.append(self.create_suggestion(
                            title=f"优化计量点{meter_point.meter_code}的峰时负荷",
                            description=f"计量点{meter_point.meter_name}峰时用电占比{peak_ratio:.1%}，可通过负荷转移降低电费",
                            detail=f"""
## 计量点负荷分析

### 计量点信息
- 编码: {meter_point.meter_code}
- 名称: {meter_point.meter_name}
- 变压器: {meter_point.transformer_name or '未配置'}
- 申报需量: {meter_point.declared_demand:.0f} {meter_point.demand_type}

### 用电分布
- 峰时占比: {peak_ratio:.1%}
- 谷时占比: {valley_ratio:.1%}
- 日均电量: {total_energy/len(mp_energy):.1f} kWh

### 可转移设备
{device_list}

### 建议
将上述设备的部分负荷从峰时段转移至谷时段运行。

### 预期效果
- 年节省电费: ¥{yearly_saving:.0f}
                            """.strip(),
                            estimated_saving=daily_shift * 365,
                            estimated_cost_saving=yearly_saving,
                            implementation_difficulty=2,
                            priority=PluginPriority.MEDIUM,
                            payback_period=0,
                            related_devices=[d.device_name for d in shiftable_devices[:5]],
                            analysis_data={
                                'meter_point_id': mp_id,
                                'meter_code': meter_point.meter_code,
                                'peak_ratio': peak_ratio,
                                'valley_ratio': valley_ratio,
                                'shiftable_device_count': len(shiftable_devices),
                                'shiftable_power': shiftable_power
                            },
                            confidence=75
                        ))

        return results

    def _format_hours(self, hours: List[int]) -> str:
        """格式化小时列表为时间段字符串"""
        if not hours:
            return "无"

        # 合并连续小时
        ranges = []
        start = hours[0]
        end = hours[0]

        for h in hours[1:]:
            if h == end + 1:
                end = h
            else:
                ranges.append((start, end))
                start = h
                end = h
        ranges.append((start, end))

        return ", ".join([
            f"{s}:00-{e+1}:00" if s != e else f"{s}:00"
            for s, e in ranges
        ])
