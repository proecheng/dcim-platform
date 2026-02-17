# Story 8.2: 配电与制冷拓扑配置

Status: ready-for-dev

## Story

As a 集成工程师,
I want 配置 PDU 三相接线关系和空调覆盖范围,
So that 系统可以建立完整的配电和制冷拓扑。

## FR 追溯

- FR63: 集成工程师可以配置 PDU 三相接线关系（每个机柜接哪个 PDU 的哪一相）
- FR64: 集成工程师可以配置空调覆盖范围（每台空调服务哪些机柜/冷通道）

## Acceptance Criteria

1. Given 集成工程师在拓扑配置页面
   When 配置配电拓扑
   Then 可设置每个机柜接哪个 PDU 的哪一相（A/B/C）
   And 支持双路供电（A路+B路 PDU）

2. Given 集成工程师在拓扑配置页面
   When 配置制冷拓扑
   Then 可配置空调覆盖范围（每台空调服务哪些机柜/冷通道分组）
   And 可设置制冷区域的设计制冷容量

3. Given 配电拓扑已配置
   When 查看三相不平衡度
   Then 系统自动计算：(max(Ia,Ib,Ic) - min(Ia,Ib,Ic)) / avg(Ia,Ib,Ic) × 100%
   And 以仪表盘形式展示每个 PDU 的三相负载分布

4. Given Cabinet 已配置空间拓扑（Story 8-1）
   When 配置配电和制冷拓扑
   Then Cabinet 作为三个拓扑的交汇点，可同时查看空间/配电/制冷归属

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| 配电拓扑模型 | `backend/app/models/energy.py` | Transformer, MeterPoint, DistributionPanel, DistributionCircuit, PowerDevice — 完整配电层级 |
| 配电拓扑 API | `backend/app/api/v1/topology.py` | POST/PUT/DELETE /topology/nodes, /batch, /connections — 节点 CRUD + 连接管理 |
| 配电拓扑 Schema | `backend/app/schemas/energy.py` | TopologyNodeCreate/Update/Delete, TopologyNodeType, TopologyBatchOperation |
| 制冷模型 | `backend/app/models/cooling.py` | CoolingGroup(群控组), CoolingUnit(精密空调, device_id FK, cooling_capacity_kw, group_id FK), ColdAisle(冷通道, device_id FK, aisle_code) |
| 空间拓扑 | `backend/app/models/spatial.py` | Site, Floor, Room, Row — Story 8-1 已完成 |
| Cabinet 模型 | `backend/app/models/asset.py` L38-62 | row_id(FK→rows), aisle_type, grid_x, grid_y — Story 8-1 已扩展 |
| 前端拓扑页面 | `frontend/src/views/energy/topology.vue` | 配电拓扑树形编辑 |
| 前端空间拓扑 | `frontend/src/views/topology/spatial.vue` | 空间拓扑配置 — Story 8-1 已完成 |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| PowerPhaseMapping 模型 | 机柜→PDU 三相接线映射表（cabinet_id, pdu_device_id(FK→devices), phase, feed_type A路/B路）。注意: PDU 在 devices 表中（device_type="PDU"），不在 power_devices 表 |
| CoolingZone 模型 | 制冷区域表（zone_name, room_id, design_capacity_kw, 关联空调列表+机柜列表） |
| CoolingZoneCabinet 关联表 | 制冷区域与机柜的多对多关联 |
| CoolingZoneUnit 关联表 | 制冷区域与空调的多对多关联 |
| 三相不平衡度计算 API | 基于 PowerPhaseMapping 计算每个 PDU 的三相负载分布 |
| 配电拓扑配置前端 | PDU 三相接线配置表单页面 |
| 制冷拓扑配置前端 | 制冷区域管理 + 空调/机柜关联配置页面 |
| 三合一拓扑汇总视图 | Cabinet 维度查看空间+配电+制冷三维归属 |

## Tasks / Subtasks

### 后端

- [ ] Task 1: 新增 PowerPhaseMapping 模型 (AC: #1) [审查修复: C-1, H-1, H-5]
  - [ ] 1.1 在 `models/topology_config.py` 新建模型文件
  - [ ] 1.2 PowerPhaseMapping: cabinet_id(FK→cabinets, ondelete=CASCADE), pdu_device_id(FK→devices.id, ondelete=CASCADE), phase(String: A/B/C), feed_type(String: primary/backup), rated_current(Float), description(Text)。**注意: PDU 在 devices 表中（device_type="PDU"），不在 power_devices 表**
  - [ ] 1.3 UniqueConstraint(cabinet_id, feed_type) — 每个机柜每路供电只能接一个 PDU 相位
  - [ ] 1.4 在 `models/__init__.py` 注册新模型

- [ ] Task 2: 新增 CoolingZone + 关联模型 (AC: #2) [审查修复: C-3, H-1, M-1]
  - [ ] 2.1 CoolingZone: zone_code(unique, 自动生成格式 CZ-{seq:03d}), zone_name, room_id(FK→rooms, nullable), design_capacity_kw(Float), description。**CoolingZone 与 CoolingGroup 的区别: CoolingGroup=空调控制策略分组（群控联动），CoolingZone=制冷拓扑区域（空间覆盖范围，用于容量规划），两者独立**
  - [ ] 2.2 CoolingZoneCabinet: zone_id(FK, ondelete=CASCADE), cabinet_id(FK→cabinets, ondelete=CASCADE), UniqueConstraint(zone_id, cabinet_id)
  - [ ] 2.3 CoolingZoneUnit: zone_id(FK, ondelete=CASCADE), cooling_unit_id(FK→cooling_units, ondelete=CASCADE), UniqueConstraint(zone_id, cooling_unit_id)
  - [ ] 2.4 在 `models/__init__.py` 注册新模型

- [ ] Task 3: 新增 Schemas (AC: #1, #2) [审查修复: H-3]
  - [ ] 3.1 在 `schemas/topology_config.py` 新建 schema 文件
  - [ ] 3.2 PowerPhaseMappingCreate/Update/Response — Response 含 pdu_device_name, pdu_device_code(响应时 join devices 表获取)
  - [ ] 3.3 CoolingZoneCreate(含 cabinet_ids, cooling_unit_ids 列表)/Update/Response — **Response 必须包含 cabinets: List[{id, cabinet_code, cabinet_name}] 和 cooling_units: List[{id, device_code, device_name, cooling_capacity_kw}]**，而非仅 ID 列表。查询时需 join cooling_units→devices 获取设备名称
  - [ ] 3.4 PhaseBalanceResponse — PDU 三相负载分布(phase_a_power, phase_b_power, phase_c_power) + 不平衡度(imbalance_rate) + data_source(标注"estimated"或"measured")
  - [ ] 3.5 CabinetTopologySummary — 机柜三合一拓扑汇总（空间+配电+制冷）

- [ ] Task 4: 新增配电拓扑配置 API (AC: #1, #3) [审查修复: C-1, C-2, H-4, H-5]
  - [ ] 4.1 在 `api/v1/topology_config.py` 新建路由文件。**权限: GET 用 require_viewer，POST/PUT 用 require_operator，DELETE 用 require_admin**
  - [ ] 4.2 GET /topology-config/power-phase — 获取所有 PDU 三相接线映射（可选 pdu_device_id 过滤）
  - [ ] 4.3 GET /topology-config/power-phase/cabinet/{cabinet_id} — 获取机柜的 PDU 接线
  - [ ] 4.4 POST /topology-config/power-phase — 创建机柜 PDU 接线。**API 层校验 pdu_device_id 对应的 device.device_type == "PDU"**
  - [ ] 4.5 PUT /topology-config/power-phase/{id} — 更新接线映射
  - [ ] 4.6 DELETE /topology-config/power-phase/{id} — 删除接线映射
  - [ ] 4.7 GET /topology-config/power-phase/pdu/{pdu_device_id}/balance — 获取 PDU 三相不平衡度
  - [ ] 4.8 三相不平衡度计算策略: 基于 PowerPhaseMapping 按 phase 分组，汇总每相关联机柜的 max_power（额定功率）作为估算值。**除零保护: 当 avg==0 时返回 imbalance_rate=null, data_source="no_data"。当只有 1-2 相有数据时，缺失相视为 0 参与计算。响应中标注 data_source="estimated"**

- [ ] Task 5: 新增制冷拓扑配置 API (AC: #2) [审查修复: H-3, H-4]
  - [ ] 5.1 GET /topology-config/cooling-zones — 获取所有制冷区域（含关联机柜和空调列表，**空调查询需 join cooling_units→devices 获取设备名称**）
  - [ ] 5.2 GET /topology-config/cooling-zones/{id} — 获取单个制冷区域详情
  - [ ] 5.3 POST /topology-config/cooling-zones — 创建制冷区域（zone_code 自动生成 CZ-{seq:03d}）
  - [ ] 5.4 PUT /topology-config/cooling-zones/{id} — 更新制冷区域（含关联关系：先删旧关联再插新关联）
  - [ ] 5.5 DELETE /topology-config/cooling-zones/{id} — 删除制冷区域（级联删除关联，由 ondelete=CASCADE 处理）
  - [ ] 5.6 GET /topology-config/cooling-zones/{id}/capacity — 获取制冷区域容量使用情况

- [ ] Task 6: 三合一拓扑汇总 API (AC: #4)
  - [ ] 6.1 GET /topology-config/cabinet/{cabinet_id}/topology-summary — 返回机柜的空间归属(Site→Floor→Room→Row) + 配电归属(PDU+相位) + 制冷归属(CoolingZone)

- [ ] Task 7: 注册路由 (AC: all)
  - [ ] 7.1 在 `api/v1/__init__.py` 注册 topology_config router，prefix="/topology-config"

- [ ] Task 8: 后端测试 (AC: all) [审查修复: M-2, H-1]
  - [ ] 8.1 test_power_phase_mapping_crud — 创建/查询/删除 PDU 接线，**验证 pdu_device_id 必须是 device_type=PDU 的设备**
  - [ ] 8.2 test_power_phase_unique_constraint — 同一机柜同一路不能重复
  - [ ] 8.3 test_phase_balance_normal — 三相均有数据时计算正确性
  - [ ] 8.4 test_phase_balance_edge_cases — 单相有数据（除零保护）、全部无数据（返回 null）、三相完全均衡（不平衡度=0）
  - [ ] 8.5 test_cooling_zone_crud — 制冷区域 CRUD + 关联管理
  - [ ] 8.6 test_cooling_zone_capacity — 制冷容量使用情况
  - [ ] 8.7 test_cabinet_topology_summary — 三合一拓扑汇总
  - [ ] 8.8 test_cascade_delete — 删除制冷区域/PDU设备/机柜时级联删除关联记录

### 前端

- [ ] Task 9: 前端 API 模块 (AC: all) [审查修复: H-2]
  - [ ] 9.1 在 `api/modules/topologyConfig.ts` 新建 API 模块
  - [ ] 9.2 配电拓扑: getPowerPhaseMappings, getPowerPhaseByPdu, createPowerPhaseMapping, updatePowerPhaseMapping, deletePowerPhaseMapping, getPduPhaseBalance。**PDU 列表复用现有 `GET /power/pdus` API（已在 power API 模块中），不新建**
  - [ ] 9.3 制冷拓扑: getCoolingZones, getCoolingZone, createCoolingZone, updateCoolingZone, deleteCoolingZone, getCoolingZoneCapacity
  - [ ] 9.4 汇总: getCabinetTopologySummary

- [ ] Task 10: 配电拓扑配置页面 (AC: #1, #3) [审查修复: H-2]
  - [ ] 10.1 在 `views/topology/power.vue` 新建页面
  - [ ] 10.2 左侧: PDU 设备列表（**复用现有 `GET /power/pdus` API 获取，PDU 在 devices 表中**）
  - [ ] 10.3 右侧: 选中 PDU 后展示三相接线表格（A/B/C 三列，每列显示接入的机柜列表）
  - [ ] 10.4 操作: 添加机柜接线（选择机柜 + 相位 + 供电路径 primary/backup）、编辑、删除接线
  - [ ] 10.5 三相不平衡度仪表盘: ECharts gauge 展示当前 PDU 的三相负载分布和不平衡度百分比

- [ ] Task 11: 制冷拓扑配置页面 (AC: #2)
  - [ ] 11.1 在 `views/topology/cooling.vue` 新建页面
  - [ ] 11.2 制冷区域列表（el-table）: zone_name, room, design_capacity_kw, 关联空调数, 关联机柜数
  - [ ] 11.3 新增/编辑制冷区域对话框: 基本信息 + 关联空调(el-transfer) + 关联机柜(el-transfer)
  - [ ] 11.4 制冷容量使用情况: 设计容量 vs 实际负载的进度条

- [ ] Task 12: 路由注册 (AC: all) [审查修复: M-3]
  - [ ] 12.1 在 `router/index.ts` 添加 /infrastructure/power-topology 和 /infrastructure/cooling-topology 路由。**菜单名称: "PDU 相位配置" 和 "制冷区域配置"，与现有 /energy/topology（"配电拓扑建模"）区分**

## Dev Notes

### 架构约束

- Architecture 3.3: Cabinet 是三个拓扑的交汇点 — `pdu_id + phase → PowerPhaseMapping`, `cooling_zone_id → CoolingZone`
- Architecture 9.1: 三合一拓扑 — 空间(Story 8-1 done) + 配电(本 Story) + 制冷(本 Story)
- Architecture 9.4: PDU 三相接线用表单配置，空调覆盖范围用表单配置（关联机柜列表或冷通道分组）
- 三相不平衡度公式: (max(Ia,Ib,Ic) - min(Ia,Ib,Ic)) / avg(Ia,Ib,Ic) × 100%

### 关键设计决策

1. **PowerPhaseMapping 独立表 vs Cabinet 字段**: 选择独立表，因为一个机柜可能有双路供电（A路+B路），每路接不同 PDU 的不同相位
2. **CoolingZone 多对多关联**: 一个制冷区域可包含多个机柜和多台空调，一个机柜也可能属于多个制冷区域（交叉覆盖），使用关联表实现
3. **三相不平衡度估算模式**: 基于 PowerPhaseMapping 按相位汇总关联机柜的 max_power（额定功率）作为估算值，响应中标注 data_source="estimated"。除零保护: avg==0 时返回 null
4. **PDU 在 devices 表中**: PDU 设备存储在 `devices` 表（device_type="PDU"），不在 `power_devices` 表。PowerPhaseMapping.pdu_device_id FK→devices.id，API 层校验 device_type
5. **复用现有 CoolingUnit**: 空调在系统中已作为 CoolingUnit 存在，不新建空调模型
6. **CoolingZone vs CoolingGroup**: CoolingGroup=空调控制策略分组（群控联动），CoolingZone=制冷拓扑区域（空间覆盖范围，用于容量规划）。两者独立，一台空调可同时属于一个 CoolingGroup 和一个 CoolingZone
7. **所有 FK 添加 ondelete=CASCADE**: PowerPhaseMapping 和 CoolingZone 关联表的所有 FK 都设置级联删除，避免孤儿记录
8. **权限控制**: GET→require_viewer, POST/PUT→require_operator, DELETE→require_admin，参照 cooling.py 模式

### 数据库约束

- SQLite 不支持 ALTER TABLE ADD COLUMN with FK — 需删除 dcim.db 重新初始化
- 所有写端点必须显式调用 `await db.commit()`（deps.get_db 不自动提交）

### Project Structure Notes

- 新增文件: `models/topology_config.py`, `schemas/topology_config.py`, `api/v1/topology_config.py`
- 新增前端: `views/topology/power.vue`, `views/topology/cooling.vue`, `api/modules/topologyConfig.ts`
- 路由前缀: `/topology-config` — 与现有 `/topology`（配电拓扑编辑）区分
- 前端路由: `/infrastructure/power-topology`, `/infrastructure/cooling-topology` — 与 `/infrastructure/spatial`（Story 8-1）同级

### References

- [Source: architecture.md#3.3] 空间拓扑层级 — Cabinet 交汇点定义
- [Source: architecture.md#9.1] 三合一拓扑 — 配电拓扑 Transformer→DistPanel→Circuit→PDU→Phase
- [Source: architecture.md#9.4] 拓扑配置方式 — PDU 三相接线表单配置，空调覆盖范围表单配置
- [Source: prd.md#FR63] PDU 三相接线关系配置
- [Source: prd.md#FR64] 空调覆盖范围配置
- [Source: epics.md#Story 8.2] 配电与制冷拓扑配置 AC 定义

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
