# Story 6-4: 节能方案执行与效果追踪

## Story

As a 能源管理员,
I want 选择节能方案并追踪执行效果,
So that 我可以验证节能措施的实际收益。

## Status: Done

## FR 追溯: FR50, FR51, FR52

## Acceptance Criteria

1. 能源管理员可从自动识别的节能机会创建执行计划（含自动生成的任务）
2. 执行后系统自动追踪效果（对比电表实际读数与基线）
3. 效果追踪定时任务自动运行，无需手动触发
4. 执行管理页面展示完整的执行流程：机会→计划→任务→效果
5. 可查看效果对比图表（执行前后能耗/电费对比）

## 对抗性审查发现（已修复）

### C1: track_execution_effect 无去重 → 定时任务会创建重复记录
**修复**: EffectTracker 自行实现追踪逻辑，内置去重（LEFT JOIN 查无记录的计划）

### C2: GET /plans/{plan_id}/tracking 是读操作却有写副作用
**修复**: 不修改现有 GET 端点，EffectTracker 自行做去重检查

### C3: achievement_rate Numeric(5,2) 最大值 999.99，计算结果可能溢出
**修复**: 写入前 clamp: min(achievement_rate, 999.99)

### H1: Story 对"缺失"描述不准确
**修复**: 现有端点已从 OpportunityMeasure 创建任务，但自动识别的机会没有 measures，需 fallback

### H3: EnergyDaily 查询无 device_id 过滤
**修复**: 从 ExecutionTask.parameters 提取设备 ID，查询时过滤

### H6: analysis_data 解析规范缺失
**修复**: 策略模式，按 source_plugin 类型分别生成任务

## 现有基础设施分析

### 已存在（不需要创建）
- **ExecutionPlan/Task/Result 模型**: 完整 ORM
- **ExecutionService**: 完整服务 (737 lines)，含 track_execution_effect（但无去重）
- **execution.py API**: 完整 CRUD
- **opportunities.py**: `/{opportunity_id}/execute` — 已从 OpportunityMeasure 创建任务
- **execution.vue**: 完整执行管理页面（追踪区域纯文字，无图表）
- **opportunity store**: loadExecutionPlans、loadPlanDetail、loadExecutionStats

### 缺失（本 Story 需要实现）
1. **效果追踪定时任务**: main.py 中没有自动追踪定时器
2. **自动识别机会的任务生成**: 自动识别的机会没有 OpportunityMeasure，只有 analysis_data，导致空计划
3. **机会执行联动**: OptimizationOverview 自动识别机会列表没有"执行"按钮
4. **效果对比图表**: execution.vue 追踪区域缺少可视化

## 技术方案

### Task 1: 效果追踪定时服务 (effect_tracker.py 新建)

**文件**: `backend/app/services/effect_tracker.py`

EffectTracker 自行实现追踪逻辑（不调用 ExecutionService.track_execution_effect，因其无去重）。

**核心方法**:
- `run_tracking()`: 主入口，找需追踪的计划 + 标记已完成的追踪
- `_find_plans_needing_tracking()`: LEFT JOIN ExecutionResult，只返回无记录的已完成计划
- `_extract_device_ids(plan)`: 从任务参数提取设备ID列表
- `_calculate_effect(plan, device_ids)`: 区分负荷转移和能耗对比
- `_calculate_energy_comparison_effect()`: 按设备过滤 EnergyDaily，按日聚合
- `_calculate_load_shift_effect()`: 基于配置参数计算
- `_mark_completed_tracking()`: 标记追踪期结束的记录

**关键设计**:
- 去重: LEFT JOIN ExecutionResult，只处理无记录的计划
- achievement_rate clamp: min(value, 999.99)
- 设备过滤: 从 task.parameters 提取 device_id
- 按日存储: energy_before/energy_after 为 [{date, energy, cost}] 数组
- SQLite 兼容: 日期用 .isoformat() 字符串比较

### Task 2: 注册定时任务到 main.py

**文件**: `backend/app/main.py`

每6小时执行，启动延迟5分钟。遵循现有定时任务模式。shutdown 时 cancel。

### Task 3: 增强 execute 端点 — analysis_data fallback

**文件**: `backend/app/api/v1/opportunities.py`

**不修改现有 measures 路径**。在 measures 为空时 fallback:

```python
if not measures and opportunity.analysis_data:
    tasks = _generate_tasks_from_analysis_data(plan.id, opportunity.source_plugin, opportunity.analysis_data)
```

**策略模式** (H6):
- `peak_valley_optimizer` → 按设备+规则生成 load_shift 任务
- `demand_controller` → 生成需量调整任务
- 其他 → 通用手动任务 fallback

### Task 4: 前端 - OptimizationOverview 执行联动

**文件**: `frontend/src/components/energy/OptimizationOverview.vue`

为自动识别机会添加"执行"按钮（仅 discovered/ready 状态显示）。
点击后调用 executeOpportunity API，成功跳转到执行页面并高亮新计划。

### Task 5: 前端 - 效果对比图表

**文件**: `frontend/src/views/energy/execution.vue`

在追踪结果区域添加 ECharts 柱状图（执行前后按日能耗对比）。
使用 energy_before/energy_after 的按日数组数据。

### Task 6: 后端测试 (10个用例)

**文件**: `backend/tests/test_effect_tracker.py`

1. test_find_plans_needing_tracking
2. test_skip_plans_with_existing_results
3. test_calculate_energy_comparison_effect
4. test_calculate_load_shift_effect
5. test_mark_completed_tracking
6. test_extract_device_ids
7. test_achievement_rate_clamp
8. test_run_tracking_no_completed_plans
9. test_execute_opportunity_with_analysis_data
10. test_execute_opportunity_with_measures_regression

### Task 7: 前端构建验证

## 实施顺序

1. Task 1 + Task 3: 后端核心（effect_tracker + execute fallback）
2. Task 6: 后端测试
3. Task 2: 定时任务注册
4. Task 4 + Task 5: 前端（执行联动 + 效果图表）
5. Task 7: 前端构建验证

## 关键约束

- **不修改 ExecutionService**: 不改动 track_execution_effect（避免影响已有 API）
- **不修改模型**: 现有字段足够
- **保留现有 measures 路径**: 只添加 fallback
- **效果追踪周期默认7天**
- **SQLite 兼容**: 日期用 .isoformat()
- **achievement_rate clamp**: min(value, 999.99)
