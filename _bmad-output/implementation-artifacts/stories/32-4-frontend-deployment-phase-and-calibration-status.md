# Story 32.4: 前端部署阶段与校准状态展示

Status: done

## Story

As a 系统管理员,
I want 在前端查看当前部署阶段和各区域校准状态,
So that 我能监控预冷功能的上线进度。

## 依赖

- Story 32.3（热参数管理 API — `GET/PUT /deployment-phase`, `POST /calibrate`, `GET /calibration-history`）— done

## Acceptance Criteria

1. Given 部署阶段 API 已就绪
   When 进入预冷管理页面（PrecoolScheduleView）
   Then 顶部显示部署阶段进度条（4 阶段：THM→校准→TCL→VPP，当前阶段高亮）
   And admin 可点击切换阶段（弹出确认对话框，含 force 选项）

2. Given 校准 API 已就绪
   When 进入预冷管理页面
   Then 在页面底部显示各区域校准状态表格
   And 每行显示：区域名称、当前 R/C 值、R² 值、校准方法、校准状态标签
   And 支持一键触发单区域校准（按钮 + loading 状态）

3. Given precool.ts API 模块
   When 需要调用部署阶段和校准接口
   Then 在 precool.ts 中追加 4 个 API 函数和对应类型

4. Given 新路由页面
   When 添加部署管理入口
   Then 在 `/energy/shift/` 路由下新增 `deployment` 路由指向 DeploymentPhaseView.vue
   And 菜单标题："部署管理"

5. Given 所有新增组件
   When 编译和运行
   Then 无 TypeScript 错误
   And 组件可正常渲染和交互

## Tasks / Subtasks

- [ ] Task 1: API 模块扩展 (AC: #3)
  - [ ] 1.1 在 precool.ts 追加类型：DeploymentPhaseInfo, CalibrationHistoryItem, CalibrationResult
  - [ ] 1.2 追加函数：getDeploymentPhase, updateDeploymentPhase, triggerCalibration, getCalibrationHistory

- [ ] Task 2: 部署管理页面 (AC: #1, #2, #4)
  - [ ] 2.1 新建 `frontend/src/views/energy/shift/DeploymentPhaseView.vue`
  - [ ] 2.2 实现部署阶段进度条（el-steps 组件，4 个步骤）
  - [ ] 2.3 实现阶段切换对话框（admin only，含 force 选项）
  - [ ] 2.4 实现区域校准状态表格（el-table）
  - [ ] 2.5 实现一键校准按钮 + loading + 结果反馈

- [ ] Task 3: 路由注册 (AC: #4)
  - [ ] 3.1 在 router/index.ts 添加 `deployment` 路由

- [ ] Task 4: 前端测试 (AC: #5)
  - [ ] 4.1 在 `frontend/src/__tests__/deployment-phase.test.ts` 编写组件逻辑测试

## Dev Notes

### API 模块扩展（precool.ts）

在 precool.ts 末尾追加：

```typescript
// ========== 部署阶段与校准 API (Story 32.4) ==========

export interface DeploymentPhaseInfo {
  current_phase: number
  phase_name: string
  description: string
  updated_at: string | null
}

export interface CalibrationHistoryItem {
  id: number
  cooling_zone_id: number
  thermal_R: number | null
  thermal_C: number | null
  fitting_r_squared: number | null
  fitting_method: string | null
  sample_count: number | null
  calibrated_at: string | null
  is_active: boolean
  created_at: string
}

export interface CalibrationResult {
  success?: boolean
  R?: number
  C?: number
  r_squared?: number
  sample_count?: number
  error?: string
}

/** 查询当前部署阶段 */
export function getDeploymentPhase() {
  return request.get<{ code: number; message: string; data: DeploymentPhaseInfo }>(
    '/v1/precool/deployment-phase'
  )
}

/** 切换部署阶段（仅 admin） */
export function updateDeploymentPhase(data: { phase: number; force?: boolean }) {
  return request.put<{ code: number; message: string; data: any }>(
    '/v1/precool/deployment-phase',
    data
  )
}

/** 触发手动校准 */
export function triggerCalibration(zoneId: number) {
  return request.post<{ code: number; message: string; data: CalibrationResult }>(
    `/v1/precool/zones/${zoneId}/calibrate`
  )
}

/** 查询校准历史 */
export function getCalibrationHistory(
  zoneId: number,
  params?: { skip?: number; limit?: number }
) {
  return request.get<{ code: number; message: string; data: { items: CalibrationHistoryItem[]; total: number } }>(
    `/v1/precool/zones/${zoneId}/calibration-history`,
    { params }
  )
}
```

### 部署管理页面设计

新建 `DeploymentPhaseView.vue`，页面分为两个区块：

**区块 1: 部署阶段进度条**
- 使用 `el-steps` 组件，`process-status="finish"` 表示已完成阶段
- 4 个步骤：THM 模式 / 校准模式 / TCL 上线 / VPP 接入
- admin 角色显示"切换阶段"按钮
- 切换时弹出 `el-dialog` 确认框，含阶段选择（el-select 1-4）和 force 复选框
- 切换失败时展示错误：code=422 时显示前置条件详情列表（`data.details`），code=400 时显示错误消息
- 校准按钮失败时：code=503 显示"scipy 未安装"提示，code=422 显示校准失败原因

**区块 2: 区域校准状态表格**
- 使用 `getDashboard()` 获取区域列表
- 每个区域调用 `getCalibrationHistory(zoneId, { limit: 1 })` 获取最新校准记录
- 表格列：区域名称 | R 值 | C 值 | R² | 校准方法 | 状态 | 操作
- 状态标签：
  - `已校准` (success) — fitting_method='auto_fit'且 R²≥0.85
  - `校准中` (warning) — 正在执行校准（loading 状态）
  - `待校准` (info) — 无记录或 R²<0.85
  - `校准失败` (danger) — 最近一次校准返回 error
- "校准"按钮：调用 `triggerCalibration(zoneId)`，校准完成后刷新该行

**⚠️ 注意:** `getDashboard()` 返回的 `DashboardZone` 包含 `zone_id` 和 `zone_name`，可直接作为区域列表数据源，无需额外查 CoolingZone。

### 路由注册

在 `router/index.ts` 中 `precool-schedule` 路由之后追加：

```typescript
{ path: 'deployment', name: 'DeploymentPhase', component: () => import('@/views/energy/shift/DeploymentPhaseView.vue'), meta: { title: '部署管理', icon: 'SetUp' } },
```

### 权限处理

页面使用 `useUserStore` 获取当前用户角色（store 已导出 `isAdmin` computed）：
```typescript
import { useUserStore } from '@/stores/user'
const userStore = useUserStore()
// 直接使用 userStore.isAdmin，不要自己重新 computed
```

只有 admin 才显示"切换阶段"按钮和 force 选项。

### THM vs TCL 模式展示

AC 要求"显示 THM vs TCL 模式对比"。`getDashboard()` 返回的 `DashboardZone.model_mode` 字段值为 `"TCL" | "THM"`，在校准状态表格中增加"当前模式"列展示即可。独立的预测曲线对比功能已由 `TemperaturePredictionChart.vue` 实现（含 `thm_result` 字段），无需重复建设。

### 现有组件模式参考

参考 `PrecoolScheduleView.vue` 的布局模式：
- `el-page-header` 返回导航
- `el-card` + `toolbar-row` 工具栏
- `el-table` 数据表格
- loading 状态管理

参考 `RollbackStatusCard.vue` 的 API 调用模式：
- `onMounted` 加载数据
- `ref` 管理加载状态
- 统一响应格式 `{ code, message, data }` 处理

### Project Structure Notes

- **新建文件:** `frontend/src/views/energy/shift/DeploymentPhaseView.vue` — 部署管理页面
- **修改文件:** `frontend/src/api/modules/precool.ts` — 追加 4 个 API 函数和类型
- **修改文件:** `frontend/src/router/index.ts` — 追加部署管理路由
- **新建文件:** `frontend/src/__tests__/deployment-phase.test.ts` — 前端测试

### 关键约束

- **auto-import:** Vue/Pinia API（ref, computed, onMounted 等）和 Element Plus 组件无需手动 import
- **API 响应格式:** 统一 `{ code: number, message: string, data: T }` 模式
- **角色检查:** 前端仅做 UI 展示控制，实际权限在后端 API 层校验
- **El-Steps active 属性:** `active` 从 0 开始，phase 从 1 开始，需要 `active = phase - 1`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 32.4, line 4192-4214]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.8 前端展示]
- [Source: frontend/src/api/modules/precool.ts — 现有 API 模式]
- [Source: frontend/src/views/energy/shift/PrecoolScheduleView.vue — 页面布局模式]
- [Source: frontend/src/components/energy/RollbackStatusCard.vue — 组件开发模式]
- [Source: frontend/src/router/index.ts — 路由注册模式]
- [Source: backend/app/api/v1/precool.py — Story 32.3 端点定义]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- R1 审查: THM vs TCL 模式展示简化为表格 model_mode 列; userStore.isAdmin 直接使用 store 导出
- R2 审查: 补充切换失败和校准失败的错误处理说明
- 代码审查修复: TypeScript 类型错误 — 统一使用 `(res as any).data` 模式处理 Axios 响应层级，与 PrecoolScheduleView 模式一致
- 22 个前端测试全部通过

### File List

- `frontend/src/views/energy/shift/DeploymentPhaseView.vue` — 部署管理页面（新建）
- `frontend/src/api/modules/precool.ts` — 追加 4 个 API 函数和类型
- `frontend/src/router/index.ts` — 追加部署管理路由
- `frontend/src/__tests__/deployment-phase.test.ts` — 前端测试（新建）
- `_bmad-output/implementation-artifacts/stories/32-4-frontend-deployment-phase-and-calibration-status.md` — Story 文档
