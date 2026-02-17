# Story 8.4: 故障影响分析

Status: done

## Story

As a 运维工程师,
I want 在配电设备故障时快速定位受影响的设备,
So that 我可以评估故障影响范围并采取应急措施。

## FR 追溯

- FR66: 配电设备故障时，系统基于拓扑模型自动定位受影响的下游机柜和设备

## Acceptance Criteria

1. Given 配电拓扑已配置
   When 配电柜/PDU 发生故障告警
   Then 系统基于拓扑模型自动定位受影响的下游机柜和设备

2. Given 故障影响分析完成
   When 查看影响报告
   Then 同时检查制冷拓扑，判断受影响区域空调是否同回路

3. Given 故障影响分析完成
   When 查看影响报告
   Then 输出影响报告（设备清单、关联告警、建议操作）

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| 配电拓扑模型 | `backend/app/models/energy.py` | Transformer, DistributionPanel(parent_panel_id 自引用), DistributionCircuit(panel_id FK), PowerDevice(circuit_id FK) |
| PDU 三相接线 | `backend/app/models/topology_config.py` | PowerPhaseMapping(cabinet_id, pdu_device_id, phase, feed_type) |
| 制冷拓扑 | `backend/app/models/topology_config.py` | CoolingZone, CoolingZoneCabinet, CoolingZoneUnit |
| 机柜模型 | `backend/app/models/asset.py` | Cabinet(row_id FK→rows), Asset(cabinet_id FK) |
| 告警模型 | `backend/app/models/alarm.py` | Alarm(point_id, alarm_level, status, alarm_type) |
| 设备模型 | `backend/app/models/device.py` | Device(device_type, device_code, device_name) |
| 拓扑配置 API | `backend/app/api/v1/topology_config.py` | 三相接线 CRUD, 制冷区域 CRUD, 机柜拓扑汇总 |
| 拓扑配置 Schema | `backend/app/schemas/topology_config.py` | PowerPhaseMappingResponse, CoolingZoneResponse 等 |
| 前端拓扑 API | `frontend/src/api/modules/topologyConfig.ts` | 配电/制冷拓扑 API |
| 前端路由 | `frontend/src/router/index.ts` | infrastructure children |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| 故障影响分析 API | 输入故障设备（PDU/配电柜），输出受影响的下游机柜、设备、制冷区域 |
| 故障影响分析 Schema | FaultImpactRequest/Response |
| 故障影响分析前端页面 | 故障影响分析查询页面 + 影响报告展示 |
| 前端 API 函数 | getFaultImpactAnalysis |

## 故障影响分析设计

### 分析流程

```
输入: 故障设备 (device_id 或 panel_id)
  ↓
Step 1: 确定故障源类型
  - PDU 设备 (devices 表, device_type="PDU")
  - 配电柜 (distribution_panels 表)
  ↓
Step 2: 查询配电拓扑下游
  - PDU 故障 → PowerPhaseMapping → 受影响机柜
  - 配电柜故障 → DistributionCircuit → PowerDevice(PDU) → PowerPhaseMapping → 受影响机柜
  - 配电柜故障 → 子配电柜(递归) → 同上
  ↓
Step 3: 查询受影响机柜中的资产
  - Cabinet → Asset (设备清单)
  ↓
Step 4: 查询制冷拓扑交叉影响
  - 受影响机柜 → CoolingZoneCabinet → CoolingZone → CoolingZoneUnit → 空调
  - 判断空调是否与故障设备同配电回路
  ↓
Step 5: 查询关联告警
  - 受影响设备的点位 → 当前活跃告警
  ↓
Step 6: 生成建议操作
  - 基于故障类型和影响范围生成建议
```

### API 设计

- `POST /topology-config/fault-impact-analysis` — 故障影响分析
  - 输入: fault_source_type("pdu" | "panel"), fault_source_id(int)
  - 输出: 影响报告

## Tasks / Subtasks

### 后端

- [ ] Task 1: 新增 Schema (AC: #1, #2, #3)
  - [ ] 1.1 在 `schemas/topology_config.py` 新增 `FaultImpactRequest`: fault_source_type(str: "pdu"/"panel"), fault_source_id(int)
  - [ ] 1.2 新增 `AffectedCabinet`: cabinet_id, cabinet_code, cabinet_name, location, feed_type, phase, asset_count, impact_level("power_loss"/"degraded"), has_redundancy(bool) [审查修复: H4]
  - [ ] 1.3 新增 `AffectedAsset`: asset_id, asset_code, asset_name, asset_type, cabinet_code
  - [ ] 1.4 新增 `CoolingImpact`: zone_id, zone_name, affected_cabinet_count, total_cabinet_count, cooling_units(List), same_power_circuit(bool), power_circuit_data_source("confirmed"/"unknown") [审查修复: C2]
  - [ ] 1.5 新增 `RelatedAlarm`: alarm_id, alarm_no, alarm_level, alarm_message, status, created_at
  - [ ] 1.6 新增 `FaultImpactResponse`: fault_source_type, fault_source_id, fault_source_name, affected_cabinets(List[AffectedCabinet]), affected_assets(List[AffectedAsset]), cooling_impacts(List[CoolingImpact]), related_alarms(List[RelatedAlarm]), suggestions(List[str]), analysis_time(datetime)

- [ ] Task 2: 新增故障影响分析 API (AC: #1, #2, #3)
  - [ ] 2.1 在 `api/v1/topology_config.py` 新增 `POST /topology-config/fault-impact-analysis`
  - [ ] 2.2 权限: require_viewer
  - [ ] 2.3 PDU 故障分析: 查询 PowerPhaseMapping where pdu_device_id → 受影响机柜
  - [ ] 2.4 配电柜故障分析: 递归BFS查子配电柜(parent_panel_id, visited集合防环, 最大深度10) → DistributionCircuit(panel_id) → PowerDevice(circuit_id, monitor_device_id IS NOT NULL) → JOIN Device(device_type="PDU") → PowerPhaseMapping → 受影响机柜 [审查修复: C1, M5]
  - [ ] 2.5 查询受影响机柜中的资产: Asset where cabinet_id in affected_cabinet_ids
  - [ ] 2.6 制冷交叉影响: CoolingZoneCabinet → CoolingZone → CoolingZoneUnit → CoolingUnit.device_id → Device(AC)。同回路判断: Device(AC) ← PowerDevice(HVAC).monitor_device_id → circuit_id → panel_id 是否在故障子树中 [审查修复: C2, M9]
  - [ ] 2.7 关联告警: 通过受影响 PDU device_id → Point(device_id) → Alarm(point_id, status in active/acknowledged) [审查修复: H3]
  - [ ] 2.8 双路供电判断: 对每个受影响机柜检查是否有另一路 PowerPhaseMapping，设置 impact_level 和 has_redundancy [审查修复: H4]
  - [ ] 2.9 建议操作: 基于影响范围生成建议列表

- [ ] Task 3: 后端测试 (AC: all)
  - [ ] 3.1 test_fault_impact_pdu — PDU 故障影响分析
  - [ ] 3.2 test_fault_impact_panel — 配电柜故障影响分析（含子配电柜递归）
  - [ ] 3.3 test_fault_impact_cooling_cross — 制冷交叉影响检查
  - [ ] 3.4 test_fault_impact_no_mapping — 无拓扑映射时返回空结果
  - [ ] 3.5 test_fault_impact_invalid_source — 无效故障源返回 404

### 前端

- [ ] Task 4: 前端 API 扩展 (AC: all)
  - [ ] 4.1 在 `api/modules/topologyConfig.ts` 新增 FaultImpactRequest, AffectedCabinet, AffectedAsset, CoolingImpact, RelatedAlarm, FaultImpactResponse 接口
  - [ ] 4.2 新增 `getFaultImpactAnalysis(data: FaultImpactRequest)` API 函数

- [ ] Task 5: 故障影响分析页面 (AC: #1, #2, #3)
  - [ ] 5.1 新建 `views/topology/fault-impact.vue`
  - [ ] 5.2 顶部: 故障源选择（类型下拉 PDU/配电柜 + 设备选择器）+ "分析"按钮
  - [ ] 5.3 影响概览卡片: 受影响机柜数、受影响设备数、受影响制冷区域数、关联告警数
  - [ ] 5.4 受影响机柜表格: cabinet_code, cabinet_name, location, feed_type, phase, asset_count
  - [ ] 5.5 受影响设备表格: asset_code, asset_name, asset_type, cabinet_code
  - [ ] 5.6 制冷交叉影响: 制冷区域列表 + 是否同回路标记
  - [ ] 5.7 关联告警列表: alarm_no, alarm_level, alarm_message, status
  - [ ] 5.8 建议操作列表

- [ ] Task 6: 路由注册 (AC: all)
  - [ ] 6.1 在 `router/index.ts` 的 infrastructure children 中添加 `/infrastructure/fault-impact` 路由，菜单名称"故障影响分析"

## 对抗性审查修复

### C1: 配电柜→PDU 链路中 PowerDevice.monitor_device_id 需过滤 Device.device_type="PDU"
**问题**: PowerDevice.monitor_device_id 可指向任何 Device（UPS/空调/PDU），且可能为 NULL。
**修复**: 配电柜故障分析时，join 查询必须过滤 `Device.device_type == "PDU"` 且 `PowerDevice.monitor_device_id IS NOT NULL`。

### C2: 空调同配电回路判断——简化为"尽力而为"
**问题**: AC2 要求判断空调是否与故障设备同配电回路，但空调供电回路需要 PowerDevice(HVAC).monitor_device_id→Device(AC) 反向查询，数据完整性无法保证。
**修复**: 通过 CoolingUnit.device_id→Device(AC)←PowerDevice(HVAC).monitor_device_id→circuit_id→panel_id 链路尝试判断。如果 PowerDevice 中无 HVAC 记录或无 monitor_device_id 映射，same_power_circuit 返回 False 并标注 data_source="unknown"。

### H3: Cabinet→Alarm 无直接 FK
**问题**: Device 和 Cabinet 之间没有直接 FK，无法从受影响机柜直接查告警。
**修复**: 通过 PowerPhaseMapping 找到受影响的 PDU device_id → Point(device_id) → Alarm(point_id) 查询关联告警。同时查询所有受影响 PowerDevice.monitor_device_id 对应的 Device 下的 Point→Alarm。

### H4: 双路供电需区分影响级别
**问题**: 机柜有 primary/backup 双路供电，PDU 故障时应区分完全断电 vs 降级运行。
**修复**: AffectedCabinet 新增 impact_level 字段（"power_loss"/"degraded"）和 has_redundancy(bool)。查询时检查该机柜是否有另一路 PowerPhaseMapping 记录。

### H7: UniqueConstraint 确认
**问题**: 每机柜每路仅一个 PDU 是否符合业务。
**修复**: 确认符合当前业务模型（每机柜 primary 一个 PDU + backup 一个 PDU）。不修改约束。

### M5: 递归深度限制
**问题**: 配电柜递归查询需防环和限深。
**修复**: 使用 Python BFS + visited 集合防环 + 最大深度 10 层限制。

### M6: 边界条件
**修复**: fault_source_id 不存在→404；无拓扑映射→200+空列表；空结果正常返回。

### M8: panel 的 fault_source_id 明确
**修复**: API 文档明确 fault_source_type="pdu" 时 id 对应 devices.id，fault_source_type="panel" 时 id 对应 distribution_panels.id。

### M9: CoolingZoneUnit 三跳关系
**修复**: 设计中明确 CoolingZoneUnit.cooling_unit_id→CoolingUnit.id→CoolingUnit.device_id→Device.id 三跳查询。

## Dev Notes

### 后端模式参考

- 异步数据库：`Depends(get_db)` + AsyncSession
- 权限：require_viewer（只读分析）
- 新 API 放在 topology_config.py 中（依赖拓扑数据）
- 配电柜递归查询：DistributionPanel.parent_panel_id 自引用，需递归查询所有子配电柜
- PowerDevice 关联 Device: PowerDevice.device_id FK→devices.id，PDU 在 devices 表中 device_type="PDU"
- `value or fallback` 陷阱: 用 `if value is not None` 判断

### 配电拓扑链路

```
Transformer → DistributionPanel(transformer_id) → DistributionCircuit(panel_id) → PowerDevice(circuit_id, device_id→devices)
                    ↓ (parent_panel_id 自引用)
              子 DistributionPanel → ...

PDU(devices 表, device_type="PDU") → PowerPhaseMapping(pdu_device_id) → Cabinet
```

### 前端模式参考

- 2.5D 样式: `@use '@/styles/mixins-25d' as *` + `@include page-dashboard(N)`
- 自动导入: Vue/Pinia API 无需手动 import
- 路由: infrastructure children

### 架构对齐

- Architecture 9.5: 故障影响分析 — 配电柜跳闸→查询配电拓扑→定位受影响回路→PDU→机柜→设备→查询制冷拓扑→输出影响报告
- FR66: 配电设备故障时快速定位受影响设备

### Project Structure Notes

- 后端修改: `schemas/topology_config.py`（新增 Schema）, `api/v1/topology_config.py`（新增 API）
- 后端新增: `tests/test_fault_impact.py`
- 前端修改: `api/modules/topologyConfig.ts`（新增类型+函数）, `router/index.ts`（新增路由）
- 前端新增: `views/topology/fault-impact.vue`

## Dev Agent Record

### Agent Model Used
claude-opus-4-6 (Sisyphus orchestrator + 2 parallel Sisyphus-Junior agents)

### Debug Log References
- 后端 agent session: ses_39614512fffeYSMDhkSBcYyzbT
- 前端 agent session: ses_396136791ffe84Ya05wnLGNAkH

### Completion Notes List
- 后端: 6 个 Schema + 1 个 API 端点 (POST /fault-impact-analysis)，5 个测试全部通过
- 前端: 7 个 TypeScript 接口 + 1 个 API 函数 + 1 个完整页面 + 1 条路由
- 代码审查修复: 前端 impact_level 列显示逻辑 — 后端返回 "power_loss"/"degraded" 而非中文，已修正 el-tag 判断和显示文本
- 对抗性审查 9 项修复全部落实: C1(PDU类型过滤), C2(制冷同回路尽力判断), H3(告警通过Point链路), H4(双路供电降级判断), M5(BFS防环+深度限制)

### File List
- backend/app/schemas/topology_config.py (修改: +64行 Schema)
- backend/app/api/v1/topology_config.py (修改: +349行 API 端点)
- backend/tests/test_fault_impact.py (新增: 256行 5个测试)
- frontend/src/api/modules/topologyConfig.ts (修改: +73行 类型+函数)
- frontend/src/views/topology/fault-impact.vue (新增: 456行 页面)
- frontend/src/router/index.ts (修改: +5行 路由)
