# Story 7.5: 智能上架推荐

Status: ready-for-dev

## Story

As a 资产管理员,
I want 获取系统推荐的最优上架位置,
So that 新设备可以放置在最合适的机柜中。

## FR 追溯

- FR60: 资产管理员可以获取系统基于容量数据生成的机柜上架推荐（≥3 个候选位置，每个位置附带空间/电力/制冷/承重多维度评分）（简化版，不含三相平衡和温度场）

## Acceptance Criteria

1. Given 资产管理员输入新设备需求（U位数、额定功率、重量）
   When 请求上架推荐
   Then 系统返回至少 3 个候选机柜，每个附带空间/电力/制冷/承重多维度评分（如满足条件的机柜不足 3 个，返回全部满足空间条件的候选）

2. Given 系统返回候选机柜列表
   When 资产管理员查看推荐结果
   Then 每个候选机柜显示四维评分（0-100分）和综合评分，按综合评分降序排列

3. Given 资产管理员不满意系统推荐
   When 手动选择其他机柜
   Then 支持人工覆盖推荐结果，将选中的机柜设为目标机柜

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| 容量规划模型 | `backend/app/models/capacity.py` L122-142 | CapacityPlan 含 required_u/required_power_kw/required_cooling_kw/required_weight_kg/target_cabinet_id/is_feasible/feasibility_notes |
| 容量规划Schema | `backend/app/schemas/capacity.py` L197-224 | CapacityPlanCreate/CapacityPlanResponse（含 target_cabinet_id, is_feasible, feasibility_notes） |
| 容量规划API | `backend/app/api/v1/capacity.py` L673-755 | create_capacity_plan 已做全局四维可行性评估 |
| 机柜模型 | `backend/app/models/asset.py` L38-56 | Cabinet 含 total_u/max_power/max_weight/location |
| 机柜Schema | `backend/app/schemas/asset.py` L42-51 | CabinetResponse 含 used_u/available_u（动态计算） |
| 机柜列表API | `backend/app/api/v1/asset.py` L131-162 | GET /asset/cabinets 返回含 used_u/available_u 的机柜列表 |
| 前端容量规划 | `frontend/src/api/modules/capacity.ts` L139-168 | CapacityPlan/CapacityPlanCreate 接口（含 target_cabinet_id） |
| 前端机柜API | `frontend/src/api/modules/asset.ts` L232-267 | getCabinets/getCabinet/getCabinetUsage |
| 前端上架评估 | `frontend/src/views/capacity/index.vue` L1103-1178 | 上架评估标签页 CRUD（表单含 required_u/required_power_kw 等） |

### 关键发现：评分数据来源

**Cabinet 模型已有的容量基线字段：**
- `total_u: Integer` — 总U数（默认42）
- `max_power: Float` — 最大功率 kW
- `max_weight: Float` — 最大承重 kg

**Cabinet 已有的动态计算（asset.py L131-162）：**
- `used_u` = SUM(Asset.u_height) WHERE cabinet_id = X — 已用U数
- `available_u` = total_u - used_u — 可用U数

**Cabinet 缺少的数据：**
- 无 `max_cooling` 字段 — 机柜级别无制冷容量上限
- 无 `current_power` — 无法直接获取当前功耗（Asset 模型无 power 字段）
- 无 `current_weight` — 无法直接获取当前承重（Asset 模型无 weight 字段）

### 评分策略设计（简化版 FR60）

由于 Cabinet 模型缺少 current_power/current_weight/max_cooling，采用以下简化策略：

1. **空间评分（space_score）**: 基于 Cabinet.available_u vs required_u — 数据完整，可精确计算
2. **电力评分（power_score）**: 基于 Cabinet.max_power vs required_power_kw — 仅检查上限是否满足（无当前功耗数据，假设未超载）
3. **制冷评分（cooling_score）**: 基于机柜所在 location 对应的 CoolingCapacity 记录的剩余制冷量 — 按 location 匹配
4. **承重评分（weight_score）**: 基于 Cabinet.max_weight vs required_weight_kg — 仅检查上限是否满足（无当前承重数据，假设未超载）

**评分公式（每维 0-100）：**
- 空间: `min(100, (available_u / required_u) * 50)` — required_u 已由 Schema 保证 >= 1，可用U位越多分越高，刚好满足得50分
- 电力: `required_power_kw 为 None → 100`（无需求=全部满足）; `max_power 为 None → 50`（未知）; 否则 `min(100, (max_power / required_power_kw) * 50)` — 渐进式评分
- 制冷: `required_cooling_kw 为 None 或 0 → 100`; 无匹配 CoolingCapacity → 50; 否则 `min(100, (available_cooling / required_cooling_kw) * 50)`
- 承重: `required_weight_kg 为 None → 100`; `max_weight 为 None → 50`; 否则 `min(100, (max_weight / required_weight_kg) * 50)` — 渐进式评分
- 综合: `(space * 0.4 + power * 0.2 + cooling * 0.2 + weight * 0.2)` — 空间权重最高

**制冷 location 匹配规则：**
- 匹配方向：`Cabinet.location.startswith(CoolingCapacity.location)`（机柜位置以制冷区域为前缀）
- 多匹配时取最长前缀匹配（最精确的区域）
- Cabinet.location 为 None → cooling_score = 50（未知）
- 无任何匹配 → cooling_score = 50（未知）

> 注：FR65（Epic 8 Story 8.3）将引入三相平衡度和温度场，届时评分公式会大幅增强。

## Tasks / Subtasks

- [ ] Task 1: 后端 — 新增推荐 Schema 和推荐 API (AC: #1, #2)
  - [ ] 1.1 在 `schemas/capacity.py` 新增 `RackingRecommendationRequest` 模型：required_u(int, Field(..., ge=1)), required_power_kw(float, Field(None, ge=0)), required_cooling_kw(float, Field(None, ge=0)), required_weight_kg(float, Field(None, ge=0)), limit(int, Field(5, ge=1, le=20))
  - [ ] 1.2 在 `schemas/capacity.py` 新增 `CabinetScore` 模型：cabinet_id(int), cabinet_code(str), cabinet_name(str), location(str), space_score(float), power_score(float), cooling_score(float), weight_score(float), total_score(float), available_u(int), max_power(float|None), max_weight(float|None), notes(str)
  - [ ] 1.3 在 `schemas/capacity.py` 新增 `RackingRecommendationResponse` 模型：request(RackingRecommendationRequest), candidates(List[CabinetScore]), total_cabinets_evaluated(int), qualified_count(int)
  - [ ] 1.4 在 `api/v1/capacity.py` 新增 `POST /capacity/recommend` 端点（放在 `/plans` 路由之前）
  - [ ] 1.5 推荐算法实现：
    - 单次聚合查询所有机柜的 used_u（避免 N+1）：`select(Asset.cabinet_id, func.sum(Asset.u_height)).where(Asset.u_height.isnot(None)).group_by(Asset.cabinet_id)`
    - 查询所有 Cabinet，结合聚合结果计算 available_u
    - 第一轮筛选（硬性）：available_u >= required_u（空间不够直接排除）
    - 第二轮筛选（软性）：max_power >= required_power_kw（如果两者都有值）；max_weight >= required_weight_kg（如果两者都有值）
    - 对通过筛选的机柜计算四维评分（公式见上方评分策略）
    - 制冷评分：查询所有 CoolingCapacity，按 location 前缀匹配机柜（取最长前缀匹配），计算剩余制冷量
    - 按 total_score 降序排列，返回 top N（limit 参数控制）
    - 如果候选不足 3 个，放宽筛选条件（仅保留空间硬性条件），重新评分
    - 放宽后仍不足 3 个时，返回所有满足空间条件的候选。如果连空间条件都无法满足，返回空列表，qualified_count = 0
  - [ ] 1.6 生成 notes 字段：对每个候选机柜生成中文说明，模板如下：
    - 空间: available_u >= required_u*2 → "空间充裕(可用{N}U)"; >= required_u → "空间满足(可用{N}U)"; < required_u → "空间不足(可用{N}U)"
    - 电力: required 为 None → 省略; max_power 为 None → "电力未配置"; max_power >= required*2 → "电力充裕({N}kW)"; >= required → "电力满足({N}kW)"; < required → "电力不足({N}kW)"
    - 制冷: required 为 None → 省略; 无匹配 → "制冷数据未知"; available >= required*2 → "制冷充裕"; >= required → "制冷满足"; < required → "制冷不足"
    - 承重: required 为 None → 省略; max_weight 为 None → "承重未配置"; max_weight >= required*2 → "承重充裕({N}kg)"; >= required → "承重满足({N}kg)"; < required → "承重不足({N}kg)"
    - 各维度用逗号连接

- [ ] Task 2: 后端 — 新增覆盖推荐 API (AC: #3)
  - [ ] 2.1 在 `api/v1/capacity.py` 新增 `PUT /capacity/plans/{id}/override-cabinet` 端点
  - [ ] 2.2 接受参数：target_cabinet_id(int, 必填)
  - [ ] 2.3 验证 cabinet_id 存在，更新 CapacityPlan.target_cabinet_id，基于目标机柜的四维容量重新评估（非全局评估，复用推荐算法的评分逻辑），更新 is_feasible/feasibility_notes（notes 中注明"已覆盖为机柜 XXX"）
  - [ ] 2.4 放在 `/plans/{id}` GET 路由之后、DELETE 路由之前

- [ ] Task 3: 后端测试 (AC: #1, #2, #3)
  - [ ] 3.1 测试 `POST /capacity/recommend` 正常返回候选列表（创建测试机柜数据）
  - [ ] 3.2 测试候选机柜按 total_score 降序排列
  - [ ] 3.3 测试空间不足的机柜被排除
  - [ ] 3.4 测试 required_u 为 0 或负数时返回 422
  - [ ] 3.5 测试 `PUT /plans/{id}/override-cabinet` 更新 target_cabinet_id
  - [ ] 3.6 测试 override 不存在的 cabinet_id 返回 404
  - [ ] 3.7 测试所有可选参数（power/cooling/weight）均为 None 时的推荐行为（应全部得 100 分）
  - [ ] 3.8 测试 Cabinet.max_power 为 None 时电力评分为 50
  - [ ] 3.9 测试无任何 CoolingCapacity 记录时制冷评分为 50
  - [ ] 3.10 测试候选不足 3 个时的放宽逻辑
  - [ ] 3.11 测试所有机柜空间都不足时返回空列表
  - [ ] 3.12 测试 Cabinet.location 为 None 时制冷评分为 50

- [ ] Task 4: 前端 — 新增推荐 API 和类型 (AC: #1, #2)
  - [ ] 4.1 在 `capacity.ts` 新增 `RackingRecommendationRequest` 接口
  - [ ] 4.2 在 `capacity.ts` 新增 `CabinetScore` 接口
  - [ ] 4.3 在 `capacity.ts` 新增 `RackingRecommendationResponse` 接口
  - [ ] 4.4 在 `capacity.ts` 新增 `getRackingRecommendation(data: RackingRecommendationRequest)` API 函数（POST /v1/capacity/recommend）
  - [ ] 4.5 在 `capacity.ts` 新增 `overridePlanCabinet(planId: number, cabinetId: number)` API 函数（PUT /v1/capacity/plans/{id}/override-cabinet）

- [ ] Task 5: 前端 — 上架评估标签页增加推荐功能 (AC: #1, #2, #3)
  - [ ] 5.1 在上架评估标签页的"新建"对话框中，将对话框宽度改为 `width="1000px"`，增加"获取推荐"按钮（在表单填写 required_u/required_power_kw/required_weight_kg 后可点击）
  - [ ] 5.2 点击"获取推荐"后调用 `getRackingRecommendation`，在对话框下方展示候选机柜列表
  - [ ] 5.3 候选列表用 el-table 展示：机柜编码、机柜名称、位置、空间评分、电力评分、制冷评分、承重评分、综合评分、备注
  - [ ] 5.4 评分列用进度条或颜色标签展示（≥80绿色，≥60橙色，<60红色）
  - [ ] 5.5 每行有"选择"按钮，点击后将 cabinet_id 填入表单的 target_cabinet_id 字段
  - [ ] 5.6 在上架评估表格中，已有 plan 的行增加"覆盖机柜"操作按钮
  - [ ] 5.7 点击"覆盖机柜"弹出机柜选择对话框（调用 getCabinets 获取列表），选择后调用 overridePlanCabinet
  - [ ] 5.8 上架评估表格增加 target_cabinet_id 对应的机柜名称列（需关联显示）

## 对抗性审查修复记录

### C-03: required_u=0 时除零崩溃
空间评分公式 `available_u / required_u` 在 required_u=0 时触发 ZeroDivisionError。
**修复**: Task 1.1 的 required_u 加 `Field(..., ge=1)` 验证，Schema 层面阻止 0 值。

### C-04: required_cooling_kw=0 时除零崩溃
制冷评分公式在 required_cooling_kw=0.0（非 None）时除零。
**修复**: 评分公式明确：required_cooling_kw 为 None 或 0 时，cooling_score = 100。

### H-01: 电力/承重二值评分导致区分度退化
原设计 100 or 0 的二值评分，通过筛选的机柜在这两个维度全部得 100 分，对排序无贡献。
**修复**: 改为渐进式评分 `min(100, (max_power / required_power_kw) * 50)`，与空间评分同构。

### H-02: required 为 None 时评分规则缺失
当用户不填功率/制冷/承重需求时，评分规则未定义。
**修复**: 明确 required 为 None → 该维度评分 100（无需求=全部满足）。

### H-03: 制冷 location 前缀匹配边界规则缺失
匹配方向、多匹配处理、location 为 None 时的行为未定义。
**修复**: 明确匹配方向为 Cabinet.location.startswith(CoolingCapacity.location)，多匹配取最长前缀，location 为 None 时 cooling_score=50。

### H-04: 放宽策略不明确 + AC #1 边界矛盾
AC 要求"至少3个"但物理上可能不足。
**修复**: AC #1 改为"如满足条件的机柜不足 3 个，返回全部满足空间条件的候选"。放宽后仍不足则返回空列表。

### H-05: 对话框 600px 塞不下 10 列推荐表格
现有对话框 600px 宽度无法容纳推荐结果的 10 列表格。
**修复**: Task 5.1 对话框宽度改为 `width="1000px"`。

### H-06: override 后重新评估逻辑不明确
现有 create_capacity_plan 是全局评估，override 后应该评估什么？
**修复**: 明确 override 后基于目标机柜的四维容量重新评估（非全局评估），复用推荐算法的评分逻辑。

### M-02: N+1 查询性能
逐机柜查询 used_u 是 N+1 查询。
**修复**: Task 1.5 改为单次聚合查询 `select(Asset.cabinet_id, func.sum(Asset.u_height)).group_by(Asset.cabinet_id)`。

### M-03: 测试用例缺少边界场景
**修复**: Task 3 补充 3.7-3.12 共 6 个边界测试用例。

### M-05: notes 模板不完整
**修复**: Task 1.6 列出完整的 notes 模板映射表，覆盖每个维度的充裕/满足/不足/未知状态。

### 信息提示: PUT /plans/{id} 不存在
后端当前缺少 `PUT /plans/{id}` 更新路由（前端 `updateCapacityPlan` 会 404），这是已有缺陷，不在本 Story 范围内。

## Dev Notes

### 后端开发约束

- **路由位置**: `POST /capacity/recommend` 与 `/plans/{id}` 路径段不同，无冲突风险。注意不要改为 `/plans/recommend`，否则会被 `{id}` 参数路由吞掉
- **路由位置**: `PUT /capacity/plans/{id}/override-cabinet` 放在 `/plans/{id}` GET 之后、DELETE 之前。注意：后端当前缺少 `PUT /plans/{id}` 更新路由（前端 updateCapacityPlan 会 404），这是已有缺陷，不在本 Story 范围内
- **数据库查询**: 推荐算法需要查询 Cabinet + Asset（计算 used_u）+ CoolingCapacity（制冷评分），注意异步查询性能
- **Cabinet 无 current_power/current_weight**: 电力和承重评分采用二值判断（max_power/max_weight 是否满足），不做精确剩余计算
- **制冷匹配**: CoolingCapacity.location 与 Cabinet.location 按前缀匹配（如机柜 location="A区/1楼/101室/A01" 匹配 CoolingCapacity location="A区/1楼/101室"）
- **`value or fallback` 陷阱**: max_power/max_weight 可能为 0.0，用 `if value is not None` 判断
- **ORM session**: commit 后用已知值而非 ORM 属性

### 前端开发约束

- **自动导入**: Vue/Pinia API 无需手动 import（unplugin-auto-import）
- **Axios 拦截器**: `response.data` 已被拦截器解包，API 调用返回的就是 data
- **2.5D 样式**: 使用 `@use '@/styles/mixins-25d' as *` 和 `@include page-dashboard(N)` mixin
- **现有颜色函数**: `getProgressColor(percentage)` 和 `getStatusType(status)` 已在 index.vue 中定义，直接复用
- **推荐结果展示**: 在现有上架评估对话框内嵌入推荐结果区域，不新建独立页面
- **机柜名称显示**: 上架评估表格中 target_cabinet_id 需要关联显示机柜名称，可在 loadPlanList 时额外调用 getCabinets 获取映射

### 已有前端 API 函数（capacity.ts）

直接复用：
- `createCapacityPlan` / `updateCapacityPlan` / `deleteCapacityPlan` — 上架评估 CRUD
- `getCapacityPlans` — 上架评估列表

需新增：
- `getRackingRecommendation` — 获取推荐候选
- `overridePlanCabinet` — 覆盖推荐机柜

### 已有前端 API 函数（asset.ts）

直接复用：
- `getCabinets` — 获取机柜列表（用于覆盖机柜选择对话框）

### Story 7-4 经验教训

- 新路由放在参数路由之前，避免被 `{id}` 吞掉
- ORM commit 后用已知值而非 ORM 属性
- `value or fallback` 对 0.0 会误判为 falsy，用 `if value is not None`
- 前端 Axios 拦截器已解包 `response.data`
- 前端接口定义必须与后端 Schema 字段名完全一致

### 与 FR65 的边界

本 Story 实现 FR60（简化版）：
- ✅ 基于 Cabinet.total_u/max_power/max_weight + CoolingCapacity 的简化评分
- ✅ 四维评分（空间/电力/制冷/承重）
- ❌ 不含三相平衡度（FR65, Epic 8 Story 8.3）
- ❌ 不含温度场分布（FR65, Epic 8 Story 8.3）
- ❌ 不含 PDU 拓扑关系（FR63, Epic 8 Story 8.2）

### Project Structure Notes

- 后端改动: `backend/app/api/v1/capacity.py`（新增 2 个端点）, `backend/app/schemas/capacity.py`（新增 3 个 Schema）
- 前端改动: `frontend/src/views/capacity/index.vue`（上架评估标签页增强）
- 前端 API: `frontend/src/api/modules/capacity.ts`（新增 3 个接口 + 2 个 API 函数）
- 测试文件: `backend/tests/test_racking_recommendation.py`（新建）
- 不需要新建页面或路由

### References

- [Source: backend/app/api/v1/capacity.py#L673-755] — 现有 create_capacity_plan 可行性评估
- [Source: backend/app/models/capacity.py#L122-142] — CapacityPlan 模型
- [Source: backend/app/models/asset.py#L38-56] — Cabinet 模型
- [Source: backend/app/schemas/asset.py#L42-51] — CabinetResponse（含 used_u/available_u）
- [Source: backend/app/api/v1/asset.py#L131-162] — GET /asset/cabinets 机柜列表
- [Source: frontend/src/api/modules/capacity.ts#L139-168] — CapacityPlan/CapacityPlanCreate 接口
- [Source: frontend/src/api/modules/asset.ts#L232-267] — 机柜 API 函数
- [Source: frontend/src/views/capacity/index.vue#L1103-1178] — 上架评估标签页
- [Source: _bmad-output/planning-artifacts/epics.md#L738-754] — Story 7.5 定义
- [Source: _bmad-output/planning-artifacts/prd.md#L805] — FR60

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
