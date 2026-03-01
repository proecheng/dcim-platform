# 测试覆盖分析报告（核心模块 / 引擎 / API / 前端）

## 1. 分析背景与口径

- 当前基线（由你提供）：总测试 1838（排除协议适配器）、Demo 模块新增 12、回归测试 59 通过。
- 本次分析方式：
  - 静态扫描目标源码与测试文件映射（是否有直接测试/仅间接覆盖/无覆盖）。
  - 抽样阅读关键源码与测试内容，判断是否覆盖了**边界条件、错误路径、权限分支、状态机分支**。
- 结论口径：本报告是“测试设计覆盖”分析，不是 line/branch 百分比报表。

---

## 2. 当前覆盖概览（按分析范围）

### 2.1 核心服务模块（backend/app/services）

| 模块 | 当前覆盖状态 | 结论 |
|---|---|---|
| `ingest_pipeline.py` | 存在 `backend/tests/demo/test_ingest_pipeline.py`，但大量副作用被 mock；主要在 demo 路径 | **部分覆盖，核心异常链路与集成链路不足** |
| `point_data.py` | 存在 `backend/tests/test_point_data.py` | **基础覆盖有，去重/断点续传/混合路径边界不足** |
| `datasource_bridge.py` | 存在 `backend/tests/test_realtime_redis.py`（偏 `sync_point_data`） | **覆盖浅，`link_datasource_to_point` 基本缺失** |
| `websocket.py` | 未发现独立服务级测试文件 | **高风险盲区** |

### 2.2 引擎模块（backend/app/engines）

| 模块 | 当前覆盖状态 | 结论 |
|---|---|---|
| `alarm_engine.py` | `backend/tests/test_alarm_engine.py` 覆盖较多阈值/死区/延迟/风暴等 | **覆盖较好** |
| `linkage_engine.py` | 主要通过 API/业务流间接覆盖（如 `test_linkage.py`、`test_fire_protection.py`） | **引擎内部分支覆盖不足** |
| `escalation_engine.py` | `backend/tests/test_escalation.py` 存在 | **主路径覆盖有，复杂升级链与异常分支不足** |
| `diagnosis_engine.py` | `backend/tests/test_diagnosis.py` 存在，包含规则匹配与去重 | **中等偏好，但异步事件与回退路径仍有盲区** |

### 2.3 API 端点（backend/app/api/v1）

- 优点：`auth/alarm/point/threshold/history/statistics/log/datasources/...` 相关测试量很大，权限与基础错误码覆盖广。
- 主要问题：存在较多“状态码即通过”的覆盖模式，复杂业务约束与失败注入覆盖不足。
- 明显缺口：
  - `device_templates.py`：未发现与 `/api/v1/device-templates` 对应的 API 级测试（现有 `test_device_template.py` 更偏模型/数据层）。
  - `ml.py`：未发现 `backend/tests` 下直接 API 覆盖；`__init__.py` 中 `_ml_available` 条件挂载分支未见覆盖。

### 2.4 前端组件与状态（frontend/src）

- Stores：覆盖总体较好（`alarm/app/bigscreen/degradation/energy/realtime/site/user/opportunity` 均有测试）。
- Views：页面级用例数量多，但部分为“测试专用组件/轻交互”风格，和真实复杂组件行为存在偏差。
- 高风险盲区集中在 `components/bigscreen` 复杂 3D 组件：
  - 已有：`BigscreenHistoryDialog.test.ts`（单点覆盖）。
  - 缺口：`ThreeScene.vue`、`DataCenterModel.vue`、`HeatmapOverlay.vue` 等核心渲染/状态联动组件缺乏针对性单测。

---

## 3. 测试盲区清单（按优先级）

> 说明：优先级依据“业务影响 × 回归概率 × 当前覆盖缺失度”。

### P0（必须优先补）

| 模块 | 缺失的测试场景 | 风险评估 |
|---|---|---|
| `backend/app/services/websocket.py` | 心跳 ping 超时清理、断链后广播自动剔除、不同 channel 隔离、`start_heartbeat/stop_heartbeat` 生命周期 | **高**：实时告警/联动推送可靠性直接受影响，线上最易出现“假在线/广播失败积累” |
| `backend/app/services/ingest_pipeline.py` | `_process_batch` 写库失败回滚、`_evaluate_alarms` 异常吞吐、WS/Redis 副作用失败隔离、告警创建与自动恢复同周期行为 | **高**：采集主链路，误回滚或吞异常会导致数据/告警不一致 |
| `backend/app/engines/linkage_engine.py` | `_match_condition` 元字段分支、动作超时与重试、`partial_failure/failed` 状态机、失败告警广播 payload 断言 | **高**：联动执行是自动控制核心，状态机错判会引发误操作或漏告警 |
| `backend/app/api/v1/device_templates.py` | 列表筛选组合、`create-datasource` 点位映射正确性、404/403、非法参数/空模板分支 | **高**：模板与数据源联动配置错误会影响批量接入质量 |

### P1（次高优先）

| 模块 | 缺失的测试场景 | 风险评估 |
|---|---|---|
| `backend/app/services/point_data.py` | `seq` 去重（重复包跳过）、映射点+未映射点混合场景、异常值转换与计数一致性、`site_id` 透传边界 | **中高**：网关重放/乱序容易出现重复处理或计数偏差 |
| `backend/app/services/datasource_bridge.py` | `link_datasource_to_point` 成功/失败分支（DataSourcePoint 不存在、Point 不存在）、并发更新一致性 | **中高**：数据源映射错误导致采集落库路径错误 |
| `backend/app/engines/escalation_engine.py` | 多级升级链（基于 `last_escalated_at`）、多规则叠加顺序、广播失败后数据一致性 | **中**：升级规则复杂时易出现跳级/重复升级 |
| `backend/app/engines/diagnosis_engine.py` | `on_alarm_event` 异步 `create_task` 调度、`_check_history` DB 回退分支、规则冲突去重边界 | **中**：诊断结果准确性和稳定性受影响 |
| `backend/app/api/v1/ml.py` + `api/v1/__init__.py` | `/ml/*` 端点参数错误/500 包装、`_ml_available` true/false 条件路由挂载 | **中**：可选模块在不同部署环境下最易出现行为分叉 |

### P2（优化优先）

| 模块 | 缺失的测试场景 | 风险评估 |
|---|---|---|
| `frontend/src/components/bigscreen/ThreeScene.vue` | provide/inject 依赖是否正确注入、初始化失败兜底 | **中**：3D 场景空白或交互异常 |
| `frontend/src/components/bigscreen/DataCenterModel.vue` | store layout/deviceData watch 联动、`generateDefaultLayout` 生成一致性、卸载清理 | **中**：大屏状态错乱、内存泄漏 |
| `frontend/src/components/bigscreen/HeatmapOverlay.vue` | 热力图显隐、更新频率与数据映射、unmount 清理 | **中**：温度热力图误导值班人员判断 |

---

## 4. 补测建议（可直接落地的测试用例）

## 4.1 后端服务/引擎

1. `websocket.py`
   - 用例 WS-01：`_ping_all` 遇到 `WebSocketState!=CONNECTED` 时剔除连接。
   - 用例 WS-02：`send_json` 超时触发 `disconnect + close`，且不影响其他连接。
   - 用例 WS-03：`broadcast(channel)` 仅向指定通道发送，失败连接自动移除。
   - 用例 WS-04：`start_heartbeat` 重入幂等，`stop_heartbeat` 后任务取消。

2. `ingest_pipeline.py`
   - 用例 IP-01：Phase1 写库抛异常，验证 `rollback` 且 `written=0`。
   - 用例 IP-02：Phase2 告警评估异常，不影响已提交实时数据。
   - 用例 IP-03：Phase3 WS 失败/Redis 失败分别注入，返回成功且主数据一致。
   - 用例 IP-04：同点位“触发 + 自动恢复”完整闭环，验证 Alarm 状态与时长字段。

3. `point_data.py`
   - 用例 PD-01：同 `gw_id+seq` 重复包只处理一次。
   - 用例 PD-02：混合数据（mapped/unmapped/无效值）计数与写入一致。
   - 用例 PD-03：`process_payload` 抛错时，未映射点位写入行为与日志一致。

4. `datasource_bridge.py`
   - 用例 DB-01：`link_datasource_to_point` 成功映射并持久化。
   - 用例 DB-02：`datasource_point_id` 不存在返回 False。
   - 用例 DB-03：`point_id` 不存在返回 False。

5. `linkage_engine.py`
   - 用例 LE-01：`_match_condition` 对 list/标量/元字段（`fire_level`）匹配正确。
   - 用例 LE-02：动作执行超时后按 `retry_count` 重试并写入日志。
   - 用例 LE-03：多动作混合成功失败时状态为 `partial_failure`，并广播失败告警。
   - 用例 LE-04：无动作策略直接 `completed`。

6. `escalation_engine.py` / `diagnosis_engine.py`
   - 用例 EE-01：多级升级链以 `last_escalated_at` 为时间基准。
   - 用例 DE-01：`on_alarm_event` 异步分支调度成功且不会阻塞主流程。
   - 用例 DE-02：历史计数不足时触发 DB 回退查询分支。

## 4.2 API 端点

1. `device_templates.py`
   - 用例 DT-API-01：分页+筛选（manufacturer/model/protocol/keyword）组合断言。
   - 用例 DT-API-02：`/{id}/create-datasource` 复制点位配置（含 enum/is_dry_contact）。
   - 用例 DT-API-03：viewer/operator/admin 权限边界（403/200）。
   - 用例 DT-API-04：模板不存在/非法请求体错误码与错误信息。

2. `ml.py`（可选模块）
   - 用例 ML-API-01：`/ml/status` 正常与 service 异常 500 分支。
   - 用例 ML-API-02：`/ml/analyze/loads` 参数校验 422 分支。
   - 用例 ML-API-03：`api/v1/__init__.py` 中 `_ml_available` 为 False 时路由不注册。

## 4.3 前端（Bigscreen 关键组件）

1. `ThreeScene.vue`
   - 用例 FS-01：初始化成功后 `provide` 注入对象存在且类型正确。
   - 用例 FS-02：初始化失败时 slot 不渲染，组件不抛错。

2. `DataCenterModel.vue`
   - 用例 DM-01：`store.layout` 变化触发模型重建并清理旧 group。
   - 用例 DM-02：`store.deviceData` 变化触发 `updateCabinetStatus`。
   - 用例 DM-03：unmount 后 `scene.remove` 与 `cabinetMap.clear`。

3. `HeatmapOverlay.vue`
   - 用例 HM-01：`layers.heatmap` 开关控制 mesh 显隐。
   - 用例 HM-02：设备温度映射到热力图更新函数参数正确。
   - 用例 HM-03：unmount 清理 mesh，避免重复挂载泄漏。

---

## 5. 质量评估结论

- **优势**：测试总量充足，API 权限与状态码覆盖面广，`alarm_engine` 与多数 store 基础行为覆盖较好。
- **主要盲区**：
  - “高复杂内部逻辑模块”缺少独立单测（`websocket/linkage_engine/ingest_pipeline`）。
  - “可选能力与条件分支”缺少环境差异测试（`ml` 路由条件挂载）。
  - 前端大屏复杂 3D 组件覆盖明显低于普通业务组件。
- **质量风险画像**：目前更像“广覆盖 + 部分浅断言”，在复杂回归（异常链路/异步状态机/边界输入）上仍有失败窗口。

---

## 6. 工作量预估（补测计划）

> 估算单位：人日（1 人日约 6~7 小时有效开发+联调）。

| 优先级 | 范围 | 预估新增用例 | 预估人日 |
|---|---|---:|---:|
| P0 | `websocket + ingest_pipeline + linkage_engine + device_templates API` | 24~32 | 6~8 |
| P1 | `point_data + datasource_bridge + escalation/diagnosis 增强 + ml API` | 18~24 | 4~6 |
| P2 | 前端 bigscreen 关键组件 | 10~14 | 2~3 |
| **合计** |  | **52~70** | **12~17** |

### 推荐排期

1. **第 1 周**：先完成 P0（保障主链路与实时告警可靠性）。
2. **第 2 周前半**：完成 P1（补齐异步/条件分支）。
3. **第 2 周后半**：完成 P2 + 回归（前端大屏稳定性）。

---

## 7. 最终建议（执行顺序）

1. 先补 `websocket.py` 与 `ingest_pipeline.py`，这两处是运行时风险最高点。
2. 同步补 `linkage_engine.py` 内部状态机测试，防止“联动执行结果与告警展示不一致”。
3. API 侧优先补 `device_templates.py` 与 `ml.py`，避免模块上线后出现“有路由无测试”盲区。
4. 前端优先补 `ThreeScene/DataCenterModel/HeatmapOverlay`，将大屏风险从“集成后发现”前移到单测阶段。
