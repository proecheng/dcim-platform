# Story 8.3: 多维度智能选址推荐

Status: in-progress

## Story

As a 资产管理员,
I want 获取基于三合一拓扑模型的智能选址推荐,
So that 新设备可以放置在空间、电力、温度、制冷综合最优的位置。

## FR 追溯

- FR65: 基于三合一拓扑模型的增强版智能选址（空间+电力+三相平衡度+温度环境+制冷余量五维评分）

## Acceptance Criteria

1. Given 三合一拓扑模型已配置完成
   When 资产管理员输入新设备需求（U 位数、额定功率、重量）
   Then 系统返回 Top N 候选机柜，每个附带多维度评分卡：空间容量(30%)、电力容量(25%)、三相平衡度(20%)、温度环境(15%)、制冷余量(10%)

2. Given 系统返回候选机柜列表
   When 查看机柜平面图
   Then 机柜平面图上用颜色标注各维度评分（绿/黄/红）

3. Given 数据不足时
   When 某些维度缺少数据
   Then 降级推荐并标注置信度（高/中/低）

4. Given 管理员需要调整权重
   When 通过前端滑块调整权重
   Then 权重默认固定，前端自动归一化确保总和为100%

## 与 Story 7-5 的关系

**并存关系**：
- `POST /capacity/recommend` (Story 7-5, FR60) — 简化版四维推荐（空间/电力/制冷/承重），基于 CoolingCapacity 模型，不依赖拓扑配置
- `POST /topology-config/smart-site-selection` (本 Story, FR65) — 增强版五维推荐，基于三合一拓扑模型，需要 8-1/8-2 拓扑配置完成

两者面向不同场景：7-5 适用于拓扑未配置时的快速推荐，本 Story 适用于拓扑完整配置后的精准推荐。前端两个入口并存。

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| 简化版推荐 | `backend/app/api/v1/capacity.py` L661-822 | POST /capacity/recommend — 四维评分（空间/电力/制冷/承重），Story 7-5 |
| 空间拓扑 | `backend/app/models/spatial.py` | Site→Floor→Room→Row→Cabinet 层级 |
| Cabinet 模型 | `backend/app/models/asset.py` L38-62 | total_u, max_power, max_weight, row_id, aisle_type, grid_x, grid_y |
| 配电拓扑 | `backend/app/models/topology_config.py` | PowerPhaseMapping(cabinet_id, pdu_device_id, phase, feed_type) |
| 制冷拓扑 | `backend/app/models/topology_config.py` | CoolingZone, CoolingZoneCabinet, CoolingZoneUnit |
| 三相不平衡度 | `backend/app/api/v1/topology_config.py` | GET /topology-config/power-phase/pdu/{id}/balance |
| 制冷容量 | `backend/app/api/v1/topology_config.py` | GET /topology-config/cooling-zones/{id}/capacity |
| 前端拓扑 API | `frontend/src/api/modules/topologyConfig.ts` | 配电/制冷拓扑 CRUD + 汇总 |
| 前端容量 API | `frontend/src/api/modules/capacity.ts` | RackingRecommendationRequest/Response |
| 前端空间拓扑 | `frontend/src/views/topology/spatial.vue` | 空间拓扑配置页面（含网格平面图） |

## 五维评分设计

### 权重分配（默认）

| 维度 | 权重 | 数据来源 | 无数据时 |
|------|------|----------|----------|
| 空间容量 | 30% | Cabinet.total_u - SUM(Asset.u_height) | 永远有数据（total_u 默认42） |
| 电力容量 | 25% | Cabinet.max_power vs required_power_kw | max_power 为 None → data_available=false |
| 三相平衡度 | 20% | PowerPhaseMapping → 基于 max_power 估算不平衡度 | 无 PowerPhaseMapping → data_available=false |
| 温度环境 | 15% | 机柜所在 CoolingZone 的制冷利用率 | 无 CoolingZone → data_available=false |
| 制冷余量 | 10% | CoolingZone 剩余制冷量 vs required_power_kw | 无 CoolingZone 或 required_power_kw 为 None → data_available=false |

### 评分公式（每维 0-100）

1. **空间评分**: `min(100, (available_u / required_u) * 50)` — 复用 7-5。data_available=true（永远有数据）

2. **电力评分**: required_power_kw 为 None → score=100, data_available=true（无需求=全满足）; max_power 为 None → score=50, data_available=false; 否则 `min(100, (max_power / required_power_kw) * 50)`（required_power_kw=0 时 score=100）, data_available=true

3. **三相平衡度评分** [审查修复: C1, H2]:
   - 查找机柜的 PowerPhaseMapping（feed_type="primary"），获取 PDU 和相位
   - 查询同 PDU 所有 PowerPhaseMapping，按 phase 分组汇总 Cabinet.max_power（与现有 balance API 一致，使用额定功率估算）
   - 模拟新设备接入：将 required_power_kw（默认0）加到目标机柜所在相位的功率上
   - 计算模拟后的不平衡度: (max-min)/avg * 100
   - 评分: `max(0, 100 - imbalance_rate * 3)` — 不平衡度 33% 时 0 分
   - 无 PowerPhaseMapping → score=50, data_available=false
   - 除零保护: avg==0 时 score=80（空载PDU，接入后不平衡度低）

4. **温度环境评分** [审查修复: C2, C3]:
   - 查找机柜所在 CoolingZone（通过 CoolingZoneCabinet）
   - 计算 CoolingZone 利用率: SUM(关联机柜.max_power) / design_capacity_kw * 100（与现有 get_cooling_zone_capacity 一致）
   - 评分: `max(0, 100 - utilization_rate)` — 利用率 0% → 100分，100% → 0分
   - 无 CoolingZone → score=50, data_available=false
   - design_capacity_kw 为 None 或 0 → score=50, data_available=false

5. **制冷余量评分** [审查修复: C2, M4]:
   - 与温度环境的区别：温度环境评估当前状态（利用率），制冷余量评估新设备接入后的剩余量
   - remaining_cooling = design_capacity_kw - SUM(关联机柜.max_power) - required_power_kw
   - required_power_kw 为 None 或 0 → score=100, data_available=true（无需求=全满足）
   - 无 CoolingZone → score=50, data_available=false
   - remaining_cooling <= 0 → score=0（制冷不足）
   - 否则 `min(100, (remaining_cooling / required_power_kw) * 50)`

### 置信度计算 [审查修复: H4]

基于 `DimensionScore.data_available` 标志（非评分值判断）：

| data_available=true 的维度数 | 置信度 |
|------------------------------|--------|
| 5/5 | 高 |
| 3-4/5 | 中 |
| 1-2/5 | 低 |

## Tasks / Subtasks

### 后端

- [ ] Task 1: 新增 Schema (AC: #1, #3, #4) [审查修复: H1, H4]
  - [ ] 1.1 在 `schemas/topology_config.py` 新增 `SmartSiteWeights`: space(float, default=30), power(float, default=25), phase_balance(float, default=20), temperature(float, default=15), cooling(float, default=10)。**添加 model_validator 确保五项之和为 100，否则自动归一化**
  - [ ] 1.2 新增 `SmartSiteRequest`: required_u(int, Field(..., ge=1)), required_power_kw(Optional[float], Field(None, ge=0)), required_weight_kg(Optional[float], Field(None, ge=0)), limit(int, Field(10, ge=1, le=50)), weights(Optional[SmartSiteWeights], default=None → 使用默认权重)
  - [ ] 1.3 新增 `DimensionScore`: dimension(str), score(float), weight(float), weighted_score(float), data_available(bool), detail(str)
  - [ ] 1.4 新增 `CabinetSiteScore`: cabinet_id(int), cabinet_code(str), cabinet_name(str), location(Optional[str]), room_name(Optional[str]), row_name(Optional[str]), available_u(int), total_score(float), confidence(str: high/medium/low), dimensions(List[DimensionScore]), grid_x(Optional[int]), grid_y(Optional[int]), aisle_type(Optional[str])
  - [ ] 1.5 新增 `SmartSiteResponse`: request(SmartSiteRequest), candidates(List[CabinetSiteScore]), total_evaluated(int), qualified_count(int)

- [ ] Task 2: 新增智能选址 API (AC: #1, #3) [审查修复: C1, C2, C3, M2]
  - [ ] 2.1 在 `api/v1/topology_config.py` 新增 `POST /topology-config/smart-site-selection`
  - [ ] 2.2 权限: require_viewer
  - [ ] 2.3 批量预加载所有数据（避免 N+1）:
    - 查询所有 Cabinet
    - 单次聚合查询 used_u: `select(Asset.cabinet_id, func.sum(Asset.u_height)).group_by(Asset.cabinet_id)`
    - 查询所有 PowerPhaseMapping（一次性加载）
    - 查询所有 CoolingZoneCabinet + CoolingZone（一次性加载）
  - [ ] 2.4 硬性筛选: available_u >= required_u
  - [ ] 2.5 五维评分（公式见上方）
  - [ ] 2.6 置信度计算（基于 data_available 标志）
  - [ ] 2.7 按 total_score 降序返回 Top N
  - [ ] 2.8 空间信息填充: 通过 Cabinet.row_id → Row → Room 获取 room_name/row_name（批量预加载 Row+Room 关系）

- [ ] Task 3: 后端测试 (AC: all)
  - [ ] 3.1 test_smart_site_basic — 基本推荐返回候选列表，验证响应结构
  - [ ] 3.2 test_smart_site_space_scoring — 空间评分正确性
  - [ ] 3.3 test_smart_site_power_scoring — 电力评分：有 max_power / 无 max_power / 无 required
  - [ ] 3.4 test_smart_site_phase_balance — 三相平衡度：有 PowerPhaseMapping / 无映射 / 模拟接入
  - [ ] 3.5 test_smart_site_temperature — 温度环境：有 CoolingZone / 无 CoolingZone
  - [ ] 3.6 test_smart_site_cooling_remaining — 制冷余量：有余量 / 无余量 / required 为 None
  - [ ] 3.7 test_smart_site_confidence — 置信度：高/中/低
  - [ ] 3.8 test_smart_site_custom_weights — 自定义权重 + 归一化验证
  - [ ] 3.9 test_smart_site_no_candidates — 无候选时返回空列表
  - [ ] 3.10 test_smart_site_required_power_zero — required_power_kw=0 不除零

### 前端

- [ ] Task 4: 前端 API 扩展 (AC: all)
  - [ ] 4.1 在 `api/modules/topologyConfig.ts` 新增 SmartSiteWeights, SmartSiteRequest, DimensionScore, CabinetSiteScore, SmartSiteResponse 接口
  - [ ] 4.2 新增 `getSmartSiteSelection(data: SmartSiteRequest)` API 函数

- [ ] Task 5: 智能选址页面 (AC: #1, #2, #4)
  - [ ] 5.1 新建 `views/topology/site-selection.vue`
  - [ ] 5.2 左侧面板: 设备需求表单（U位数必填、功率可选、重量可选）+ 权重滑块（5个 el-slider，联动归一化确保总和100%）+ "开始推荐"按钮
  - [ ] 5.3 右侧上: 候选机柜列表（el-table）— 机柜编码、位置、可用U、五维评分（进度条+颜色）、综合评分、置信度标签
  - [ ] 5.4 右侧下: 机柜平面图（CSS Grid，复用 spatial.vue 的网格模式）— 候选机柜用颜色标注综合评分（≥80绿、≥60橙、<60红），非候选灰色
  - [ ] 5.5 点击候选行高亮平面图中对应机柜，显示五维评分详情弹窗

- [ ] Task 6: 路由注册 (AC: all)
  - [ ] 6.1 在 `router/index.ts` 的 infrastructure children 中添加 `/infrastructure/site-selection` 路由，菜单名称"智能选址"

## 对抗性审查修复记录

### C1: 三相平衡度"模拟新设备接入"逻辑不可行
**问题**: PowerPhaseMapping 记录的是接线关系而非实际负载，无法基于实际负载模拟。
**修复**: 明确使用 Cabinet.max_power 估算（与现有 balance API 一致）。模拟策略：取 primary feed_type 的 PDU，将 required_power_kw 加到该 PDU 对应相位上重新计算不平衡度。

### C2: 温度环境和制冷余量数据重叠
**问题**: 两个维度都基于 CoolingZone 容量数据，高度相关。
**修复**: 明确区分语义 — 温度环境评估"当前状态"（利用率），制冷余量评估"新设备接入后的剩余量"。

### C3: CoolingZone "当前负载" 数据来源未定义
**问题**: Story 未定义"当前负载"的计算方式。
**修复**: 明确"当前负载 = SUM(关联机柜.max_power)"，与现有 get_cooling_zone_capacity 端点保持一致。

### H1: 权重归一化
**问题**: 前端滑块调整后权重总和可能不为 100%。
**修复**: SmartSiteWeights 添加 model_validator，自动归一化确保总和为 100。

### H2: 三相不平衡度系数过于宽松
**问题**: 系数 2 意味着不平衡度 50% 才 0 分。
**修复**: 改为系数 3，不平衡度 33% 时 0 分。

### H3: 与旧 API 关系未明确
**修复**: 新增"与 Story 7-5 的关系"章节，明确并存关系。

### H4: 置信度用评分值 50 判断会误判
**修复**: 使用 DimensionScore.data_available 布尔标志判断。

### M1: API 路径位置
**决策**: 保留在 topology_config 下，因为核心依赖三合一拓扑数据。

### M2: N+1 查询性能
**修复**: Task 2.3 明确批量预加载所有数据。

### M3: 前端路由新增
**修复**: Task 6.1 明确在 infrastructure children 中新增路由。

### M4: required_power_kw=0 除零
**修复**: 评分公式中明确 required_power_kw 为 None 或 0 → score=100。

## Dev Notes

### 后端模式参考

- 复用 capacity.py L661-822 的推荐算法模式（聚合查询 + 评分 + 排序）
- 新 API 放在 topology_config.py 中（依赖三合一拓扑数据）
- 权限: require_viewer（只读推荐）
- 批量预加载: 一次性查询 Cabinet、used_u、PowerPhaseMapping、CoolingZoneCabinet+CoolingZone，构建内存映射后逐机柜评分
- 三相平衡度计算参考: topology_config.py 现有 get_phase_balance 端点
- CoolingZone 负载计算参考: topology_config.py 现有 get_cooling_zone_capacity 端点
- `value or fallback` 陷阱: max_power/design_capacity_kw 可能为 0.0，用 `if value is not None` 判断

### 前端模式参考

- 页面布局参考 topology/spatial.vue 的网格平面图
- 评分展示参考 capacity/index.vue 的上架推荐表格
- 2.5D 样式: `@use '@/styles/mixins-25d' as *` + `@include page-dashboard(N)`
- 自动导入: Vue/Pinia API 无需手动 import
- 权重滑块联动: 调整一个滑块时，其他滑块按比例缩放确保总和 100%

### 架构对齐

- Architecture 9.5: 智能选址 = 空间+配电+制冷三合一拓扑 + 多维评分
- FR65: 五维评分卡 + 颜色标注 + 置信度 + 可调权重

### Project Structure Notes

- 后端修改: `schemas/topology_config.py`（新增 Schema）, `api/v1/topology_config.py`（新增 API）
- 后端新增: `tests/test_smart_site_selection.py`
- 前端修改: `api/modules/topologyConfig.ts`（新增类型+函数）, `router/index.ts`（新增路由）
- 前端新增: `views/topology/site-selection.vue`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
