# 算力中心智能监控系统 (DCIM) — 模块化单体架构设计文档

---

## 1. 文档概述

### 1.1 文档目的

本文档对 DCIM 系统当前代码库进行模块化单体（Modular Monolith）架构分析与设计。通过梳理现有代码结构，划定清晰的领域边界，识别跨模块依赖关系，并为未来可能的微服务拆分提供演进路线图。

### 1.2 为什么选择模块化单体

DCIM 系统当前处于「单体应用」阶段——所有功能模块运行在同一个 FastAPI 进程中，共享同一个数据库连接池。这种架构在早期开发阶段具有以下优势：

- **部署简单**：单进程启动，无需服务编排
- **开发效率高**：模块间可直接调用，无网络开销
- **事务一致性**：共享数据库，天然支持 ACID 事务
- **调试方便**：单进程内可完整追踪调用链

但随着系统规模增长（47 个路由模块、77 个服务文件、27 个 ORM 模型），模块间的隐式耦合逐渐增加。模块化单体是在「保留单体部署优势」的前提下，通过「明确领域边界 + 规范模块间通信」来控制复杂度的最佳实践。

### 1.3 当前状态评估

| 维度 | 评估 |
|------|------|
| 部署形态 | 单进程单体（FastAPI + Uvicorn） |
| 模块边界 | 按技术层分包（models/、services/、api/），非按领域分包 |
| 模块间通信 | 直接 import + 部分 event_bus 事件 |
| 数据隔离 | 无隔离，所有模型共享同一数据库 |
| 可独立部署性 | 无，所有模块必须一起部署 |
| 前后端对齐度 | 较好，前端 API 模块与后端路由基本一一对应 |

---

## 2. 系统现状

### 2.1 技术栈

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + TypeScript)                │
│   Element Plus · ECharts · Three.js · Pinia · Vite         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              代理层 (Express / Vite Dev Proxy)              │
│                    端口 3000 → 8080                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (FastAPI 单进程)                     │
│  47 路由 · 27 模型 · 33 Schema · 77 服务 · 8 引擎          │
│  9 分析插件 · 9 后台任务 · 11 步启动初始化                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              数据层 (SQLite / PostgreSQL)                   │
│                  Redis (可选，优雅降级)                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 代码规模统计

| 类别 | 数量 | 位置 |
|------|------|------|
| API 路由模块 | 47 | `backend/app/api/v1/` |
| ORM 模型文件 | 27 | `backend/app/models/` |
| Pydantic Schema | 33 | `backend/app/schemas/` |
| 业务服务文件 | 77 | `backend/app/services/` |
| 分析插件 | 9 | `backend/app/services/analysis_plugins/` |
| 引擎模块 | 8 | `backend/app/engines/` |
| 网关模块文件 | 16+ | `backend/gateway/` |
| 后台定时任务 | 9 | `backend/app/main.py` lifespan |
| 启动初始化步骤 | 11 | `backend/app/main.py` lifespan |
| 前端 API 模块 | 38 | `frontend/src/api/modules/` |
| Pinia Store | 10 | `frontend/src/stores/` |
| 前端视图目录 | 28 | `frontend/src/views/` |

### 2.3 后台任务清单

| 任务 | 周期 | 职责 |
|------|------|------|
| `simulator.start()` | 每 5 秒 | 数据模拟器，为点位生成模拟数据 |
| `alarm_engine.check_version()` | 每 30 秒 | 告警阈值刷新 |
| `check_communication_status()` | 每 30 秒 | 通信状态监控 |
| `check_escalations()` | 每 60 秒 | 告警升级检查 |
| `write_pue_history()` | 每 15 分钟 | PUE 历史记录写入 |
| `aggregate_hourly/daily/monthly()` | 每 30 分钟 | 能耗数据聚合 |
| `OpportunityDetector.run_detection()` | 每 1 小时 | 节能机会检测 |
| `EffectTracker.run_tracking()` | 每 6 小时 | 节能效果追踪 |
| `ws_manager.start_heartbeat()` | 每 30 秒 | WebSocket 心跳保活 |

### 2.4 启动初始化序列

```
main.py lifespan 启动流程（顺序执行）：

 1. init_db()                    ─── 创建所有数据库表
 2. init_default_data()           ─── 创建管理员用户 + 角色权限
 3. init_default_configs()        ─── 系统配置 + 数据字典
 4. seed_power_devices()          ─── 供配电设备种子数据
 5. seed_cooling_devices()        ─── 制冷设备种子数据
 6. redis_service.connect()       ─── 连接 Redis（可选）
 7. alarm_engine.load_thresholds()─── 加载告警阈值
 8. fire_protection sync          ─── 同步消防 YAML 到数据库
 9. linkage_engine.load_policies()─── 加载联动策略
10. cross_confirmation subscribe  ─── 订阅告警事件
11. diagnosis_engine.load_rules() ─── 加载诊断规则
```

---

## 3. 领域划分

基于业务职责和代码依赖关系，将系统划分为 8 个限界上下文（Bounded Context）。

### 3.1 领域总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DCIM 模块化单体                              │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ 认证与用户 │  │ 监控与采集 │  │ 告警与联动 │  │   能源管理       │    │
│  │ 2 路由    │  │ 3 路由    │  │ 7 路由    │  │   10 路由        │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ 节能优化  │  │ 资产与运维 │  │ 采集网关  │  │   系统基础设施    │    │
│  │ 4 路由    │  │ 6 路由    │  │ 4 路由    │  │   11 路由        │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
│                                                                     │
│  ═══════════════════ 共享基础设施层 ═══════════════════════════     │
│  core/ · middleware/ · event_bus · websocket · 后台任务调度器        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 领域一：认证与用户

| 维度 | 内容 |
|------|------|
| 职责 | 用户认证、JWT 令牌管理、RBAC 权限控制、会话管理、密码策略 |
| API 路由 | `auth.py` (/auth)、`user.py` (/users) |
| ORM 模型 | `user.py` |
| Schema | `user.py` |
| 服务 | （内嵌于路由层，无独立服务文件） |
| 引擎 | 无 |
| 后台任务 | 无 |
| 前端对齐 | 视图: `login/`、API: `auth.ts`/`user.ts`、Store: `user.ts` |

### 3.3 领域二：监控与采集

| 维度 | 内容 |
|------|------|
| 职责 | 设备管理、点位管理、实时数据采集与推送、数据模拟、通信状态监控 |
| API 路由 | `device.py` (/devices)、`point.py` (/points)、`realtime.py` (/realtime) |
| ORM 模型 | `device.py`、`point.py`、`history.py` |
| Schema | `device.py`、`point.py`、`realtime.py`、`history.py` |
| 服务 | `simulator.py`、`collector.py`、`point_data.py`、`point_import.py`、`point_device_matcher.py`、`communication_monitor.py`、`websocket.py` |
| 引擎 | 无 |
| 后台任务 | `simulator.start()`（每 5 秒）、`check_communication_status()`（每 30 秒）、`ws_manager.start_heartbeat()`（每 30 秒） |
| 前端对齐 | 视图: `device/`、`device-manage/`、`device-status/`、`environment/`、API: `device.ts`/`point.ts`/`realtime.ts`、Store: `realtime.ts` |

### 3.4 领域三：告警与联动

| 维度 | 内容 |
|------|------|
| 职责 | 阈值告警触发、告警升级、联动规则引擎、智能诊断、故障恢复、控制命令、漂移检测、数据质量 |
| API 路由 | `alarm.py` (/alarms)、`threshold.py` (/thresholds)、`escalation.py` (/escalations)、`data_quality.py` (/data-quality)、`linkage.py` (/linkage)、`diagnosis.py` (/diagnosis)、`command.py` (/command)、`drift.py` (/drift) |
| ORM 模型 | `alarm.py`、`command.py`、`diagnosis.py`、`drift.py`、`linkage.py` |
| Schema | `alarm.py`、`threshold.py`、`command.py`、`data_quality.py`、`diagnosis.py`、`drift.py`、`linkage.py` |
| 服务 | `command_service.py`、`device_control_service.py`、`drift_detection.py`、`fire_protection.py` |
| 引擎 | `alarm_engine.py`、`escalation_engine.py`、`linkage_engine.py`、`diagnosis_engine.py`、`event_bus.py`、`cross_confirmation.py`、`action_handlers.py`、`recovery_engine.py` |
| 后台任务 | `alarm_engine.check_version()`（每 30 秒）、`check_escalations()`（每 60 秒） |
| 前端对齐 | 视图: `alarm/`、`linkage/`、`diagnosis/`、`security/`、API: `alarm.ts`/`threshold.ts`/`linkage.ts`/`command.ts`/`diagnosis.ts`/`drift.ts`/`dataQuality.ts`、Store: `alarm.ts` |

### 3.5 领域四：能源管理

| 维度 | 内容 |
|------|------|
| 职责 | 用电管理、供配电管理、电价配置、电费监控、PUE 计算、配电拓扑、负荷调节、调度优化、VPP 分析、制冷系统 |
| API 路由 | `energy.py` (/energy)、`power.py` (/power)、`pricing.py` (/pricing)、`demand.py`、`monitoring.py` (/monitoring)、`topology.py` (/topology)、`regulation.py` (/regulation)、`dispatch.py` (/dispatch)、`optimization.py` (/optimization)、`vpp.py` (/vpp)、`cooling.py` (/cooling) |
| ORM 模型 | `energy.py`、`power.py`、`cooling.py`、`vpp_data.py` |
| Schema | `energy.py`、`power.py`、`cooling.py` |
| 服务 | `energy_aggregator.py`、`energy_analysis.py`、`energy_config.py`、`energy_topology.py`、`energy_report_service.py`、`energy_report_excel.py`、`energy_report_pdf.py`、`pue_calculator.py`、`pricing_service.py`、`formula_calculator.py`、`traced_formula_calculator.py`、`ml_traced_calculator.py`、`power_device.py`、`power_seed.py`、`load_regulation.py`、`realtime_dispatch.py`、`vpp_calculator.py`、`demand_analysis_service.py`、`device_regulation_service.py`、`device_selector_service.py`、`cooling_seed.py` |
| 引擎 | 无 |
| 后台任务 | `write_pue_history()`（每 15 分钟）、`aggregate_hourly/daily/monthly()`（每 30 分钟） |
| 前端对齐 | 视图: `energy/`、`power/`、`cooling/`、`vpp/`、`topology/`、API: `energy.ts`/`power.ts`/`cooling.ts`/`demand.ts`/`monitoring.ts`/`dispatch.ts`/`optimization.ts`/`vpp.ts`、Store: `energy.ts` |

### 3.6 领域五：节能优化

| 维度 | 内容 |
|------|------|
| 职责 | 节能机会检测、6 种分析插件、执行管理、效果追踪、方案提议、ML 深度学习优化 |
| API 路由 | `opportunities.py` (/opportunities)、`execution.py` (/execution)、`proposal.py`、`ml.py` (/ml，可选，需 torch) |
| ORM 模型 | （复用 energy.py 模型） |
| Schema | `proposal_schema.py` |
| 服务 | `opportunity_detector.py`、`opportunity_engine.py`、`suggestion_engine.py`、`effect_tracker.py`、`effect_monitoring_service.py`、`execution_service.py`、`proposal_executor.py`、`optimizer.py`、`optimization_integration.py`、`adaptive_optimization_service.py`、`feedback_learning.py`、`forecasting.py`、`ml_service.py`、`ml_template_generator.py` |
| 分析插件 | `base.py`、`manager.py`、`registry.py`、`peak_valley.py`、`demand_optimization.py`、`equipment_efficiency.py`、`load_shifting.py`、`power_factor.py`、`pue_optimization.py` |
| 后台任务 | `OpportunityDetector.run_detection()`（每 1 小时）、`EffectTracker.run_tracking()`（每 6 小时） |
| 前端对齐 | 视图: （复用 energy/ 视图）、API: `opportunities.ts`/`optimization.ts`、Store: `opportunity.ts` |

### 3.7 领域六：资产与运维

| 维度 | 内容 |
|------|------|
| 职责 | 资产台账、容量管理、空间管理、楼层图、拓扑配置、工单巡检、知识库 |
| API 路由 | `asset.py`、`capacity.py`、`spatial.py`、`topology_config.py` (/topology-config)、`floor_map.py` (/floor-map)、`operation.py` |
| ORM 模型 | `asset.py`、`capacity.py`、`spatial.py`、`topology_config.py`、`floor_map.py`、`operation.py` |
| Schema | `asset.py`、`capacity.py`、`spatial.py`、`topology_config.py`、`operation.py` |
| 服务 | `asset.py`、`capacity.py`、`floor_map_generator.py`、`topology_sync.py`、`operation.py` |
| 引擎 | 无 |
| 后台任务 | 无 |
| 前端对齐 | 视图: `asset/`、`capacity/`、`topology/`、`operation/`、API: `asset.ts`/`capacity.ts`/`spatial.ts`/`topologyConfig.ts`/`floorMap.ts`/`operation.ts` |

### 3.8 领域七：采集网关

| 维度 | 内容 |
|------|------|
| 职责 | 数据源管理、网关注册与监控、设备模板、OTA 升级、多协议适配（Modbus/SNMP/MQTT/HTTP/BACnet/OPC-UA） |
| API 路由 | `datasources.py` (/datasources)、`gateways.py` (/gateways)、`device_templates.py` (/device-templates)、`ota.py` (/ota) |
| ORM 模型 | `gateway.py` |
| Schema | `gateway.py`、`ota.py` |
| 服务 | `gateway_registration.py`、`gateway_monitor.py`、`datasource_bridge.py`、`connection_test.py`、`config_push.py`、`device_sync.py`、`device_config_generator.py`、`template_generator.py`、`ota_service.py` |
| 网关独立模块 | `backend/gateway/` — `adapters/`（6 种协议适配器）、`mqtt_client.py`、`scheduler.py`、`cache.py`、`config_loader.py`、`config_receiver.py`、`dry_contact.py`、`normalizer.py`、`retry.py`、`status_reporter.py` |
| 引擎 | 无 |
| 后台任务 | 无 |
| 前端对齐 | 视图: `datasource/`、`gateway/`、`device-template/`、API: `gateway.ts` |

### 3.9 领域八：系统基础设施

| 维度 | 内容 |
|------|------|
| 职责 | 系统配置、系统健康、视频监控、历史数据、统计分析、报表、日志、数据追溯、演示数据、大屏展示 |
| API 路由 | `config.py` (/configs)、`system_health.py` (/system)、`demo.py`、`video.py` (/video)、`history.py` (/history)、`statistics.py` (/statistics)、`report.py` (/reports)、`log.py` (/logs)、`trace.py` |
| ORM 模型 | `config.py`、`system.py`、`video.py`、`history.py`、`log.py`、`report.py`、`trace.py` |
| Schema | `config.py`、`system.py`、`video.py`、`history.py`、`log.py`、`report.py`、`trace_schema.py`、`trace.py`、`common.py` |
| 服务 | `video_service.py`、`data_trace_service.py`、`history_generator.py`、`demo_data_service.py`、`demo_data_provider.py`、`simulation_service.py`、`report_export.py`、`pdf_generator.py`、`timeline_report.py`、`cache_service.py`、`dedup_service.py`、`diagnosis_loader.py`、`ocr_service.py`、`emqx_acl.py` |
| 引擎 | 无 |
| 后台任务 | 无 |
| 前端对齐 | 视图: `video/`、`history/`、`report/`、`settings/`、`system/`、`bigscreen/`、`dashboard/`、`common/`、API: `video.ts`/`history.ts`/`statistics.ts`/`report.ts`/`log.ts`/`config.ts`/`bigscreen.ts`/`demo.ts`、Store: `app.ts`/`bigscreen.ts`/`degradation.ts`/`site.ts` |
---
## 4. 领域依赖关系图
### 4.1 领域间依赖关系
```
                          ┌──────────────┐
                          │  认证与用户  │
                          │ (JWT/RBAC)  │
                          └─────┬────────┘
                                │
                ┌────────┼─────────────────────────────────┐
                │        │ (所有领域均依赖 JWT 认证)       │
                ▼        ▼                                ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  监控与采集  │  │  资产与运维  │  │ 系统基础设施 │
  │ (核心领域)  │  │              │  │              │
  └───┬──┬─────┘  └──────────────┘  └──────────────┘
      │  │
      │  ├───────────────────────────────────────────┐
      │  │                                            │
      ▼  ▼                                            ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  告警与联动  │  │  能源管理    │  │  采集网关    │
  │              │  │              │  │              │
  └──────────────┘  └─────┬────────┘  └──────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │  节能优化    │
                  │              │
                  └──────────────┘
```
### 4.2 依赖方向说明
| 依赖关系 | 方向 | 说明 |
|----------|------|------|
| 所有领域 → 认证与用户 | 单向 | 所有 API 路由通过 JWT 依赖认证模块进行身份验证和权限检查 |
| 告警与联动 → 监控与采集 | 单向 | 告警引擎从点位实时数据触发阈值告警，依赖 device/point 模型 |
| 能源管理 → 监控与采集 | 单向 | 能耗计算依赖设备点位的实时数据和历史数据 |
| 节能优化 → 能源管理 | 单向 | 节能分析插件依赖能耗数据、电价配置、PUE 指标 |
| 采集网关 → 监控与采集 | 单向 | 网关采集的数据写入设备/点位模型，依赖 device/point 定义 |
| 监控与采集 → 告警与联动 | 弱依赖 | 通过 event_bus 发布数据事件，告警引擎订阅处理 |
### 4.3 依赖矩阵
```
              认证  监控  告警  能源  节能  资产  网关  系统
认证与用户   -     .     .     .     .     .     .     .
监控与采集   ●     -     ○     .     .     .     .     .
告警与联动   ●     ●     -     .     .     .     .     .
能源管理     ●     ●     .     -     .     .     .     .
节能优化     ●     .     .     ●     -     .     .     .
资产与运维   ●     .     .     .     .     -     .     .
采集网关     ●     ●     .     .     .     .     -     .
系统基础     ●     .     .     .     .     .     .     -

图例： ● = 强依赖（直接 import）  ○ = 弱依赖（通过 event_bus）  . = 无依赖
```
---
## 5. 共享基础设施
以下基础设施被所有领域共享，属于「平台层」而非任何单一领域。
### 5.1 核心基础设施 (app/core/)
| 文件 | 职责 | 被依赖方式 |
|------|------|----------|
| `config.py` | 应用配置（pydantic-settings，环境变量） | `get_settings()` 单例，通过 `@lru_cache()` 缓存 |
| `database.py` | SQLAlchemy 异步引擎、会话工厂、`init_db()` | `async_session` 会话工厂，所有服务共享 |
| `security.py` | 密码哈希、JWT 令牌创建/验证 | 认证中间件和路由依赖注入 |
| `redis.py` | Redis 服务（可选，优雅降级） | 缓存、去重、会话管理 |
| `cache_headers.py` | HTTP 缓存头工具 | API 路由层使用 |
| `logging.py` | 日志配置 | 全局日志基础设施 |
### 5.2 中间件 (app/middleware/)
| 文件 | 职责 |
|------|------|
| `request_logging.py` | 请求/响应日志记录 |
| `metrics_middleware.py` | 指标采集中间件 |
| `metrics.py` | 指标收集器 |
| `error_handler.py` | 全局异常处理器 |
### 5.3 进程内事件总线 (app/engines/event_bus.py)
事件总线是当前系统中唯一的跨领域解耦机制，基于进程内发布/订阅模式实现。
当前事件流：
```
监控与采集 (simulator)                告警与联动
      │                                    │
      ├── 发布: point_data_event ───────→ alarm_engine (阈值检测)
      │                                    │
      │                                    ├── 发布: alarm_event
      │                                    │         │
      │                                    │         ├→ cross_confirmation (交叉确认)
      │                                    │         ├→ linkage_engine (联动触发)
      │                                    │         ├→ escalation_engine (升级检查)
      │                                    │         └→ diagnosis_engine (故障诊断)
      │                                    │
      │                                    └── action_handlers (执行联动动作)
      │                                              │
      │                                              └→ recovery_engine (故障恢复)
```
### 5.4 WebSocket 管理器
统一的 WebSocket 连接管理，支持三个通道：
| 通道 | URL | 用途 | 所属领域 |
|------|-----|------|----------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送 | 监控与采集 |
| alarms | `/ws/alarms?token=xxx` | 告警通知 | 告警与联动 |
| system | `/ws/system?token=xxx` | 系统状态 | 系统基础设施 |
### 5.5 后台任务调度器
当前所有后台任务均在 `main.py` 的 `lifespan` 函数中通过 `asyncio.create_task()` 启动，无独立的任务调度框架。这是当前架构的一个耦合点，所有领域的后台任务生命周期统一由 main.py 管理。
---
## 6. 跨域耦合分析
### 6.1 耦合点清单
| 编号 | 耦合点 | 严重程度 | 说明 |
|------|--------|----------|------|
| C1 | `main.py` 上帝文件 | ★★★ 高 | 631 行代码，集中了所有领域的初始化逻辑、11 步启动序列、9 个后台任务、所有路由注册。任何领域的修改都可能需要触碰此文件 |
| C2 | event_bus 跨域耦合 | ★★ 中 | 告警引擎、联动引擎、诊断引擎、交叉确认通过 event_bus 耦合。虽然是解耦机制，但事件合约未显式定义，且为进程内同步调用 |
| C3 | 数据模拟器跨域 | ★★ 中 | `simulator.py` 同时触及设备/点位（监控领域）、告警触发（告警领域）、历史数据写入（系统领域） |
| C4 | 能耗聚合跨域 | ★★ 中 | `energy_aggregator.py` 依赖 point_history 表（监控领域）的历史数据进行能耗统计 |
| C5 | 共享数据库会话 | ★★★ 高 | 所有领域共享同一个 `async_session` 工厂，无数据隔离，任何领域可直接查询其他领域的表 |
| C6 | 模型层交叉引用 | ★★ 中 | ORM 模型间通过外键关联产生跨域依赖，如 alarm 引用 device/point，energy 引用 device |
| C7 | 服务层直接 import | ★★ 中 | 服务间通过直接 Python import 调用，无接口抽象，如节能服务直接 import 能源服务 |
### 6.2 耦合点影响分析
```
严重程度分布：

★★★ 高风险 (2个):
  C1 main.py 上帝文件 ─── 影响所有领域的启动和部署
  C5 共享数据库会话 ─── 阻稍未来数据隔离和微服务拆分

★★ 中风险 (5个):
  C2 event_bus ────── 事件合约未显式化，难以追踪数据流
  C3 数据模拟器 ───── 跨域操作，但仅用于开发/演示环境
  C4 能耗聚合 ─────── 跨域数据读取，但为只读操作
  C6 模型交叉引用 ─── 外键约束阻稍数据库拆分
  C7 服务直接 import ── 无接口抽象，难以替换实现
```
---
## 7. 模块化整改建议
以下建议旨在在「不拆分微服务」的前提下，显著提升系统的模块化程度。
### 7.1 从 main.py 提取领域初始化器
当前问题：`main.py` 集中了所有领域的初始化逻辑，是最大的耦合点。
整改方案：每个领域提供自己的初始化器，`main.py` 只负责编排调用。
```python
# 整改前：main.py 中混合所有领域的初始化代码
# 整改后：每个领域提供 initializer

# backend/app/domains/alarm/initializer.py
class AlarmDomainInitializer:
    async def startup(self):
        await alarm_engine.load_thresholds()
        await linkage_engine.load_policies()
        await diagnosis_engine.load_rules()
        # 启动后台任务
        asyncio.create_task(alarm_engine.check_version_loop())
        asyncio.create_task(check_escalations_loop())

    async def shutdown(self):
        # 清理资源
        pass

# main.py 简化为编排器
domain_initializers = [
    AuthDomainInitializer(),
    MonitoringDomainInitializer(),
    AlarmDomainInitializer(),
    EnergyDomainInitializer(),
    # ...
]
for init in domain_initializers:
    await init.startup()
```
### 7.2 定义显式领域接口（Protocol 类）
当前问题：服务间通过直接 import 调用，无接口抽象。
整改方案：为每个领域定义 Python Protocol 接口，跨域调用必须通过接口。
```python
# backend/app/domains/monitoring/protocols.py
from typing import Protocol

class PointDataProvider(Protocol):
    """
    监控领域对外提供的点位数据接口。
    告警领域和能源领域通过此接口获取点位数据，
    而非直接 import 监控服务的内部实现。
    """
    async def get_current_value(self, point_id: int) -> float: ...
    async def get_history(self, point_id: int, start: datetime, end: datetime) -> list: ...
```
### 7.3 统一使用 event_bus 进行跨域通信
当前问题：部分跨域通信通过 event_bus，部分通过直接 import，不一致。
整改方案：
- 所有跨域写操作必须通过 event_bus
- 跨域读操作通过 Protocol 接口
- 显式定义事件合约（事件名、负载结构）
```python
# backend/app/domains/shared/events.py
from dataclasses import dataclass

@dataclass
class PointDataEvent:
    """ 监控领域发布：点位数据更新 """
    point_id: int
    device_id: int
    value: float
    timestamp: datetime

@dataclass
class AlarmTriggeredEvent:
    """ 告警领域发布：告警触发 """
    alarm_id: int
    level: str  # info/minor/major/critical
    device_id: int
    point_id: int
    message: str
```
### 7.4 按领域重组文件结构
当前问题：按技术层分包（models/alarm.py、services/alarm.py），同一领域的文件分散在不同目录。
整改方案：按领域分包，每个领域是一个自包含的目录。
```
当前结构（按技术层分包）：              建议结构（按领域分包）：
backend/app/                            backend/app/
├── api/v1/                             ├── domains/
│   ├── alarm.py                        │   ├── alarm/
│   ├── device.py                       │   │   ├── __init__.py    (公开 API)
│   ├── energy.py                       │   │   ├── routes.py      (API 路由)
│   └── ...                             │   │   ├── models.py      (ORM 模型)
├── models/                             │   │   ├── schemas.py     (Pydantic)
│   ├── alarm.py                        │   │   ├── services.py    (业务服务)
│   ├── device.py                       │   │   ├── engines.py     (引擎)
│   └── ...                             │   │   ├── events.py      (事件定义)
├── schemas/                            │   │   └── initializer.py (初始化)
│   ├── alarm.py                        │   ├── monitoring/
│   └── ...                             │   ├── energy/
├── services/                           │   ├── optimization/
│   ├── alarm_engine.py                 │   └── ...
│   └── ...                             ├── shared/            (共享基础设施)
└── engines/                            │   ├── events.py
    ├── alarm_engine.py                 │   ├── protocols.py
    └── ...                             │   └── event_bus.py
                                        └── core/              (不变)
```
### 7.5 通过 __init__.py 定义领域公开 API
每个领域的 `__init__.py` 显式导出允许外部访问的接口，未导出的内容视为领域内部实现。
```python
# backend/app/domains/alarm/__init__.py
""" 告警与联动领域 - 公开 API """

# 路由注册
from .routes import router as alarm_router

# 领域初始化
from .initializer import AlarmDomainInitializer

# 对外接口（其他领域可使用）
from .protocols import AlarmNotifier, AlarmQueryService

# 事件定义
from .events import AlarmTriggeredEvent, AlarmResolvedEvent

# 注意：以下内容不导出，为领域内部实现
# - alarm_engine 内部实现
# - escalation_engine 内部实现
# - action_handlers 内部实现
```
### 7.6 数据库迁移按领域前缀分组
当前问题：所有 Alembic 迁移文件混在一起，难以识别哪个迁移属于哪个领域。
整改方案：迁移文件命名加领域前缀，便于未来拆分时识别归属。
```
命名规范：
  {timestamp}_{domain}_{description}.py
示例：
  20260224_alarm_add_escalation_table.py
  20260224_energy_add_pue_history.py
  20260224_monitoring_add_point_quality_flag.py
```
---
## 8. 微服务拆分路线图
当系统规模进一步增长，或出现明确的性能瓶颈/团队协作瓶颈时，可按以下顺序逐步拆分为微服务。
### 8.1 拆分优先级与路线图
```
阶段          拆分目标          难度    理由
────────────────────────────────────────────────────────────────────────────────
Phase 1       采集网关            ★       已有独立 requirements.txt，
              (Gateway)                    与主应用耦合最低，
                                           可独立部署在边缘节点
Phase 2       认证与用户          ★★     JWT 无状态，边界清晰，
              (Auth)                       拆分后其他服务只需验证 token
Phase 3       能源管理 +            ★★★   最大领域（21 个服务文件），
              节能优化                       复杂度高，需先完成模块化整改
              (Energy + Optimization)       再拆分
Phase 4       告警与联动          ★★★   需将 event_bus 迁移为
              (Alarm)                      消息队列（Redis Pub/Sub 或
                                           RabbitMQ），影响面广
保留          监控与采集          -       核心领域，被多个领域依赖，
              (Monitoring)                 建议保留在单体中或最后拆分
```
### 8.2 Phase 1 详细方案：采集网关拆分
采集网关是最适合优先拆分的领域，原因如下：
- `backend/gateway/` 已是独立目录，有自己的 `requirements.txt`
- 与主应用的交互仅通过 API 调用和数据库写入
- 可部署在边缘节点，贴近采集设备
拆分步骤：
1. 将 `backend/gateway/` 升级为独立服务，添加自己的 FastAPI 入口
2. 网关服务通过 HTTP API 或 MQTT 向主应用推送采集数据
3. 主应用中的 `datasources.py`、`gateways.py`、`device_templates.py`、`ota.py` 路由迁移到网关服务
4. 保留主应用中的网关管理 API 作为代理层
### 8.3 Phase 2 详细方案：认证服务拆分
拆分步骤：
1. 将 `auth.py`、`user.py` 路由和 `user.py` 模型拆分为独立服务
2. 认证服务提供 JWT 签发/验证 API
3. 其他服务通过 JWT 公钥本地验证 token，无需调用认证服务
4. 用户信息通过 token payload 携带，减少跨服务查询
### 8.4 拆分前置条件
在进行任何微服务拆分之前，必须先完成以下模块化整改：
| 前置条件 | 对应整改建议 | 原因 |
|----------|------------|------|
| 领域初始化器 | 7.1 | 拆分后每个服务需要独立启动 |
| 显式接口 | 7.2 | 拆分后接口变为 RPC/HTTP 调用 |
| 事件合约 | 7.3 | event_bus 需迁移为消息队列 |
| 领域分包 | 7.4 | 文件结构清晰才能干净拆分 |
| 公开 API | 7.5 | 明确哪些接口需要跨服务暴露 |
| 迁移分组 | 7.6 | 数据库拆分时需识别归属 |
---
## 9. 前后端领域对齐
### 9.1 对齐矩阵
| 领域 | 后端 API 路由 | 前端 API 模块 | 前端视图 | Pinia Store |
|------|-------------|-------------|----------|-------------|
| 认证与用户 | `auth.py`、`user.py` | `auth.ts`、`user.ts` | `login/` | `user.ts` |
| 监控与采集 | `device.py`、`point.py`、`realtime.py` | `device.ts`、`point.ts`、`realtime.ts` | `device/`、`device-manage/`、`device-status/`、`environment/` | `realtime.ts` |
| 告警与联动 | `alarm.py`、`threshold.py`、`escalation.py`、`data_quality.py`、`linkage.py`、`diagnosis.py`、`command.py`、`drift.py` | `alarm.ts`、`threshold.ts`、`linkage.ts`、`command.ts`、`diagnosis.ts`、`drift.ts`、`dataQuality.ts` | `alarm/`、`linkage/`、`diagnosis/`、`security/` | `alarm.ts` |
| 能源管理 | `energy.py`、`power.py`、`pricing.py`、`demand.py`、`monitoring.py`、`topology.py`、`regulation.py`、`dispatch.py`、`optimization.py`、`vpp.py`、`cooling.py` | `energy.ts`、`power.ts`、`cooling.ts`、`demand.ts`、`monitoring.ts`、`dispatch.ts`、`optimization.ts`、`vpp.ts` | `energy/`、`power/`、`cooling/`、`vpp/`、`topology/` | `energy.ts` |
| 节能优化 | `opportunities.py`、`execution.py`、`proposal.py`、`ml.py` | `opportunities.ts`、`optimization.ts` | （复用 energy/ 视图） | `opportunity.ts` |
| 资产与运维 | `asset.py`、`capacity.py`、`spatial.py`、`topology_config.py`、`floor_map.py`、`operation.py` | `asset.ts`、`capacity.ts`、`spatial.ts`、`topologyConfig.ts`、`floorMap.ts`、`operation.ts` | `asset/`、`capacity/`、`topology/`、`operation/` | 无独立 Store |
| 采集网关 | `datasources.py`、`gateways.py`、`device_templates.py`、`ota.py` | `gateway.ts` | `datasource/`、`gateway/`、`device-template/` | 无独立 Store |
| 系统基础设施 | `config.py`、`system_health.py`、`demo.py`、`video.py`、`history.py`、`statistics.py`、`report.py`、`log.py`、`trace.py` | `config.ts`、`video.ts`、`history.ts`、`statistics.ts`、`report.ts`、`log.ts`、`bigscreen.ts`、`demo.ts` | `video/`、`history/`、`report/`、`settings/`、`system/`、`bigscreen/`、`dashboard/`、`common/` | `app.ts`、`bigscreen.ts`、`degradation.ts`、`site.ts` |
### 9.2 对齐度评估
| 评估维度 | 现状 | 说明 |
|----------|------|------|
| API 模块对应 | ★★★★ 良好 | 前端 38 个 API 模块与后端 47 个路由基本一一对应，部分后端路由无前端对应（如 escalation、regulation 等管理类 API） |
| 视图目录对应 | ★★★★ 良好 | 28 个视图目录覆盖所有业务领域，命名与后端领域基本一致 |
| Store 覆盖 | ★★★ 中等 | 10 个 Store 覆盖了核心领域，但资产与运维、采集网关缺少独立 Store |
| 领域边界一致性 | ★★★ 中等 | 前端按页面组织，后端按技术层组织，领域边界未显式对齐 |
### 9.3 前端模块化建议
1. 前端 API 模块按领域分组，与后端领域划分保持一致
2. 为资产与运维、采集网关领域添加独立的 Pinia Store
3. 视图目录命名与后端领域名称对齐，避免歧义（如 `device/` vs `device-manage/` vs `device-status/` 可合并为 `monitoring/`）
---
*文档版本: v1.0*
*创建日期: 2026-02-24*
*适用于: DCIM V3.0.0*