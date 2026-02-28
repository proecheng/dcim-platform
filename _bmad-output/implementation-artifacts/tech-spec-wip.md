---
title: '模拟系统解耦重构 — 演示数据插件化与真实算力中心建模'
slug: 'demo-system-decoupling'
created: '2026-02-27'
status: 'approved'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.9+/FastAPI/SQLAlchemy 2.0 async/Pydantic', 'Vue 3/TypeScript/Element Plus/Vite', 'pytest/pytest-asyncio(auto mode)/httpx AsyncClient', 'SQLite+aiosqlite/Redis/MQTT(aiomqtt)']
files_to_modify: ['backend/app/main.py', 'backend/app/core/config.py', 'backend/app/api/v1/__init__.py', 'backend/app/api/v1/monitoring.py', 'backend/app/api/v1/demand.py', 'backend/app/api/v1/optimization.py', 'backend/app/services/demand_analysis_service.py', 'backend/app/services/energy_analysis.py', 'backend/app/services/analysis_plugins/manager.py', 'backend/app/services/feedback_learning.py', 'backend/app/services/effect_monitoring_service.py', 'backend/app/services/datasource_bridge.py', 'backend/app/mqtt/client.py', 'frontend/src/components/DemoDataLoader.vue', 'frontend/src/views/dashboard/index.vue']
code_patterns: ['FastAPI lifespan async context manager', 'SQLAlchemy 2.0 async session with select()', 'Pydantic BaseModel for request/response', 'Singleton service pattern (module-level instance)', 'Background task via asyncio.create_task', 'Redis cache with TTL for point data', 'WebSocket broadcast via ConnectionManager']
test_patterns: ['pytest + pytest-asyncio auto mode', 'In-memory SQLite with savepoint rollback', 'httpx AsyncClient with ASGITransport', 'Class-based test grouping for API tests', 'unittest.mock.patch + AsyncMock for service mocking', 'Shared fixtures in single root conftest.py']
---

# Tech-Spec: 模拟系统解耦重构 — 演示数据插件化与真实算力中心建模

**Created:** 2026-02-27

## Overview

### Problem Statement

当前 DCIM 系统的模拟/演示数据深度耦合在核心代码中，存在以下问题：

1. **6 层耦合**：模拟器引擎（simulator.py）硬编码在 main.py 启动流程中；12+ 处 `simulation_enabled` 分支散布在 6+ 个业务服务中；8 个业务服务内嵌 `_generate_mock_*` 方法；种子脚本（power_seed/cooling_seed）无条件执行
2. **数据注入路径不一致**：模拟器直写 PointRealtime 表，绕过了真实采集链路（Gateway → MQTT → handle_point_data → PointDataLatest → datasource_bridge → PointRealtime），导致模拟数据与真实数据格式/流程不一致
3. **无法干净卸载**：当前 unload 覆盖 42 张表但遗漏 22+ 张表（种子设备、VPP 数据、能源模型表、Redis 缓存），卸载后系统残留大量孤儿数据
4. **演示数据不够真实**：现有模拟器仅生成简单的随机波动数据，缺乏真实算力中心的完整设备体系、配电拓扑、制冷层级和环境监控布局

### Solution

将模拟系统重构为完全独立的"演示数据插件"，实现：

1. **虚拟 Gateway 模式**：创建虚拟 Gateway + DataSource，模拟数据通过真实采集管道（MQTT payload → handle_point_data → PointDataLatest → datasource_bridge → PointRealtime → WebSocket）注入，确保数据格式与真实采集完全一致
2. **完全解耦**：所有演示相关代码抽离到独立模块 `backend/app/demo/`，main.py 通过条件导入加载，业务服务零 mock 依赖
3. **真实算力中心建模**：设计一套逼真的 4 层楼、约 200 机架的中型算力中心演示数据模型，包含完整的配电链路（高压进线 → 变压器 → 低压配电柜 → UPS → 列头柜 → 机架 PDU）、制冷系统（冷水机组 → 水泵 → 精密空调 → 冷通道）、环境监控、消防安防等全部子系统
4. **一键卸载归零**：提供单一 API 接口，清理所有演示数据（含种子设备、VPP 数据、能源表、Redis 缓存），卸载后系统为完全空白的 DCIM（仅保留 admin 账户、RBAC、系统配置）

### Scope

**In Scope:**

- 模拟器引擎重构：虚拟 Gateway 模式，走真实采集链路
- 统一入库管道：新建 ingest_pipeline.process_payload()，MQTT 和 DemoEngine 共用，修复管道断裂
- 4 层楼算力中心完整数据模型设计（设备、点位、配电拓扑、制冷层级、环境传感器）
- main.py 启动流程解耦：条件导入，非侵入式加载
- 业务服务 mock 方法清理：8 个文件中的 mock 回退全部移除
- what-if 分析功能保留为正式业务功能，移除 simulation_enabled 依赖
- 卸载 API 扩展：补齐 22+ 张遗漏表 + Redis 缓存清理
- 前端 DemoDataLoader 组件适配
- 种子脚本（power_seed / cooling_seed）纳入演示模块
- 演示数据生成器：基于真实算力中心模型生成逼真的模拟数据

**Out of Scope:**

- 真实采集网关硬件对接
- 前端 UI 大改版
- 数据库 schema 变更（仅清理数据，不改表结构）
- 系统默认数据（admin 账户、RBAC 权限、系统配置、数据字典）— 卸载后保留
- Device 模型的 device_type 枚举扩展（使用现有枚举映射）

## Context for Development

### 4 层楼算力中心数据模型

#### 楼层布局

| 楼层 | 功能定位 | 主要房间 |
|------|---------|---------|
| 1F | 动力核心层 | 高压配电室、变压器室、低压配电室、UPS 室、电池室、柴油发电机房、消防钢瓶间 |
| 2F | IT 生产层 A | 机房大厅 A（~100 架）、列头柜区、弱电间、网络配线区 |
| 3F | IT 生产层 B | 机房大厅 B（~100 架）、列头柜区、弱电间、备件间 |
| 4F | 冷站+运维层 | 冷水机组机房、泵房、冷却塔控制室、NOC 监控中心、办公区 |

#### 供配电系统（A/B 双路冗余）

```
10kV 双路市电进线 (2路)
  → 高压开关柜 (6面)
    → 干式变压器 (2 x 1600kVA)
      → 低压配电柜/MDB (8面)
        → UPS A/B (4 x 300kVA 模块化)
          → UPS 输出配电柜 (4面)
            → 列头柜/RPP (20台, 每排 A/B)
              → 机架 PDU (400条, 每架 A+B)
        → 精密空调配电
        → 照明/动力配电
  → 柴油发电机 (2 x 1600kVA, N+1)
```

#### 制冷系统

```
冷水机组 (3 x 200RT, N+1)
  → 冷冻水泵 (4台, N+1, 变频)
    → 精密空调/CRAH (24台, 2F/3F 各12台)
      → 冷通道封闭 (10条通道)
冷却水泵 (4台, N+1, 变频)
  → 冷却塔 (3台, N+1)
```

#### 环境与安防

- 温湿度传感器：每机房 8-12 个点（冷/热通道各布点）
- 漏水检测：机房地板下绳式漏水 + 空调下方点式漏水
- 烟感探测器：每房间 2-4 个
- 门禁：每房间入口
- 摄像头：机房走廊 + 配电室 + 出入口

#### 设备数量汇总

| 设备类型 | 数量 | 每台采集点数 | 总点位数 |
|---------|------|------------|---------|
| 高压开关柜 | 6 | 8 | 48 |
| 变压器 | 2 | 10 | 20 |
| 低压配电柜 | 8 | 12 | 96 |
| UPS | 4 | 18 | 72 |
| 电池组 | 8 | 8 | 64 |
| 柴油发电机 | 2 | 12 | 24 |
| 列头柜/RPP | 20 | 14 | 280 |
| 机架 PDU | 400 | 4 | 1600 |
| 冷水机组 | 3 | 9 | 27 |
| 冷冻水泵 | 4 | 7 | 28 |
| 冷却水泵 | 4 | 7 | 28 |
| 冷却塔 | 3 | 7 | 21 |
| 精密空调 | 24 | 8 | 192 |
| 冷通道温度 | 10 | 7 | 70 |
| 温湿度传感器 | 40 | 3 | 120 |
| 漏水检测 | 30 | 2 | 60 |
| 烟感探测器 | 40 | 1 | 40 |
| 门禁 | 20 | 2 | 40 |
| **合计** | **~628** | — | **~2,830** |

### Codebase Patterns

- **服务单例模式**：业务服务在模块底部创建全局实例（如 `demo_data_service = DemoDataService()`），通过 import 使用
- **FastAPI lifespan**：`main.py` 使用 `@asynccontextmanager` 管理启动/关闭生命周期，所有后台任务在此创建和取消
- **异步数据库**：SQLAlchemy 2.0 async 模式，`async_session()` 上下文管理器，`select()` 查询风格
- **Redis 缓存**：点位实时数据缓存在 `point:{id}:latest`，TTL 60s，设备在线状态 `device:{id}:online`
- **WebSocket 广播**：`ws_manager` 单例管理多通道（realtime/alarms/control/system/linkage），`broadcast_realtime()` 推送点位数据
- **告警引擎**：内存阈值缓存 + 风暴保护（60s 窗口）+ 死区/延迟逻辑 + 批量告警检测
- **配置单例**：`@lru_cache()` 的 `get_settings()` 确保配置唯一

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `backend/app/main.py` | 应用入口，lifespan 生命周期管理。[DEMO] 行：20-22(imports), 219-220(seed), 262(simulator task), 396(print), 415-416(shutdown) |
| `backend/app/services/simulator.py` | 当前模拟器引擎，DataSimulator 单例(L445)，内部 simulation_enabled 守卫(L408) |
| `backend/app/services/demo_data_service.py` | 演示数据加载/卸载服务(1479行)，7阶段加载，42表清理 |
| `backend/app/services/demo_data_provider.py` | 确定性假数据提供者(sin波)，5个方法，仅被 monitoring.py 使用 |
| `backend/app/services/power_seed.py` | UPS/PDU/电池柜种子数据，无 simulation_enabled 守卫 |
| `backend/app/services/cooling_seed.py` | 精密空调/冷通道种子数据，无 simulation_enabled 守卫 |
| `backend/app/api/v1/demo.py` | 演示数据 REST API：status/load/progress/unload/refresh-dates |
| `backend/app/api/v1/monitoring.py` | 5处 simulation_enabled 检查 + /dispatch/simulation 端点(L690-715) |
| `backend/app/api/v1/demand.py` | 3处调用 mock 生成器(L161, L319, L424) |
| `backend/app/api/v1/optimization.py` | 2处调用 generate_sample_history(L406-408, L478-480) |
| `backend/app/services/demand_analysis_service.py` | 3个静态 mock 方法(L564-682) |
| `backend/app/services/energy_analysis.py` | _generate_mock_analysis(L192-262) + 内联 mock 回退 |
| `backend/app/services/analysis_plugins/manager.py` | 5个 _generate_mock_* 方法(L239-611) |
| `backend/app/services/feedback_learning.py` | _generate_mock_execution_data(L288-342) + generate_sample_history(L399-457) |
| `backend/app/services/effect_monitoring_service.py` | 2处 simulation_enabled 分支(L113-136, L237-247) |
| `backend/app/services/ingest_pipeline.py` | **新建** 统一入库编排函数 process_payload()，MQTT + DemoEngine 共用入口 |
| `backend/app/mqtt/client.py` | MQTT 订阅 dcim/{site_id}/gw/{gw_id}/data，路由到 handle_point_data |
| `backend/app/services/point_data.py` | handle_point_data()：MQTT 数据入库 PointDataLatest + Redis |
| `backend/app/services/datasource_bridge.py` | sync_point_data()：桥接 PointDataLatest → PointRealtime + Redis |
| `backend/app/services/websocket.py` | ConnectionManager 单例，broadcast_realtime() 推送前端 |
| `backend/app/engines/alarm_engine.py` | alarm_engine.evaluate()：内存阈值检查，返回 EvaluateResult |
| `backend/app/tools/demo_data_generator.py` | 独立 CLI 工具，直接 SQLite 写入（遗留） |
| `backend/app/tools/realtime_simulator.py` | 独立 CLI 实时模拟器（遗留） |
| `backend/app/services/collector.py` | 遗留 DataCollector（已被 simulator.py 取代） |
| `frontend/src/components/DemoDataLoader.vue` | 演示数据加载/卸载 UI 组件(365行) |
| `frontend/src/api/modules/demo.ts` | 前端 demo API 模块，5个函数 |
| `frontend/src/views/dashboard/index.vue` | 挂载 DemoDataLoader(L216)，按钮触发(L60) |

### Technical Decisions

1. **统一入库管道（非混合串调）**：深度调查发现当前系统存在**管道断裂**问题 — MQTT 管道只写 PointDataLatest，模拟器管道直写 PointRealtime。Oracle 审查建议：不应串调四个独立 service，而应新建统一入库编排函数 `ingest_pipeline.process_payload()`，内部完成：最新值落库(PointDataLatest) → 实时值同步(PointRealtime) → 告警判定/落库(alarm_engine) → WebSocket 推送(ws_manager)。MQTT 消费端和 DemoEngine 共用此唯一入口，彻底消除双路径分叉。批量处理：每批 100-300 点位、单事务单次 commit，禁止逐点 commit（当前 sync_point_data 的逐点 commit 需改掉）。WebSocket 采用批量帧或节流广播（每批/每秒一次），不逐条推送 2830 点。
2. **演示模块完全独立**：所有演示代码放在 `backend/app/demo/` 下，main.py 通过 `if settings.demo_enabled` 条件导入。配置项从 `simulation_enabled` 重命名为 `demo_enabled` 以明确语义。
3. **卸载即归零（前缀过滤，非 FLUSHDB）**：卸载 API 清理所有演示创建的数据（64+ 张表）。Redis 采用前缀删除（`point:*` / `device:*`）而非 FLUSHDB，避免误清非 demo 缓存/会话。补充 Oracle 发现的遗漏表：`point_data_latest`、`gateway_events`、`capacity_histories`、`capacity_plans`、`linkage_actions`、`linkage_executions`、`linkage_logs`、`linkage_recoveries`、`linkage_recovery_logs`。卸载按 demo_site_id + gateway_id 前缀做范围过滤，避免误删真实数据。
4. **what-if 功能正式化**：simulation_service.py(纯 DB 驱动)、load_regulation.py(纯 CRUD)、device_control_service.py(SIMULATED 是合法接口模式) 保留为正式业务功能，零改动。feedback_learning.py 和 effect_monitoring_service.py 需移除 simulation_enabled 分支，改为从 PointRealtime 查询真实数据。
5. **业务服务无 mock 回退**：12 个 mock 方法/分支全部删除，无数据时返回空结果或零值结构体。
6. **遗留代码清理**：`tools/demo_data_generator.py`、`tools/realtime_simulator.py`、`services/collector.py` 标记为遗留，在本次重构中移除或归档。
7. **is_demo_data 字段保留**：Pydantic 模型中的 `is_demo_data` 字段保留但硬编码为 `False`，避免前端 breaking change。后续版本可移除。
8. **设备类型粗分类映射**：现有 Device.device_type 枚举（UPS/AC/PDU/TH/DOOR/SMOKE/WATER）不做 schema 变更。新设备类型映射为：高压开关柜/变压器/低压配电柜/列头柜 → `PDU`，电池组/柴油发电机 → `UPS`，冷水机组/水泵/冷却塔 → `AC`，冷通道 → `TH`。具体设备名称写入 `device_code` / `model` / `description` 字段区分。这样最大化复用现有 API 按类型过滤逻辑。
9. **告警引擎补全**：`alarm_engine.evaluate()` 只返回 EvaluateResult，不负责落库与广播。统一入库管道中需补全告警落库（创建/解除 Alarm 记录）+ WebSocket 告警推送 + 事件总线发布（参考现模拟器 simulator.py:131 的逻辑）。

## Implementation Plan

### Tasks

#### Phase 1: 核心解耦（无功能变更，纯代码分离）

**Task 1.1: 创建演示模块骨架**
- 创建 `backend/app/demo/__init__.py`
- 创建 `backend/app/demo/config.py` — 演示模块配置（demo_enabled 开关）
- 创建 `backend/app/demo/router.py` — 演示数据 API 路由（从 api/v1/demo.py 迁移）
- 创建 `backend/app/demo/service.py` — 演示数据服务（从 demo_data_service.py 迁移）
- 创建 `backend/app/demo/lifecycle.py` — 演示模块启动/关闭钩子（供 main.py 调用）
- 验证：模块可独立 import，无循环依赖

**Task 1.2: main.py 启动流程解耦**
- `config.py`：将 `simulation_enabled` 重命名为 `demo_enabled`（保留 `simulation_enabled` 作为别名，标记 deprecated）
- `main.py` L20-22：将 simulator/power_seed/cooling_seed 的 import 移入 `demo/lifecycle.py`
- `main.py` L219-220：将 `seed_power_devices()` / `seed_cooling_devices()` 调用移入 `demo/lifecycle.py:startup()`
- `main.py` L261-262：将 `simulator_task` 创建移入 `demo/lifecycle.py:startup()`
- `main.py` L415-416：将 simulator 停止/取消移入 `demo/lifecycle.py:shutdown()`
- `main.py` L396：条件化打印信息
- `main.py` lifespan 中添加：`if settings.demo_enabled: await demo_lifecycle.startup(app)`
- 验证：`demo_enabled=false` 时 main.py 零 demo import，启动无 demo 相关日志

**Task 1.3: 业务服务 mock 方法清理**
- `analysis_plugins/manager.py`：删除 5 个 `_generate_mock_*` 方法(L239-611)，except 分支改为 `logger.error(); return []`
- `demand_analysis_service.py`：删除 3 个静态 mock 方法(L564-682)
- `demand.py`：3 处调用点(L161, L319, L424)改为返回空数据结构
- `energy_analysis.py`：删除 `_generate_mock_analysis`(L192-262)，内联 mock 回退改为返回零值 dict
- `feedback_learning.py`：删除 `_generate_mock_execution_data`(L288-342) 和 `generate_sample_history`(L399-457)
- `optimization.py`：删除 2 处 `generate_sample_history` 调用(L406-408, L478-480)
- `effect_monitoring_service.py`：删除 2 处 simulation_enabled 分支(L123-136, L240-247)，保留非模拟路径
- 验证：全局搜索 `_generate_mock` / `simulation_enabled` / `demo_provider` 零命中（demo/ 目录除外）

**Task 1.4: monitoring.py 解耦**
- 删除 `demo_provider` import(L21)
- 删除 5 处 `if settings.simulation_enabled` 分支(L207-210, L333-340, L385-387, L447-449, L517-519)，保留 else 分支作为无条件返回
- 删除 `/dispatch/simulation` 端点(L690-715)
- 删除 6 处死代码 `settings = get_settings()` 调用(L148, L286, L357, L417, L469, L579)
- `is_demo_data` 字段保留，硬编码 `False`
- 验证：monitoring.py 零 simulation/demo import

**Task 1.5: 遗留代码清理**
- 删除 `backend/app/services/demo_data_provider.py`（仅被 monitoring.py 使用，已解耦）
- 删除 `backend/app/services/collector.py`（已被 simulator.py 取代）
- 删除 `backend/app/tools/demo_data_generator.py`（遗留 CLI 工具）
- 删除 `backend/app/tools/realtime_simulator.py`（遗留 CLI 工具）
- 将 `backend/app/services/simulator.py` 移入 `backend/app/demo/engine.py`
- 将 `backend/app/services/power_seed.py` 移入 `backend/app/demo/seeds/power_seed.py`
- 将 `backend/app/services/cooling_seed.py` 移入 `backend/app/demo/seeds/cooling_seed.py`
- 将 `backend/app/services/demo_data_service.py` 移入 `backend/app/demo/service.py`（合并）
- 更新 `api/v1/__init__.py`：demo_router 改为从 `demo/router.py` 条件导入
- 验证：`backend/app/services/` 下无 demo/simulator/seed 相关文件

#### Phase 2: 虚拟 Gateway 引擎重构

**Task 2.1: 统一入库管道 (ingest_pipeline)**
- 创建 `backend/app/services/ingest_pipeline.py` — 统一入库编排函数（非 demo 专属，是核心基础设施）
- 核心函数 `async def process_payload(payload: dict, db: AsyncSession, site_id: int)`：
  1. 解析 payload（与 handle_point_data 相同格式）：`{"gw_id": str, "seq"?: int, "points": [{"id": str, "v": any, "q": int, "t": int}]}`
  2. 去重检查（如有 seq）
  3. 批量写入 PointDataLatest（bulk upsert，单事务）
  4. 批量同步到 PointRealtime（bulk update，同一事务）
  5. 批量告警判定：对每个点位调用 `alarm_engine.evaluate()`，收集结果
  6. 批量告警落库：创建/解除 Alarm 记录（参考 simulator.py:131 逻辑）
  7. 单次 commit（整批一个事务）
  8. 批量 Redis 缓存：pipeline 写入 `point:{id}:latest`
  9. 批量 WebSocket 推送：将本批所有点位打包为一个帧 `{"type": "realtime_batch", "data": [...]}`，或节流为每秒一次
  10. 告警 WebSocket 推送 + 事件总线发布（如有告警）
- 修改 `mqtt/client.py:167`：MQTT 消费端改为调用 `process_payload()`（替代当前只调 handle_point_data）
- 修改 `datasource_bridge.py:47`：移除逐点 commit，改为由调用方控制事务
- 验证：MQTT 和 DemoEngine 共用同一入口，PointDataLatest 和 PointRealtime 同时有数据，告警正常触发
**Task 2.2: DemoEngine 引擎**
- 创建 `backend/app/demo/engine.py` — 新的 DemoEngine 类（替代旧 DataSimulator）
- DemoEngine 核心循环（每 5 秒）：
  1. 为每个演示点位生成模拟值（基于设备类型 + 时间曲线 + 随机扰动）
  2. 构造 MQTT 格式 payload：`{"gw_id": "virtual-gw-demo", "points": [{"id": point_code, "v": value, "q": 0, "t": timestamp}]}`
  3. 调用 `ingest_pipeline.process_payload(payload, db, site_id)` — 与 MQTT 完全相同的入口
- 批量处理：每轮处理所有 ~2830 个点位，分批（100-300 个/批）调用 process_payload
- 验证：前端实时监控页面能看到数据更新，告警能正常触发和推送

**Task 2.3: 数据模拟算法**
- AI 点位（模拟量）：基准值 + 日周期正弦波 + 随机噪声（±2%）+ 负载相关性
  - 温度类：跟随时间（白天高、夜间低）+ 负载关联
  - 电力类：跟随负载曲线（工作日/周末不同）+ 功率因数关联
  - 流量/压力类：跟随设备运行状态
- DI 点位（开关量）：正常状态为主，0.1% 概率触发状态变化
- 设备间关联：
  - UPS 输出功率 ≈ 下游列头柜功率之和
  - 精密空调送风温度 ≈ 冷冻水供水温度 + 2~4°C
  - 冷水机组 COP 与负载率相关（部分负载时 COP 更高）
  - PUE = 总功率 / IT 功率（动态计算）
- 验证：PUE 值在 1.3~1.6 范围内波动，符合真实数据中心特征

#### Phase 3: 4 层楼算力中心数据模型

**Task 3.1: 空间层级创建**
- 创建 `backend/app/demo/seeds/spatial.py`
- 创建 Site："演示算力中心"
- 创建 4 个 Floor（1F-4F），每层 3-7 个 Room
- 创建 Row（2F/3F 机房各 5 排，冷/热通道交替）
- 创建 Cabinet（200 个机架，2F/3F 各 100 个，42U 标准）
- 验证：空间层级完整，Floor → Room → Row → Cabinet 关系正确

**Task 3.2: 供配电系统创建**
- 创建 `backend/app/demo/seeds/power.py`（替代旧 power_seed.py）
- 创建 Gateway：`virtual-gw-power`（协议类型 modbus_tcp）
- 创建 DataSource：每类设备一个数据源
- 创建设备 + 点位（按设备数量汇总表）：
  - 高压开关柜 × 6：电压/电流/功率/频率/功率因数/断路器状态/母线温度/告警
  - 变压器 × 2：绕组温度/油温/负载率/风机状态/瓦斯告警 + Transformer 模型
  - 低压配电柜 × 8：三相电压/电流/功率因数/THD/断路器状态 + DistributionPanel 模型
  - UPS × 4：输入输出电压电流/负载率/旁路状态/电池温度SOC + PowerDevice 模型
  - 电池组 × 8：组电压/单体电压/内阻/SOC/SOH/温度
  - 柴油发电机 × 2：电压/电流/频率/油位/冷却液温度/油压/运行小时
  - 列头柜 × 20：支路电流(6路)/总功率/电压/开关状态/过载告警
  - 机架 PDU × 400：A/B 路电流/电压/功率/温度
- 创建 MeterPoint（4 个，每变压器 2 个）
- 创建 DistributionCircuit（每配电柜 4-6 回路）
- 创建 ElectricityPricing（5 条，尖/峰/平/谷/深谷）
- 创建 PricingConfig（1 条默认配置）
- 创建 AlarmThreshold（每 AI 点位 1-2 条阈值规则）
- 验证：配电拓扑完整，Transformer → MeterPoint → Panel → Circuit → PowerDevice 链路正确

**Task 3.3: 制冷系统创建**
- 创建 `backend/app/demo/seeds/cooling.py`（替代旧 cooling_seed.py）
- 创建 Gateway：`virtual-gw-cooling`（协议类型 bacnet_ip）
- 创建设备 + 点位：
  - 冷水机组 × 3：供/回水温度/冷量/COP/压缩机状态/冷媒压力/告警
  - 冷冻水泵 × 4：运行状态/变频频率/流量/压差/功率/振动/故障
  - 冷却水泵 × 4：同上
  - 冷却塔 × 3：风机状态速度/进出水温度/液位/功率/告警
  - 精密空调 × 24：送/回风温度湿度/风机转速/压缩机状态/滤网压差/功率/告警
  - 冷通道 × 10：底/中/顶温度(冷热各3点)/压差
- 验证：制冷链路完整，Chiller → Pump → CRAH → Cold Aisle 关系正确

**Task 3.4: 环境与安防系统创建**
- 创建 `backend/app/demo/seeds/environment.py`
- 创建 Gateway：`virtual-gw-env`（协议类型 snmp_v2c）
- 创建设备 + 点位：
  - 温湿度传感器 × 40：温度/湿度/露点（每机房 8-12 个）
  - 漏水检测 × 30：绳式告警/定位距离 或 点式告警
  - 烟感探测器 × 40：烟雾告警状态
  - 门禁 × 20：门状态/刷卡结果
- 验证：每个房间都有环境传感器覆盖

**Task 3.5: 历史数据与能源数据生成**
- 创建 `backend/app/demo/seeds/history.py`
- 生成 30 天 PointHistory（AI 点位，每 5 分钟一条）
- 生成 30 天 EnergyDaily / EnergyMonthly 汇总
- 生成 30 天 DemandHistory（每 15 分钟最大需量）
- 生成 30 天 PUEHistory（每 15 分钟 PUE 值）
- 生成 AlarmDailyStats（每日告警统计）
- 验证：历史数据时间连续，能源数据与点位数据一致

**Task 3.6: VPP/调度演示数据**
- 创建 `backend/app/demo/seeds/dispatch.py`（从 dispatch.py init-demo-data 迁移）
- 创建 8 个可调度设备 + 2 个储能系统 + 2 个光伏系统
- 创建调度策略和执行计划
- 验证：调度管理页面数据完整

#### Phase 4: 卸载 API 完善

**Task 4.1: 完整卸载逻辑**
- 重写 `backend/app/demo/service.py` 的 unload 方法
- 清理顺序（按 FK 依赖倒序）：
  1. 告警相关：alarms, alarm_daily_stats, alarm_escalations
  2. 历史数据：point_history, point_history_archive, point_change_log
  3. 实时数据：point_realtime
  4. 能源数据：energy_daily, energy_monthly, pue_history, demand_history, demand_daily_stats
  5. 配电拓扑：distribution_circuits → distribution_panels → meter_points → transformers
  6. 电力设备：power_devices, electricity_pricing, pricing_configs
  7. 调度数据：dispatchable_devices, energy_storage_systems, pv_systems, dispatch_plans, execution_plans, execution_tasks
  8. 点位数据：datasource_points → points → point_groups, point_group_members
  9. 数据源：datasources → gateways
  10. 设备：devices
  11. 资产：assets, asset_lifecycle, maintenance_records
  12. 空间：cabinets → rows → rooms → floors → sites（仅演示站点）
  13. 容量：space_capacity, power_capacity, cooling_capacity, weight_capacity
  14. 联动/诊断：linkage_policies, diagnosis_rules, fire_protection_policies
  15. 节能：energy_suggestions, monitoring_records, measure_baselines, effect_reports
  16. 楼层地图：layout_templates
  17. Redis：按 pattern 前缀删除 `point:*` / `device:*` / `alarm:*`（不使用 FLUSHDB，避免误清非 demo 缓存）
- 添加事务保护：整个卸载在一个事务中，失败则回滚
- 验证：卸载后所有业务表为空（除 users/roles/permissions/system_configs/data_dictionaries），Redis 无残留

**Task 4.2: 前端适配**
- `DemoDataLoader.vue`：API 路径不变（/v1/demo/*），无需修改
- `dashboard/index.vue`：无需修改（DemoDataLoader 挂载方式不变）
- `dispatch.ts`：`initDemoData()` 调用迁移到 demo 模块统一管理
- 验证：前端加载/卸载/刷新日期功能正常

#### Phase 5: 测试

**Task 5.1: 演示模块单元测试**
- `tests/demo/test_engine.py`：DemoEngine 数据生成 + 管道注入测试
- `tests/demo/test_service.py`：加载/卸载/进度测试
- `tests/demo/test_seeds.py`：种子数据创建 + FK 完整性测试
- `tests/demo/test_lifecycle.py`：启动/关闭钩子测试

**Task 5.2: 回归测试**
- 更新 `test_datasources_demo_dispatch_floormap_monitoring_coverage.py`：移除 simulation_enabled mock
- 更新 `test_small_modules_coverage.py`：TestDispatchDemoData 适配新路径
- 更新 `tests/services/test_demand_analysis.py`：删除 mock 方法测试(L212-249)
- 运行全量 `pytest` 确保无回归

**Task 5.3: 集成验证**
- 启动系统（demo_enabled=true）→ 加载演示数据 → 验证前端所有页面数据正常
- 卸载演示数据 → 验证系统完全空白
- 启动系统（demo_enabled=false）→ 验证零 demo 代码加载

### Acceptance Criteria

1. **完全解耦**：`demo_enabled=false` 时，`backend/app/demo/` 模块不被 import，main.py 启动日志无 demo 相关信息，全局搜索 `simulation_enabled` / `_generate_mock` / `demo_provider` 在 `demo/` 目录外零命中
2. **统一管道注入**：演示数据经过 `ingest_pipeline.process_payload()` 统一入口，内部完成 PointDataLatest 写入 → PointRealtime 同步 → 告警判定/落库 → WebSocket 推送。MQTT 和 DemoEngine 共用此入口，PointDataLatest 和 PointRealtime 同时有数据
3. **逼真数据模型**：4 层楼、~628 台设备、~2830 个采集点，配电拓扑完整（高压 → 变压器 → 低压 → UPS → 列头柜 → PDU），制冷链路完整（冷机 → 泵 → 空调 → 冷通道），PUE 在 1.3~1.6 范围
4. **一键卸载归零**：卸载后所有业务表为空（仅保留 users/roles/permissions/system_configs/data_dictionaries），Redis 无残留 point/device 键，前端显示空白状态
5. **业务服务零 mock**：8 个业务服务文件中无 `_generate_mock_*` 方法，无 `simulation_enabled` 分支，无数据时返回空结果
6. **what-if 功能独立**：simulation_service.py / load_regulation.py / device_control_service.py 不依赖 demo 模块，demo_enabled=false 时仍可正常使用
7. **测试通过**：全量 pytest 通过，新增演示模块测试覆盖率 > 80%
8. **前端兼容**：DemoDataLoader 加载/卸载/刷新日期功能正常，实时监控页面数据更新正常，告警通知正常

## Additional Context

### Dependencies

- 无新增外部依赖。所有功能使用现有技术栈（FastAPI/SQLAlchemy/Redis/aiomqtt）实现
- `simulation_enabled` → `demo_enabled` 重命名需要更新 `.env` 文件和部署文档
- 前端 API 路径不变（/v1/demo/*），无前端依赖变更

### Testing Strategy

- **框架**：pytest + pytest-asyncio (auto mode) + httpx AsyncClient
- **DB 隔离**：in-memory SQLite + savepoint rollback（沿用现有 conftest.py 模式）
- **测试分层**：
  - 单元测试：DemoEngine 数据生成算法、种子数据 FK 完整性
  - 集成测试：统一管道注入（ingest_pipeline.process_payload → PointDataLatest + PointRealtime + alarm + ws）
  - API 测试：demo 路由端点（status/load/unload/progress）
  - 回归测试：现有 monitoring/demand/optimization 测试更新后通过
- **关键测试场景**：
  - `demo_enabled=false` 时零 demo import（通过 mock settings 验证）
  - 卸载后所有表为空（遍历所有 model 做 count 断言）
  - 数据生成值在合理范围内（温度 18-35°C，电压 380±10%，PUE 1.3-1.6）
  - 设备间关联一致性（UPS 输出 ≈ 下游列头柜之和 ±5%）

### Notes

- **性能考量**：~2830 个点位每 5 秒更新一轮，需要批量 DB 操作（bulk insert/update）避免逐条写入。建议每批 100 个点位，使用 `session.execute(insert().values([...]))` 批量写入
- **内存占用**：DemoEngine 需要在内存中维护所有点位的当前状态（用于关联计算），约 2830 × 100 bytes ≈ 280KB，可接受
- **启动时间**：首次加载演示数据（创建 628 台设备 + 2830 个点位 + 30 天历史）预计需要 2-5 分钟，通过进度条反馈用户
- **管道统一是核心价值**：本次重构的最大架构收益不是 demo 解耦，而是通过 `ingest_pipeline.process_payload()` 统一了 MQTT 和 DemoEngine 的入库路径，修复了长期存在的管道断裂问题。后续新增协议适配器（Modbus/SNMP/BACnet）也应调用此入口
- **配置迁移**：`simulation_enabled` → `demo_enabled` 需要在 CLAUDE.md 和 docs/ 中同步更新
- **数据量控制**：机架 PDU 400 条 × 4 点 = 1600 个点位占总量 56%。如果性能有压力，可以先减少到 50 个 PDU（代表性采样），后续按需扩展
- **未来演进**：若后续并发站点或点位翻倍，再评估把实时链路从 SQLite 写入迁移为“Redis 优先 + 异步落库”。若要保留细粒度设备语义，下一期再引入 `device_subtype`（当前先不改 schema 是正确取舍）

---

## Pre-Implementation Validation Report (2026-02-27)

### 1. 测试基线

- **1779 passed**, 1 skipped, 0 failures（API 1558 + services 221）
- 6 个协议适配器测试文件 hang（pre-existing，尝试真实网络连接，与本次重构无关）
- 命令: `pytest tests/api/ tests/test_*.py tests/services/ --timeout=10 -q`（排除 modbus_rtu/tcp, snmp, mqtt_adapter, bacnet_ip, opc_ua）

### 2. Git 标记

- Tag: `pre-demo-refactor`
- Message: "Pre-demo-refactor baseline: 1779 tests pass, tech spec approved"
- 基于 commit `4c8ebaa`

### 3. 性能基准测试

#### 3.1 SQLite 入库 benchmark (`benchmark_ingest.py`)

| 测试项 | batch=300 | 结论 |
|--------|-----------|------|
| PointDataLatest bulk upsert (INSERT OR REPLACE) | 0.31s +/- 0.017s | 极快 |
| PointRealtime 逐行 UPDATE (executemany) | 1.55s +/- 0.073s | 可用但慢 |
| PointRealtime CASE WHEN 批量 UPDATE | 0.043s +/- 0.002s | 极快，比逐行快 36x |
| 综合管道 (PDL + PR 单事务) | 0.40s +/- 0.022s | 5秒预算仅用 8% |

**决策**: 采用 CASE WHEN 批量 UPDATE，batch=300 为最优批次。

#### 3.2 WebSocket + 告警引擎 benchmark (`benchmark_ws_alarm.py`)

| 测试项 | 结果 | 结论 |
|--------|------|------|
| alarm_engine.evaluate() x 2830 | 3.2ms +/- 0.3ms | 纯内存，极快 |
| JSON 序列化 2830 点 payload | 4.7ms +/- 0.3ms | 不是瓶颈 |
| WS 广播 10 clients (full payload) | 42.5ms +/- 2.6ms | OK |
| WS 广播 10 clients (chunked 500/frame) | 33.7ms +/- 0.9ms | 分块更优 |

#### 3.3 全管道时间预算

| 环节 | 耗时 |
|------|------|
| DB 写入 (PDL + PR, batch=300) | ~400ms |
| 告警判定 (2830 x evaluate) | ~3ms |
| JSON 序列化 | ~5ms |
| WS 广播 (10 clients) | ~42ms |
| Redis pipeline (估算) | ~50ms |
| **总计** | **~500ms** |
| **5 秒预算余量** | **~4,500ms** |

**结论**: 2830 点/5秒方案完全可行，全管道仅占预算 10%。无需减少 PDU 数量，无需换 PostgreSQL。

### 4. 前端依赖扫描

| 类别 | 文件 | 影响 |
|------|------|------|
| 组件挂载 | `views/dashboard/index.vue` L60, L216, L235, L249 | 唯一消费者 - 移除 import + template + ref + button |
| API 模块 | `api/modules/demo.ts` | 5 个 API 函数 - 删除整个文件 |
| API 导出 | `api/modules/index.ts` L110 | `export * from './demo'` - 移除此行 |
| 调度 API | `api/modules/dispatch.ts` L278-283 | `initDemoData()` - 移除此函数 |
| 调度 UI | `components/energy/DispatchConfig.vue` L359, L432 | import + 调用 initDemoData - 移除 |
| 类型声明 | `components.d.ts` L31 | 自动生成 - rebuild 后自动更新 |
| 测试文件 | `__tests__/components/demo-data-loader.test.ts` | 删除整个文件 |
| 容量类型 | `api/modules/capacity.ts` L426 | `is_demo: boolean` - 保留（匹配后端 is_demo_data 字段） |
| Stores | 无 | 无 demo 相关 Pinia store |
| Router | 无 | 无 demo 相关路由 |

**结论**: 前端 demo 依赖链很浅，移除干净无风险。

### 5. Task 排序优化

#### 并行机会

- **Phase 1**: Task 1.2 + 1.3 + 1.4 可并行（操作不同文件集，无冲突）
- **Phase 3**: Task 3.2 + 3.3 + 3.4 可并行（不同设备类型，独立种子文件）
- **Phase 3**: Task 3.5 + 3.6 可并行
- **Phase 4**: Task 4.1 + 4.2 可并行（后端/前端独立）

#### 排序调整建议

1. **Task 5.2（回归测试更新）提前到 Phase 1 末尾** - mock 清理后现有测试会 break，应立即修复而非留到最后
2. **Task 2.2 + 2.3 合并** - 模拟算法就是 DemoEngine 的核心逻辑，分开无意义
3. **Task 4.2（前端适配）可提前** - 技术规范确认 API 路径不变，前端几乎不需要改

#### 优化后执行计划

```
Phase 1 (核心解耦):
  1.1 创建演示模块骨架
  1.2 + 1.3 + 1.4 并行（main.py 解耦 / mock 清理 / monitoring 解耦）
  1.5 遗留代码清理 + 文件迁移
  5.2 回归测试更新（提前）

Phase 2 (统一管道):
  2.1 ingest_pipeline（最关键 task）
  2.2+2.3 DemoEngine + 模拟算法（合并）

Phase 3 (数据模型):
  3.1 空间层级
  3.2 + 3.3 + 3.4 并行（供配电 / 制冷 / 环境安防）
  3.5 + 3.6 并行（历史数据 / VPP 调度）

Phase 4+5 (收尾):
  4.1 + 4.2 并行（卸载逻辑 / 前端适配）
  5.1 演示模块单元测试
  5.3 集成验证
```
