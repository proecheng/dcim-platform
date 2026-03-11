# Story 31.5: 前端预冷计划时间线展示

Status: done

## Story

As a 运维人员,
I want 在前端查看预冷计划的时间线和执行状态,
So that 我能直观管理预冷操作。

## 依赖

- Story 31.3（预冷计划 API 端点）— done
- Story 31.4（预冷配置管理）— done

## Acceptance Criteria

1. Given 预冷计划 API 已就绪
   When 进入预冷管理页面
   Then 显示今日/明日预冷计划甘特图时间线
   And 时间线标注峰/谷/平电价时段底色
   And 计划状态用颜色区分（蓝=pending, 绿=executing, 灰=completed, 红=aborted）

2. Given 预冷计划已执行
   When 查看计划详情
   Then 显示预期/实际节省电费对比
   And 显示温度轨迹图（预测 vs 实际）

3. Given 管理员操作
   When 点击生成计划按钮
   Then 调用 POST /zones/{zone_id}/schedule 生成计划
   And 点击中止按钮可中止 executing 状态的计划

4. Given 预冷配置
   When 进入页面
   Then 显示当前 zone 的 precool_enabled 状态和 precool_target_temp
   And 支持查看/切换 zone

5. Given 路由注册
   When 访问 /energy/shift/precool-schedule
   Then 加载预冷计划页面

## Tasks / Subtasks

- [ ] Task 1: API 封装 (AC: #1-3)
  - [ ] 1.1 在 `frontend/src/api/modules/precool.ts` 追加 Schedule/Config 类型定义
  - [ ] 1.2 追加 4 个 Schedule API 函数（createSchedule, listSchedules, getSchedule, abortSchedule）
  - [ ] 1.3 追加 2 个 Config API 函数（getPrecoolConfig, updatePrecoolConfig）

- [ ] Task 2: 预冷时间线组件 (AC: #1)
  - [ ] 2.1 在 `frontend/src/utils/echarts.ts` 追加注册 `CustomChart`、`MarkAreaComponent`、`MarkPointComponent`
  - [ ] 2.2 新建 `frontend/src/components/energy/PrecoolTimeline.vue`
  - [ ] 2.3 使用 ECharts custom series 绘制甘特图时间线（24h 横轴，单 zone 单行显示当前选中 zone 的计划）
  - [ ] 2.4 电价时段用 markArea 底色标注（从 schedule 的 peak_start/end 推断：峰=红色/谷=绿色/平=灰色）
  - [ ] 2.5 计划状态颜色条（蓝/绿/灰/红）
  - [ ] 2.6 Tooltip 显示计划摘要（时段、目标温度、节省量）

- [ ] Task 3: 预冷计划页面 (AC: #1-4)
  - [ ] 3.1 新建 `frontend/src/views/energy/shift/PrecoolScheduleView.vue`
  - [ ] 3.2 顶部：zone 选择器（数据源 getDashboard().zones）+ 日期切换（今日/明日）+ precool_enabled 状态标签
  - [ ] 3.3 中部：PrecoolTimeline 时间线组件
  - [ ] 3.4 操作栏：生成计划按钮（传递当前选中日期 schedule_date）+ 中止按钮（仅 executing 状态可点击）
  - [ ] 3.5 底部：计划列表表格（状态、时段、目标温度、计划/实际节省）
  - [ ] 3.6 计划详情对话框：温度轨迹图（predicted vs actual 双线 + ASHRAE markLine）+ 功率轨迹图（q_cool vs q_cool_actual 双线），使用 LineChart 双 Y 轴或双图

- [ ] Task 4: 路由注册 (AC: #5)
  - [ ] 4.1 在 `frontend/src/router/index.ts` 追加 precool-schedule 路由

- [ ] Task 5: 前端构建验证
  - [ ] 5.1 `npm run build` 无 TypeScript 错误

## Dev Notes

### API 封装类型定义

```typescript
// Schedule 类型
export interface ScheduleListItem {
  id: number
  cooling_zone_id: number
  schedule_date: string
  precool_start_time: string
  precool_end_time: string
  target_temp: number
  peak_start_time: string
  peak_end_time: string
  planned_savings_kwh: number | null
  actual_savings_kwh: number | null
  status: 'pending' | 'executing' | 'completed' | 'aborted'
  abort_reason: string | null
  is_validated: boolean
  created_at: string | null
}

export interface ScheduleDetail extends ScheduleListItem {
  temperature_trajectory: {
    predicted?: number[]
    actual?: number[]
    timestamps?: string[]
    q_cool?: number[]
    q_cool_actual?: number[]
    prices?: number[]
  } | null
  validated_at: string | null
}

export interface PrecoolConfig {
  zone_id: number
  precool_enabled: boolean
  precool_target_temp: number
}
```

### ECharts 组件注册追加

`frontend/src/utils/echarts.ts` 需追加：
```typescript
import { CustomChart } from 'echarts/charts'
import { MarkAreaComponent, MarkPointComponent } from 'echarts/components'
// 添加到 echarts.use([...]) 数组中
```

### 时间线组件设计

使用 ECharts custom series 绘制单行甘特图（当前选中 zone）：
- X 轴：0-24h 时间轴（value 类型，范围 0-86400000ms 或 Date 对象）
- 电价时段用 markArea 底色标注，数据源：从 schedule 列表的 peak_start_time/peak_end_time 推断峰时段，其余为谷/平
- 计划用 custom series renderItem 绘制矩形条
- 状态颜色映射：pending=#409EFF, executing=#67C23A, completed=#909399, aborted=#F56C6C

### API 时间格式

后端返回的时间字段格式：
- `schedule_date`: ISO date 字符串 `"2026-03-12"`
- `precool_start_time` / `precool_end_time` / `peak_start_time` / `peak_end_time`: ISO datetime 字符串 `"2026-03-12T02:00:00"`
- 前端解析时使用 `new Date(str)` 或 dayjs

### 温度轨迹对话框

计划详情对话框包含两个 ECharts 图表：
1. **温度轨迹图**: X 轴=timestamps, 两条 line（predicted 蓝虚线 + actual 绿实线），ASHRAE 27°C/18°C markLine
2. **功率轨迹图**: X 轴=timestamps, 两条 line（q_cool 计划功率 + q_cool_actual 实际功率）

### 路由位置

在 `/energy/shift/` 子路由下追加：
```typescript
{ path: 'precool-schedule', name: 'PrecoolSchedule',
  component: () => import('@/views/energy/shift/PrecoolScheduleView.vue'),
  meta: { title: '预冷计划', icon: 'Timer' } },
```

### 简化决策

- **不实现拖拽调整**：Epic AC 提到"支持拖拽调整计划时间段（仅 pending 状态）"，这属于 P2 功能且复杂度高，本 Story 聚焦核心展示+操作功能
- **不实现约束可视化 tooltip**：Epic AC 标注为"P2-12 修复"，属于增强功能，留到后续迭代
- **不实现 WebSocket 实时更新**：使用手动刷新按钮替代

### Project Structure Notes

- 追加文件：`frontend/src/utils/echarts.ts`（注册 CustomChart, MarkAreaComponent, MarkPointComponent）
- 新建文件：`frontend/src/views/energy/shift/PrecoolScheduleView.vue`
- 新建文件：`frontend/src/components/energy/PrecoolTimeline.vue`
- 追加文件：`frontend/src/api/modules/precool.ts`
- 追加文件：`frontend/src/router/index.ts`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 31, Story 31.5]
- [Source: frontend/src/api/modules/precool.ts — 现有 API 封装模式]
- [Source: frontend/src/components/energy/TemperaturePredictionChart.vue — ECharts 组件模式]
- [Source: frontend/src/views/energy/shift/CoolingLinkageMonitor.vue — 页面布局模式]
- [Source: frontend/src/router/index.ts — 路由结构]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- R1-P0-1: ECharts 缺少 CustomChart/MarkAreaComponent/MarkPointComponent 注册，追加 Task 2.1 和 echarts.ts 修改说明
- R1-P0-2: 补充 API 时间格式说明（ISO date/datetime 字符串）
- R1-P1-1: 明确电价时段数据来源：从 schedule 的 peak_start/end 推断
- R1-P1-2: 甘特图改为单 zone 单行显示（非多 zone 纵轴）
- R1-P1-3: 补充温度轨迹对话框图表设计细节
- R2-P1-1: 路由组件路径修正为 `@/views/energy/shift/PrecoolScheduleView.vue`，与现有 shift 子页面一致
- R2-P1-2: 明确 zone 列表数据源：复用 getDashboard().zones
- R2-P1-3: 生成计划按钮传递当前选中日期，中止按钮仅 executing 状态可点击

### File List

- `frontend/src/utils/echarts.ts` — 追加 CustomChart, MarkAreaComponent, MarkPointComponent 注册
- `frontend/src/api/modules/precool.ts` — 追加 6 个 API 函数 + 3 个类型定义
- `frontend/src/components/energy/PrecoolTimeline.vue` — 预冷时间线甘特图组件（新建）
- `frontend/src/views/energy/shift/PrecoolScheduleView.vue` — 预冷计划管理页面（新建）
- `frontend/src/router/index.ts` — 追加 precool-schedule 路由
- `_bmad-output/implementation-artifacts/stories/31-5-frontend-precooling-plan-timeline.md` — Story 文档
