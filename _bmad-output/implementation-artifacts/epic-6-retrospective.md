# Epic 6 回顾：能源管理

## 完成情况

全部 5 个 Story 完成，实现了 PUE 监控适配、能耗统计与电价管理、节能机会自动识别、节能方案执行追踪和能效报告导出。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 6-1 | PUE 监控与配电拓扑适配 | ✅ | ✅ |
| 6-2 | 能耗统计与电价管理 | ✅ | ✅ |
| 6-3 | 节能机会自动识别 | ✅ | ✅ |
| 6-4 | 节能方案执行与效果追踪 | ✅ | ✅ |
| 6-5 | 能效报告导出 | ✅ | ✅ |

## 关键经验教训

### 架构决策

1. **模拟/真实数据双模式**：所有能源 API 通过 `settings.simulation_enabled` 判断数据来源。`true` 时保留确定性模拟逻辑，`false` 时查询真实数据表。响应新增 `data_source` 字段标识来源
2. **PUE 计算重构**：从确定性模拟切换为基于 PowerDevice 关联的真实点位数据。IT 负载功率为 0 或数据缺失时 PUE 显示"--"，不使用过期数据计算
3. **节能分析插件架构**：6 种分析插件通过 plugin_manager 逐插件执行，绕过 OpportunityEngine.generate_opportunities() 直接调用，用 plugin.plugin_id 标记来源

### 反复出现的模式

1. **确定性模拟辅助函数**：`_deterministic_ratio` 和 `_deterministic_offset` 从 energy.py 提取到 `utils/deterministic.py`，多个端点复用
2. **数据聚合定时任务**：每小时 PointHistory → EnergyHourly，每日 EnergyHourly → EnergyDaily（含峰谷平分段），每月 EnergyDaily → EnergyMonthly。仅在 simulation_enabled=false 时运行
3. **PricingService 真实电价**：能耗汇总和电费统计从硬编码乘数切换为调用 PricingService 获取真实电价计算分段电费

### 对抗性审查高价值发现

- **6-3 C1**: SuggestionResult 无 plugin_id 属性，所有结果映射为 'unknown' → 检测器直接调用 plugin_manager 逐插件执行
- **6-3 C2**: SuggestionResult.priority 是 PluginPriority 枚举(1-4)，不是 int(1-3) → 修正优先级映射
- **6-4 C1**: track_execution_effect 无去重，定时任务会创建重复记录 → EffectTracker 内置去重（LEFT JOIN 查无记录的计划）
- **6-4 C3**: achievement_rate Numeric(5,2) 最大值 999.99，计算结果可能溢出 → 写入前 clamp

### 技术模式沉淀

- **PUE 历史定时写入**：每 15 分钟将当前 PUE 值写入 PUEHistory 表，PUE 趋势 API 优先读取真实记录
- **节能机会去重**：同一插件在同一天内不重复生成相同类型的机会
- **效果追踪**：对比电表实际读数与基线，自动计算 achievement_rate
- **能效报告导出**：支持 Excel 和 PDF 两种格式，包含 PUE 趋势表、电费对比表、节能成果表

## 下一步

Epic 7: 资产与容量管理 — 6 个 Stories
