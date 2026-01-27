# 负荷转移执行方案完整流程实现计划

> **状态:** ✅ 已完成
> **最后更新:** 2026-01-27

**Goal:** 实现负荷转移配置 → 创建执行计划 → 执行管理 → 查看详情的完整闭环流程

**Architecture:**
- 在ShiftPlanBuilder点击"执行方案"时弹出确认对话框，让用户输入计划名称（提供默认值）
- 调用后端API创建EnergyOpportunity和ExecutionPlan
- 在execution.vue中展示新创建的计划，并支持从详情返回原配置页面

**Tech Stack:** Vue 3 + TypeScript + Element Plus + FastAPI + SQLAlchemy

---

## 实现状态总览

| Task | 描述 | 状态 |
|------|------|------|
| Task 1 | 创建执行计划确认对话框组件 | ✅ 完成 |
| Task 2 | 创建后端执行计划创建API | ✅ 完成 |
| Task 3 | 添加前端API调用方法 | ✅ 完成 |
| Task 4 | 修改ShiftPlanBuilder集成执行计划创建流程 | ✅ 完成 |
| Task 5 | 修改execution.vue支持高亮新计划和查看详情跳转 | ✅ 完成 |
| Task 6 | 修改analysis.vue支持从执行管理页面恢复配置 | ✅ 完成 |
| Task 7 | 全面测试和验证 | ✅ 完成 |
| 追加 | 统计API响应格式修复 | ✅ 完成 |
| 追加 | 实际年节省计算逻辑改进 | ✅ 完成 |
| 追加 | 总体达成率计算改进 | ✅ 完成 |
| 追加 | 深色主题样式优化 | ✅ 完成 |

---

## 已实现的核心功能

### 1. 执行计划创建流程

**入口:** `frontend/src/components/energy/ShiftPlanBuilder.vue`

用户在负荷转移分析页面配置转移规则后，点击"执行方案"按钮：
1. 弹出确认对话框（ExecutionPlanDialog）
2. 显示默认计划名称：`负荷转移方案 - YYYY-MM-DD HH:mm`
3. 显示预期收益（日节省、年节省）和涉及设备
4. 用户确认后调用 `POST /v1/execution/plans/from-shift` 创建计划
5. 跳转到执行管理页面，高亮显示新计划

**关键文件:**
- `frontend/src/components/energy/ExecutionPlanDialog.vue` - 确认对话框组件
- `frontend/src/components/energy/ShiftPlanBuilder.vue` - 集成对话框和API调用
- `frontend/src/api/modules/opportunities.ts` - `createLoadShiftPlan` API方法

### 2. 后端执行计划API

**端点:** `POST /v1/execution/plans/from-shift`

**文件:** `backend/app/api/v1/execution.py`

创建流程：
1. 创建 `EnergyOpportunity` 记录（category=1, source_plugin='peak_valley_optimizer'）
2. 创建 `ExecutionPlan` 记录
3. 为每个设备的每条转移规则创建 `ExecutionTask`

**请求Schema:**
```python
class CreateLoadShiftPlanRequest(BaseModel):
    plan_name: str
    strategy: str  # 'max_benefit' | 'min_cost'
    daily_saving: float
    annual_saving: float
    device_rules: List[DeviceShiftRule]
    remark: Optional[str]
    meter_point_id: Optional[int]
```

### 3. 执行管理页面

**文件:** `frontend/src/views/energy/execution.vue`

**统计卡片:**
- 总计划数（含状态分解：待执行/执行中/已完成）
- 预期年节省（万元）
- 实际年节省（万元）
- 总体达成率

**功能:**
- 计划列表（支持状态筛选）
- 计划详情抽屉
- 高亮新创建的计划
- "查看原配置"按钮跳转回原配置页面

### 4. 配置恢复功能

**文件:** `frontend/src/views/energy/analysis.vue`

从执行管理页面点击"查看原配置"后：
1. 跳转到 `/energy/analysis?tab=shift&plan_id=xxx&restore=true`
2. 根据 `plan_id` 获取执行计划详情
3. 从 `opportunity.analysis_data` 恢复配置
4. 通过 `pendingRestoreData` 传递给 ShiftPlanBuilder
5. ShiftPlanBuilder 恢复设备选择和转移规则

### 5. 统计数据计算

**文件:** `backend/app/api/v1/execution.py` - `get_execution_stats()`

**计算公式:**

| 指标 | 数据来源 | 计算公式 |
|-----|---------|---------|
| 总计划数 | ExecutionPlan表 | COUNT(所有计划) |
| 预期年节省 | ExecutionPlan.expected_saving | SUM(所有计划) |
| 实际年节省 | ExecutionResult.actual_saving | SUM(已追踪完成的年化值) |
| 总体达成率 | 计算 | 实际年节省 / 已追踪计划预期节省 × 100% |

**实际年节省计算逻辑:**

**文件:** `backend/app/services/execution_service.py` - `track_execution_effect()`

对于负荷转移方案（source_plugin='peak_valley_optimizer'）：
```
日节省 = Σ(转移功率 × 转移时长 × (源时段电价 - 目标时段电价))
年化节省 = 日节省 × 250工作日
```

对于其他方案：
```
能耗节省 = 执行前能耗 - 执行后能耗
成本节省 = 能耗节省 × 加权平均电价
年化节省 = (成本节省 / 追踪天数) × 250工作日
```

---

## 关键代码位置

### 前端

| 文件 | 功能 |
|------|------|
| `frontend/src/components/energy/ExecutionPlanDialog.vue` | 执行计划确认对话框 |
| `frontend/src/components/energy/ShiftPlanBuilder.vue` | 负荷转移配置和执行 |
| `frontend/src/views/energy/execution.vue` | 执行管理页面 |
| `frontend/src/views/energy/analysis.vue` | 能源分析页面（含恢复逻辑） |
| `frontend/src/api/modules/opportunities.ts` | 执行相关API |

### 后端

| 文件 | 功能 |
|------|------|
| `backend/app/api/v1/execution.py` | 执行管理API端点 |
| `backend/app/services/execution_service.py` | 执行计划服务 |
| `backend/app/schemas/energy.py` | 请求/响应Schema |
| `backend/app/models/energy.py` | 数据库模型 |

---

## 数据库表结构

已使用的表：
- `energy_opportunity` - 节能机会主表
- `execution_plan` - 执行计划表
- `execution_task` - 执行任务表
- `execution_result` - 效果追踪表

关键字段：
- `energy_opportunity.analysis_data` - JSON存储完整转移规则配置
- `energy_opportunity.source_plugin` - 来源插件标识（'peak_valley_optimizer'）
- `execution_task.parameters` - JSON存储单个任务参数
- `execution_result.actual_saving` - 年化实际节省金额

---

## 完整流程图

```
用户打开能源分析页面 → 切换到"负荷转移分析" tab
    ↓
选择可转移设备，配置转移规则
    ↓
点击"执行方案"按钮
    ↓
弹出确认对话框
  - 显示默认名称: "负荷转移方案 - 2026-01-27 10:30"
  - 可修改名称
  - 显示预期收益和涉及设备
    ↓
用户确认 → 调用 POST /v1/execution/plans/from-shift
    ↓
后端创建:
  1. EnergyOpportunity (source_plugin='peak_valley_optimizer')
  2. ExecutionPlan
  3. ExecutionTask × N (每设备每规则一个任务)
    ↓
跳转到 /energy/execution?highlight={plan_id}
    ↓
执行管理页面:
  - 新计划高亮显示（蓝色背景渐隐动画）
  - 自动展开详情抽屉
  - 显示统计卡片（总计划数、预期节省、实际节省、达成率）
    ↓
点击"查看原配置"按钮
    ↓
跳转到 /energy/analysis?tab=shift&plan_id={id}&restore=true
    ↓
恢复原配置:
  - 优化策略
  - 设备选择
  - 转移规则（源时段、目标时段、功率、时长）
    ↓
可修改后重新创建计划（完成闭环）
```

---

## 样式说明

执行管理页面采用深色科技风主题：
- 统计卡片：固定高度140px，flexbox垂直居中
- 详情抽屉：渐变背景 `#0d1b2a` → `#1b263b`
- 任务项：半透明背景 + 蓝色边框 + hover效果
- 进度条：蓝绿渐变填充

---

## 后续可扩展

1. **自动执行支持** - 对于可自动控制的设备，支持自动执行任务
2. **定时执行** - 支持设置定时执行计划
3. **批量操作** - 支持批量标记任务完成
4. **效果对比** - 执行前后的能耗曲线对比图表
5. **报告导出** - 执行计划和效果报告PDF导出
