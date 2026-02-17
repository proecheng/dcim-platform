# Story 8.1: 空间拓扑配置

Status: done

## Story

As a 集成工程师,
I want 配置机柜的物理位置和空间层级,
So that 系统可以建立完整的空间拓扑模型。

## FR 追溯

- FR62: 集成工程师可以配置机柜物理位置（行列号、冷热通道归属、楼层/房间/区域层级）

## Acceptance Criteria

1. Given 集成工程师在物理拓扑配置页面
   When 配置机柜物理位置
   Then 可设置行列号、冷热通道归属、楼层/房间/区域层级（Site-Floor-Room-Row-Cabinet）

2. Given 集成工程师有大量机柜需要配置
   When 使用 Excel 批量导入
   Then 系统解析 Excel 文件，批量创建/更新空间层级和机柜位置关系

3. Given 集成工程师在空间拓扑页面
   When 使用可视化拖拽配置
   Then 可在平面图上拖拽机柜到指定行列位置，实时更新位置信息

4. Given 集成工程师需要快速配置标准机房
   When 选择布局模板
   Then 提供常见机房布局模板（2N 冷通道、单排、双排等），一键应用后自动生成行列和机柜位置

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| Cabinet 模型 | `backend/app/models/asset.py` L38-55 | cabinet_code, cabinet_name, location(str), row_number(str), column_number(str), total_u, max_power, max_weight |
| Cabinet Schema | `backend/app/schemas/asset.py` | CabinetBase/Create/Update/Response |
| Cabinet API | `backend/app/api/v1/asset.py` | GET/POST/PUT/DELETE /asset/cabinets |
| FloorMap 模型 | `backend/app/models/floor_map.py` | floor_code, floor_name, map_type(2d/3d), map_data(JSON), thumbnail, is_default |
| FloorMap API | `backend/app/api/v1/floor_map.py` | GET /floor-maps/floors, GET /{floor_code}/{map_type} |
| 拓扑编辑 API | `backend/app/api/v1/topology.py` | POST/PUT/DELETE /topology/nodes, /batch, /export, /import |
| 拓扑 Schema | `backend/app/schemas/energy.py` | TopologyNodeCreate/Update/Delete, TopologyNodePosition(x,y) |
| 前端拓扑编辑 | `frontend/src/views/energy/topology.vue` | 拓扑树形展示、节点编辑、位置字段 |
| 前端拓扑 API | `frontend/src/api/modules/energy.ts` | getDistributionTopology, createTopologyNode, etc. |
| 前端机柜 API | `frontend/src/api/modules/asset.ts` | getCabinets, createCabinet, updateCabinet |
| Excel 导入参考 | `backend/app/api/v1/asset.py` L505+ | IMPORT_COLUMN_MAP, openpyxl 解析, 批量创建 |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| Site/Floor/Room/Row 数据模型 | 架构要求 Site→Floor→Room→Row→Cabinet 层级，当前无独立模型 |
| Cabinet 扩展字段 | 架构要求 `aisle_type`(cold/hot) 和 `cooling_zone_id`，当前 Cabinet 模型无此字段 |
| 空间拓扑 CRUD API | 无 Site/Floor/Room/Row 的管理端点 |
| 空间拓扑前端页面 | 无专门的空间拓扑配置页面 |
| Excel 批量导入空间拓扑 | 现有 Excel 导入仅支持资产，不支持空间层级 |
| 布局模板库 | FloorMap 存在但无预置模板数据 |

### 关键设计决策

#### 1. 空间层级模型设计

架构定义：`Site→Floor→Room→Row→Cabinet`

**决策**: 新建 `SpatialTopology` 模型文件 `backend/app/models/spatial.py`，包含 4 个模型：
- `Site`: id, site_code, site_name, address, description
- `Floor`: id, floor_code, floor_name, site_id(FK→Site), sort_order
- `Room`: id, room_code, room_name, floor_id(FK→Floor), area_sqm, description
- `Row`: id, row_code, row_name, room_id(FK→Room), aisle_type(cold/hot/none), sort_order

Cabinet 扩展：在现有 Cabinet 模型上新增字段（全部 nullable=True，C2 修复）：
- `row_id`: FK→Row（nullable=True，兼容现有无层级的机柜）
- `aisle_type`: Enum(cold/hot/none)（冷热通道归属，nullable=True）
- `grid_x`: Integer（平面图 X 坐标，nullable=True）
- `grid_y`: Integer（平面图 Y 坐标，nullable=True）

Schema 扩展：`CabinetCreate`/`CabinetUpdate`/`CabinetResponse` 中新增字段均为 `Optional[int/str] = None`。

#### 2. API 设计

新增路由前缀 `/api/v1/spatial`：
- `GET /spatial/tree` — 获取完整空间层级树（Site→Floor→Room→Row→Cabinet）
- `POST/PUT/DELETE /spatial/sites` — Site CRUD
- `POST/PUT/DELETE /spatial/floors` — Floor CRUD
- `POST/PUT/DELETE /spatial/rooms` — Room CRUD
- `POST/PUT/DELETE /spatial/rows` — Row CRUD
- `PUT /spatial/cabinets/{id}/position` — 更新机柜位置（row_id, grid_x, grid_y, aisle_type）
- `POST /spatial/import` — Excel 批量导入
- `GET /spatial/export` — Excel 导出
- `GET /spatial/templates` — 获取布局模板列表
- `POST /spatial/templates/{template_id}/apply` — 应用布局模板到指定 Room

#### 3. Excel 批量导入格式

| 列名 | 字段 | 必填 |
|------|------|------|
| 站点编码 | site_code | 是 |
| 楼层编码 | floor_code | 是 |
| 房间编码 | room_code | 是 |
| 行编码 | row_code | 是 |
| 通道类型 | aisle_type | 否(默认none) |
| 机柜编码 | cabinet_code | 是 |
| 机柜名称 | cabinet_name | 是 |
| 列号 | column_number | 否 |
| 总U数 | total_u | 否(默认42) |
| 最大功率 | max_power | 否 |
| 最大承重 | max_weight | 否 |

导入逻辑（两阶段，C4 修复）：
1. 扫描阶段：遍历所有行，收集去重后的 Site/Floor/Room/Row 集合
2. 批量创建阶段：查询已存在实体，只创建缺失的（避免 UNIQUE 冲突）
3. 机柜关联阶段：逐行处理机柜，关联到对应 Row
整个操作在单个事务中完成（M3 修复）。

#### 4. 布局模板

预置 3 个模板，存储在 `LayoutTemplate` 模型中：
- `2n_cold_aisle`: 2N 冷通道布局（双排面对面，中间冷通道）
- `single_row`: 单排布局
- `double_row`: 双排背靠背布局

模板数据结构（JSON）：
```json
{
  "name": "2N 冷通道",
  "rows": [
    {"row_code": "R1", "aisle_type": "cold", "cabinets": 10},
    {"row_code": "R2", "aisle_type": "cold", "cabinets": 10}
  ],
  "description": "双排面对面，中间冷通道"
}
```

应用模板时：在指定 Room 下自动创建 Row 和 Cabinet（cabinet_code 自动生成）。

#### 5. 可视化拖拽

前端在 Room 级别展示网格平面图，机柜可拖拽到网格位置。拖拽完成后调用 `PUT /spatial/cabinets/{id}/position` 更新 grid_x/grid_y。

**简化方案**: 使用 CSS Grid + 拖拽事件实现，不引入额外拖拽库。网格大小固定（如 20x20），每个格子代表一个机柜位。

## Tasks / Subtasks

### Task 1: 后端 — 空间层级模型 (AC: #1)

- [ ] 1.1 新建 `backend/app/models/spatial.py`，定义 Site, Floor, Room, Row, LayoutTemplate 模型
- [ ] 1.2 在 Cabinet 模型上新增 `row_id`, `aisle_type`, `grid_x`, `grid_y` 字段
- [ ] 1.3 在 `models/__init__.py` 导出新模型
- [ ] 1.4 新建 `backend/app/schemas/spatial.py`，定义 CRUD Schema + 树形响应 Schema

### Task 2: 后端 — 空间拓扑 API (AC: #1)

- [ ] 2.1 新建 `backend/app/api/v1/spatial.py`，实现 Site/Floor/Room/Row CRUD
  - 删除端点实现"拒绝删除含子实体"策略（C3）：先查子实体数量，>0 返回 400
- [ ] 2.2 实现 `GET /spatial/tree` 返回完整层级树
- [ ] 2.3 实现 `PUT /spatial/cabinets/{id}/position` 更新机柜位置
- [ ] 2.4 在 `api/v1/__init__.py` 注册新路由

### Task 3: 后端 — Excel 导入导出 (AC: #2)

- [ ] 3.1 实现 `POST /spatial/import` Excel 批量导入（openpyxl）
  - 两阶段导入（C4）：先扫描去重 → 批量创建缺失实体 → 再处理机柜关联
  - 显式事务管理（M3）：整个操作在单个事务中，错误时回滚
  - 返回导入结果（成功/失败/跳过数量）
- [ ] 3.2 实现 `GET /spatial/export` Excel 导出

### Task 4: 后端 — 布局模板 (AC: #4)

- [ ] 4.1 实现 `GET /spatial/templates` 返回预置模板列表
- [ ] 4.2 实现 `POST /spatial/templates/{template_id}/apply` 应用模板到 Room
  - 在 Room 下自动创建 Row 和 Cabinet
  - cabinet_code 格式：`{room_code}-{row_code}-C{seq:02d}`（H2：含完整空间路径前缀）
  - 应用前检查 cabinet_code 是否已存在，冲突则跳过并报告（H2）
  - 显式事务管理（M3）
- [ ] 4.3 在数据库初始化时插入 3 个预置模板

### Task 5: 后端 — 测试 (AC: #1-#4)

- [ ] 5.1 测试 Site/Floor/Room/Row CRUD
- [ ] 5.2 测试空间层级树
- [ ] 5.3 测试 Excel 导入导出
- [ ] 5.4 测试布局模板应用

### Task 6: 前端 — 空间拓扑页面 (AC: #1, #3, #4)

- [ ] 6.1 新建 `frontend/src/views/topology/spatial.vue` 空间拓扑配置页面
- [ ] 6.2 新建 `frontend/src/api/modules/spatial.ts` API 模块
- [ ] 6.3 左侧：空间层级树（Site→Floor→Room→Row），支持增删改
- [ ] 6.4 右侧：Room 级别网格平面图，机柜可拖拽定位
  - CSS Grid 实现网格
  - 机柜显示编码 + 通道类型颜色标注（冷通道蓝色、热通道红色）
  - 拖拽完成后更新 grid_x/grid_y
- [ ] 6.5 工具栏：Excel 导入/导出按钮 + 模板选择器
- [ ] 6.6 添加路由 `/topology/spatial`

## 对抗性审查修复

### C1: SQLite ALTER TABLE 限制
**问题**: SQLite 不支持 ALTER TABLE ADD COLUMN with FK/Enum 约束。
**修复**: 开发环境使用"删除 dcim.db + 重启自动重建"策略。不使用 Alembic 迁移。在 Dev Notes 中明确标注。

### C2: Cabinet `row_id` FK 必须 nullable=True
**问题**: 现有 9 个文件、157 处引用 Cabinet 的创建/更新流程，若 `row_id` 非空会全部报错。
**修复**: `row_id` 定义为 `nullable=True`。`CabinetCreate`/`CabinetUpdate` schema 中 `row_id` 为 `Optional[int] = None`。`CabinetResponse` 中也为 `Optional[int] = None`。

### C3: 级联删除策略
**问题**: 删除 Room/Row 等父实体时，子实体的 FK 会导致约束违反或数据丢失。
**修复**: 采用"拒绝删除含子实体的父实体"策略。每个删除端点先查询子实体数量，若 > 0 返回 400 错误（提示"请先删除子实体"）。

### C4: Excel 导入竞态条件
**问题**: 逐行"自动创建缺失实体"会导致 UNIQUE 约束冲突（多行引用同一 site_code）。
**修复**: 两阶段导入：
1. 扫描所有行，收集去重后的 Site/Floor/Room/Row 集合
2. 批量创建缺失实体（先查询已存在的，只创建不存在的）
3. 再逐行处理机柜关联

### H1: FloorMap vs Floor 模型语义冲突
**问题**: FloorMap 有 `floor_code`/`floor_name` 但与新 Floor 模型无 FK 关系。
**修复**: 两者独立。FloorMap 是 2D/3D 地图数据，Floor 是空间层级节点。在 Dev Notes 中注明它们是独立概念，未来可通过 `floor_code` 关联但本 Story 不建立 FK。

### H2: 布局模板 cabinet_code 唯一性
**问题**: 自动生成的 cabinet_code 可能与已有机柜冲突。
**修复**: 模板应用时 cabinet_code 格式为 `{room_code}-{row_code}-C{seq:02d}`（含完整空间路径前缀）。应用前检查 cabinet_code 是否已存在，若冲突则跳过并在结果中报告。

### H3: 现有 location/row_number/column_number 字段重叠
**问题**: Cabinet 已有 `location`(str), `row_number`(str), `column_number`(str)，与新增 `row_id`/`grid_x`/`grid_y` 语义重叠。
**修复**: 保留旧字段不动（向后兼容），新字段独立使用。旧字段为自由文本，新字段为结构化空间关系。不做迁移脚本，不做废弃标记。

### H4: API 路由粒度
**修复**: 4 个扁平 CRUD 组（sites/floors/rooms/rows）+ tree 端点。机柜空间字段更新通过 `PUT /spatial/cabinets/{id}/position` 独立端点，不修改现有 `/asset/cabinets/{id}`。

### M1: CSS Grid 性能限制
**修复**: 网格最大尺寸限制为 50×50（2500 格）。前端在 Room 配置中限制 grid_cols/grid_rows 最大值为 50。

### M2: 新模型注册
**修复**: 已在 Task 1.3 中明确要求在 `models/__init__.py` 中导出新模型。

### M3: 事务管理
**修复**: Excel 导入和模板应用使用显式事务管理。整个导入/应用操作在单个事务中完成，任何错误回滚整个操作。使用 `try/except` + `await db.rollback()`。

## Dev Notes

### 后端模式参考

- 异步数据库：`Depends(get_db)` + AsyncSession
- Excel 导入参考：`asset.py` 的 `import_assets` 函数（IMPORT_COLUMN_MAP + openpyxl）
- 路由注册：在 `api/v1/__init__.py` 中 `include_router`
- 权限：Site/Floor/Room/Row 管理用 `require_operator`，查看用 `require_viewer`
- **数据库迁移策略（C1）**: SQLite 不支持 ALTER TABLE ADD FK/Enum。开发环境直接删除 dcim.db 重启重建。不使用 Alembic 迁移。
- **FloorMap vs Floor（H1）**: FloorMap 是地图数据模型，Floor 是空间层级模型，两者独立，不建立 FK 关系。
- **旧字段兼容（H3）**: Cabinet 的 location/row_number/column_number 保留不动，新增 row_id/grid_x/grid_y 独立使用。

### 前端模式参考

- 树形组件：Element Plus `el-tree`
- 拖拽：HTML5 Drag and Drop API（dragstart/dragover/drop）
- 网格布局：CSS Grid，**最大 50×50（M1）**
- ECharts 不需要（纯 DOM 交互）
- 路由添加到 `router/index.ts`

### 架构对齐

- Architecture 3.3: Site→Floor→Room→Row→Cabinet 层级
- Architecture 9.1: 空间拓扑为三合一拓扑的第一维
- Architecture 9.4: 机柜物理位置 = Excel 批量导入 + 可视化拖拽
- Cabinet 扩展字段 `aisle_type`, `cooling_zone_id` 来自 Architecture 3.2

### Project Structure Notes

- 后端新增文件：`models/spatial.py`, `schemas/spatial.py`, `api/v1/spatial.py`, `tests/test_spatial.py`
- 前端新增文件：`views/topology/spatial.vue`, `api/modules/spatial.ts`
- 修改文件：`models/asset.py`(Cabinet 扩展), `schemas/asset.py`(Cabinet schema 扩展), `models/__init__.py`, `api/v1/__init__.py`, `router/index.ts`

### References

- [Source: _bmad-output/planning-artifacts/architecture.md L250-261] — 空间拓扑层级定义
- [Source: _bmad-output/planning-artifacts/architecture.md L651-695] — 机房物理拓扑模型
- [Source: _bmad-output/planning-artifacts/prd.md L812] — FR62
- [Source: _bmad-output/planning-artifacts/epics.md L782-797] — Story 8.1 定义
- [Source: backend/app/models/asset.py L38-55] — 现有 Cabinet 模型
- [Source: backend/app/api/v1/asset.py L505+] — Excel 导入参考

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- 10/10 后端测试通过，前端 build 通过
- 代码审查修复：C1(flush→commit), C2(文件大小限制10MB), C3(float异常处理), H1(网格边界校验), H2(坐标唯一性校验), M1(Blob双重包装), M2(模板竞态IntegrityError)
- 后端新增文件：models/spatial.py, schemas/spatial.py, api/v1/spatial.py, tests/test_spatial.py
- 后端修改文件：models/asset.py, schemas/asset.py, models/__init__.py, api/v1/__init__.py
- 前端新增文件：api/modules/spatial.ts, views/topology/spatial.vue
- 前端修改文件：router/index.ts

### File List

- backend/app/models/spatial.py (新增)
- backend/app/schemas/spatial.py (新增)
- backend/app/api/v1/spatial.py (新增)
- backend/tests/test_spatial.py (新增)
- backend/app/models/asset.py (修改)
- backend/app/schemas/asset.py (修改)
- backend/app/models/__init__.py (修改)
- backend/app/api/v1/__init__.py (修改)
- frontend/src/api/modules/spatial.ts (新增)
- frontend/src/views/topology/spatial.vue (新增)
- frontend/src/router/index.ts (修改)
