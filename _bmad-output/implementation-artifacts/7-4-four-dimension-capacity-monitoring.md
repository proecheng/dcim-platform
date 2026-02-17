# Story 7.4: 四维容量监控

Status: ready-for-dev

## Story

As a 资产管理员,
I want 查看空间/电力/制冷/承重容量使用情况,
So that 我可以评估机房的剩余容量。

## FR 追溯

- FR59: 资产管理员可以查看空间/电力/制冷/承重容量使用情况

## Acceptance Criteria

1. Given 机柜和设备数据已录入
   When 资产管理员查看容量管理页面
   Then 显示空间容量（U位使用率）、电力容量（功率使用率）、制冷容量（制冷负荷率）、承重容量（重量使用率）

2. Given 容量数据已录入
   When 资产管理员选择区域/楼层/房间维度筛选
   Then 按所选维度聚合显示四维容量使用情况

3. Given 容量使用率超过阈值（如80%）
   When 资产管理员查看容量管理页面
   Then 超阈值的容量项高亮预警显示

## 现有代码分析

### 已有实现（不需要重新开发）

容量管理系统已有完整的 CRUD 基础设施：

| 层级 | 文件 | 内容 |
|------|------|------|
| 模型 | `backend/app/models/capacity.py` | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity, CapacityPlan, CapacityHistory |
| Schema | `backend/app/schemas/capacity.py` | 全部 Create/Update/Response schemas |
| API | `backend/app/api/v1/capacity.py` | 四维 CRUD + 统计 + 规划（890行） |
| 前端API | `frontend/src/api/modules/capacity.ts` | 全部 API 调用 + 类型定义（429行） |
| 前端页面 | `frontend/src/views/capacity/index.vue` | 四维统计卡片 + 空间/电力/制冷/上架评估标签页（1257行） |

### 已有功能清单

- ✅ 四维统计卡片（顶部，显示使用率+进度条+颜色）
- ✅ 空间容量 CRUD（标签页 + 对话框）
- ✅ 电力容量 CRUD（标签页 + 对话框）
- ✅ 制冷容量 CRUD（标签页 + 对话框）
- ✅ 上架评估 CRUD（标签页 + 对话框，含四维可行性自动评估）
- ✅ 统计 API（`GET /capacity/statistics`）
- ✅ 状态计算（normal/warning/critical/full）
- ✅ 进度条颜色（≥90%红/≥70%橙/其他绿）
- ✅ 状态标签（正常/警告/严重/已满）

### 缺失功能（本 Story 需实现）

1. **承重容量标签页** — 前端 `index.vue` 缺少承重容量标签页（后端 API 和前端 API 模块已有，但页面未展示）
2. **区域/楼层/房间维度聚合** — 后端无按 location 分组聚合的 API；前端无筛选器
3. **容量预警面板** — 前端无专门的预警视图，仅在表格中有状态标签

### 关键数据结构

**Cabinet 模型** (`backend/app/models/asset.py`):
- `location: String(200)` — 位置字段，格式如 "A区/1楼/101室"
- `total_u: Integer` — 总U数
- `max_power: Float` — 最大功率 kW
- `max_weight: Float` — 最大承重 kg

**SpaceCapacity 模型** (`backend/app/models/capacity.py`):
- `location: String(200)` — 位置字段
- `total_u_positions / used_u_positions` — U位
- `warning_threshold / critical_threshold` — 阈值

**所有四维容量模型都有 `location` 字段**，可用于按区域聚合。

### 前端容量页面现有结构

```
capacity/index.vue
├── 统计卡片行（4列：空间/电力/制冷/承重）  ← 已有
├── el-tabs
│   ├── 空间容量（表格 + CRUD）  ← 已有
│   ├── 电力容量（表格 + CRUD）  ← 已有
│   ├── 制冷容量（表格 + CRUD）  ← 已有
│   ├── 上架评估（表格 + CRUD）  ← 已有
│   ├── 承重容量（表格 + CRUD）  ← 需新增
│   └── 容量预警（预警列表）     ← 需新增
```

## 对抗性审查修复记录

### C-1: 前端 CapacityPlan 类型定义与后端 Schema 完全不匹配
前端 `CapacityPlanCreate` 用 `plan_name`/`plan_type`/`target_date`/`space_requirement`，后端用 `name`/`description`/`device_count`/`required_u`。
前端 `submitPlanForm()` 发送的字段后端不认识，必填字段 `name` 缺失导致 422。
**修复**: 新增 Task 0 修复前端接口定义，以后端 schema 为准。

### C-2: 统计 API 字段名不匹配导致卡片显示 0
后端电力统计返回 `total_capacity_kw`/`used_capacity_kw`，前端用 `total_power`/`used_power`。
制冷/承重同理（后端带 `_kw`/`_kg` 后缀，前端不带）。
**修复**: 后端 `/statistics` API 增加兼容别名字段，同时返回 `total_power` 和 `total_capacity_kw`。

### C-3: 电力/制冷表格字段名与后端响应不匹配
前端 `PowerCapacity` 接口用 `total_power`/`used_power`，后端返回 `total_capacity_kw`/`used_capacity_kw`。
**修复**: 在 Task 0 中统一修复前端 `capacity.ts` 所有接口定义，字段名改为与后端 schema 一致。

### H-1: 路由插入位置不明确
**修复**: 明确两个新端点放在 `# ==================== 容量统计 ====================` 区块内，`/statistics` 端点之后。FastAPI 对 `{id: int}` 有类型校验，`statistics`/`alerts` 字符串不会匹配 int 参数，无冲突风险。

### H-2: Task 6.1 指令矛盾 — getCapacityAlerts 已完整存在
`capacity.ts` L414-428 已有完整的 `getCapacityAlerts` 函数（含签名、参数、返回类型），不是"类型定义"。
**修复**: Task 6.1 改为"直接 import 使用已有的 `getCapacityAlerts`，无需新增"。

### H-3: CapacityStatistics 类型定义与后端不匹配
前端期望 `warning_count`/`critical_count`/`plan_count`，后端返回 `status_summary`/`total_capacity_records`。
**修复**: 在 Task 0 中修复 `CapacityStatistics` 及子类型定义，以后端实际返回为准。

### M-2: location 解析容错不足
**修复**: Task 1.3 明确：支持 `/`、`-`、空格等多种分隔符；空值或无法解析的归入"未分类"组。

### M-3: handleTabChange 遗漏
**修复**: Task 4 和 Task 6 各增加子任务，在 `handleTabChange` switch 中添加 `weight` 和 `alerts` case。

### M-4: 承重接口字段名不匹配
前端 `WeightCapacity` 用 `total_weight`/`used_weight`，后端用 `total_weight_kg`/`used_weight_kg`。
**修复**: 在 Task 0 中一并修复。

## Tasks / Subtasks

- [ ] Task 0: 前端 — 修复 capacity.ts 接口定义与后端 Schema 对齐 (前置修复)
  - [ ] 0.1 修复 `PowerCapacity` 接口：`total_power` → `total_capacity_kw`, `used_power` → `used_capacity_kw`, 删除 `reserved_power`/`available_power`（后端不返回）
  - [ ] 0.2 修复 `CoolingCapacity` 接口：`total_cooling` → `total_cooling_kw`, `used_cooling` → `used_cooling_kw`, 删除 `reserved_cooling`/`available_cooling`
  - [ ] 0.3 修复 `WeightCapacity`/`WeightCapacityCreate` 接口：`total_weight` → `total_weight_kg`, `used_weight` → `used_weight_kg`
  - [ ] 0.4 修复 `CapacityPlan`/`CapacityPlanCreate` 接口：`plan_name` → `name`, 删除 `plan_type`/`target_date`/`space_requirement`/`power_requirement`/`cooling_requirement`/`weight_requirement`/`status`/`priority`/`approved_by`/`approved_at`，改为 `description`/`device_count`/`required_u`/`required_power_kw`/`required_cooling_kw`/`required_weight_kg`
  - [ ] 0.5 修复 `CapacityStatistics` 及子类型：`SpaceStatistics` 删除 `total_area`/`used_area`/`available_area`/`total_cabinets`/`used_cabinets`，改为 `available_u_positions`/`count`；`PowerStatistics` 改为 `total_capacity_kw`/`used_capacity_kw`/`available_capacity_kw`/`count`；`CoolingStatistics` 同理；`WeightStatistics` 同理；顶层删除 `warning_count`/`critical_count`/`plan_count`，改为 `status_summary`/`total_capacity_records`
  - [ ] 0.6 修复 `index.vue` 统计卡片模板：电力用 `statistics.power?.used_capacity_kw`/`total_capacity_kw`，制冷用 `statistics.cooling?.used_cooling_kw`/`total_cooling_kw`，承重用 `statistics.weight?.used_weight_kg`/`total_weight_kg`
  - [ ] 0.7 修复 `index.vue` 电力表格模板：`row.used_power` → `row.used_capacity_kw`, `row.total_power` → `row.total_capacity_kw`
  - [ ] 0.8 修复 `index.vue` 制冷表格模板：`row.total_cooling` → `row.total_cooling_kw`
  - [ ] 0.9 修复 `index.vue` 上架评估表单提交：`plan_name` → `name`, 删除 `plan_type`/`target_date`，改用后端 schema 字段
  - [ ] 0.10 修复 `index.vue` 上架评估表格列：`row.plan_name` → `row.name`, `row.space_requirement` → `row.required_u` 等

- [ ] Task 1: 后端 — 新增按 location 聚合的统计 API (AC: #2)
  - [ ] 1.1 在 `capacity.py` 容量统计区块（`/statistics` 之后）新增 `GET /capacity/statistics/by-location` 端点
  - [ ] 1.2 按 location 字段分组，对四维容量分别聚合（sum total, sum used, calc rate）
  - [ ] 1.3 支持 `dimension` 查询参数（area/floor/room），解析 location 字段层级。分隔符支持 `/`、`-`、空格。空值或无法解析的归入"未分类"组
  - [ ] 1.4 返回格式：`{ items: [{ location, space: {total, used, rate}, power: {...}, cooling: {...}, weight: {...} }] }`

- [ ] Task 2: 后端 — 新增容量预警列表 API (AC: #3)
  - [ ] 2.1 在 `capacity.py` 容量统计区块新增 `GET /capacity/alerts` 端点
  - [ ] 2.2 查询所有四维容量中 status 为 warning/critical/full 的记录
  - [ ] 2.3 返回统一格式：`[{ type, name, location, status, usage_rate, threshold, created_at }]`
  - [ ] 2.4 支持按 type（space/power/cooling/weight）和 status 筛选

- [ ] Task 3: 后端测试 (AC: #1, #2, #3)
  - [ ] 3.1 测试 `GET /capacity/statistics/by-location` 正常返回
  - [ ] 3.2 测试按 dimension 参数聚合
  - [ ] 3.3 测试 `GET /capacity/alerts` 返回预警列表
  - [ ] 3.4 测试 alerts 按 type/status 筛选

- [ ] Task 4: 前端 — 新增承重容量标签页 (AC: #1)
  - [ ] 4.1 在 `index.vue` 添加承重容量 `el-tab-pane`（使用后端字段名 `total_weight_kg`/`used_weight_kg`，不要复制制冷标签页的错误字段名）
  - [ ] 4.2 添加承重容量 CRUD 对话框
  - [ ] 4.3 导入并使用 `getWeightCapacities, createWeightCapacity, updateWeightCapacity, deleteWeightCapacity`
  - [ ] 4.4 在 `handleTabChange` switch 中添加 `case 'weight': loadWeightList(); break;`

- [ ] Task 5: 前端 — 新增区域维度筛选器 (AC: #2)
  - [ ] 5.1 在 `capacity.ts` 添加 `getCapacityByLocation` API 调用
  - [ ] 5.2 在统计卡片上方添加维度选择器（区域/楼层/房间 + 具体值下拉）
  - [ ] 5.3 选择维度后，统计卡片数据切换为聚合数据
  - [ ] 5.4 添加"全部"选项恢复总览模式

- [ ] Task 6: 前端 — 新增容量预警标签页 (AC: #3)
  - [ ] 6.1 直接 import 使用已有的 `getCapacityAlerts`（capacity.ts L414-428），无需新增函数
  - [ ] 6.2 在 el-tabs 新增"容量预警"标签页
  - [ ] 6.3 预警列表表格：类型、名称、位置、状态（带颜色标签）、使用率（带进度条）、阈值
  - [ ] 6.4 支持按类型和状态筛选
  - [ ] 6.5 超阈值行高亮（warning 橙色背景，critical/full 红色背景）
  - [ ] 6.6 在 `handleTabChange` switch 中添加 `case 'alerts': loadAlertList(); break;`

## Dev Notes

### 后端开发约束

- **路由位置**: 新端点添加到 `backend/app/api/v1/capacity.py` 的 `# ==================== 容量统计 ====================` 区块内，`/statistics` 端点之后
- **路由顺序**: FastAPI 对 `{id: int}` 有类型校验，`statistics`/`alerts` 字符串不会匹配 int 参数，无冲突风险
- **location 解析**: location 字段是自由文本 `String(200)`，格式不固定。分隔符支持 `/`、`-`、空格。空值或无法解析的归入"未分类"组
- **`_calculate_usage_rate` 和 `_calculate_status`**: 已有辅助函数，直接复用

### 前端开发约束

- **自动导入**: Vue/Pinia API 无需手动 import（unplugin-auto-import）
- **Axios 拦截器**: `response.data` 已被拦截器解包，API 调用返回的就是 data
- **2.5D 样式**: 使用 `@use '@/styles/mixins-25d' as *` 和 `@include page-dashboard(N)` mixin
- **现有颜色函数**: `getProgressColor(percentage)` 和 `getStatusType(status)` 已在 index.vue 中定义，直接复用
- **Element Plus 组件**: 使用 `el-select` 做维度选择器，`el-table` 做预警列表
- **前端 API 模块**: `capacity.ts` 已有完整的 `getCapacityAlerts` 函数（L414-428），直接 import 使用，无需新增

### 已知前后端字段不匹配清单（Task 0 修复）

| 前端接口 | 前端字段名 | 后端 Schema 字段名 |
|----------|-----------|-------------------|
| `PowerCapacity` | `total_power` / `used_power` | `total_capacity_kw` / `used_capacity_kw` |
| `CoolingCapacity` | `total_cooling` / `used_cooling` | `total_cooling_kw` / `used_cooling_kw` |
| `WeightCapacity` | `total_weight` / `used_weight` | `total_weight_kg` / `used_weight_kg` |
| `CapacityPlan` | `plan_name` / `plan_type` / `target_date` | `name` / `description` / `device_count` |
| `CapacityStatistics` | `warning_count` / `critical_count` | `status_summary` / `total_capacity_records` |

### 前端已有 API 函数（capacity.ts）

已有但页面未使用的：
- `getWeightCapacities / createWeightCapacity / updateWeightCapacity / deleteWeightCapacity` — 承重 CRUD
- `getCapacityAlerts` — 容量预警列表（完整函数，直接使用）
- `getCapacityTrend` — 容量趋势（Story 7-6 用）
- `getCapacityForecast` — 容量预测（Story 7-6 用）

**警告**: 现有电力/制冷标签页的字段映射有问题（前端字段名与后端不一致），承重标签页不要盲目复制，应以后端 schema 为准。

### Project Structure Notes

- 所有改动集中在现有文件，不需要新建文件
- 后端改动: `backend/app/api/v1/capacity.py`（新增 2 个端点）
- 前端改动: `frontend/src/views/capacity/index.vue`（新增承重标签页 + 预警标签页 + 维度筛选器）
- 前端 API: `frontend/src/api/modules/capacity.ts`（新增 1 个 API 函数 `getCapacityByLocation`）
- 测试文件: `backend/tests/test_capacity_monitoring.py`（新建）

### Story 7-3 经验教训

- 新路由放在参数路由之前，避免被 `{id}` 吞掉
- ORM commit 后用已知值而非 ORM 属性
- `value or fallback` 对 0.0 会误判为 falsy，用 `if value is not None`
- 前端 Axios 拦截器已解包 `response.data`

### References

- [Source: backend/app/api/v1/capacity.py] — 现有容量 API（890行）
- [Source: backend/app/models/capacity.py] — 容量模型定义（159行）
- [Source: backend/app/schemas/capacity.py] — 容量 Schema（242行）
- [Source: frontend/src/api/modules/capacity.ts] — 前端 API 模块（429行）
- [Source: frontend/src/views/capacity/index.vue] — 容量管理页面（1257行）
- [Source: _bmad-output/planning-artifacts/epics.md#L722-736] — Story 7.4 定义
- [Source: _bmad-output/planning-artifacts/prd.md#L804] — FR59

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

### File List
