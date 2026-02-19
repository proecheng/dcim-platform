# Story 11-2: 巡检计划与任务

## Story

As a 运维主管,
I want 创建巡检计划并管理巡检任务,
So that 巡检工作规范化且不会遗漏。

**FR 追溯:** FR69, FR70

---

## 状态: 已审查

## Brownfield 分析

### 已有代码（无需新建）

| 层级 | 文件 | 已有内容 |
|------|------|----------|
| Model | `models/operation.py` | InspectionPlan, InspectionTask, InspectionStatus 枚举 |
| Schema | `schemas/operation.py` | InspectionPlanBase/Create/Update/Response, InspectionTaskBase/Create/Update/Response |
| API | `api/v1/operation.py` | CRUD for /plans, /tasks + start/complete endpoints |
| Frontend API | `api/modules/operation.ts` | InspectionPlan/Task 类型 + API 函数 |
| Router | `router/index.ts` | /operation/inspection 路由已定义 |

### 需要增强的部分

#### 1. 后端 API 增强 (`api/v1/operation.py`)

**1a. 巡检任务状态机**
当前 start/complete 端点没有状态校验。需要添加类似工单的状态转换规则：
```
pending → in_progress → completed
pending → overdue (系统自动)
```
- `POST /tasks/{id}/start`: 仅允许 pending 状态开始
- `POST /tasks/{id}/complete`: 仅允许 in_progress 状态完成

**1b. 新增端点: 从计划生成任务**
```
POST /plans/{id}/generate-tasks
```
根据计划的 frequency 和 assignee 自动创建一个巡检任务，关联 plan_id，复制 assignee，设置 scheduled_date。

**1c. 新增端点: 删除巡检任务**
```
DELETE /tasks/{id}
```
当前缺少此端点。

**1d. 列表过滤增强**
- `GET /plans`: 增加 `is_active` 过滤参数、`name` 关键词搜索
- `GET /tasks`: 增加 `plan_id` 过滤参数、`assignee` 过滤参数

#### 2. 前端 API 修正 (`api/modules/operation.ts`)

当前前端 API 存在严重不匹配：
- URL 路径: 前端用 `/operation/inspection-plans` 但后端是 `/operation/plans`
- 类型字段: InspectionPlan 接口字段名与后端 schema 不一致（如 `plan_name` vs `name`）

需要修正：
- URL: `/v1/operation/inspection-plans` → `/v1/operation/plans`
- URL: `/v1/operation/inspection-tasks` → `/v1/operation/tasks`
- InspectionPlan 接口: 对齐后端 InspectionPlanResponse 字段
- InspectionTask 接口: 对齐后端 InspectionTaskResponse 字段
- InspectionPlanCreate 接口: 对齐后端 InspectionPlanCreate 字段
- InspectionTaskCreate 接口: 对齐后端 InspectionTaskCreate 字段
- 新增 `generateInspectionTasks(planId: number)` 函数
- 新增 `deleteInspectionTask(id: number)` 函数

#### 3. 前端页面 (`views/operation/inspection.vue`)

新建巡检管理页面，包含两个 Tab：

**Tab 1: 巡检计划**
- 表格展示计划列表（名称、频率、位置、负责人、启用状态、创建时间）
- 新建/编辑计划对话框（表单字段对齐 InspectionPlanCreate）
- 启用/停用切换
- 删除计划
- "生成任务" 按钮 → 调用 POST /plans/{id}/generate-tasks

**Tab 2: 巡检任务**
- 表格展示任务列表（任务编号、关联计划、状态、执行人、计划日期、开始/完成时间、异常数）
- 状态筛选（待巡检/巡检中/已完成/已逾期）
- "开始巡检" 按钮 → 调用 POST /tasks/{id}/start
- "完成巡检" 对话框 → 填写结果和异常数 → 调用 POST /tasks/{id}/complete
- 删除任务

#### 4. 测试 (`tests/test_inspection.py`)

测试用例（约 15 个）：
1. 创建巡检计划
2. 获取巡检计划列表
3. 获取巡检计划列表 - is_active 过滤
4. 获取巡检计划列表 - name 关键词搜索
5. 获取巡检计划详情
6. 更新巡检计划
7. 删除巡检计划
8. 创建巡检任务
9. 获取巡检任务列表
10. 获取巡检任务列表 - status 过滤
11. 获取巡检任务列表 - plan_id 过滤
12. 开始巡检任务（pending → in_progress）
13. 开始巡检任务 - 非 pending 状态返回 400
14. 完成巡检任务（in_progress → completed）
15. 完成巡检任务 - 非 in_progress 状态返回 400
16. 从计划生成任务
17. 删除巡检任务

---

## 验收标准

1. ✅ 巡检计划 CRUD 完整可用，支持 is_active 过滤和 name 搜索
2. ✅ 巡检任务 CRUD 完整可用，支持 status/plan_id/assignee 过滤
3. ✅ 任务状态机: pending → in_progress → completed，非法转换返回 400
4. ✅ 从计划生成任务端点可用
5. ✅ 前端 API 模块 URL 和类型与后端完全对齐
6. ✅ 前端巡检管理页面包含计划和任务两个 Tab
7. ✅ 所有新增测试通过，回归测试 109+ 通过
8. ✅ InspectionStatus 枚举值为中文（待巡检/巡检中/已完成/已逾期）

---

## 审查发现

1. **APScheduler 降级**: Epic AC 提到 APScheduler 定时任务，但引入调度器依赖过重。改为 `POST /plans/{id}/generate-tasks` 手动/API 触发，未来可接入调度器。
2. **任务响应需包含计划名称**: InspectionTaskResponse 需新增 `plan_name` 字段，API 查询时 join plan 表获取。需同步修改 schema。
3. **前端 API URL 不匹配**: 已在 spec 中标注，实施时必须修正。
4. **逐项巡检结果**: 使用 JSON text 字段存储，结构由前端定义，后端不校验 JSON 内容。

## 技术约束

- 枚举值为中文: `pending="待巡检"`, `in_progress="巡检中"`, `completed="已完成"`, `overdue="已逾期"`
- 测试中 query params 和 assertions 使用中文值
- Vue 3 auto-imports: 不需要 import ref/computed/onMounted/ElMessage
- Element Plus 组件自动导入
- SCSS: `@use '@/styles/_mixins-25d' as *;` + `@include page-list;`
- 后端 API 直接做异步操作，不通过 services/operation.py
