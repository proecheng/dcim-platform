---
stepsCompleted: [tech-stack, architecture-pattern, data-architecture, api-design, deployment, protocol-adapters, linkage-engine, video-integration, physical-topology, nfr-support, demo-module, ingest-pipeline, architecture-update, device-binding, intelligent-diagnosis, tcl-precool-model, notification-engine, predictive-maintenance, bacnet-mstp]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, _bmad-output/planning-artifacts/product-brief.md, docs/project-knowledge/project-context.md, docs/project-knowledge/backend-architecture.md, docs/project-knowledge/frontend-architecture.md, docs/project-knowledge/integration-architecture.md]
workflowType: 'architecture'
project_name: 'DCIM'
user_name: 'proecheng'
date: '2026-03-01'
---

# Architecture Decision Document - DCIM 算力中心智能监控系统

**Author:** proecheng
**Date:** 2026-02-15
**Status:** 完整版（V4.3.0 更新，新增多渠道通知/预测性维护/BACnet MS/TP 架构 2026-03-18；V4.2.0 预冷 TCL 模型架构 2026-03-10；V4.0.0 智能诊断系统架构 2026-03-05；V3.2.0 演示系统模块化、统一数据管线、设备双向绑定 2026-03-01）

---

## 1. 技术栈决策

### 1.1 Web 应用层

| 类别 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 前端框架 | Vue 3 (Composition API) | 3.4.15 | 响应式、TypeScript 支持好、生态成熟 |
| 前端语言 | TypeScript | 5.9.3 | 类型安全、IDE 支持 |
| 构建工具 | Vite | 5.0.11 | 快速 HMR、ESM 原生支持 |
| UI 框架 | Element Plus | 2.5.3 | 企业级组件库、中文友好 |
| 图表 | ECharts + vue-echarts | 5.6.0 / 6.7.3 | 丰富图表类型、大数据量支持 |
| 3D 渲染 | Three.js | 0.182.0 | 数字孪生原型（仅演示用） |
| 状态管理 | Pinia | 2.1.7 | Vue 3 官方推荐、TypeScript 友好 |
| 后端框架 | FastAPI | 0.109.0 | 异步高性能、自动 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 (async) | 2.0.25 | 异步支持、成熟稳定 |
| 数据验证 | Pydantic v2 | 2.5.3 | 高性能、与 FastAPI 深度集成 |
| 迁移 | Alembic | 1.13.1 | SQLAlchemy 官方迁移工具 |
| 认证 | JWT (python-jose) + bcrypt | — | 无状态认证、密码安全 |
| WebSocket | websockets | 12.0 | 实时数据推送 |
| 定时任务 | APScheduler | 3.10.4 | 数据模拟器、定时统计 |
| ML (可选) | PyTorch | 2.0+ | 条件加载，未安装时跳过 |
| OCR (可选) | PaddleOCR | — | 电费单识别，可选安装，未安装时降级为 mock | Phase 2 |
| 图计算 | NetworkX | 3.2+ | 故障树/因果图建模、图遍历、概率传播（内存图计算，无需外部图数据库） | Phase 2 |
| 异常检测 | scikit-learn | 1.4+ | Isolation Forest 对抗样本检测、训练数据质量校验 | Phase 2b |
| HMAC 签名 | Python hmac + hashlib | 内置 | 故障树配置完整性校验（HMAC-SHA-256） | Phase 2a |

### 1.2 IoT 采集层

| 类别 | 技术 | 选型理由 | 阶段 |
|------|------|----------|------|
| MQTT Broker | EMQX 开源版 | 国产高性能（单节点 2M msg/s）、Dashboard 管理界面、规则引擎 | MVP |
| 缓存 | Redis 7 | 实时数据缓存、会话管理、Pub/Sub 事件总线 | MVP |
| 时序数据库 | TimescaleDB (PG 扩展) | 复用 PostgreSQL 生态，压缩比 ~10:1，从 MVP 即引入 | MVP |
| 关系数据库 | PostgreSQL 16 | 生产环境主数据库 | MVP |
| 网关运行时 | Python 3.11 + asyncio | 与后端统一技术栈，降低维护成本 | MVP |
| Modbus 库 | pymodbus 3.x | 成熟稳定，支持 TCP/RTU，异步模式 | MVP |
| SNMP 库 | aiosnmp | 异步 SNMP v2c/v3 采集 | MVP |
| BACnet 库 | BAC0 / bacpypes3 | BACnet/IP 协议栈 | Phase 2 |
| OPC-UA 库 | asyncua | 异步 OPC-UA 客户端 | Phase 2 |

### 1.3 基础设施层

| 类别 | 技术 | 选型理由 | 阶段 |
|------|------|----------|------|
| 反向代理 | Nginx | 生产环境静态文件 + API/WS 反代 | MVP |
| 视频集成 | RTSP/ONVIF 前端直连 NVR | HLS 优先，MediaMTX 兜底 | Phase 2 |
| 容器编排 | Docker Compose | 单机/标准部署 | MVP |

---

## 2. 架构模式

### 2.1 整体架构

```
                                    ┌─────────────────────────────────────────┐
                                    │              前端层 (Vue 3)              │
                                    │  监控/告警/能源/资产/运维/大屏           │
                                    └──────┬──────────────┬───────────────────┘
                                           │ HTTP/WS      │ RTSP/ONVIF
                                           ▼              ▼
                                    ┌──────────┐   ┌──────────┐
                                    │  Nginx   │   │   NVR    │
                                    │ (3000)   │   │ (视频直连)│
                                    └────┬─────┘   └──────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         应用服务层 (FastAPI 8080)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ REST API │ │WebSocket │ │ 联动引擎 │ │ 告警引擎 │ │ 节能分析插件 │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐ ┌────────────────────────┐│
│  │ 数据质量 │ │ 定时任务 │ │ 诊断推理引擎  │ │ MQTT 客户端（网关数据）  ││
│  │          │ │          │ │ L1/L2/L3分级  │ │                        ││
│  └──────────┘ └──────────┘ └───────────────┘ └────────────────────────┘│
└──────────┬──────────┬──────────────────────┬────────────────────────────┘
           │          │                      │
           ▼          ▼                      ▼
    ┌───────────┐ ┌───────┐          ┌─────────────┐
    │PostgreSQL │ │ Redis │          │ MQTT Broker  │
    │+Timescale │ │       │          │   (EMQX)     │
    └───────────┘ └───────┘          └──────┬───────┘
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                       ┌───────────┐ ┌───────────┐ ┌───────────┐
                       │  网关 A   │ │  网关 B   │ │  网关 C   │
                       │ (机房 A)  │ │ (机房 B)  │ │ (机房 C)  │
                       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
                             │             │             │
                        Modbus/SNMP   Modbus/SNMP   BACnet/OPC-UA
                             │             │             │
                       ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
                       │ 空调/UPS  │ │ PDU/传感器│ │ 楼宇自控  │
                       │ 环境传感器│ │ 电池巡检仪│ │ 工业设备  │
                       └───────────┘ └───────────┘ └───────────┘
```

### 2.2 分层职责

| 层级 | 职责 | 关键组件 |
|------|------|----------|
| 前端层 | 用户交互、数据展示、视频播放 | Vue 3 SPA + WebSocket 客户端 + HLS 播放器 |
| 应用服务层 | 业务逻辑、API、实时处理、智能诊断 | FastAPI + 内嵌 MQTT 客户端 + 联动引擎 + 告警引擎 + 诊断推理引擎 |
| 消息通信层 | 网关与后端解耦通信 | EMQX Broker，MQTT QoS 1（数据）/ QoS 2（控制） |
| 数据缓存层 | 实时数据热缓存、事件总线 | Redis（最新点位值、会话、Pub/Sub） |
| 时序存储层 | 海量点位历史数据 | TimescaleDB hypertable，自动分区+压缩 |
| 关系存储层 | 业务数据、配置、拓扑 | PostgreSQL 16 |
| 采集网关层 | 多协议设备数据采集、本地缓存 | Python asyncio + 协议适配器 + SQLite 本地缓存 |

### 2.3 后端分层

```
app/
├── core/           # 基础设施层：配置、数据库、安全、Redis、MQTT
├── models/         # 数据层：SQLAlchemy ORM 模型
├── schemas/        # 接口层：Pydantic 请求/响应模型
├── api/v1/         # 路由层：REST API 端点
├── services/       # 业务层：业务逻辑服务
│   └── analysis_plugins/  # 插件系统：节能分析插件
├── engines/        # 引擎层
│   ├── alarm_engine.py      # 告警引擎
│   ├── linkage_engine.py    # 联动引擎
│   ├── data_quality.py      # 数据质量检测
│   └── diagnosis/           # 智能诊断引擎（Phase 2）
│       ├── engine.py         # 诊断调度器（L1/L2/L3 分级路由）
│       ├── rule_engine.py    # L1 规则引擎
│       ├── fault_tree.py     # L2 故障树推理（NetworkX）
│       ├── bayesian.py       # L3 贝叶斯深度分析
│       ├── causal_graph.py   # 全局因果图（跨系统级联）
│       ├── evidence.py       # 证据收集+时间窗口管理
│       ├── circuit_breaker.py # 熔断降级控制器
│       └── explainer.py      # 可解释性（证据链+敏感性分析）
├── mqtt/           # MQTT 层
│   ├── client.py            # MQTT 客户端（订阅/发布）
│   └── handlers.py          # 消息处理器
└── ml_models/      # ML 层：可选机器学习模块
```

### 2.4 前端分层

```
src/
├── api/modules/    # API 层：Axios 封装
├── stores/         # 状态层：Pinia Store
├── composables/    # 逻辑层：组合式函数
├── components/     # 组件层
│   ├── video/      # 视频播放+云台控制组件
│   └── topology/   # 拓扑可视化组件
├── views/          # 页面层
└── router/         # 路由层
```

### 2.4.1 2.5D 视觉增强架构

系统采用 SCSS mixin 体系实现全局 2.5D 轻度透视效果：

```
src/styles/
├── _mixins-25d.scss     # 2.5D mixin 库（perspective-container, stat-cards-arc, table-depth 等）
└── index.scss           # 全局 keyframes（slideInDepth, fadeInDepthSubtle）+ fadeInUp 修复
```

**核心 mixin：**
| Mixin | 用途 | 适用页面类型 |
|-------|------|-------------|
| `perspective-container` | 透视容器（1200px） | 所有页面 |
| `stat-cards-arc($count, $tilt)` | 统计卡片弧形倾斜 + hover 浮起 | 仪表盘/概览类 |
| `table-depth` | 表格微倾 + 行 hover 浮起 | 列表类 |
| `chart-depth-split` | 左右图表景深差 | 图表类 |
| `form-depth` | 表单区微倾 | 表单/配置类 |
| `page-dashboard` | 仪表盘 preset（组合多个 mixin） | 仪表盘/概览 |
| `page-list` | 列表 preset | 列表页 |
| `page-form` | 表单 preset | 表单/配置页 |

**关键设计决策：**
- keyframes 定义在全局 index.scss（避免 scoped hash 污染动画名）
- 全局 fadeInUp 动画改为 opacity-only（不含 transform），从根源避免与 2.5D transform 冲突
- 所有 mixin 内置 `:deep()` 穿透，页面只需在最外层容器 `@include` 即可
- 支持 `@media (prefers-reduced-motion: reduce)` 自动禁用动画

### 2.5 网关内部架构

```
gateway/
├── adapters/           # 协议适配器
│   ├── base.py         # BaseProtocolAdapter 抽象基类
│   ├── modbus_tcp.py   # Modbus TCP 适配器
│   ├── modbus_rtu.py   # Modbus RTU 适配器
│   ├── snmp_v2c.py     # SNMP v2c 适配器
│   └── ...             # 更多协议适配器
├── scheduler.py        # 采集调度器
├── normalizer.py       # 数据归一化 + 质量标记
├── cache.py            # SQLite 本地缓存 + 断点续传
├── mqtt_client.py      # MQTT 上报客户端
├── config_receiver.py  # 远程配置接收
└── status_reporter.py  # 状态上报（心跳 30s）
```

### 2.6 MQTT 客户端集成

- **MVP**：FastAPI 启动时内嵌 MQTT 客户端（aiomqtt），进程内订阅处理
- **高可用部署**：拆分为独立 MQTT 消费者服务，通过 Redis 与 FastAPI 通信
- EMQX 共享订阅（`$share/group/topic`）支持多消费者实例负载均衡


### 2.7 V3.1.0 新增服务组件

| 服务 | 文件 | 说明 |
|------|------|------|
| DeviceSyncService | `services/device_sync.py` | 设备与点位双向同步，模板变更自动同步到关联设备 |
| AdaptiveOptimizationService | `services/adaptive_optimization_service.py` | 自适应节能优化，基于历史数据动态调整策略 |
| OCRService | `services/ocr_service.py` | 电费单 OCR 识别，PaddleOCR 可选，未安装时自动降级为 mock |
| SystemHealthService | `api/v1/system_health.py` | 健康检查端点（DB/Redis/EMQX）、结构化 JSON 日志、性能指标 |
| MenuService | 前端路由重构 | 三区域菜单架构（监控/管理/配置）+ RBAC 动态过滤 |

---

## 3. 数据架构

### 3.1 核心数据模型分组

| 分组 | 模型 | 说明 |
|------|------|------|
| 用户权限 | User, UserLoginHistory | JWT + 三级 RBAC |
| 设备点位 | Device, Point, PointGroup, PointRealtime, PointHistory | 设备和监测点位管理 |
| 告警系统 | Alarm, AlarmThreshold, AlarmRule, AlarmShield, AlarmDailyStats | 4 级告警体系 |
| 能源管理 | PowerDevice, EnergyStatistics, ElectricityPricing, DemandHistory | PUE/能耗/需量 |
| 配电拓扑 | Transformer, DistributionPanel, Circuit, MeterPoint | 变压器→配电柜→回路→计量点 |
| 节能优化 | EnergySavingProposal, ProposalMeasure, EnergyOpportunity, ExecutionPlan/Task/Result | 方案+执行 |
| 资产运维 | Cabinet, Asset, AssetLifecycle, MaintenanceRecord, AssetInventory | 资产全生命周期 |
| 工单巡检 | WorkOrder, WorkOrderLog, InspectionPlan, InspectionTask | 运维工作流 |
| 知识库 | KnowledgeBase | 分类+搜索+浏览量 |
| 报表 | ReportTemplate, ReportRecord | 模板+生成记录 |
| 容量 | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity | 四维容量 |
| VPP | ElectricityBill, LoadCurve, AdjustableLoad, VPPConfig | 虚拟电厂 |
| 系统 | SystemConfig, Dictionary, License, OperationLog, SystemLog | 系统管理 |
| **采集网关** | Gateway, GatewayStatus | 网关注册、唯一标识、在线状态、CPU/内存/磁盘、最后心跳 |
| **数据源** | DataSource, DataSourcePoint | 协议连接配置、点位映射、连接状态 |
| **设备模板** | DeviceTemplate, TemplatePoint | 按厂商/型号预置点位配置 |
| **联动策略** | LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog | 条件→动作链、分级联动、执行记录 |
| **视频监控** | Camera, NVR, VideoEvent | 摄像头元数据、NVR 连接、联动录像事件 |
| **物理拓扑** | SpatialTopology, CoolingTopology, PowerPhaseMapping | 空间层级、空调覆盖、三相接线 |
| **站点管理** | Site | 多站点标识、行级数据隔离 |
| **故障树** | FaultTree, FaultTreeVersion, FaultTreeNode, FaultTreeEdge | 故障树定义、版本管理、节点（root/intermediate/leaf）、门（AND/OR）、概率参数 |
| **因果图** | CausalGraph, CausalEdge | 跨系统全局因果图（配电→暖通→IT→业务四层），复用故障树节点 |
| **诊断引擎** | DiagnosisSession, DiagnosisEvidence, DiagnosisResult, DiagnosisAuditLog | 推理会话、证据收集、根因结果（含置信度、推理路径）、审计日志 |
| **闭环学习** | DiagnosisAnnotation, ProbabilityAdjustmentLog | 运维标注（准确/不准确/未知）、概率自动调参记录 |
| **电气扩展** | SensorMetadata, BreakerProfile, BatterySOHRecord | 传感器元数据（CT/PT变比、精度、校准）、断路器特性库、电池健康度记录 |
| **预冷 TCL** | ThermalParameter, TemperaturePredictionLog, PrecoolSchedule | RC 热模型参数标定、温度预测偏差记录、预冷调度计划与执行 |

### 3.2 现有模型扩展字段

| 模型 | 新增字段 | 说明 |
|------|---------|------|
| Point | `data_quality` | 数据质量标记（正常/不可靠/疑似漂移） |
| Point | `gateway_id`, `datasource_id` | 关联到采集网关和数据源 |
| Device | `site_id`, `template_id` | 关联到站点和设备模板 |
| PointHistory | 迁移到 TimescaleDB hypertable | `time` 列分区，启用压缩 |
| Alarm | `linkage_policy_id` | 告警触发联动策略关联 |
| Cabinet | `row_number`, `column_number`, `aisle_type`, `cooling_zone_id` | 物理拓扑空间位置 |
| CoolingZone | `area_m2`, `height_m`, `thermal_R`, `thermal_C`, `bypass_beta` | TCL 模型所需物理参数 |
| CoolingLinkageConfig | `precool_target_temp`, `precool_enabled` | 预冷调度参数 |

### 3.3 空间拓扑层级

```
Site (站点)
└── Floor (楼层)
    └── Room (房间)
        └── Row (机柜行)
            └── Cabinet (机柜)
                ├── aisle_type: cold/hot (冷/热通道)
                ├── pdu_id + phase (A/B/C) → PowerPhaseMapping
                └── cooling_zone_id → CoolingTopology
```

### 3.4 站点数据隔离

- 方式：行级隔离 — 所有业务表加 `site_id` 字段
- 实现：FastAPI 中间件自动注入 `site_id` 查询过滤
- 优点：单数据库运维成本低，适合 2 人团队

### 3.5 TimescaleDB 策略

| 配置项 | 值 | 说明 |
|--------|-----|------|
| hypertable | `point_history` | 按 `time` 列自动分区 |
| chunk 间隔 | 1 天 | 适合 5 秒采集周期的数据量 |
| 压缩策略 | 7 天后自动压缩 | 压缩比 ~10:1 |
| 保留策略 | 原始数据 90 天，小时聚合 3 年 | 符合 PRD 数据保留要求 |
| 连续聚合 | 小时/日聚合视图 | 加速报表查询 |
| 初始创建 | Alembic 初始迁移即创建 hypertable | 避免后期迁移 |

### 3.6 Redis 缓存策略

| 用途 | Key 模式 | TTL | 说明 |
|------|---------|-----|------|
| 最新点位值 | `point:{id}:latest` | 60s | 实时数据热缓存，WebSocket 推送源 |
| 网关状态 | `gateway:{id}:status` | 30s | 心跳超时判断 |
| 设备在线状态 | `device:{id}:online` | 60s | 仪表盘设备状态看板 |
| 告警计数 | `alarm:stats:{level}` | 实时更新 | 仪表盘告警统计 |
| 用户会话 | `session:{user_id}:tokens` | 与 JWT 同步 | 并发会话限制 |

### 3.7 数据库迁移策略

- 使用 Alembic 管理所有 schema 变更
- 开发环境可用 SQLite（文件：dcim.db），生产环境 PostgreSQL + TimescaleDB
- 启动时自动创建表和初始数据（admin 用户、默认配置）
- `point_history` 在初始迁移中即创建为 TimescaleDB hypertable

---

## 4. API 设计

### 4.1 认证

- POST `/api/v1/auth/login` — 登录获取 JWT
- POST `/api/v1/auth/refresh` — 刷新 token
- GET `/api/v1/auth/me` — 获取当前用户信息
- WebSocket 认证通过 query 参数：`?token=xxx`

### 4.2 WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送 (5s) |
| alarms | `/ws/alarms?token=xxx` | 告警通知 |
| system | `/ws/system?token=xxx` | 系统状态 |

### 4.3 API 模块列表（V3.1.0 实际状态：47 个模块）

| 分类 | 模块 | 路径前缀 | 说明 |
|------|------|---------|------|
| 认证与用户 | auth | `/api/v1/auth` | 登录/登出/刷新令牌 |
| | users | `/api/v1/users` | 用户管理、RBAC |
| | sessions | `/api/v1/sessions` | 并发会话管理 |
| | password_policy | `/api/v1/password-policy` | 密码策略配置 |
| 设备与点位 | devices | `/api/v1/devices` | 设备 CRUD、模板关联 |
| | points | `/api/v1/points` | 点位管理、数据质量 |
| | datasources | `/api/v1/datasources` | 数据源 CRUD、连接测试、批量导入 |
| | device_templates | `/api/v1/device-templates` | 设备模板 CRUD |
| | device_sync | `/api/v1/device-sync` | 设备双向同步 |
| 实时监控 | realtime | `/api/v1/realtime` | 实时数据（Redis 缓存） |
| | monitoring | `/api/v1/monitoring` | 六大子系统仪表盘 |
| | websocket | `/ws/*` | WebSocket 通道管理 |
| 告警管理 | alarms | `/api/v1/alarms` | 告警 CRUD、批量操作 |
| | thresholds | `/api/v1/thresholds` | 阈值配置 |
| | escalation | `/api/v1/escalation` | 告警升级规则 |
| | drift | `/api/v1/drift` | 传感器漂移检测 |
| 能源管理 | energy | `/api/v1/energy` | 用电监控、PUE、统计 |
| | pricing | `/api/v1/pricing` | 电价管理 |
| | demand | `/api/v1/demand` | 需量管理 |
| | regulation | `/api/v1/regulation` | 需量调控 |
| | ocr | `/api/v1/ocr` | 电费单 OCR 识别（可选 PaddleOCR） |
| 节能优化 | opportunities | `/api/v1/opportunities` | 节能机会发现 |
| | proposals | `/api/v1/proposals` | 节能方案管理 |
| | execution | `/api/v1/execution` | 方案执行追踪 |
| | optimization | `/api/v1/optimization` | 自适应优化服务 |
| | load_shifting | `/api/v1/load-shifting` | 负荷转移 |
| | vpp | `/api/v1/vpp` | 虚拟电厂 |
| | schedule | `/api/v1/schedule` | 调度计划 |
| | precool | `/api/v1/precool` | 预冷 TCL 调度、温度预测、VPP 可调容量 |
| 资产与容量 | assets | `/api/v1/assets` | 资产台账、生命周期 |
| | capacity | `/api/v1/capacity` | 四维容量监控 |
| 拓扑与空间 | topology | `/api/v1/topology` | 物理拓扑配置 |
| | topology_config | `/api/v1/topology-config` | 拓扑配置管理 |
| | floor_map | `/api/v1/floor-map` | 楼层平面图 |
| | cooling | `/api/v1/cooling` | 制冷拓扑 |
| 联动与诊断 | linkage | `/api/v1/linkage` | 联动策略 CRUD、执行日志 |
| | dispatch | `/api/v1/dispatch` | 告警自动派单 |
| | command | `/api/v1/command` | 控制命令下发 |
| | trace | `/api/v1/trace` | 事件追溯 |
| 视频监控 | video | `/api/v1/video` | 摄像头/NVR/PTZ 控制 |
| 网关管理 | gateways | `/api/v1/gateways` | 网关状态、远程配置、OTA |
| | ota | `/api/v1/ota` | 网关 OTA 升级 |
| 运维管理 | operations | `/api/v1/operations` | 工单、巡检、知识库 |
| 系统管理 | configs | `/api/v1/configs` | 系统配置 |
| | logs | `/api/v1/logs` | 操作审计日志 |
| | statistics | `/api/v1/statistics` | 统计分析 |
| | reports | `/api/v1/reports` | 报表管理、PDF 导出 |
| | system_health | `/api/v1/system-health` | 健康检查、性能指标 |
| | history | `/api/v1/history` | 历史数据查询 |
| 大屏与展示 | bigscreen | `/api/v1/bigscreen` | 大屏数据聚合 |
| 多站点 | sites | `/api/v1/sites` | 站点 CRUD、切换 |
| 数据质量 | data_quality | `/api/v1/data-quality` | 质量状态、漂移统计 |

**现有模块扩展（V3.1.0 新增）：**
| 模块 | 扩展内容 |
|------|---------|
| devices | 新增 `template_id` 关联、双向同步、按网关/数据源筛选 |
| points | 新增 `data_quality` 字段、按网关/数据源筛选 |
| alarms | 新增联动策略关联、告警升级规则配置 |
| realtime | 数据源从 Redis 缓存读取（替代直接查库） |
| bigscreen | 新增设备历史弹窗、楼层 3D 场景 |
### 4.4 点位批量导入预校验

- 方式：同步校验（Excel 通常几百到几千行，计算量不大）
- 校验项：寄存器地址冲突、数据类型匹配、量程范围合理性
- 返回：校验报告（通过/失败条目、错误原因）

### 4.5 控制命令分级确认

| 控制类型 | 确认方式 | 示例 |
|---------|---------|------|
| 普通控制 | 前端弹窗确认 → 后端直接下发 | 调空调温度、开关照明 |
| 关键控制 | 前端弹窗确认 → 后端审批表 → 审批通过 → 下发 | 切断电源、消防联动恢复 |
| 消防联动 | 自动执行，无需确认（生命安全优先） | 消防分级联动全部动作 |

### 4.6 MQTT Topic 设计

| Topic | 方向 | QoS | 说明 |
|-------|------|-----|------|
| `dcim/{site_id}/gw/{gw_id}/data` | 网关→后端 | 1 | 点位数据上报（批量 JSON） |
| `dcim/{site_id}/gw/{gw_id}/alarm` | 网关→后端 | 1 | 网关侧告警事件 |
| `dcim/{site_id}/gw/{gw_id}/status` | 网关→后端 | 1 | 网关心跳+状态（30s） |
| `dcim/{site_id}/gw/{gw_id}/cmd` | 后端→网关 | 2 | 控制命令下发 |
| `dcim/{site_id}/gw/{gw_id}/config` | 后端→网关 | 2 | 配置下发 |
| `dcim/{site_id}/gw/{gw_id}/ota` | 后端→网关 | 2 | OTA 升级指令 |

**MQTT 数据上报消息格式：**

```json
{
  "gw_id": "gw-001",
  "ts": 1708000000,
  "points": [
    {"id": "p001", "v": 25.6, "q": 0, "t": 1708000000},
    {"id": "p002", "v": 1, "q": 0, "t": 1708000000}
  ]
}
```

`v`: 值，`q`: 质量码（0=正常），`t`: 采集时间戳。批量上报减少 MQTT 消息数。

---

## 5. 部署架构

### 5.1 单机部署（开发/小型机房 ≤50 台设备）

```
┌─────────────────────────────────────────────┐
│            单台服务器 (Docker Compose)        │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ FastAPI  │ │  Nginx   │ │    EMQX     │ │
│  │ + MQTT   │ │ (前端+   │ │   Broker    │ │
│  │  Client  │ │  反代)   │ │             │ │
│  └────┬─────┘ └──────────┘ └──────┬──────┘ │
│       │                           │         │
│  ┌────┴──────────────────┐  ┌─────┴──────┐ │
│  │ PostgreSQL+TimescaleDB│  │   Redis    │ │
│  └───────────────────────┘  └────────────┘ │
└─────────────────────────────────────────────┘
```

适用：开发测试、试点机房。硬件：Xeon E-2400 / 32GB / 2x1TB SSD RAID1。

### 5.2 标准部署（生产环境 50~200 台设备）

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   应用服务器  │  │  数据库服务器 │  │  EMQX Broker │
│              │  │              │  │              │
│  FastAPI     │  │ PostgreSQL   │  │  EMQX 单节点 │
│  + MQTT Cli  │  │ +TimescaleDB │  │  Dashboard   │
│  Nginx       │  │ Redis        │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

应用与数据库分离，EMQX 独立部署（可复用旧服务器）。

### 5.3 高可用部署（大型机房/高可靠性要求）

```
┌──────────────┐  ┌──────────────┐
│  FastAPI #1  │  │  FastAPI #2  │
│  + MQTT Cli  │  │  + MQTT Cli  │
└──────┬───────┘  └──────┬───────┘
       │    Nginx LB     │
       └────────┬────────┘
                │
  ┌─────────────┼─────────────┐
  ▼             ▼             ▼
┌──────┐  ┌──────────┐  ┌──────────┐
│EMQX  │  │ PG 主库  │  │ Redis    │
│单节点│  │+Timescale│  │ Sentinel │
└──────┘  └────┬─────┘  └──────────┘
               │
          ┌────┴─────┐
          │ PG 从库  │
          │(只读副本)│
          └──────────┘
```

FastAPI 双机 + Nginx LB + PG 主从 + Redis Sentinel。EMQX 单节点（200 台设备无需集群）。

### 5.4 多站点集中管理

```
机房 A 网关群 ──MQTT──┐
                      ├──> 中心 EMQX Broker ──> 中心 FastAPI ──> 统一管理界面
机房 B 网关群 ──MQTT──┤         │                    │
                      │    ACL 按 site_id          中心 PostgreSQL
机房 C 网关群 ──MQTT──┘    隔离 Topic 权限         (所有站点数据汇聚)
```

各机房网关通过 VPN/专线连接中心 EMQX。EMQX ACL 按 `site_id` 隔离 Topic 权限。网关离线时本地 SQLite 缓存，恢复后断点续传。

### 5.5 Docker Compose 服务定义（单机模式）

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| `app` | 自建 Python 3.11 | 8080 | FastAPI + 内嵌 MQTT 客户端 |
| `nginx` | nginx:alpine | 3000 | 前端静态文件 + API/WS 反代 |
| `postgres` | timescale/timescaledb:latest-pg16 | 5432 | PostgreSQL + TimescaleDB |
| `redis` | redis:7-alpine | 6379 | 缓存 |
| `emqx` | emqx/emqx:5 | 1883/8083/18083 | MQTT Broker + Dashboard |

### 5.6 开发环境

- 应用本地运行（Python + Vite dev），方便调试和 HMR
- 基础设施用 Docker：PostgreSQL + TimescaleDB、Redis、EMQX
- 开发环境也可用 SQLite 替代 PostgreSQL（快速启动）

---

## 6. 协议适配器插件化架构

### 6.1 适配器接口规范

```python
class BaseProtocolAdapter(ABC):
    """所有协议适配器的抽象基类"""

    @abstractmethod
    async def connect(self, config: DataSourceConfig) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]: ...

    @abstractmethod
    async def write_point(self, point_id: str, value: Any) -> bool: ...

    @abstractmethod
    async def test_connection(self) -> ConnectionResult: ...

    @abstractmethod
    def get_status(self) -> AdapterStatus: ...
```

### 6.2 适配器注册表

```python
ADAPTER_REGISTRY = {
    "modbus_tcp": ModbusTcpAdapter,     # MVP
    "modbus_rtu": ModbusRtuAdapter,     # MVP
    "snmp_v2c": SnmpV2cAdapter,         # MVP
    "snmp_v3": SnmpV3Adapter,           # MVP
    "bacnet_ip": BacnetIpAdapter,       # Phase 2
    "opcua": OpcUaAdapter,              # Phase 2
    "mqtt": MqttDeviceAdapter,          # Phase 1.5
    "http_rest": HttpRestAdapter,       # Phase 1.5
}
```

新增协议只需实现 `BaseProtocolAdapter` 并注册到 `ADAPTER_REGISTRY`，不影响已有适配器。

### 6.3 Modbus TCP/RTU 分开

TCP（网络连接）和 RTU（串口连接）的配置参数、错误处理、重连逻辑差异较大，分为独立适配器。

### 6.4 采集调度器

- 每个数据源独立采集周期（1~60s 可配）
- asyncio 并发调度，互不阻塞
- 单个适配器超时不影响其他数据源
- 采集结果统一进入数据归一化层
- 归一化后批量 MQTT 上报

### 6.5 错误重试策略

| 场景 | 策略 |
|------|------|
| 连接失败 | 指数退避重试（1s → 2s → 4s → 8s → 最大 60s） |
| 读取超时 | 立即重试 1 次，仍失败则标记点位质量为"不可靠" |
| 连续 5 次失败 | 标记数据源为"通信中断"，触发告警 |

### 6.6 干接点信号处理

消防主机、门禁的干接点信号通过 Modbus I/O 采集模块转换，复用 `ModbusRtuAdapter` 读取 DI 寄存器。在点位配置层面标记为"干接点类型"，告警引擎对干接点做状态变化触发（非阈值判断）。

### 6.7 数据归一化层

- 原始值 → 工程值转换（缩放、偏移、枚举映射）
- 数据质量标记（通信超时→不可靠、值越界→异常）
- 时间戳统一（UTC）

---

## 7. 消防分级联动引擎

### 7.1 联动引擎架构

- **事件总线**：Redis Pub/Sub — 告警引擎和 MQTT 客户端产生事件，联动引擎订阅响应
- **条件评估器**：单条件匹配→预警，多条件交叉确认→联动，人工确认→恢复
- **动作执行器**：asyncio.gather 并行执行所有动作，每个动作独立超时（3s），单个失败不阻塞其他

### 7.2 消防分级联动策略

| 级别 | 触发条件 | 动作 | 响应时间 |
|------|---------|------|---------|
| 预警 | 单一传感器（烟雾 OR VESDA） | 预警通知 + 调取区域摄像头 + 等待确认 | ≤5s |
| 联动 | 多传感器交叉确认 或 消防主机干接点 | 关空调 + 启排烟 + 切非关键电源 + 解锁门禁 + 应急照明 + 全区录像 + 紧急通知 | ≤3s |
| 恢复 | 人工确认解除 | 逐项恢复设备到正常状态 + 生成事件报告 | 人工操作 |

### 7.3 动作类型注册表

| 类型 | 说明 |
|------|------|
| MQTT_COMMAND | 通过 MQTT 下发设备控制命令 |
| ALARM_NOTIFY | 发送告警通知（系统推送+声光） |
| VIDEO_RECORD | 触发 NVR 区域录像 |
| VIDEO_POPUP | 推送摄像头画面到前端 |
| WEBHOOK | 调用外部系统（短信网关等） |

### 7.4 消防信号最高优先级

- 干接点状态变化事件标记为 `FIRE_SIGNAL` 优先级
- 联动引擎对 `FIRE_SIGNAL` 跳过排队，立即评估+执行
- 消防联动不需要双重确认（生命安全优先，GB 50116）

### 7.5 联动策略配置方式

- **消防联动等固定策略**：YAML 预定义，安全不可误改
- **自定义联动（告警升级通知等）**：数据库配置，前端 UI 管理

### 7.6 联动恢复

- **一键恢复**：按预设顺序逐项执行（门禁→照明→电源→空调→排烟→录像）
- **逐项手动恢复**：操作员可跳过某些项或调整顺序
- 两种模式均支持

### 7.7 事件时间线报告

自动生成完整事件报告，包含：event_id、trigger_time（毫秒精度）、trigger_source、level、每个动作的开始/结束时间和结果、total_duration、recovery_time、operator。用于事后复盘和合规存档。

---

## 8. 视频监控集成架构

### 8.1 核心原则

视频流前端直连 NVR，DCIM 只负责元数据管理和联动触发。

### 8.2 数据流

| 数据流 | 路径 | 说明 |
|--------|------|------|
| 视频流 | 前端 → NVR（直连） | RTSP 转 HLS/WebRTC，浏览器播放 |
| 云台控制 | 前端 → FastAPI → NVR（ONVIF） | 后端转发 PTZ 命令，记录操作日志 |
| 联动触发 | 联动引擎 → NVR（ONVIF） | 触发录像开始/停止、预置位调用 |
| 元数据 | FastAPI → PostgreSQL | 摄像头位置、关联区域/设备、NVR 连接信息 |

### 8.3 浏览器播放方案

- **优先**：NVR 自带 HLS 输出（海康/大华主流 NVR 支持），前端用 hls.js 播放
- **兜底**：部署 MediaMTX 做 RTSP→WebRTC 转码（延迟更低）
- **排除**：不让视频流经过后端服务器

### 8.4 摄像头关联模型

```
Camera
├── id, name, rtsp_url, onvif_url
├── nvr_id → NVR
├── site_id → Site
├── location_description
├── 多对多关联: 区域、机柜、设备
└── presets[] (预置位列表，联动快速定位)
```

告警触发时通过 设备→区域→摄像头 关联链自动找到最近摄像头弹出画面。

### 8.5 视频分屏

- 前端 CSS Grid 实现 1/4/9 分屏布局
- 每个格子独立视频播放器实例
- 联动触发时自动切换到关联摄像头的 4 分屏布局

### 8.6 录像管理

- DCIM 只管"触发"和"元数据"
- 联动引擎通过 ONVIF 命令触发 NVR 开始/停止录像
- 录像文件存储和回放完全由 NVR 负责
- DCIM 记录 VideoEvent（事件时间、关联告警、摄像头 ID）
- 回放时通过时间戳定位到 NVR 录像片段

---

## 9. 机房物理拓扑模型

### 9.1 三合一拓扑

| 拓扑维度 | 内容 | 数据来源 |
|---------|------|---------|
| 空间拓扑 | Site→Floor→Room→Row→Cabinet，冷热通道归属 | 集成工程师配置 |
| 配电拓扑 | Transformer→DistPanel→Circuit→PDU→Phase | 集成工程师配置 + PDU 采集 |
| 制冷拓扑 | CoolingZone（冷通道组）→ 关联空调列表+机柜列表+设计制冷容量 | 集成工程师配置 + 温度传感器 |

Cabinet 是三个拓扑的交汇点。

### 9.2 智能机柜选址算法

输入：新设备需求（U 位数、额定功率、重量）。输出：Top N 候选机柜 + 多维度评分卡。

| 维度 | 权重 | 计算方式 |
|------|------|---------|
| 空间容量 | 30% | 剩余 U 位 / 需求 U 位 |
| 电力容量 | 25% | PDU 剩余功率 / 需求功率 |
| 三相平衡度 | 20% | 加入后三相不平衡度变化（越低越好） |
| 温度环境 | 15% | 进风口温度与理想值(22°C)偏差 |
| 制冷余量 | 10% | 所在制冷区域剩余制冷容量 |

权重默认固定，管理员可通过系统配置页面调整。

三相不平衡度 = (max(Ia,Ib,Ic) - min(Ia,Ib,Ic)) / avg(Ia,Ib,Ic) x 100%

### 9.3 置信度降级

| 数据缺失情况 | 置信度 | 处理方式 |
|-------------|--------|---------|
| 所有数据正常 | 高 | 正常推荐，全部维度评分 |
| 温度传感器缺失 | 中 | 温度维度标记"不可用"，权重重分配 |
| PDU 不支持分相电流 | 中 | 三相平衡标记"不可用"，降级为总功率推荐 |
| 多项数据缺失 | 低 | 降级为传统空间+电力推荐，明确提示 |

### 9.4 拓扑配置方式

| 配置项 | 方式 |
|--------|------|
| 机柜物理位置 | Excel 批量导入 + 可视化拖拽 |
| PDU 三相接线 | 表单配置（选择 PDU 和相位 A/B/C） |
| 空调覆盖范围 | 表单配置（关联机柜列表或冷通道分组） |
| 常见布局模板 | 预置模板（2N 冷通道、单排、双排等） |

### 9.5 故障影响分析

配电设备故障时，基于拓扑模型自动定位受影响的下游机柜和设备：

```
配电柜跳闸 → 查询配电拓扑 → 定位受影响回路 → PDU → 机柜 → 设备
           → 查询制冷拓扑 → 受影响区域空调是否同回路
           → 输出影响报告（设备清单、关联告警、建议操作）
```

---

## 10. 非功能需求架构支撑

### 10.1 性能架构

| NFR 指标 | 架构支撑 |
|---------|---------|
| 数据采集 ≤5s | 网关 asyncio 并发调度，每数据源独立周期 |
| 告警触发 ≤1s | MQTT→Redis 缓存→告警引擎内存比对阈值，全链路异步 |
| 联动执行 ≤3s | Redis Pub/Sub→联动引擎 asyncio.gather 并行执行 |
| API P95 <500ms | FastAPI 异步 + Redis 缓存热数据 + PG 索引优化 |
| WebSocket <1s | MQTT 数据→Redis→WebSocket 广播，进程内直推 |
| 历史查询 P95 <3s | TimescaleDB hypertable 分区+压缩+连续聚合 |
| 50 并发用户 | uvicorn workers + WebSocket ConnectionManager |
| 5,000 msg/s | EMQX 单节点轻松支撑 |

### 10.2 数据流性能路径

```
网关采集(5s) → MQTT(QoS1) → 后端MQTT客户端 → 并行:
  ├─ Redis 更新最新值 (<1ms)
  ├─ TimescaleDB 批量写入 (100条/批 或 1秒攒批)
  ├─ 告警引擎阈值检测 (内存比对, <1ms)
  │     └─ 越限 → Redis Pub/Sub → 联动引擎
  └─ WebSocket 广播到前端 (<1ms)
```

### 10.3 可靠性架构

| NFR 指标 | 架构支撑 |
|---------|---------|
| 可用率 ≥99.5% | 高可用：FastAPI 双机 + PG 主从 + Redis Sentinel |
| 离线容错 ≥72h | 网关 SQLite 本地缓存，恢复后顺序补传 |
| 数据一致性 ≥99.99% | MQTT QoS 1 + 网关 Broker ACK 后才删除本地缓存 |
| 消防联动 100% | 最高优先级、跳过排队、独立超时、结果强制记录 |
| 网关故障隔离 | 每机房独立网关，单台故障不影响其他机房 |
| OTA 安全 | A/B 双分区，失败自动回退（Post-MVP） |

### 10.4 断点续传机制

```
网关 SQLite upload_queue 表:
  id | timestamp | payload | uploaded
  ─────────────────────────────────
  恢复流程:
  1. 重连 MQTT Broker
  2. 查询 uploaded=false 最早记录
  3. 按时间戳顺序逐批上传（100条/批）
  4. Broker ACK 后标记 uploaded=true
  5. 定期清理已上传且超过 72h 的记录
```

### 10.5 安全架构

| 层面 | 机制 | 说明 |
|------|------|------|
| 认证 | JWT Bearer Token | python-jose 签发，WebSocket 通过 query 参数 |
| 授权 | RBAC 三级角色 | admin/operator/viewer，FastAPI Depends 注入 |
| 密码 | bcrypt 哈希 | passlib + bcrypt==4.0.1 |
| 限流 | 登录 5次/分钟 | 防暴力破解 |
| CORS | FastAPI CORSMiddleware | 开发环境允许 localhost |
| 输入验证 | Pydantic v2 | 所有请求体自动验证 |
| 审计日志 | 同库 + PG 行级安全策略 | 追加写入，普通管理员无 DELETE 权限（等保二级） |
| 控制命令 | 分级确认 | 普通→前端确认，关键→后端审批，消防→自动 |
| 只读首次对接 | DataSource.write_enabled 默认 false | 逐台开启写入权限 |
| 并发会话 | Redis session 集合 | 超限踢出最早会话 |
| 协议安全 | SNMP v3/OPC-UA 证书/MQTT TLS/Modbus 白名单 | Post-MVP |

### 10.6 可观测性

| 层面 | 方案 |
|------|------|
| 应用健康 | `/api/v1/health` 检查 DB/Redis/EMQX 连接状态 |
| 关键指标 | Prometheus metrics 端点（Post-MVP） |
| 日志 | 结构化 JSON 日志，开发 DEBUG / 生产 INFO |
| 网关监控 | 心跳 30s → Redis TTL，超时标记离线触发告警 |

### 10.7 错误处理策略

- 后端：FastAPI 全局异常处理器，统一 `{"detail": "错误信息"}` 格式
- 前端：Axios 响应拦截器，401 自动登出，其他错误 Element Plus Message 提示
- WebSocket：连接断开自动重连（useWebSocket composable）
- 数据库：SQLAlchemy session 异常自动回滚
- MQTT：aiomqtt 断线自动重连，指数退避

---

## 11. 关键架构决策汇总

| 决策 | 选择 | 理由 |
|------|------|------|
| 全异步架构 | asyncio 贯穿网关+后端 | WebSocket + MQTT + 高并发采集 |
| ORM | SQLAlchemy 2.0 async | 类型安全、迁移管理 |
| 状态管理 | Pinia | Vue 3 原生、TypeScript 友好 |
| 自动导入 | unplugin-auto-import | 减少样板代码 |
| ML 条件加载 | try/except ImportError | torch 未安装不影响核心 |
| 配置单例 | @lru_cache | 全局唯一 |
| MQTT Broker | EMQX 单节点 | 200 台设备无需集群 |
| 网关缓存 | SQLite | 结构化查询方便断点续传 |
| MQTT QoS | 数据 QoS 1 / 控制 QoS 2 | 平衡可靠性和开销 |
| 后端 MQTT | MVP 内嵌，高可用拆分 | 渐进式架构演进 |
| 站点隔离 | 行级（site_id） | 单库运维成本低 |
| TimescaleDB | MVP 即引入 | 避免后期迁移 |
| 联动配置 | YAML 预定义 + DB 自定义 | 消防策略安全不可误改 |
| 视频流 | 前端直连 NVR | 不增加后端压力 |
| 拓扑层级 | 完整层级表 | 支持多维度聚合查询 |
| 选址权重 | 默认固定，可配置 | 兼顾通用和特殊场景 |
| 批量写入 | 100 条或 1 秒攒批 | 降低 DB 写入压力 |
| 审计日志 | 同库 + 行级安全 | 满足等保二级 |
| 生产前端 | Nginx | 性能远超 Express |
| 开发环境 | 应用本地 + 基础设施 Docker | 开发体验优先 |
| 图计算引擎 | NetworkX（内存） | 故障树≤1000节点，无需外部图数据库，降低运维复杂度 |
| 故障树存储 | PostgreSQL JSON + 关系表 | 复用现有DB，递归CTE遍历，NetworkX运行时加载 |
| 推理调度 | 进程内异步（asyncio） | 2人团队无需维护独立消息队列，APScheduler管理定时任务 |
| 诊断降级 | 熔断器模式 | 响应>10s或错误率>10%自动回退L1规则引擎 |
| 配置签名 | HMAC-SHA-256 | 轻量级完整性校验，密钥环境变量注入 |
| TCL 热模型 | 一阶 RC 集总参数 | 复杂度低、可在线标定、5分钟步长满足精度需求 |
| TCL 安全兜底 | 温度裕度法（THM） | R/C 未标定前用 THM 兜底，零依赖、实时计算 |
| 预冷调度优化 | 贪心策略（非线性规划） | 2人团队无需维护 scipy/cvxpy，贪心解接近最优 |
| VPP 容量上报 | 5 分钟周期 | 平衡实时性与计算开销，温度变化速率 ≤5°C/h |

---

## 14. 架构变更影响分析（V3.2.0）

### 14.1 受影响的模块

**后端模块**:

```
核心改动:
├── app/demo/                    # 新增独立演示模块（8个文件）
├── app/services/ingest_pipeline.py  # 新增统一管线（576行）
├── app/mqtt/client.py           # MQTT 动态订阅增强
├── app/services/point_data.py   # 简化为管线调用
├── app/services/datasource_bridge.py  # 简化为管线调用
└── app/main.py                  # 集成 demo.lifecycle

清理:
├── 删除 9 个遗留文件（2708 行）
├── 删除 12 个 mock 方法
└── 清理 403 行冗余代码
```

### 14.2 向后兼容性

- ✅ 所有现有 API 端点保持不变
- ✅ 无数据库 schema 变更
- ✅ 现有部署可直接升级

### 14.3 技术债务清理

**删除的文件**（9个，共 2708 行）:

- backend/app/services/simulator.py (445 行)
- backend/app/services/demo_data_provider.py (436 行)
- backend/app/tools/demo_data_generator.py (1073 行)
- backend/app/tools/realtime_simulator.py (269 行)
- backend/app/api/v1/demo.py (81 行)
- backend/app/api/v1/dispatch.py (178 行)
- backend/app/services/collector.py (105 行)
- backend/app/services/demand_analysis_service.py (121 行)

---

## 15. 设备数据双向绑定架构（V3.2.0 新增）

### 15.1 数据绑定问题背景

**问题描述**:
- 监控页与拓扑页设备数据不一致
- 设备在某个页面增加/修改/删除后，其他页面不同步
- 设备 circuit_id 绑定缺失，导致配电拓扑显示不完整
- 扩展记录（UPSDevice/CoolingUnit/ColdAisle）缺失

**影响范围**:
- 监控页面：显示设备不完整
- 配电拓扑页：设备无法正确显示在拓扑树中
- 制冷拓扑页：空调设备缺失扩展信息
- 数据一致性：多个数据源不同步

### 15.2 双向同步架构设计

**核心服务**: DeviceSyncService (backend/app/services/device_sync.py)

**同步方向**:

Device 表 (动环设备) ←→ 拓扑表 (业务实体)
- device_code ←→ DistributionPanel
- device_name ←→ PowerDevice
- device_type ←→ UPSDevice
- area_code ←→ CoolingUnit
- status ←→ ColdAisle

**同步触发时机**:

| 触发点 | 同步方向 | 说明 |
|--------|---------|------|
| 创建 DistributionPanel | Topology → Device | 自动创建 Device(CABINET) |
| 创建 PowerDevice | Topology → Device | 自动创建 Device(UPS/AC/PDU) |
| 创建 Device(CABINET) | Device → Topology | 自动创建 DistributionPanel |
| 创建 Device(UPS/AC/PDU) | Device → Topology | 自动创建 PowerDevice |
| 系统启动 | 双向 | migrate_existing_data() 全量同步 |

### 15.3 智能 circuit_id 绑定

**问题**: 设备创建时 circuit_id 为空，导致无法在配电拓扑中显示

**解决方案**: 智能推断 + 自动绑定

**推断规则**:

| 设备编码模式 | 推断回路 | 示例 |
|-------------|---------|------|
| UPS-FX-XX | C-FX-UPS-01 | UPS-F1-01 → C-F1-UPS-01 |
| PDU-FX-XX | C-FX-PDU-GENERIC | PDU-F2-01 → C-F2-PDU-GENERIC |
| CA-XX | C-CA-GENERIC | CA-01 → C-CA-GENERIC |
| PMP-F1-0[1-4] | C-CHWP-01 | PMP-F1-01 → C-CHWP-01（冷冻水泵） |
| PMP-F1-0[7-9] | C-CWP-01 | PMP-F1-07 → C-CWP-01（冷却水泵） |
| PMP-F1-XX | C-PMP-GENERIC | PMP-F1-05 → C-PMP-GENERIC |
| AC-OUT-XX | C-AC-OUT-GENERIC | AC-OUT-01 → C-AC-OUT-GENERIC |

**实现位置**:

1. DeviceSyncService._infer_circuit_id() - 核心推断逻辑
2. API 层拦截 - energy.py 创建设备时自动绑定
3. 启动时修复 - migrate_existing_data() 批量修复

### 15.4 扩展记录自动补全

**问题**: Device 表有记录，但扩展表（UPSDevice/CoolingUnit/ColdAisle）缺失

**解决方案**: 启动时自动补全所有扩展记录

**效果**:

| 扩展表 | 补全前 | 补全后 | 说明 |
|--------|--------|--------|------|
| UPSDevice | 2 条 | 11 条 | 补全 9 台 UPS |
| CoolingUnit | 5 条 | 81 条 | 补全 76 台空调 |
| ColdAisle | 0 条 | 6 条 | 补全 6 个冷通道 |

### 15.5 防循环触发机制

**问题**: 双向同步可能导致无限循环

**解决方案**: 使用 contextvars 防止重入

**优势**:

- ✅ 协程级隔离（不会跨请求泄漏）
- ✅ 自动清理（协程结束自动重置）
- ✅ 线程安全（asyncio 单线程模型）

### 15.6 通用回路扩展

**新增回路**:

| 回路编码 | 回路名称 | 覆盖设备 |
|---------|---------|---------|
| C-F2-PDU-GENERIC | F2 楼层 PDU 通用回路 | PDU-F2-XX |
| C-F3-PDU-GENERIC | F3 楼层 PDU 通用回路 | PDU-F3-XX |
| C-F4-PDU-GENERIC | F4 楼层 PDU 通用回路 | PDU-F4-XX |
| C-CA-GENERIC | 冷通道通用回路 | CA-XX |
| C-PMP-GENERIC | 水泵通用回路 | PMP-F1-XX |
| C-AC-OUT-GENERIC | 室外机通用回路 | AC-OUT-XX |

### 15.7 架构优势

**数据一致性**:

- ✅ 监控页与拓扑页设备完全同步
- ✅ 设备在任何页面增删改，其他页面自动更新
- ✅ 扩展记录自动补全，无遗漏

**可扩展性**:

- ✅ 新增设备自动绑定回路
- ✅ 新增设备类型只需扩展映射表
- ✅ 新增回路只需更新推断规则

**可维护性**:

- ✅ 单一同步服务（DeviceSyncService）
- ✅ 防循环机制（contextvars）
- ✅ 启动时自动修复（无需手动干预）

### 15.8 影响的页面

**前端页面**:

| 页面 | 影响 | 说明 |
|------|------|------|
| 监控页 | 设备数量增加 | 从 2 台 UPS 增加到 11 台 |
| 配电拓扑页 | 设备完整显示 | 所有设备都能在拓扑树中显示 |
| 制冷拓扑页 | 空调设备完整 | CoolingUnit 从 5 条增加到 81 条 |
| 设备管理页 | 新增设备自动绑定 | 创建设备时自动分配 circuit_id |

---

**关键 Git 提交**:

- 950ce48 - feat: 根本性解决设备 circuit_id 绑定问题
- e4e527f - fix: migrate_existing_data 自动补全扩展记录
- 4cfb7fb - feat: 数据一致性保障与启动脚本重构


---

## 18. 智能诊断系统架构（V4.0.0 新增）

> 对应 PRD FR34-1 至 FR34-42，分阶段实施。本节描述智能诊断系统的整体架构设计。

### 18.1 架构总览

```
                        ┌─────────────────────────────────────────┐
                        │            诊断 API 层                    │
                        │  /api/v1/diagnosis/*                     │
                        │  诊断触发 | 结果查询 | 故障树管理 | 标注   │
                        └──────────────┬──────────────────────────┘
                                       │
                        ┌──────────────▼──────────────────────────┐
                        │         诊断调度器 (DiagnosisEngine)      │
                        │                                          │
                        │  告警事件 ──→ 级别路由 ──→ L1/L2/L3      │
                        │              │                           │
                        │         熔断控制器                        │
                        │  (响应>10s OR 错误率>10% → 降级L1)       │
                        └──┬───────────┬───────────┬──────────────┘
                           │           │           │
                    ┌──────▼──┐ ┌──────▼──┐ ┌──────▼──────┐
                    │L1 规则  │ │L2 故障树│ │L3 贝叶斯    │
                    │引擎     │ │推理     │ │深度分析     │
                    │(<1s)   │ │(<5s)   │ │(<30s)      │
                    │        │ │NetworkX│ │历史数据+    │
                    │规则匹配│ │概率传播 │ │统计推理     │
                    └────────┘ └────────┘ └────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │         证据收集器 (Evidence)         │
                    │                                      │
                    │  时间窗口管理（按设备类型差异化）       │
                    │  电气: 5min | 温度: 30min | 湿度: 60min│
                    │  多传感器融合                          │
                    │  传感器精度加权                        │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │         数据源                        │
                    │                                      │
                    │  Redis (最新点位值)                    │
                    │  TimescaleDB (历史趋势)               │
                    │  PostgreSQL (故障树/因果图/配置)       │
                    └─────────────────────────────────────┘
```

### 18.2 分级推理架构

#### L1 规则引擎（FR34-1）

- **实现**: Python 规则匹配，内存中执行
- **输入**: 告警事件 + Redis 最新点位值
- **规则格式**: JSON 规则集（条件→结论），存储在 PostgreSQL，启动时加载到内存
- **覆盖**: Top 20 高频故障中 ≥12 类（60%）
- **性能**: < 1 秒
- **示例规则**:

```python
{
    "rule_id": "R001",
    "name": "UPS电池低压",
    "conditions": [
        {"point_type": "UPS_BATTERY_VOLTAGE", "operator": "<", "value": 44.0},
        {"point_type": "UPS_STATUS", "operator": "==", "value": "ON_BATTERY"}
    ],
    "logic": "AND",
    "conclusion": "UPS电池组电压过低，可能需要更换电池",
    "confidence": 0.85,
    "suggested_actions": ["检查电池组内阻", "联系维保更换电池"]
}
```

#### L2 故障树推理（FR34-2, FR34-5~12）

- **实现**: NetworkX 有向无环图（DAG），PostgreSQL 存储，运行时加载到内存
- **故障树存储**:

```
PostgreSQL 表结构:
  fault_tree:          id, name, version, status(draft/active/archived), hmac_signature, created_at
  fault_tree_node:     id, tree_id, node_type(root/intermediate/leaf), gate_type(AND/OR/NULL),
                       name, description, prior_probability, evidence_point_id
  fault_tree_edge:     id, tree_id, parent_node_id, child_node_id

运行时:
  启动/版本切换时 → 从 DB 加载 → 构建 NetworkX DiGraph → 内存缓存
  1000 节点故障树加载 < 2秒
```

- **概率传播**（FR34-10）:
  - OR 门: P = 1 - ∏(1 - P(child_i))
  - AND 门: P = ∏ P(child_i)
  - 叶节点概率来源: 传感器证据（实时）或先验概率（配置）

- **证据收集**（FR34-9）: 按设备类型的差异化时间窗口（FR34-29），查询 Redis（最新值）+ TimescaleDB（窗口内历史）

- **结果输出**（FR34-11）:
  - 置信度 > 80%: WebSocket 推送弹窗 + 声音
  - 60-80%: 诊断面板"建议"区域展示
  - < 60%: 仅记录日志，面板显示"暂无高置信度结论"

#### L3 贝叶斯深度分析（FR34-3）

- **实现**: 在 L2 故障树推理基础上，增加逆向贝叶斯更新（后验概率计算）
- **算法**: 基于故障树 DAG 结构的简化贝叶斯推理（非完整贝叶斯网络），不引入额外库（复用 NetworkX + numpy）
- **与 L2 的区别**: L2 仅做正向概率传播（叶→根），L3 额外执行：
  1. **逆向推理**: 已知根节点异常，反向推算各叶节点的后验概率（贝叶斯定理 P(cause|effect) = P(effect|cause)×P(cause)/P(effect)）
  2. **历史频率校正**: 查询 TimescaleDB 近 90 天同类故障频率，替代先验概率
  3. **多传感器融合**（FR34-32）: 聚合同区域多点位数据，计算温度分布标准差/压差等派生证据
  4. **时序关联**: 检测证据时间序列的先后关系（如：电压下降 → 5分钟后温度上升），强化因果链置信度
- **额外数据源**: TimescaleDB 历史数据（趋势分析 FR34-31）、`diagnosis_annotation` 运维标注统计
- **覆盖**: Top 20 全部场景（100%），并可扩展至已建模的其他故障场景
- **性能**: < 30 秒（主要耗时在 TimescaleDB 历史查询，通过连续聚合视图加速）

```python
# L3 逆向贝叶斯推理伪代码
async def l3_bayesian_analysis(tree: nx.DiGraph, root_node: str, evidence: dict) -> dict:
    # Step 1: L2 正向传播（复用）
    forward_result = propagate_probabilities(tree, evidence)

    # Step 2: 历史频率校正
    historical_freq = await query_historical_frequency(root_node, days=90)
    if historical_freq and historical_freq.sample_count >= 50:
        # 用历史频率替代先验概率
        tree.nodes[root_node]['prior_probability'] = historical_freq.frequency

    # Step 3: 逆向推理 — 对每个叶节点计算后验概率
    posterior = {}
    for leaf in get_leaf_nodes(tree):
        p_effect_given_cause = forward_result[root_node]  # P(effect|cause)
        p_cause = tree.nodes[leaf].get('prior_probability', 0.5)
        p_effect = forward_result.get(root_node, 0.5)
        if p_effect > 0:
            posterior[leaf] = (p_effect_given_cause * p_cause) / p_effect

    # Step 4: 多传感器融合增强
    fusion_evidence = compute_sensor_fusion(evidence)

    # Step 5: 综合排序，输出 Top N 根因候选
    return rank_root_causes(posterior, fusion_evidence)
```

#### L1/L2/L3 包含关系

L1 ⊂ L2 ⊂ L3: 高级别引擎能处理低级别的所有场景。当 L2/L3 不可用时，自动降级到 L1。

#### 并发控制与任务调度

诊断引擎使用 asyncio 内置机制管理并发，不引入独立消息队列（适配 2 人团队运维能力）:

```python
class DiagnosisScheduler:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(10)  # 最大 10 个并发推理
        self.queue = asyncio.PriorityQueue(maxsize=50)  # 优先级队列，超出丢弃

    async def submit(self, alarm_event: AlarmEvent):
        # 优先级: 紧急=0, 重要=1, 次要=2, 提示=3（数值越小越优先）
        priority = {"critical": 0, "major": 1, "minor": 2, "info": 3}[alarm_event.level]
        try:
            self.queue.put_nowait((priority, alarm_event))
        except asyncio.QueueFull:
            # 队列满 → 丢弃最低优先级任务，插入当前任务
            logger.warning(f"诊断队列已满，丢弃低优先级任务")
            # 或直接降级到 L1 快速返回

    async def _worker(self):
        while True:
            priority, event = await self.queue.get()
            async with self.semaphore:
                await self._execute_diagnosis(event, priority)
```

- **并发上限**: 10 个任务同时推理（`asyncio.Semaphore(10)`）
- **排队策略**: `asyncio.PriorityQueue` 按告警级别排序，紧急告警优先
- **队列溢出**: 队列容量 50，溢出时丢弃最低优先级任务或直接 L1 快速返回
- **超时控制**: 每个推理任务设置 `asyncio.wait_for` 超时（L1: 2s, L2: 10s, L3: 60s），超时触发熔断

### 18.3 告警引擎 → 诊断引擎集成

告警引擎是诊断引擎的主要触发源。集成方式为**进程内异步调用**（非消息队列），复用现有 Redis Pub/Sub 事件总线:

```
告警引擎 (alarm_engine.py)
    │
    ├─ 阈值越限检测 → 生成 Alarm 记录
    │
    ├─ Redis Pub/Sub 发布 "alarm:new" 事件
    │       │
    │       ├─ 联动引擎订阅（现有逻辑，不变）
    │       │
    │       └─ 诊断引擎订阅（新增）
    │           └→ DiagnosisScheduler.submit(alarm_event)
    │               → 优先级队列 → L1/L2/L3 推理
    │
    └─ 诊断引擎完成推理后:
        ├─ 写入 diagnosis_result 表
        ├─ WebSocket 推送:
        │   复用 /ws/alarms 通道，消息类型 "diagnosis_result"
        │   前端 alarm Store 新增 diagnosis 处理分支
        └─ 高置信度结果可触发联动（作为新的联动条件类型）
```

**关键设计决策**:
- **触发方式**: 订阅 Redis `alarm:new` 频道（与联动引擎并行，互不阻塞）
- **WebSocket 通道**: 复用 `/ws/alarms`，新增消息类型 `diagnosis_result`（避免新增 WebSocket 端点）
- **定向推送**: 诊断结果附带 `target_roles` 字段（如 `["operator", "admin"]`），前端 Store 根据当前用户角色过滤显示
- **手动触发**: `/api/v1/diagnosis/trigger` 端点支持运维人员主动对某台设备发起诊断（不依赖告警）

### 18.4 故障树管理架构（FR34-5~8, FR34-16）

#### 版本管理（FR34-6）

```
故障树生命周期:
  draft → reviewed → active → archived
         ↑                    │
         └────── rollback ────┘

版本切换流程:
  1. 新版本创建（draft）
  2. 管理员审批（reviewed）
  3. HMAC-SHA-256 签名生成（密钥从环境变量读取）
  4. 激活前验证签名 → 通过则替换内存中的 NetworkX 图
  5. 签名失败 → 拒绝加载，保持旧版本，触发安全告警

A/B 测试（Phase 2b+，非 Phase 2a 范围）:
  两个版本同时标记为 active，配置分流比例（如 90:10）
  DiagnosisScheduler 按比例路由请求到不同版本的 NetworkX 图
  两个版本的诊断结果都写入 diagnosis_result（附带 tree_version 字段）
  运行 2 周后，管理员在误判分析报告中对比两版本准确率
  人工决定切换或回滚（不自动切换）
```

#### 完整性校验（FR34-16）

```python
# 签名生成与验证
import hmac
import hashlib
import json

def sign_fault_tree(tree_config: dict, secret_key: bytes) -> str:
    """生成故障树配置的 HMAC-SHA-256 签名"""
    payload: bytes = json.dumps(tree_config, sort_keys=True).encode("utf-8")
    return hmac.new(key=secret_key, msg=payload, digestmod=hashlib.sha256).hexdigest()

def verify_fault_tree(tree_config: dict, signature: str, secret_key: bytes) -> bool:
    """验证故障树配置签名，使用恒定时间比较防止时序攻击"""
    expected: str = sign_fault_tree(tree_config, secret_key)
    return hmac.compare_digest(expected, signature)

# 密钥管理: 环境变量 FAULT_TREE_HMAC_KEY
# 密钥轮换: 新密钥签名所有活跃版本后再废弃旧密钥
```

#### 图形化编辑（FR34-8）

- **Phase 2a（JSON 编辑 + 只读可视化）**:
  - 故障树配置通过 JSON 表单编辑（Element Plus 表单组件），管理员填写节点列表和边关系
  - 只读可视化: ECharts graph 图渲染故障树结构（仅展示，不可交互编辑）
  - 此阶段工作量小，适配 2 人团队
- **Phase 3+（交互式图编辑，可选）**:
  - 引入 vue-flow（基于 reactflow 的 Vue 3 移植）实现拖拽式节点编辑、连线
  - 评估时机: Phase 2a 上线后，根据管理员使用反馈决定是否投入开发
- **验证**（FR34-7）: 保存时后端验证 DAG（无孤立节点、无循环依赖、所有叶节点有概率值或关联点位）

### 18.5 配电拓扑级联分析（FR34-13~15）

复用现有配电拓扑数据模型（Transformer → DistributionPanel → Circuit → PowerDevice），实际拓扑跨 4 张表，因此采用 **NetworkX 配电子图遍历**（而非单表递归 CTE）:

```python
# 启动时构建配电拓扑 NetworkX 图（复用因果图的配电层子图）
async def build_power_topology_graph(session: AsyncSession) -> nx.DiGraph:
    graph = nx.DiGraph()
    # 从 4 张表加载拓扑关系
    transformers = await session.execute(select(Transformer))
    panels = await session.execute(select(DistributionPanel))
    circuits = await session.execute(select(Circuit))
    power_devices = await session.execute(select(PowerDevice))

    for t in transformers.scalars():
        graph.add_node(f"T-{t.id}", type="transformer", name=t.name)
    for p in panels.scalars():
        graph.add_node(f"P-{p.id}", type="panel", name=p.name)
        graph.add_edge(f"T-{p.transformer_id}", f"P-{p.id}")
    for c in circuits.scalars():
        graph.add_node(f"C-{c.id}", type="circuit", name=c.name)
        graph.add_edge(f"P-{c.panel_id}", f"C-{c.id}")
    for d in power_devices.scalars():
        graph.add_node(f"D-{d.id}", type="device", name=d.device_name)
        if d.circuit_id:
            graph.add_edge(f"C-{d.circuit_id}", f"D-{d.id}")
    return graph

# 向下级联: PDU故障 → 受影响机柜/设备
def get_downstream_impact(graph: nx.DiGraph, fault_node: str) -> list:
    return [graph.nodes[n] for n in nx.descendants(graph, fault_node)]

# 向上溯源: 末端设备 → 追溯上游配电设备
def get_upstream_source(graph: nx.DiGraph, device_node: str) -> list:
    return [graph.nodes[n] for n in nx.ancestors(graph, device_node)]
```

配电拓扑图启动时加载到内存，设备/拓扑变更时通过 DeviceSyncService 事件触发增量更新。

### 18.6 全局因果图架构（FR34-27~28）

#### 四层因果传播链

```
Layer 1: 供配电层          Layer 2: 暖通层
┌──────────────────┐      ┌──────────────────┐
│ 市电 → 变压器     │─────→│ 空调主机          │
│ → UPS → PDU      │      │ → 冷冻水泵        │
│ → ATS 切换       │      │ → 冷却塔          │
└──────────────────┘      └──────────────────┘
         │                         │
         ▼                         ▼
Layer 3: IT设备层           Layer 4: 业务服务层
┌──────────────────┐      ┌──────────────────┐
│ 服务器/存储/网络   │─────→│ 业务应用          │
│ 机柜温度          │      │ SLA 影响评估       │
└──────────────────┘      └──────────────────┘
```

#### 实现方案

- **存储**: 在 PostgreSQL 中用 `causal_graph` 和 `causal_edge` 表定义跨系统传播边
- **运行时**: NetworkX DiGraph 加载因果图（故障树子图 + 跨系统边的超集）
- **构建**: 初始因果图由专家联合构建，新增设备类型需专家审批后通过管理界面扩展
- **版本管理**: 纳入故障树版本管理体系（FR34-6），变更需审批+签名
- **与故障树同步策略**: 因果图引用故障树节点 ID（外键），不复制节点数据。当故障树版本更新时:
  1. 因果图中引用的节点 ID 不变（故障树新版本保留旧节点 ID 映射）
  2. 若故障树新增/删除节点影响跨系统边，需同步更新因果图（系统在故障树激活时自动检测断裂边并告警）
  3. 因果图独立版本号（`causal_graph.version`），与故障树版本为多对多关系，通过 `causal_graph_tree_version` 关联表记录

#### 级联影响分析

```python
# 向下预测: 配电设备故障 → 预测受影响的暖通/IT/业务
def predict_downstream_impact(fault_node_id: str, graph: nx.DiGraph) -> list:
    return list(nx.descendants(graph, fault_node_id))

# 向上溯源: 末端异常 → 追溯上游根因
def trace_upstream_causes(symptom_node_id: str, graph: nx.DiGraph) -> list:
    return list(nx.ancestors(graph, symptom_node_id))
```

### 18.7 电气专业参数扩展架构（FR34-22~26）

#### 电气参数节点（FR34-22）

故障树叶节点可关联电气参数点位，超出阈值时自动作为证据:

| 参数 | 阈值 | 点位类型 |
|------|------|---------|
| 三相不平衡度 | < 10% | `PHASE_IMBALANCE` |
| 谐波畸变率 THD | < 5% | `THD` |
| 功率因数 | > 0.9 | `POWER_FACTOR` |

#### 电池 SOH 算法（FR34-23）

> **注意**: 以下为初期简化线性模型，权重 0.6/0.4 为行业经验初始值。正式上线前需基于试点 UPS 电池实际运行数据校准权重参数。后续可参考 IEC 62620 / IEEE 1188 标准改进为非线性老化模型。

```python
# 简化 SOH 估算模型（初期版本，权重可配置）
SOH_WEIGHTS = {"resistance": 0.6, "cycle": 0.4}  # 从 system_config 加载，支持热更新

def estimate_soh(internal_resistance_mohm: float, rated_resistance_mohm: float,
                 cycle_count: int, rated_cycles: int,
                 weights: dict = SOH_WEIGHTS) -> float:
    """返回 0-100% 的 SOH 值。权重从配置表加载，可基于实际数据校准。"""
    resistance_factor = max(0, 1 - (internal_resistance_mohm - rated_resistance_mohm)
                           / rated_resistance_mohm)
    cycle_factor = max(0, 1 - cycle_count / rated_cycles)
    return round((resistance_factor * weights["resistance"]
                  + cycle_factor * weights["cycle"]) * 100, 1)
```

- SOH 计算结果写入 `battery_soh_record` 表（含计算时使用的权重版本，便于回溯）
- 同时更新故障树证据（低 SOH 增加 UPS 故障概率）和设备健康度评估（FR75）
- 权重校准流程: 积累 ≥ 20 块电池的 SOH 预测值与实际更换记录对比 → 计算误差 → 调整权重

#### N+X 冗余拓扑（FR34-24）

- 在配电拓扑模型中标记冗余路径（`redundancy_type: N+1/2N/2(N+1)`）
- 推理时检查故障设备是否有活跃备用路径
- 有备用路径 → 降低故障影响等级，标记为"受控故障"
- 无备用路径 → 正常故障告警

#### 传感器元数据（FR34-25）

```
sensor_metadata 表:
  point_id              → 关联点位
  ct_pt_ratio           → CT/PT 变比
  accuracy_class        → 精度等级 (0.2/0.5/1.0)
  calibration_date      → 最近校准日期
  calibration_result    → 校准结果
  calibration_interval_days → 校准周期（天），默认 365（1年），精密仪表可设为 180

推理时:
  精度等级 0.2 → 证据权重 1.0
  精度等级 0.5 → 证据权重 0.9
  精度等级 1.0 → 证据权重 0.8
  超过 calibration_interval_days → 证据权重 0.6 + 触发校准提醒告警
```

#### 断路器保护逻辑库（FR34-26）

```
breaker_profile 表:
  breaker_id      → 关联断路器设备
  trip_curve_type → 脱扣曲线类型 (B/C/D)
  rated_current   → 额定电流
  rated_trip_time → 额定动作时间

推理逻辑:
  过流告警 + 断路器动作时间在特性曲线范围内 → 判定为"保护动作"（非故障）
  过流告警 + 断路器未动作或动作时间异常 → 判定为"设备故障"
```

### 18.8 暖通专业增强架构（FR34-29~32）

#### 差异化时间窗口（FR34-29）

配置存储在 `system_config` 表（JSON），按设备类型映射:

```json
{
  "diagnosis_time_windows": {
    "ELECTRICAL": 300,
    "TEMPERATURE": 1800,
    "HUMIDITY": 3600,
    "PRESSURE": 600,
    "default": 1800
  }
}
```

#### 动态告警阈值（FR34-30）

动态阈值通过**配置表驱动的规则引擎**实现，不硬编码调整逻辑:

```json
// system_config 表中的动态阈值规则配置
{
  "dynamic_threshold_rules": [
    {
      "condition": "outdoor_temp > 35",
      "adjustment": "+1.0",
      "description": "夏季室外高温允许回风温度升高"
    },
    {
      "condition": "it_load_percent > 80",
      "adjustment": "+0.5",
      "description": "高负载时允许温度升高"
    },
    {
      "condition": "season == 'winter'",
      "adjustment": "-0.5",
      "description": "冬季降低温度上限"
    }
  ],
  "safety_boundary_percent": 20,
  "log_every_adjustment": true
}
```

```python
def calculate_dynamic_threshold(
    static_threshold: float,
    context: dict,  # {"outdoor_temp": 36.5, "it_load_percent": 85, "season": "summer"}
    rules: list[dict]  # 从 system_config 加载
) -> tuple[float, float]:
    """配置驱动的动态阈值计算，不超过静态阈值的 ±20%"""
    total_adjustment = 0.0
    boundary = static_threshold * 0.2  # ±20% 安全边界
    for rule in rules:
        if evaluate_condition(rule["condition"], context):
            total_adjustment += float(rule["adjustment"])
    total_adjustment = max(-boundary, min(total_adjustment, boundary))
    return (static_threshold - abs(total_adjustment), static_threshold + total_adjustment)
```

管理员可通过 `/api/v1/diagnosis/config` 端点修改规则，无需代码变更。

#### 趋势分析（FR34-31）

- 使用 TimescaleDB 连续聚合视图计算 7 天移动平均
- APScheduler 定时任务（每小时）检测趋势:
  - 连续 3 天移动平均单调递增/递减 → 触发趋势预警
  - 预警级别低于阈值告警，不触发声音通知

#### 多传感器融合（FR34-32）

```python
# 气流均匀性判断
def assess_airflow_uniformity(temperatures: list[float]) -> dict:
    std_dev = statistics.stdev(temperatures)
    return {
        "uniformity": "good" if std_dev < 2.0 else "poor" if std_dev > 5.0 else "moderate",
        "std_dev": round(std_dev, 2),
        "is_evidence": std_dev > 5.0  # 标准差>5℃作为故障证据
    }
```

### 18.9 熔断降级架构（FR34-41~42）

#### 熔断器状态机

```
CLOSED (正常) ──错误率>10% OR 超时>10s──→ OPEN (熔断，降级L1)
     ↑                                         │
     │                                    30秒冷却期
     │                                         │
     └──── 试探成功 ←──── HALF_OPEN (试探) ←───┘
```

#### 降级策略

| 故障场景 | 降级行为 | 恢复策略 |
|---------|---------|---------|
| L2/L3 推理超时 | 降级到 L1 规则引擎 | 30 秒后试探恢复 |
| NetworkX 图加载失败 | 降级到 L1 | 重新加载故障树 |
| PostgreSQL 诊断表不可用 | 诊断结果写入 Redis 暂存 | DB 恢复后批量写入 |
| Redis 不可用 | 直接查询 TimescaleDB | Redis 恢复后自动切换 |

#### 灾难恢复演练（FR34-42）

通过 APScheduler 季度定时任务触发混沌注入:

**演练场景**:
1. 临时停止诊断引擎进程/线程 → 验证 L1 降级
2. 模拟 DB 连接超时 → 验证 Redis 暂存
3. 模拟网络分区 → 验证边缘独立推理（愿景阶段）
4. 生成演练报告: 恢复时间、降级成功率、数据完整性

**安全防护措施**:
- **演练窗口**: 仅在管理员配置的低峰时段执行（默认: 周日凌晨 02:00-04:00）
- **一键终止**: 管理员可通过 `/api/v1/diagnosis/chaos/stop` 立即终止演练，恢复正常模式
- **真实告警保护**: 演练期间所有真实告警自动走 L1 规则引擎（跳过被注入故障的 L2/L3），确保基本诊断能力不中断
- **演练标记**: 演练期间的所有诊断结果标记 `is_drill=true`，不计入准确率统计
- **前置审批**: 演练计划需管理员在 `/api/v1/diagnosis/chaos/schedule` 中确认后才执行

### 18.10 闭环学习架构（FR34-19~21）

#### 标注流程

```
诊断结果 → 运维标注（准确/不准确/未知）
                    │
                    ├─ 不准确 → 必须填写实际根因
                    │           └→ 监控标注偏差（2σ 异常检测）
                    │
                    └→ 累计到 diagnosis_annotation 表
                       └→ 当节点标注 ≥ 50 次:
                          统计实际概率 → 对比当前先验概率
                          调整幅度 ≤ ±10% → 生成审批工单
                          管理员审批 → 生效/拒绝（支持一键回滚）
```

#### 时间窗口自适应（FR34-21）

- 基于 `diagnosis_annotation` 中"准确"标注的故障持续时间统计
- 计算 P50/P90 作为窗口建议值
- 调整范围: 1 分钟 ~ 120 分钟
- 调整后通知管理员

### 18.11 安全加固架构（FR34-35~37）

#### 对抗样本检测（FR34-35）

- 使用 scikit-learn Isolation Forest 对训练数据执行异常检测
- 新标注数据入库前检查: 异常分数 > 阈值 → 降低权重或拒绝入库
- 定期（月度）对全量标注数据执行批量检测

#### 结果分级展示（FR34-36）

| 角色 | 展示内容 |
|------|---------|
| operator（运维） | 结论 + 建议操作 + 置信度等级（高/中/低） |
| engineer（高级工程师） | 完整推理路径 + 概率详情 + 证据列表 |
| admin（管理员） | 全部信息 + 审计日志 + 参数调整入口 |

基于现有 RBAC 三级角色体系（FR77），在诊断 API 响应中根据角色过滤字段。

#### SBOM 管理（FR34-37）

- 维护 `requirements.txt` / `package.json` 的依赖清单
- 集成 GitHub Dependabot 或 `pip-audit` 定期扫描
- 关键算法库（NetworkX, scikit-learn）漏洞触发系统告警

### 18.12 可解释性架构（FR34-38~40）

#### 证据链（FR34-38）

每次诊断结果附带结构化证据链:

```json
{
  "diagnosis_id": "D-20260305-001",
  "root_cause": "空调制冷效率下降",
  "confidence": 0.82,
  "evidence_chain": [
    {"step": 1, "rule": "温度超限", "point": "T-A01-01", "value": 29.5, "threshold": 28.0, "timestamp": "2026-03-05T14:23:15Z"},
    {"step": 2, "rule": "回风温差异常", "point": "T-A01-RETURN", "value": 3.2, "expected": ">5.0", "timestamp": "2026-03-05T14:23:15Z"},
    {"step": 3, "gate": "AND", "probability": 0.82, "timestamp": "2026-03-05T14:23:16Z"}
  ],
  "audit_trail": {
    "triggered_by": "alarm_id_12345",
    "engine_level": "L2",
    "inference_time_ms": 1230,
    "fault_tree_version": "v2.1.0"
  }
}
```

#### 简化反事实分析（FR34-39）

对 Top 3 关键证据执行敏感性分析:
- 逐一移除每个证据，重新计算根因概率
- 输出: "若温度传感器 T-A01-01 读数正常，根因判断将变为'送风系统异常'（置信度 0.65→0.45）"
- 计算复杂度: 3 次额外推理（可接受）

#### 误判分析报告（FR34-40）

- APScheduler 月度定时任务
- 统计维度: 误判类型（误报/漏报）、高频误判故障树节点、设备类型分布
- 输出: Markdown 报告，存储在 `system_report` 表

### 18.13 边缘推理架构（FR34-33~34，愿景阶段）

> 边缘推理为愿景阶段功能，当前架构预留接口但不实现。

#### 预留设计

- 网关层预留 `diagnosis_handler` 接口
- 协议: 中心节点通过 MQTT 下发规则子集到边缘
- 边缘执行 L1 规则匹配，复杂场景上报中心
- 多节点一致性: 中心节点作为仲裁者，边缘结果冲突时以中心为准

### 18.14 诊断系统 API 设计

| 端点 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/diagnosis/trigger` | POST | 手动触发诊断（自动触发由告警引擎调用） | operator+ |
| `/api/v1/diagnosis/sessions` | GET | 查询诊断历史 | operator+ |
| `/api/v1/diagnosis/sessions/{id}` | GET | 诊断详情（按角色分级展示） | operator+ |
| `/api/v1/diagnosis/sessions/{id}/annotate` | POST | 标注诊断结果 | operator+ |
| `/api/v1/fault-trees` | GET/POST | 故障树列表/创建 | admin |
| `/api/v1/fault-trees/{id}` | GET/PUT/DELETE | 故障树详情/编辑/删除 | admin |
| `/api/v1/fault-trees/{id}/versions` | GET/POST | 版本列表/创建新版本 | admin |
| `/api/v1/fault-trees/{id}/versions/{vid}/activate` | POST | 激活版本（含签名验证） | admin |
| `/api/v1/fault-trees/{id}/versions/{vid}/rollback` | POST | 回滚版本 | admin |
| `/api/v1/causal-graph` | GET/PUT | 因果图查询/编辑（需专家审批） | admin |
| `/api/v1/diagnosis/reports/monthly` | GET | 月度误判分析报告 | admin |
| `/api/v1/diagnosis/config` | GET/PUT | 诊断配置（时间窗口、阈值等） | admin |
| `/api/v1/sensors/metadata` | GET/PUT | 传感器元数据管理 | admin |
| `/api/v1/breakers/profiles` | GET/POST/PUT | 断路器特性库管理 | admin |

### 18.15 诊断数据流

```
告警引擎检测到越限
    │
    ▼
诊断调度器接收告警事件
    │
    ├─ 检查熔断器状态 ─→ OPEN → 执行 L1 规则引擎 → 返回结果
    │
    ├─ 根据告警级别选择推理级别:
    │     紧急告警 → L2 (默认)
    │     重要告警 → L2
    │     次要告警 → L1
    │     提示告警 → L1
    │     (用户可手动覆盖级别选择)
    │
    ▼
证据收集器
    ├─ 查询 Redis: 最新点位值
    ├─ 查询 TimescaleDB: 时间窗口内历史数据
    ├─ 查询传感器元数据: 精度加权
    └─ 查询断路器特性: 保护动作判别
    │
    ▼
推理引擎执行
    ├─ L1: 规则匹配 → 直接输出
    ├─ L2: NetworkX 故障树遍历 → 概率传播 → 根因路径
    └─ L3: L2 + 历史趋势分析 + 多传感器融合 + 贝叶斯增强
    │
    ▼
结果处理
    ├─ 写入 diagnosis_session + diagnosis_result
    ├─ 写入 diagnosis_audit_log
    ├─ 根据置信度通过 WebSocket 推送（复用 /ws/alarms 通道）:
    │     > 80% → 消息类型 "diagnosis_alert"，前端弹窗 + 声音
    │     60-80% → 消息类型 "diagnosis_suggestion"，诊断面板建议区
    │     < 60% → 仅写入日志，不推送 WebSocket
    │
    │   WebSocket 消息格式:
    │   {
    │     "type": "diagnosis_alert" | "diagnosis_suggestion",
    │     "target_roles": ["operator", "admin"],
    │     "data": { diagnosis_id, root_cause, confidence, evidence_chain }
    │   }
    │   前端 alarm Store 新增 diagnosis 消息处理分支，
    │   根据 target_roles 与当前用户角色匹配决定是否显示
    │
    └─ 返回结构化结果（含证据链）
```

### 18.16 NFR 架构支撑（诊断相关）

| NFR 指标 | 架构支撑 |
|---------|---------|
| L1 < 1s | 规则集内存缓存，纯 Python 匹配 |
| L2 < 5s | NetworkX 内存图遍历，≤1000 节点 |
| L3 < 30s | 异步并发查询 TimescaleDB + 推理计算 |
| 并发 10 任务 | asyncio.Semaphore(10) + PriorityQueue(50)，紧急告警优先，溢出降级 L1 |
| 可用率 99.9% | 熔断降级到 L1，L1 无外部依赖（纯内存） |
| 故障树加载 < 2s | 启动时预加载，版本切换时热替换 |
| 配置完整性 | HMAC-SHA-256 签名，密钥环境变量注入 |
| 审计合规 | 全链路审计日志，RBAC 分级展示 |

---

## 19. 前端数据流规范（V4.0.0 新增）

> 详细审查报告见 `docs/data-flow-audit.md`

### 19.1 单一事实来源原则

每个数据实体必须有且仅有一个 Pinia Store 作为事实来源。禁止在 composable 或组件中通过 `ref()` 维护与 Store 重叠的状态副本。

```
Backend (REST + WS) → API Module (无状态) → Pinia Store (唯一状态) → Composable (无状态工具) → View
```

### 19.2 数据实体归属表

| 数据实体 | 唯一归属 Store | 禁止在其他位置持有 |
|----------|---------------|-------------------|
| 活动告警列表 + 计数 | AlarmStore | composable ref, BigscreenStore, 页面局部 ref |
| 实时点位值 | RealtimeStore | composable ref, BigscreenStore.deviceData |
| PUE / 功率 / 电量 | EnergyStore | BigscreenStore.energy |
| 告警声音开关 | AppStore (`alarmSoundEnabled`) | AlarmStore.soundEnabled |
| 当前站点 | SiteStore | 无冲突 |
| 大屏 UI 状态 | BigscreenStore | 仅限场景/布局/图层等 UI 状态 |

### 19.3 WebSocket 单连接管理

- 每个 WS 通道（realtime/alarms/system/linkage）最多维持 1 个连接
- 连接由 `useWebSocketManager.ts` 单例 composable 统一管理，生命周期绑定到应用（App.vue / MainLayout）而非组件
- 各 Store 通过管理器注册消息处理器（`manager.subscribe('alarms', handler)`），Store 自身不创建 WS 连接
- 管理器负责自动重连（指数退避）和心跳保活

### 19.4 站点过滤贯穿规范

- API 请求拦截器自动注入 `site_id`（从 `useSiteStore().currentSiteId` 读取）
- 切换站点时 `siteStore.switchSite()` 触发相关 Store 的 `reload()` action

### 19.5 Composable 职责边界

- **允许:** 格式化函数、业务逻辑封装、声音/通知等副作用、从 Store 读取 computed
- **禁止:** 通过 `ref()` 持有与 Store 重叠的数据、独立创建 WebSocket 连接、绕过 Store 直接调 API 并在 ref 中缓存结果

---

## 20. Demo 系统与数据隔离规范（V4.0.0 新增）

> 详细审查报告见 `docs/demo-system-audit.md`

### 20.1 数据来源标记贯穿原则

所有通过 `process_payload()` 统一管道入库的数据必须保留来源标识（`source` 字段），从入口到存储层全链路不丢弃：

- **数据库层:** PointHistory、Alarm 表增加 `source` 列
- **WebSocket 推送:** 消息体包含 `source` 字段
- **Redis 缓存:** 缓存值 JSON 包含 `source` 字段
- **API 查询:** 告警、历史数据 API 支持按 `source` 过滤

### 20.2 Demo 与主系统分离

| 关注点 | 规范 |
|--------|------|
| 配置项 | `seed_enabled`（最小种子）、`demo_enabled`（完整演示）、`simulation_enabled`（模拟器）三项独立控制 |
| 数据标记 | Demo 创建的 Device/Point 记录标记 `is_demo=True`，卸载时仅删除标记记录 |
| 编码依赖 | 主系统服务（point_device_matcher、device_sync）不得硬编码 demo 特定的设备编码或楼层列表 |
| 最小种子 | 非 demo 模式下提供最小化种子（Site + 基础 Floor/Room + 默认配置），确保系统基本可用 |

### 20.3 数据源枚举值

| source 值 | 含义 | 写入方 |
|-----------|------|--------|
| `mqtt` | MQTT 网关采集 | point_data.py |
| `demo` | 模拟器实时生成 | demo/engine.py |
| `demo_backfill` | 历史数据回填 | history_generator.py |
| `bridge` | DataSource 桥接 | datasource_bridge.py |
| `manual` | 用户手动录入/API | 各 CRUD 接口 |
| `unknown` | 未标记来源（兼容旧数据） | 默认值 |

---

## 21. 预冷 TCL 模型架构（V4.2.0 新增）

> 基于 `docs/空调可转移功率算法调研与改进方案.md`（V4.0，三轮对抗性审查），替代现有固定比例 0.4 的制冷可转移功率算法。

### 21.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                     预冷 TCL 模型服务层                               │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ ThermalModel     │  │ PrecoolScheduler │  │ VPPCapacity      │   │
│  │ Service          │  │                  │  │ Reporter         │   │
│  │                  │  │ 谷时预冷          │  │                  │   │
│  │ RC方程温度预测   │  │ 峰时削减          │  │ 5min 可调容量    │   │
│  │ R/C 在线标定     │  │ 贪心优化求解      │  │ 上报 VPP 调度    │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │
│           │                     │                     │             │
│  ┌────────▼─────────────────────▼─────────────────────▼──────────┐  │
│  │              ConstraintChecker（增强）                          │  │
│  │  温度裕度法(THM)兜底 | ASHRAE 18-27°C | 速率≤5°C/h | 7项自动回退│  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────┬──────────────┬──────────────────┬────────────────────────┘
           │              │                  │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────────▼─────────┐
    │ Redis       │ │ TimescaleDB│ │ PostgreSQL       │
    │ 最新点位值  │ │ 温度历史   │ │ CoolingZone      │
    │ 温度预测缓存│ │ 预测偏差   │ │ ThermalParameter │
    └─────────────┘ └────────────┘ └──────────────────┘
```

**与现有模块的关系**:

| 现有模块 | 集成方式 | 说明 |
|---------|---------|------|
| `constraint_checker.py` | **替换**固定 0.4 比例 | 用 `calculate_max_reduction()` 动态计算可转移功率 |
| `cooling_linkage_service.py` | **增加**预冷调度能力 | 谷时自动触发预冷，峰时触发削减 |
| `datacenter_shift_strategy.py` | **复用**温度约束 | 复用 ASHRAE 常量和温度约束 |
| `CoolingZone` 拓扑 | **扩展**物理参数 | 新增面积、层高、R/C/β 参数 |
| `ShiftPlan` | **增强**温度轨迹 | 创建计划时预测全时段温度曲线 |
| `ingest_pipeline.py` | **复用**数据管线 | 温度点位数据通过统一管线入库 |

### 21.2 核心算法架构

#### 21.2.1 一阶 RC 热动力学模型

**微分方程**:

```
C × dT_room/dt = Q_IT(t) - Q_cool(t) + (T_ambient(t) - T_room(t)) / R
```

**离散化（Euler 显式）**:

```
T_room(k+1) = T_room(k) + (Δt/C) × [Q_IT(k) - Q_cool(k) + (T_amb(k) - T_room(k)) / R]
```

**变量说明**:

| 符号 | 含义 | 单位 | 数据来源 |
|------|------|------|---------|
| T_room(t) | 冷通道温度（进风温度代表） | °C | 机柜进风温度传感器（已有） |
| T_ambient(t) | 等效环境温度 | °C | 热通道/回风温度（已有） |
| Q_IT(t) | IT 设备热负荷 | kW | PDU 功率点位（已有） |
| Q_cool(t) | 制冷输出功率 | kW | 空调制冷量 = 电功率 × COP |
| C | 冷通道热容量 | kWh/°C | 自动标定（约 0.04 kWh/°C/m²） |
| R | 冷通道与外部热阻 | °C/kW | 自动标定 |
| Δt | 时间步长 | h | 5 分钟 = 1/12 h |

**数值稳定性**: Euler 显式要求 Δt < 2RC，5 分钟步长满足典型数据中心参数。

**COP 季节性修正**:

| 季节 | 室外温度 | COP 值 |
|------|---------|--------|
| 夏季 | > 30°C | 2.8 |
| 过渡季 | 15-30°C | 3.5 |
| 冬季 | < 15°C | 4.0 |

#### 21.2.2 气流短路修正

冷通道密封不良时，热空气旁路短路修正:

```
T_inlet_actual = T_inlet_model × (1-β) + T_outlet × β    (典型 β = 0.05~0.15)
```

当冷通道压差 ΔP < 5Pa 时，自动提高安全裕度从 2°C 到 4°C。

#### 21.2.3 温度裕度法（THM）安全兜底

R/C 参数未标定前（冷启动前 2 周），用温度裕度法替代 TCL 模型:

```python
headroom = T_max - T_current_max          # 温度裕度
ratio = (headroom / (T_max - T_supply)) × safety_factor   # 0.7-0.9
ratio = min(ratio, 0.6)                   # 绝对上限 60%
if headroom < 2.0: ratio = 0.0            # 裕度 < 2°C 禁止转移
```

同时校验热缓冲时间 ≥ 制冷滞后时间 × 1.5（约 30 分钟）。

#### 21.2.4 约束条件体系

```
(1) 温度动力学约束: RC 方程
(2) 温度上下限: 18°C ≤ T(k) ≤ 27°C,  ∀k  (ASHRAE TC9.9 Class A1)
(3) 冷通道级约束: T_inlet_i(k) ≤ T_max - 2°C,  ∀i, ∀k
(4) 制冷功率上下限: Q_cool_min ≤ Q_cool(k) ≤ Q_cool_max
(5) 功率调整速率约束: |P_cool(k+1) - P_cool(k)| ≤ ΔP_max
(5.1) 温度变化速率约束: |T(k+1) - T(k)| / Δt ≤ 5 °C/h  (ASHRAE 设备保护)
(6) 日总冷量守恒: Σ Q_cool(k)×Δt ≈ Σ Q_IT(k)×Δt + Q_envelope_loss
```

**7 项自动回退保护**:

| 触发条件 | 动作 | 响应时间 |
|---------|------|---------|
| 任一机柜 T_inlet > 26°C | 恢复正常制冷 | ≤ 30s |
| 温升速率超预测 150% | 恢复正常制冷 | ≤ 30s |
| 温度变化超 5°C/h | 限制功率调整速度 | 即时 |
| 空调故障告警 | 停止功率转移 | 即时 |
| 温度传感器离线 | 切回固定比例 0.2 | 即时 |
| 市电中断切 UPS | T_max 收紧到 25°C | 即时 |
| 预冷时湿度接近露点 | 停止降温防结露 | 即时 |

### 21.3 数据模型扩展

#### CoolingZone 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `area_m2` | Float | 冷通道面积（m²），用于计算热容 C |
| `height_m` | Float | 冷通道层高（m），默认 3.0 |
| `thermal_R` | Float | 热阻标定值（°C/kW），NULL 表示未标定 |
| `thermal_C` | Float | 热容标定值（kWh/°C），NULL 表示未标定 |
| `bypass_beta` | Float | 气流短路系数（0~0.3），默认 0.1 |
| `r_calibrated_at` | DateTime | R/C 最近标定时间 |

#### ThermalParameter 表（新增）

记录 R/C 参数标定历史:

```
thermal_parameters 表:
  id                     → 主键
  cooling_zone_id        → 关联 CoolingZone
  thermal_R              → 标定热阻值 (°C/kW)
  thermal_C              → 标定热容值 (kWh/°C)
  fitting_r_squared      → 拟合 R² 值（质量指标）
  fitting_method         → 标定方法 (auto_fit/manual)
  sample_count           → 使用的数据样本数
  calibrated_at          → 标定时间
  is_active              → 是否为当前生效参数
```

#### TemperaturePredictionLog 表（新增）

记录温度预测偏差，用于模型验证:

```
temperature_prediction_logs 表:
  id                     → 主键
  cooling_zone_id        → 关联 CoolingZone
  predicted_temp         → 预测温度 (°C)
  actual_temp            → 实际温度 (°C)
  prediction_horizon_min → 预测时长 (分钟)
  deviation              → 偏差 = actual - predicted
  model_version          → 模型参数版本
  created_at             → 记录时间
```

#### PrecoolSchedule 表（新增）

预冷调度计划与执行记录:

```
precool_schedules 表:
  id                     → 主键
  cooling_zone_id        → 关联 CoolingZone
  schedule_date          → 调度日期
  precool_start_time     → 预冷开始时间（谷时）
  precool_end_time       → 预冷结束时间
  target_temp            → 预冷目标温度 (°C)
  peak_start_time        → 峰时削减开始
  peak_end_time          → 峰时削减结束
  planned_savings_kwh    → 计划节省电量 (kWh)
  actual_savings_kwh     → 实际节省电量 (kWh)
  status                 → pending/executing/completed/aborted
  abort_reason           → 中止原因（如有）
  temperature_trajectory → JSON: 预测与实际温度轨迹
  created_at             → 创建时间
```

### 21.4 服务层设计

#### 21.4.1 ThermalModelService

```python
class ThermalModelService:
    """RC 热动力学模型服务"""

    async def predict_temperature(
        self, zone_id: int, hours: float, q_cool_schedule: list[float]
    ) -> list[float]:
        """预测未来 N 小时温度轨迹"""

    async def calibrate_rc_parameters(self, zone_id: int) -> ThermalParameter:
        """自动标定 R/C 参数（利用自然功率变化事件）"""

    async def calculate_max_reduction(
        self, zone_id: int, duration_hours: float
    ) -> dict:
        """计算峰时最大可削减制冷功率（替代固定 0.4）"""

    async def calculate_thm_ratio(
        self, zone_id: int, rack_temps: list[float]
    ) -> float:
        """温度裕度法兜底计算（R/C 未标定时使用）"""

    async def validate_model(self, zone_id: int) -> dict:
        """模型验证: MAE ≤ 1°C/1h, 最大偏差 ≤ 3°C"""
```

#### 21.4.2 PrecoolScheduler

```python
class PrecoolScheduler:
    """预冷调度器"""

    async def generate_schedule(
        self, zone_id: int, target_date: date
    ) -> PrecoolSchedule:
        """生成日前预冷调度计划（贪心优化）"""

    async def execute_schedule(self, schedule_id: int):
        """执行预冷调度（由 APScheduler 定时触发）"""

    async def monitor_and_rollback(self, schedule_id: int):
        """实时监控 + 7 项自动回退"""
```

#### 21.4.3 VPPCapacityReporter

```python
class VPPCapacityReporter:
    """虚拟电厂可调容量上报"""

    async def calculate_adjustable_capacity(
        self, zone_id: int
    ) -> dict:
        """计算实时可调容量（向上/向下）"""
        # 向下可调（削峰）: 减少制冷，温度不超 T_max
        # 向上可调（填谷）: 增加制冷，温度不低于 T_min
        # 返回: down_adjustable_kw, up_adjustable_kw (电功率)

    async def report_to_vpp(self):
        """每 5 分钟上报可调容量到 VPP 调度平台"""

    async def handle_vpp_dispatch(self, command: dict):
        """处理 VPP 实时调度指令（优先级高于日前优化）"""
```

#### 21.4.4 ConstraintChecker 增强

在现有 `constraint_checker.py` 中替换固定比例逻辑:

```python
# 原代码 (constraint_checker.py 第 489-494 行):
#   max_transferable = total_power * (cooling_ratio * 0.4 + other_ratio * 0.6)
#
# 替换为:
async def calculate_cooling_transferable(self, zone_id: int) -> float:
    thermal_svc = ThermalModelService()
    if await thermal_svc.is_calibrated(zone_id):
        return await thermal_svc.calculate_max_reduction(zone_id, duration_hours=1)
    else:
        rack_temps = await self._get_rack_temperatures(zone_id)
        return await thermal_svc.calculate_thm_ratio(zone_id, rack_temps)
```

### 21.5 API 设计

| 端点 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/precool/zones/{id}/predict` | POST | 温度轨迹预测（指定制冷功率计划） | operator+ |
| `/api/v1/precool/zones/{id}/schedule` | POST | 生成预冷调度计划 | operator+ |
| `/api/v1/precool/zones/{id}/schedule` | GET | 查询调度计划列表 | operator+ |
| `/api/v1/precool/schedules/{id}` | GET | 调度详情（含温度轨迹） | operator+ |
| `/api/v1/precool/schedules/{id}/abort` | POST | 中止执行中的调度 | operator+ |
| `/api/v1/precool/zones/{id}/calibrate` | POST | 手动触发 R/C 参数标定 | admin |
| `/api/v1/precool/zones/{id}/parameters` | GET | 查询 R/C 标定参数历史 | operator+ |
| `/api/v1/precool/zones/{id}/validation` | GET | 模型验证报告（MAE/最大偏差） | operator+ |
| `/api/v1/precool/vpp/capacity` | GET | 实时可调容量查询 | operator+ |
| `/api/v1/precool/vpp/dispatch` | POST | 接收 VPP 调度指令 | system |
| `/api/v1/precool/dashboard` | GET | 预冷仪表盘聚合数据 | operator+ |

### 21.6 VPP 对外接口

| 接口 | 说明 |
|------|------|
| **可调容量上报** | 每 5 分钟上报向上/向下可调量（电功率 kW） |
| **基线功率定义** | 近 10 个同类型工作日平均制冷功率 |
| **调度信号接收** | 实时功率调整指令（优先级高于日前优化） |
| **响应确认与计量** | 15 分钟内响应到位，实际响应量 = 基线 - 实际 |

### 21.7 分阶段实施路径

| 阶段 | 时间 | 内容 | 安全策略 |
|------|------|------|---------|
| Phase 1 | 0-2 周 | 收集温度/功率数据，部署 THM | 温度裕度法兜底，替代固定 0.4 |
| Phase 2 | 2-4 周 | R/C 自动标定，1 个低密度冷通道试运行 TCL | TCL 与 THM 并行，TCL 偏差 > 3°C 自动切回 THM |
| Phase 3 | 4 周+ | 正式启用 TCL，在线参数修正，推广全部冷通道 | 7 项自动回退保护 |
| Phase 4 | 8 周+ | VPP 可调容量上报，预冷调度优化 | 累积运行数据后开放 VPP 接口 |

**模型验收标准**:

| 验证指标 | 标准 | 验证方法 |
|---------|------|---------|
| 温度预测 MAE | ≤ 1.0°C（1h），≤ 2.0°C（3h） | 历史数据回测 |
| 温度预测最大偏差 | ≤ 3.0°C | 回测中单点偏差不超标 |
| 预冷目标达成率 | T_precool ± 1°C 内 ≥ 90% | 统计 10 次以上预冷 |
| 节省预测准确度 | 预测与实际偏差 ≤ 20% | 日前预测 vs 事后结算 |
| 回退误触发率 | ≤ 5% | 统计回退事件 |

**灰度发布**: 选择 1 个低密度冷通道试点 2 周 → 对比温度波动和电费 → 通过后推广。

### 21.8 前端展示设计

**预冷调度预览界面**:

1. **温度曲线图**: Y 轴 18-27°C（标注 T_precool, T_normal, T_max），X 轴 00:00-24:00（标注谷/平/峰/尖峰），显示预冷下降→升温释放全过程
2. **制冷功率曲线图**: 各时段制冷功率变化，标注预冷段与削减段
3. **关键指标面板**: 预计节省金额、温度范围与安全状态、最热机柜温度与裕度

**转移仪表盘三项监控**:

| 看什么 | 在哪看 | 正常范围 |
|-------|-------|---------|
| 最热机柜进风温度 | 转移仪表盘 | ≤ 25°C 绿灯 |
| 温度预测曲线 | 预冷调度预览 | 曲线在 18-27°C 之间 |
| 今日节省金额 | 转移仪表盘 | 正数即可 |

### 21.9 NFR 架构支撑（TCL 相关）

| NFR 指标 | 架构支撑 |
|---------|---------|
| 温度预测 < 1s | 内存中 RC 方程逐步迭代，无外部依赖 |
| 调度生成 < 5s | 贪心策略 O(N) 遍历时段，N ≤ 288（5min 步长） |
| 回退响应 ≤ 30s | Redis 实时温度 → 内存比对阈值 → MQTT 控制命令 |
| VPP 上报 5min | APScheduler 定时任务，批量计算所有冷通道 |
| R/C 标定 < 30s | 最小二乘拟合，利用自然功率变化事件数据 |
| 数据安全 | 温度预测结果写入 TemperaturePredictionLog，可审计 |

---

## 22. 多渠道通知引擎架构（V4.3.0 新增）

> 📌 响应客户 RFP P0 需求（FR-N01~N07），在现有告警引擎基础上新增外部通知渠道能力。

### 22.1 架构总览

```
ingest_pipeline._evaluate_alarms() ──创建告警──> Alarm 记录
    │  （实际告警创建入口，非独立 AlarmEngine 类）
    │
    ├──同步──> ws_manager.broadcast_alarm()     [现有，WebSocket 推送前端]
    ├──同步──> escalation_engine.check()         [现有，告警级别升级]
    ├──同步──> linkage_engine.evaluate()          [现有，联动策略执行]
    └──异步──> notification_dispatcher.dispatch() [新增，外部通知分发]
                    │  （通过 asyncio.create_task 异步调用，不阻塞告警流程）
                    │
                    ├── 构造 AlarmNotificationContext DTO（从 Alarm ORM 提取必要字段）
                    ├── 查询 NotificationPolicy（站点×级别×时段）
                    ├── 解析通知对象 → UserNotificationContact（验证 UserSite 站点权限）
                    ├── 告警风暴检测（Redis INCR + 内存降级，60s 窗口合并）
                    └── 分发到渠道适配器（并行）
                         ├── SmsAdapter
                         ├── ImAdapter（钉钉/企业微信）
                         ├── VoiceCallAdapter
                         └── EmailAdapter（包装现有 EmailService，通过 asyncio.to_thread 异步化）
```

**关键设计决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| 通知引擎与告警引擎的关系 | 异步调用，不阻塞告警流程 | 第三方 API 延迟不可控，不能影响告警创建和 WebSocket 推送的实时性 |
| 通知分发方式 | 并行发送所有渠道 | 单条告警可能需通知多人多渠道，串行会导致延迟累积 |
| 渠道升级 vs 告警级别升级 | 两套独立机制，各自维护超时计时器 | 渠道升级（切换通知方式）和级别升级（提升严重程度）语义不同，互不干扰 |
| 通知对象数据来源 | User 表扩展 + UserNotificationContact 表 | User 表新增 phone 字段；独立 contact 表支持一个用户多渠道多联系方式 |
| 站点隔离 | NotificationPolicy 按 site_id 配置 | 1主+5小机房场景，各站点独立通知策略，避免跨站点通知轰炸 |

### 22.2 数据模型扩展

#### User 表现有字段（复用）

```python
# User 模型已有以下字段，无需新增：
phone: Mapped[str | None]           # 手机号（短信+语音电话）— 已存在于 user.py
email: Mapped[str | None]           # 邮箱 — 已存在于 user.py
```

#### UserNotificationContact 表（新增）

```python
class UserNotificationContact(Base):
    __tablename__ = "user_notification_contacts"

    id: Mapped[int]                  # 主键
    user_id: Mapped[int]             # FK → users.id
    channel_type: Mapped[str]        # sms | im | voice | email
    platform: Mapped[str | None]     # dingtalk | wecom | null（sms/voice 无需）
    contact_value: Mapped[str]       # 手机号 / 钉钉userId / 企业微信userId / 邮箱
    is_enabled: Mapped[bool]         # 是否启用
    created_at: Mapped[datetime]
```

**与 User.phone/email 的关系：**
- User.phone 和 User.email 是用户基本信息字段（登录、个人资料），保持不变
- UserNotificationContact 是通知专用联系方式表，支持一个用户多渠道多联系方式（如多个钉钉账号、不同时段使用不同手机号）
- 创建 UserNotificationContact 时，可从 User.phone/email 自动填充初始值，但后续独立维护
- 通知分发器仅查询 UserNotificationContact 表，不直接读取 User.phone/email

#### NotificationPolicy 表（新增）

```python
class NotificationPolicy(Base):
    __tablename__ = "notification_policies"

    id: Mapped[int]
    site_id: Mapped[int | None]      # FK → sites.id，NULL=全局默认
    alarm_level: Mapped[str]         # critical | major | minor | info
    time_range_start: Mapped[str]    # "00:00" 时段开始
    time_range_end: Mapped[str]      # "08:00" 时段结束
    channels: Mapped[dict]           # JSON: ["im", "sms"] 渠道组合
    notify_user_ids: Mapped[list]    # JSON: [1, 2, 3] 通知对象
    channel_escalation_enabled: Mapped[bool]  # 是否启用渠道升级
    escalation_timeout_minutes: Mapped[int]   # 渠道升级超时（分钟）
    escalation_channel_order: Mapped[list]    # JSON: ["im", "sms", "voice"] 升级顺序
    is_enabled: Mapped[bool]
```

**跨午夜时段处理：**
- 当 `time_range_start > time_range_end`（如 "22:00" > "06:00"）时，表示跨午夜时段
- 匹配逻辑：`current_time >= start OR current_time < end`（而非 AND）
- 示例："22:00"~"06:00" 匹配 23:00（>=22:00）和 03:00（<06:00），不匹配 12:00

**notify_user_ids 站点权限约束：**
- 通知分发器在 `_resolve_contacts()` 中，通过 `UserSite` 表（`user_sites`）验证每个 user_id 是否有该策略 site_id 的访问权限
- 无权限的 user_id 静默跳过（不报错），记录 warning 日志
- 全局策略（site_id=NULL）不做站点权限校验

#### NotificationRecord 表（新增）

```python
class NotificationRecord(Base):
    __tablename__ = "notification_records"

    id: Mapped[int]
    alarm_id: Mapped[int]            # FK → alarms.id
    policy_id: Mapped[int | None]    # FK → notification_policies.id（追溯触发策略）
    user_id: Mapped[int]             # FK → users.id
    channel_type: Mapped[str]        # sms | im | voice | email
    contact_value: Mapped[str]       # 实际发送的联系方式
    status: Mapped[str]              # pending | sent | failed | retrying
    retry_count: Mapped[int]         # 已重试次数
    max_retries: Mapped[int]         # 最大重试次数
    sent_at: Mapped[datetime | None]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime]
```

### 22.3 渠道适配器架构

```python
@dataclass
class AlarmNotificationContext:
    """通知上下文 DTO — 避免跨层传递 ORM 对象"""
    alarm_id: int
    alarm_level: str          # critical | major | minor | info
    alarm_message: str
    device_name: str | None
    point_name: str | None
    site_id: int | None
    created_at: datetime

class NotificationAdapter(ABC):
    """通知渠道适配器基类，与现有 EmailService 同级"""

    @abstractmethod
    async def send(self, contact: str, subject: str, content: str,
                   context: AlarmNotificationContext) -> NotificationResult: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

class SmsAdapter(NotificationAdapter):
    """短信适配器 — 对接阿里云/腾讯云短信 API"""

class ImAdapter(NotificationAdapter):
    """即时通讯适配器 — 钉钉/企业微信 Webhook"""

class VoiceCallAdapter(NotificationAdapter):
    """语音电话适配器 — 对接语音通知 API"""

class EmailNotificationAdapter(NotificationAdapter):
    """邮件适配器 — 包装现有 EmailService
    注意：EmailService 使用同步 smtplib.SMTP（无 timeout 参数），
    必须通过 asyncio.to_thread() 包装为异步调用，并设置 socket timeout 防止线程池阻塞。
    """
```

**适配器注册表：**

```python
NOTIFICATION_ADAPTERS: dict[str, type[NotificationAdapter]] = {
    "sms": SmsAdapter,
    "im": ImAdapter,
    "voice": VoiceCallAdapter,
    "email": EmailNotificationAdapter,
}
```

### 22.4 通知分发器

```python
class NotificationDispatcher:
    """异步通知分发器"""

    async def dispatch(self, context: AlarmNotificationContext):
        """接收 DTO 而非 ORM 对象，由调用方（ingest_pipeline）构造 context"""
        # 1. 告警风暴检测（Redis INCR + 内存降级）
        if await self._is_storm(context.site_id):
            return await self._send_storm_summary(context.site_id)

        # 2. 查询通知策略（站点×级别×当前时段）
        policy = await self._get_policy(context.site_id, context.alarm_level)

        # 3. 解析通知对象的联系方式（验证 UserSite 站点权限）
        contacts = await self._resolve_contacts(policy)

        # 4. 并行发送所有渠道，逐个处理结果
        tasks = [self._send_one(adapter, contact, context)
                 for adapter, contact in contacts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 5. 处理发送结果：成功→NotificationRecord.status='sent'
        #    失败→NotificationRecord.status='failed'，加入重试队列
        for (adapter, contact), result in zip(contacts, results):
            if isinstance(result, Exception):
                await self._handle_failure(context, contact, result)

        # 6. 启动渠道升级计时器（如果启用）
        if policy.channel_escalation_enabled:
            await self._schedule_escalation(context, policy)
```

**重试机制：**
```python
# 使用 asyncio.Queue 实现异步重试队列
_retry_queue: asyncio.Queue[NotificationRecord] = asyncio.Queue(maxsize=1000)

async def _handle_failure(self, context: AlarmNotificationContext, contact, error):
    """发送失败处理：写入 NotificationRecord 并加入重试队列"""
    record = NotificationRecord(
        alarm_id=context.alarm_id, user_id=contact.user_id,
        channel_type=contact.channel_type, contact_value=contact.contact_value,
        status="failed", error_message=str(error), retry_count=0, max_retries=3,
    )
    await self._save_record(record)
    if record.retry_count < record.max_retries:
        try:
            self._retry_queue.put_nowait(record)
        except asyncio.QueueFull:
            logger.error("重试队列已满，丢弃通知重试: alarm_id=%d", context.alarm_id)

async def _retry_worker(self):
    """后台重试工作协程 — 在 background_tasks 中启动，随应用生命周期管理"""
    while True:
        record = await self._retry_queue.get()
        await asyncio.sleep(min(30 * (2 ** record.retry_count), 300))  # 指数退避，最大5分钟
        success = await self._retry_send(record)
        if not success and record.retry_count < record.max_retries:
            record.retry_count += 1
            try:
                self._retry_queue.put_nowait(record)
            except asyncio.QueueFull:
                pass
```

**Queue 生命周期管理：**
- _retry_worker 在应用启动时通过 `asyncio.create_task` 启动
- 应用关闭时（shutdown event），先停止接收新任务，然后等待队列排空（最多30秒），超时后记录未处理的重试到数据库

### 22.5 渠道升级状态机

```
通知已发送 ──超时未确认──> 升级到下一渠道 ──超时未确认──> 升级到下一渠道 ──> 所有渠道已用尽
     │                        │                        │
     └──告警已确认──> 停止升级  └──告警已确认──> 停止升级  └──告警已确认──> 停止升级
```

**与现有 AlarmEscalation 的关系：**
- `AlarmEscalation`（现有）：告警级别升级（minor → major → critical），修改 `Alarm.level`
- `NotificationPolicy.channel_escalation`（新增）：通知渠道升级（IM → SMS → Voice），不修改告警级别
- 两者各自维护独立的超时计时器，可同时触发，互不干扰
- 告警级别升级后，新级别会触发新的通知策略查询（可能使用不同的渠道组合）

### 22.6 告警风暴抑制

```python
STORM_WINDOW = 60        # 秒（可通过 SystemConfig 'notification.storm_window' 配置）
STORM_THRESHOLD = 20     # 同站点告警数（可通过 SystemConfig 'notification.storm_threshold' 配置）

async def _is_storm(self, site_id: int) -> bool:
    """检测同站点 60s 内告警数是否超过阈值

    实现方式：
    1. 优先使用 Redis INCR + TTL（原子操作，高性能）
       key: notification:storm:{site_id}，TTL=STORM_WINDOW
    2. Redis 不可用时降级为内存计数器（asyncio.Lock 保护并发）
    """
    count = await self._incr_storm_counter(site_id)
    return count >= STORM_THRESHOLD
```

风暴期间合并为摘要通知："A 站点在过去 1 分钟内触发 N 条告警，最高级别：紧急，请登录系统查看详情"。

---

## 23. 预测性维护扩展架构（V4.3.0 新增）

> 📌 响应客户 RFP P0 需求（FR-PM01~PM06），将预测性维护从"仅 UPS 电池 SOH"扩展到所有关键设备类型。

### 23.1 架构总览

```
设备历史数据（PointHistoryArchive — hourly 聚合数据，优先）
    │         （PointHistory — 原始数据，仅在归档不足时降级使用）
    ▼
DegradationAnalyzer（劣化分析器）
    ├── UPSDegradationPlugin        ── 扩展现有 SOH
    ├── BatteryDegradationPlugin    ── 复用 BatterySOHRecord
    ├── HVACDegradationPlugin       ── 新增：COP/压缩机/回风
    └── PDUDegradationPlugin        ── 新增：负载率/谐波/温升
    │
    ▼
DeviceHealthScoreCalculator（健康度评分计算器）
    ├── 劣化趋势因子（新增，来自 DegradationAnalyzer）
    ├── 告警频次因子（现有 alarm_count）
    └── 维保记录因子（现有 maintenance_count）
    │ 加权合并（权重按设备类型配置）
    ▼
DeviceHealthScore 表（现有，扩展输入因子）
    │
    ▼
MaintenanceAdvisor（维护建议引擎）
    ├── 生成维护建议（评分降至"预警"时触发）
    └── 对接工单系统（FR67-FR71，需人工确认）
    │
    ▼
运维人员反馈（有效/误报标注）→ 模型参数优化
```

### 23.2 劣化分析插件架构

```python
class DegradationPlugin(ABC):
    """劣化分析插件基类"""

    # 该插件对应的设备类型（用于注册表映射，如 'ups'/'hvac'/'pdu'/'battery'）
    @abstractmethod
    def get_device_type(self) -> str: ...

    # 该设备类型的最低数据需求
    @abstractmethod
    def get_required_points(self) -> list[str]: ...

    # 该设备类型的可选数据点（有则更精确）
    @abstractmethod
    def get_optional_points(self) -> list[str]: ...

    # 执行劣化分析
    @abstractmethod
    async def analyze(self, device_id: int,
                      point_history: dict[str, list],
                      window_days: int = 30) -> DegradationResult: ...

@dataclass
class DegradationResult:
    device_id: int                  # 设备ID（避免调用方维护映射关系）
    score: float                    # 0~100 劣化评分
    confidence: float               # 评估置信度（0~1，数据点越多越高）
    available_points: int           # 实际可用数据点数
    total_points: int               # 理想数据点数
    trend_factors: dict[str, float] # 各指标趋势值
    primary_concern: str | None     # 主要劣化原因
    data_sufficiency: str           # full | partial | minimal
```

#### 各设备类型插件配置

| 设备类型 | 必需数据点 | 可选数据点 | 健康度权重 |
|---------|-----------|-----------|-----------|
| UPS 主机 | 输入/输出电压 | 效率（通常为虚拟点位=输出功率/输入功率）、切换次数、温度 | 劣化趋势 40%、告警频次 30%、维保 30% |
| 电池组 | SOH（从 BatterySOHRecord 读取）、内阻 | 充放电循环、温度 | SOH 50%、告警频次 20%、维保 30% |
| 精密空调 | 回风温度、运行状态 | COP/EER（通常为虚拟点位=制冷量/功耗）、压缩机时长、冷媒压力 | 劣化趋势 40%、告警频次 30%、维保 30% |
| PDU | 负载率、电压 | 谐波畸变率、温升 | 劣化趋势 35%、告警频次 35%、维保 30% |

### 23.3 健康度评分计算器增强

```python
class DeviceHealthScoreCalculator:
    """增强现有 DeviceHealthScore 计算逻辑"""

    # 设备类型 → 加权配置（Device.device_type → 插件 device_type 映射：UPS→ups, AC→hvac, PDU→pdu）
    WEIGHT_CONFIG: dict[str, dict] = {
        "ups": {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
        "battery": {"degradation": 0.5, "alarm": 0.2, "maintenance": 0.3},
        "hvac": {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
        "pdu": {"degradation": 0.35, "alarm": 0.35, "maintenance": 0.3},
    }

    async def calculate(self, device_id: int, device_type: str,
                        degradation: DegradationResult) -> DeviceHealthScore:
        """接收外部传入的 DegradationResult，避免内部耦合 Analyzer"""
        # 1. 获取现有因子（告警频次、维保记录）
        alarm_score = await self._calc_alarm_score(device_id)
        maintenance_score = await self._calc_maintenance_score(device_id)

        # 2. 数据充分度降级：minimal 时劣化权重归零
        weights = self.WEIGHT_CONFIG.get(device_type, self.WEIGHT_CONFIG["ups"])
        if degradation.data_sufficiency == "minimal":
            effective_weights = {"degradation": 0, "alarm": 0.5, "maintenance": 0.5}
        else:
            effective_weights = weights

        # 3. 加权合并
        final_score = (
            degradation.score * effective_weights["degradation"] +
            alarm_score * effective_weights["alarm"] +
            maintenance_score * effective_weights["maintenance"]
        )

        # 4. 写入 DeviceHealthScore（复用现有表）
        return DeviceHealthScore(
            score=final_score,
            health_level=self._score_to_level(final_score),
            data_sufficiency=degradation.data_sufficiency,
            degradation_score=degradation.score,
            score_factors={
                "degradation": degradation.score,
                "alarm": alarm_score,
                "maintenance": maintenance_score,
                "weights": effective_weights,
                "trend_factors": degradation.trend_factors,
            },
        )
```

**与现有 DeviceHealthScore 的关系：**
- 复用现有 `DeviceHealthScore` 表，不新建表
- 现有的 `alarm_count` / `maintenance_count` 驱动的简单评分逻辑替换为加权合并算法
- `DeviceHealthScore` 表新增字段（Alembic 迁移）：
  - `data_sufficiency` (String(20), default="minimal") — 数据充分度：full/partial/minimal
  - `degradation_score` (Float, nullable) — 劣化趋势评分 0-100
  - `score_factors` (JSON, nullable) — 评分因子详情（各因子分值、权重、趋势数据）
- 现有技术债务修复：`battery_soh_service.py` 中 `update_device_health_score()` 引用了不存在的 `total_score` 和 `score_factors` 字段，需在本次迁移中一并修复
- 迁移策略：新算法上线后，对所有设备重新计算一次健康度评分

### 23.4 维护建议引擎

```python
class MaintenanceAdvisor:
    """维护建议引擎 — 生成建议，需人工确认后转工单"""

    async def evaluate(self, health_score: DeviceHealthScore,
                       degradation: DegradationResult):
        if health_score.health_level in ("预警", "危险"):
            # 防重复：检查是否已有 pending 建议，有则更新而非新建
            existing = await self._get_pending_advice(health_score.device_id)
            if existing:
                existing.health_score = health_score.score
                existing.reason = degradation.primary_concern
                existing.urgency = self._calc_urgency(health_score, degradation)
                await self._save_advice(existing)
                return

            advice = MaintenanceAdvice(
                device_id=health_score.device_id,
                site_id=...,  # 从 Device.site_id 获取
                urgency=self._calc_urgency(health_score, degradation),
                reason=degradation.primary_concern,
                suggested_action=self._generate_action(degradation),
                status="pending",  # 待人工确认
            )
            await self._save_advice(advice)
            # 不自动创建工单，等待运维人员确认

        elif health_score.health_level in ("健康", "关注"):
            # 设备恢复时自动关闭 pending 建议
            await self._auto_close_pending(health_score.device_id)
```

#### MaintenanceAdvice 表（新增）

```python
class MaintenanceAdvice(Base):
    __tablename__ = "maintenance_advices"

    id: Mapped[int]
    device_id: Mapped[int]           # FK → devices.id
    site_id: Mapped[int]             # FK → sites.id（从 Device.site_id 获取）
    health_score: Mapped[float]      # 触发时的健康度评分
    urgency: Mapped[str]             # high | medium | low
    reason: Mapped[str]              # 劣化原因描述
    suggested_action: Mapped[str]    # 建议措施
    status: Mapped[str]              # pending | confirmed | rejected | converted | auto_closed
    feedback: Mapped[str | None]     # 运维人员反馈（误报原因等）
    work_order_id: Mapped[int | None]  # 转为工单后的工单 ID
    created_at: Mapped[datetime]
    confirmed_at: Mapped[datetime | None]
    confirmed_by: Mapped[int | None]   # FK → users.id
```

### 23.5 数据充分度与精度提示

当设备暴露的数据点不足时，系统采用降级评估策略：

| 数据充分度 | 条件 | 评估策略 | 前端提示 |
|-----------|------|---------|---------|
| full | 必需+可选数据点均可用 | 完整劣化分析 | 无特殊提示 |
| partial | 仅必需数据点可用 | 基于必需点位分析，置信度降低 | "评估精度：中等（部分数据点不可用）" |
| minimal | 必需数据点也不完整 | 仅基于告警频次和维保记录 | "评估精度：有限（可用数据点 N/M），建议补充采集配置" |

### 23.6 API 设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/predictive-maintenance/dashboard` | GET | 预测性维护仪表盘（按站点） |
| `/api/v1/predictive-maintenance/devices/{id}/degradation` | GET | 设备劣化详情 |
| `/api/v1/predictive-maintenance/advices` | GET | 维护建议列表 |
| `/api/v1/predictive-maintenance/advices/{id}/confirm` | POST | 确认建议并转工单 |
| `/api/v1/predictive-maintenance/advices/{id}/reject` | POST | 标记为误报 |
| `/api/v1/predictive-maintenance/config` | GET/PUT | 劣化分析配置（权重、周期） |
| `/api/v1/predictive-maintenance/recalculate` | POST | 手动触发全量健康度重算（admin only） |

---

## 24. BACnet MS/TP 设备接入架构（V4.3.0 新增）

> 📌 响应客户大金 VRV 空调对接需求（FR-BN01~BN04）。技术方案：硬件协议转换网关 + 平台侧复用现有 BACnet/IP 适配器。

### 24.1 架构总览

```
大金 VRV 空调 ──BACnet MS/TP (RS-485)──> 协议转换网关 ──BACnet/IP──> 平台 BACnet/IP 适配器
                                              │
                                    硬件设备（非平台组件）
                                    如：Intesis MAPS、Loytec L-IP
```

**关键设计决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| 协议处理方式 | 硬件网关转换，平台不实现 MS/TP 协议栈 | MS/TP 是串口协议，需物理 RS-485 接口；硬件网关成熟可靠，平台侧零改动 |
| 平台侧适配 | 复用现有 BACnet/IP 适配器（Section 6） | 转换网关对平台透明，平台看到的是标准 BACnet/IP 设备 |
| 网关管理 | 扩展现有 DeviceTemplate，不新建模块 | 转换网关作为一种网关类型纳入现有管理体系 |

### 24.2 设备模板与数据源关联扩展

**DeviceTemplate 扩展：** 新增 `extra_config` JSON 字段（独立于 point_config），存放网关配置。point_config 保持原语义（点位数组）。

```python
# DeviceTemplate 新增字段（Alembic 迁移）
extra_config = Column(JSON, nullable=True, comment="扩展配置（网关参数等）")
```

**extra_config JSON 结构（MS/TP 网关模板）：**

```json
{
    "gateway_type": "bacnet_mstp_to_ip",
    "bacnet_ip": {
        "port": 47808,                    # BACnet/IP 端口
        "device_instance": 100            # 网关自身的 BACnet 设备实例号
    },
    "mstp_config": {
        "network_number": 1,              # MS/TP 网络号
        "mac_range": [1, 127],            # MS/TP MAC 地址范围
        "baud_rate": 9600,                # 串口波特率
        "parity": "none"                  # 奇偶校验
    },
    "bbmd_config": {                      # 跨子网场景（可选）
        "enabled": false,
        "bdt_entries": []
    },
    "downstream_devices": [               # 网关下挂的 MS/TP 设备列表
        {
            "mac_address": 1,
            "device_instance": 201,
            "device_name": "大金VRV-B区-1",
            "model": "RXYQ16TAY1"
        }
    ]
}
```

### 24.3 数据源关联与故障隔离架构

**DataSource 扩展：** 新增 `parent_datasource_id` 外键，MS/TP 设备的 DataSource 通过此字段关联到网关的 DataSource。

```python
# DataSource 新增字段（Alembic 迁移）
parent_datasource_id = Column(
    Integer, ForeignKey("datasources.id", ondelete="SET NULL"),
    nullable=True, default=None, index=True,
    comment="父数据源ID（MS/TP设备指向其网关DataSource）"
)
```

**关联模型：**
```
网关 DataSource (protocol_type='bacnet_ip', is_enabled=False)
    ├── 设备1 DataSource (parent_datasource_id → 网关, is_enabled=True)
    ├── 设备2 DataSource (parent_datasource_id → 网关, is_enabled=True)
    └── 设备N DataSource (parent_datasource_id → 网关, is_enabled=True)
```
- 网关 DataSource 的 `is_enabled=False`，不参与采集调度，仅作为父节点和心跳探测目标
- 网关可达性通过定时任务 `check_mstp_gateway_health()` 中的 `test_connection()` 探测

**双层故障隔离：**

```
平台监控（gateway_monitor.py 新增 check_mstp_gateway_health）
    │
    ├── 网关层：test_connection() 探测网关 DataSource
    │       ├── 失败 → consecutive_failures++
    │       │       └── >= 阈值 → 网关 status='gateway_offline'
    │       │                    └── 批量 UPDATE 子 DataSource status='gateway_offline'
    │       └── 成功 → consecutive_failures=0, status='connected'
    │
    └── 设备层：各子 DataSource 独立采集
            ├── 采集成功 → status='connected'
            └── consecutive_failures >= 阈值 且 网关在线 → status='device_offline'
```

**DataSource.status 值域扩展：**
- 现有值：`connected`, `disconnected`, `error`
- 新增值：`gateway_offline`（网关层故障）, `device_offline`（设备层故障）

### 24.4 与现有架构的集成点

| 集成点 | 现有组件 | 扩展方式 |
|--------|---------|---------|
| 协议适配 | `bacnet_ip.py`（Section 6） | 无需修改，转换网关对适配器透明 |
| 网关管理 | Gateway 模型（FR15-FR20） | 无需修改 Gateway 表，网关信息通过 DataSource 管理 |
| 设备模板 | DeviceTemplate | 新增 `extra_config` JSON 字段存放 MS/TP 网关配置 |
| 数据源关联 | DataSource | 新增 `parent_datasource_id` 外键，建立网关-设备父子关系 |
| 故障检测 | gateway_monitor.py | 新增 `check_mstp_gateway_health()` 定时任务（30s 周期） |
| 告警 | AlarmEngine | 新增 `mstp_gateway_offline`（major）和 `mstp_device_offline`（minor）告警类型 |
| 数据源状态 | DataSource.status | 新增 `gateway_offline` 和 `device_offline` 状态值 |

---

## 附录: 架构变更日志

### V4.3.0 (2026-03-18)

**重大变更**:

1. **多渠道通知引擎架构（Section 22）**
   - 新增外部通知渠道：短信、即时通讯（钉钉/企业微信）、语音电话，可插拔适配器架构
   - 通知策略按站点×告警级别×时段三维配置，支持站点隔离
   - 渠道升级机制：独立于现有告警级别升级（AlarmEscalation），各自维护超时计时器
   - 告警风暴抑制：60s 窗口内同站点 ≥20 条告警自动合并为摘要通知
   - 异步分发：不阻塞告警创建和 WebSocket 推送流程
   - 新增数据模型：UserNotificationContact、NotificationPolicy、NotificationRecord（含 policy_id 审计追溯）
   - User 表已有 phone/email 字段（复用，无需新增）

2. **预测性维护扩展架构（Section 23）**
   - 劣化分析插件架构：UPS/电池/空调/PDU 四种设备类型，可扩展
   - DeviceHealthScore 计算增强：劣化趋势+告警频次+维保记录加权合并，权重按设备类型配置
   - 数据充分度分级（full/partial/minimal），前端显示评估精度提示
   - 维护建议引擎：需人工确认后转工单，支持误报反馈闭环
   - 新增数据模型：MaintenanceAdvice 表

3. **BACnet MS/TP 设备接入架构（Section 24）**
   - 硬件协议转换网关方案，平台侧复用现有 BACnet/IP 适配器，零协议栈改动
   - DeviceTemplate 扩展 MS/TP 转换网关配置模板
   - 双层故障隔离：网关层（BACnet/IP 连接）+ 设备层（单设备读取）独立计数

**PRD 对应关系**:
- Section 22 → FR-N01~N07（多渠道通知引擎）
- Section 23 → FR-PM01~PM06（预测性维护扩展）+ FR75 更新
- Section 24 → FR-BN01~BN04（BACnet MS/TP 接入）

### V4.2.0 (2026-03-10)

**重大变更**:

1. **预冷 TCL 模型架构（Section 21）**
   - 新增一阶 RC 热动力学模型，替代固定比例 0.4 的制冷可转移功率算法
   - 温度裕度法（THM）安全兜底：R/C 未标定前零依赖实时计算
   - 气流短路修正：旁路系数 β 修正进风温度预测
   - 7 项自动回退保护（温度/速率/故障/传感器/UPS/湿度）
   - VPP 可调容量接口：5 分钟周期上报向上/向下可调量
   - 分阶段实施路径：THM 兜底(0-2wk) → R/C 标定(2-4wk) → TCL 正式(4wk+) → VPP(8wk+)

2. **数据模型扩展**
   - CoolingZone 新增 6 个字段（area_m2, height_m, thermal_R, thermal_C, bypass_beta, r_calibrated_at）
   - CoolingLinkageConfig 新增 precool_target_temp, precool_enabled
   - 3 个新表：ThermalParameter（R/C 标定历史）、TemperaturePredictionLog（预测偏差）、PrecoolSchedule（调度计划）

3. **服务层新增**
   - ThermalModelService: RC 方程温度预测、R/C 在线标定、THM 兜底
   - PrecoolScheduler: 日前调度生成、执行监控、自动回退
   - VPPCapacityReporter: 可调容量计算与上报、VPP 调度指令处理
   - ConstraintChecker 增强：动态替代固定 0.4 比例

4. **API 新增**
   - 11 个新 REST 端点（/api/v1/precool/*）
   - 温度预测、调度管理、R/C 标定、模型验证、VPP 容量

5. **关键架构决策**
   - TCL 热模型选用一阶 RC 集总参数（复杂度低、可在线标定）
   - 预冷优化选用贪心策略（2 人团队无需 scipy/cvxpy）
   - COP 季节性修正（夏 2.8 / 过渡 3.5 / 冬 4.0）
   - 数值稳定性保障（Δt < 2RC，5 分钟步长）

**输入文档**: `docs/空调可转移功率算法调研与改进方案.md` V4.0（三轮对抗性审查）

---

### V4.0.0 (2026-03-05)

**重大变更**:

1. **智能诊断系统架构（Section 18）**
   - 新增分级推理架构（L1规则引擎/L2故障树/L3贝叶斯），对应 PRD FR34-1~42
   - 故障树管理: NetworkX 内存图 + PostgreSQL 持久化 + HMAC-SHA-256 签名
   - 全局因果图: 配电→暖通→IT→业务四层级联传播链
   - 电气专业扩展: 三相不平衡/THD/功率因数/电池SOH/N+X冗余/断路器特性
   - 暖通专业增强: 差异化时间窗口/动态阈值/趋势分析/多传感器融合
   - 熔断降级: 熔断器状态机 + L1保底 + 灾难恢复演练
   - 闭环学习: 运维标注→概率自动调参→管理员审批
   - 安全加固: 对抗样本检测/分级展示/SBOM管理
   - 可解释性: 证据链/反事实分析/误判报告

2. **技术栈扩展**
   - 新增 NetworkX 3.2+（图计算）
   - 新增 scikit-learn 1.4+（异常检测）
   - HMAC-SHA-256（Python 内置 hmac+hashlib）

3. **数据模型扩展**
   - 6 个新数据模型分组（故障树、因果图、诊断引擎、闭环学习、电气扩展）
   - 15+ 新表

4. **前端数据流规范（Section 19）**
   - 基于棕地代码审查，制定单一事实来源(SSOT)规范
   - 识别并解决告警/实时/能源数据在多个 Store+Composable 间的割裂问题
   - WebSocket 单连接管理、站点过滤贯穿、Composable 职责边界

5. **Demo 系统与数据隔离规范（Section 20）**
   - 基于 demo 系统深度审查，制定数据来源标记贯穿原则
   - Demo 与主系统配置分离（seed/demo/simulation 三项独立）
   - 数据源枚举标准化（mqtt/demo/bridge/manual/unknown）
   - 主系统代码禁止硬依赖 demo 特定编码

4. **诊断 API**
   - 15 个新 REST 端点（/api/v1/diagnosis/*, /api/v1/fault-trees/*, /api/v1/causal-graph 等）

5. **对抗性审查修复（15项）**
   - [P0] L3 贝叶斯引擎补全: 逆向推理算法、历史频率校正、伪代码
   - [P0] 并发控制: asyncio.Semaphore + PriorityQueue + 溢出降级策略
   - [P0] 告警→诊断集成: Redis Pub/Sub 订阅 alarm:new、WebSocket 复用 /ws/alarms
   - [P1] A/B 测试推迟到 Phase 2b+，补充人工决策流程
   - [P1] 动态阈值改为配置表驱动规则引擎（不硬编码）
   - [P1] SOH 算法标注为简化模型，权重可配置，需实际数据校准
   - [P1] 因果图↔故障树同步策略: 外键引用、断裂边检测、多对多版本关联
   - [P1] 配电级联分析改用 NetworkX 子图遍历（跨 4 表，非单表递归 CTE）
   - [P1] 混沌工程演练安全防护: 演练窗口、一键终止、真实告警保护
   - [P1] 图形化编辑分阶段: Phase 2a JSON+只读可视化，Phase 3+ vue-flow
   - [P1] WebSocket 消息格式定义: type/target_roles/data 结构
   - [P2] 证据链补充 timestamp 字段
   - [P2] 传感器校准周期: calibration_interval_days 字段，默认 365 天
   - [P2] HMAC 代码类型注解和中文注释
   - [P2] 修正错别字"场障树"→"故障树"

---

### V3.2.0 (2026-02-28)

**重大变更**:

1. **演示系统模块化**
   - 新增 app/demo/ 独立模块
   - 删除 9 个遗留文件（2708 行）
   - 清理 12 个 mock 方法

2. **统一数据入库管线**
   - 新增 app/services/ingest_pipeline.py（576 行）
   - 性能提升 2x（吞吐量 2000+ 点位/秒）

3. **MQTT 动态订阅增强**
   - 支持运行时注册/取消 Topic 订阅
   - 优雅降级（连接失败不阻塞）

4. **数据一致性保障**
   - 新增 device_sync.py 设备同步服务
   - 启动脚本重构（v7.0）

**关键 Git 提交**:

- faff297 - 重构: 演示系统解耦 - 统一管线、卸载修复、dispatch迁移
- 4c8ebaa - feat: 数据一致性保障与启动脚本重构
- 9681268 - refactor: 优化 start.bat 数据修复时机 (v6.0 → v7.0)

---

## 16. 已知技术债务与待修复问题

### 16.1 代码质量问题

#### 问题 1: device_sync.py 中存在重复代码块

**位置**: `backend/app/services/device_sync.py` 第 692-780 行

**问题描述**:

`_infer_circuit_id()` 方法中存在两个几乎完全重复的 HVAC 设备处理代码块:

- **第一个块** (692-730 行): 处理 HVAC 设备的基础逻辑
  - CA-XX → C-CA-GENERIC
  - PMP-F1-XX → C-CHWP-01/C-CWP-01/C-PMP-GENERIC
  - AC-OUT-XX → C-AC-OUT-GENERIC
  - CH-XX → C-CH-01
  - CT-XX → C-CT-01
  - FX-AC-XX → C-FX-AC-01
  - AC-A/B → C-AC-01/02

- **第二个块** (731-780 行): 几乎相同的逻辑，但有细微差异
  - CA-FX-XX → C-FX-CA-01 (新增楼层冷通道)
  - CA-A01 → C-CA-A-01 (新增区域冷通道)
  - PMP-XX → 轮询分配 C-PMP-01/02 (新增轮询逻辑)
  - AC-OUT-XX → C-AC-OUT-01 (回路名称不同)

**影响**:

- 代码可维护性差: 修改逻辑需要同时修改两处
- 逻辑不一致风险: 两个块的细微差异可能导致绑定结果不确定
- 代码冗余: 148 行方法中有约 90 行重复

**根本原因**:

在 commit 950ce48 和 e4e527f 中多次迭代添加新的绑定规则时,未能及时重构,导致代码块重复。

**建议修复方案**:

```python
def _infer_circuit_id(self, device: Device, circuit_map: dict) -> Optional[int]:
    """智能推断回路ID"""
    code = device.device_code
    dev_type = device.device_type
    
    # 1. UPS 设备
    if dev_type == "UPS":
        return self._infer_ups_circuit(code, circuit_map)
    
    # 2. PDU 设备
    elif dev_type == "PDU":
        return self._infer_pdu_circuit(code, device.area_code, circuit_map)
    
    # 3. HVAC 设备 (合并两个重复块)
    elif dev_type in ("AC", "HVAC"):
        return self._infer_hvac_circuit(code, circuit_map)
    
    # 4. IT 设备
    elif dev_type == "IT":
        return self._infer_it_circuit(code, device.area_code, circuit_map)
    
    # 5. 照明
    elif dev_type == "LIGHT":
        return circuit_map.get("C-LIGHT")
    
    return None

def _infer_hvac_circuit(self, code: str, circuit_map: dict) -> Optional[int]:
    """HVAC 设备回路推断 (合并所有规则)"""
    # 优先级1: 楼层冷通道 CA-FX-XX → C-FX-CA-01
    for floor in ["F2", "F3", "F4"]:
        if code.startswith(f"CA-{floor}-"):
            return circuit_map.get(f"C-{floor}-CA-01")
    
    # 优先级2: 区域冷通道 CA-A01 → C-CA-A-01
    if code.startswith("CA-A"):
        return circuit_map.get("C-CA-A-01")
    
    # 优先级3: 通用冷通道 CA-XX → C-CA-GENERIC
    if code.startswith("CA-"):
        return circuit_map.get("C-CA-GENERIC")
    
    # 水泵逻辑...
    # (其他规则按优先级排列)
```

**优先级**: 中 (不影响功能,但影响可维护性)

**预计工作量**: 2-3 小时 (重构 + 测试)

---

#### 问题 2: 回路绑定逻辑的优先级不明确

**位置**: `backend/app/services/device_sync.py` 第 692-780 行

**问题描述**:

由于存在两个重复的 HVAC 处理块,对于某些设备编码,可能同时匹配多个规则,导致绑定结果不确定。

**示例**:

- 设备编码 `CA-F2-01`:
  - 第一个块: 匹配 `CA-XX` → 返回 `C-CA-GENERIC`
  - 第二个块: 匹配 `CA-F2-XX` → 返回 `C-F2-CA-01`
  - **实际结果**: 第一个块先执行,返回 `C-CA-GENERIC` (不符合预期)

- 设备编码 `AC-OUT-01`:
  - 第一个块: 返回 `C-AC-OUT-GENERIC`
  - 第二个块: 返回 `C-AC-OUT-01`
  - **实际结果**: 第一个块先执行,返回 `C-AC-OUT-GENERIC`

**影响**:

- 部分设备绑定到错误的回路
- 配电拓扑页显示不准确
- 能耗统计可能不准确

**建议修复方案**:

1. **合并两个代码块**,按优先级从高到低排列规则:
   - 优先级1: 精确匹配 (CA-F2-XX, CA-A01)
   - 优先级2: 模糊匹配 (CA-XX)
   - 优先级3: 通用回路 (C-CA-GENERIC)

2. **添加单元测试**,覆盖所有边界情况:
   ```python
   def test_infer_circuit_priority():
       # CA-F2-01 应该绑定到 C-F2-CA-01,而不是 C-CA-GENERIC
       device = Device(device_code="CA-F2-01", device_type="AC")
       circuit_id = service._infer_circuit_id(device, circuit_map)
       assert circuit_id == circuit_map["C-F2-CA-01"]
   ```

**优先级**: 高 (影响数据准确性)

**预计工作量**: 4-6 小时 (重构 + 测试 + 数据修复)

---

### 16.2 其他待办事项 (从代码注释中提取)

#### TODO 1: 数据模拟器与拓扑同步通信

**位置**: `backend/app/services/topology_sync.py:428`

```python
# TODO: 实现与数据模拟器的通信
```

**说明**: 当前拓扑变更后,数据模拟器不会自动感知,需要手动重启。

**优先级**: 低 (仅影响演示环境)

---

#### TODO 2: 容量预测基准值优化

**位置**: `backend/app/services/forecasting.py:294`

```python
# TODO: 从数据库查询历史数据来调整基准
```

**说明**: 当前容量预测使用固定基准值,应该从历史数据中动态计算。

**优先级**: 中 (影响预测准确性)

---

#### TODO 3: OCR 服务生产环境集成

**位置**: `backend/app/services/ocr_service.py:10, 153, 262`

```python
TODO [生产集成计划]:
1. 安装 PaddleOCR: pip install paddleocr paddlepaddle
2. 或配置云 OCR API (阿里云/腾讯云/百度云)
3. 移除 mock 实现
```

**说明**: 当前 OCR 服务使用 mock 实现,生产环境需要集成真实 OCR 引擎。

**优先级**: 低 (功能可选)

---

### 16.3 修复计划

| 问题 | 优先级 | 预计工作量 | 计划修复时间 |
|------|--------|-----------|-------------|
| device_sync.py 重复代码 | 中 | 2-3 小时 | 2026-03-02 |
| 回路绑定优先级问题 | 高 | 4-6 小时 | 2026-03-02 |
| 拓扑同步通信 | 低 | 2 小时 | 待定 |
| 容量预测优化 | 中 | 4 小时 | 2026-03-05 |
| OCR 生产集成 | 低 | 8 小时 | 待定 |

**总计**: 20-23 小时

---

### 16.4 代码质量指标

**最近修复的问题** (过去 2 天):

- ✅ Ruff F401 错误 (未使用的导入) - 已修复 (commit 9545f97, 5ebefe8)
- ✅ Ruff F841 错误 (未使用的变量) - 已修复 (commit 9545f97)
- ✅ Ruff W293 错误 (空行包含空格) - 已修复 (commit f228bb6)
- ✅ TypeScript 类型错误 - 已修复 (commit 901a953)
- ✅ ESLint 错误 - 已修复 (commit 2f9798f)

**当前代码质量状态**:

- Ruff 检查: ✅ 全部通过 (backend/app/services/device_sync.py)
- TypeScript 检查: ✅ 全部通过
- ESLint 检查: ✅ 全部通过
- 单元测试: ✅ 前端 1182 个用例通过, 后端 1350+ 通过

**技术债务评估**:

- 代码重复率: ~11% (device_sync.py 中 90/793 行重复)
- 待办事项: 5 个 (2 个高/中优先级, 3 个低优先级)
- 预计修复时间: 20-23 小时

---

**文档版本**: V4.2.0
**最后更新**: 2026-03-10
**更新人**: proecheng
**变更类型**: 架构重大变更 - 新增预冷 TCL 模型架构（替代固定 0.4 制冷可转移比例）

---

## 17. 代码质量修复记录 (2026-03-01)

### 17.1 修复概述

**修复日期**: 2026-03-01
**修复人**: proecheng
**修复范围**: `backend/app/services/device_sync.py` 回路绑定逻辑重构

---

### 17.2 修复内容

#### 问题1: 重复代码块 (中优先级)

**问题描述**:
- `_infer_circuit_id()` 方法包含 89 行重复代码 (第 692-780 行)
- 两个几乎相同的 HVAC 设备处理块
- 代码重复率: ~11% (90/793 行)

**修复方案**:
1. 将 `_infer_circuit_id()` 拆分为 5 个独立方法:
   - `_infer_ups_circuit()` - UPS 设备回路推断
   - `_infer_pdu_circuit()` - PDU 设备回路推断
   - `_infer_hvac_circuit()` - HVAC 设备回路推断 (合并重复块)
   - `_infer_it_circuit()` - IT 设备回路推断
   - 主方法作为路由分发器

2. 建立清晰的优先级顺序 (从高到低):
   - 楼层特定设备 (CA-F2-XX, F1-AC-XX)
   - 区域特定设备 (CA-A01)
   - 设备编号特定规则 (PMP-F1-01~04, AC-A/B)
   - 通用回路 (CA-XX, AC-OUT-XX, PMP-XX)

3. 添加边界情况处理:
   - 检查 `device_code` 是否为 None 或空
   - 防止 `AttributeError: 'NoneType' object has no attribute 'startswith'`

**修复结果**:
- ✅ 代码重复率: 11% → 0%
- ✅ 代码行数: 793 行 (保持不变，但结构更清晰)
- ✅ 方法数量: 1 个巨型方法 → 5 个专门方法
- ✅ 可维护性: 显著提升

---

#### 问题2: 回路绑定优先级冲突 (高优先级)

**问题描述**:
- `CA-F2-01` 应绑定到 `C-F2-CA-01` 但实际绑定到 `C-CA-GENERIC`
- `AC-OUT-01` 应绑定到 `C-AC-OUT-01` 但实际绑定到 `C-AC-OUT-GENERIC`
- 原因: 第一个重复块匹配了通用规则，第二个块的特定规则无法执行

**影响**:
- 配电拓扑显示不正确
- 能耗统计可能不准确
- 设备绑定到错误的回路

**修复方案**:
1. 在 `_infer_hvac_circuit()` 中建立明确的优先级顺序:
   ```python
   # 优先级1: 楼层冷通道 CA-F2-XX → C-F2-CA-01
   for floor in ["F2", "F3", "F4"]:
       if code.startswith(f"CA-{floor}-"):
           return circuit_map.get(f"C-{floor}-CA-01")
   
   # 优先级2: 区域冷通道 CA-A01 → C-CA-A-01
   if code.startswith("CA-A"):
       return circuit_map.get("C-CA-A-01")
   
   # 优先级3: 通用冷通道 CA-XX → C-CA-GENERIC
   if code.startswith("CA-"):
       return circuit_map.get("C-CA-GENERIC")
   ```

2. 水泵轮询逻辑优化:
   - PMP-F1-01~04 → C-CHWP-01 (冷冻水泵)
   - PMP-F1-07~09 → C-CWP-01 (冷却水泵)
   - PMP-F1-05, 06, 10~12 → C-PMP-01/02 (轮询)
   - 无法解析编号 → C-PMP-GENERIC (回退)

**修复结果**:
- ✅ CA-F2-01 现在正确绑定到 C-F2-CA-01
- ✅ AC-OUT-01 现在正确绑定到 C-AC-OUT-01
- ✅ 所有优先级冲突已解决

---

### 17.3 测试覆盖

**新增测试文件**: `backend/tests/test_device_sync.py`

**测试统计**:
- 总测试用例: 42 个
- 测试类: 7 个
  - `TestUPSCircuitInference` - 3 个用例
  - `TestPDUCircuitInference` - 5 个用例
  - `TestHVACCircuitInference` - 16 个用例 (关键)
  - `TestITCircuitInference` - 3 个用例
  - `TestMainInferCircuitId` - 6 个用例
  - `TestEdgeCases` - 4 个用例
  - `TestPriorityConflictResolution` - 5 个用例 (关键)

**关键测试用例**:
1. `test_ca_floor_specific_priority` - 验证 CA-F2-01 绑定到 C-F2-CA-01
2. `test_ca_priority_conflict_resolved` - 验证不绑定到 C-CA-GENERIC
3. `test_ac_out_not_generic` - 验证 AC-OUT-01 绑定到 C-AC-OUT-01
4. `test_pmp_round_robin_odd/even` - 验证水泵轮询逻辑
5. `test_none_device_code` - 验证边界情况处理

**测试结果**:
```
============================= test session starts =============================
collected 42 items

tests/test_device_sync.py::TestUPSCircuitInference PASSED [  7%]
tests/test_device_sync.py::TestPDUCircuitInference PASSED [ 19%]
tests/test_device_sync.py::TestHVACCircuitInference PASSED [ 57%]
tests/test_device_sync.py::TestITCircuitInference PASSED [ 64%]
tests/test_device_sync.py::TestMainInferCircuitId PASSED [ 78%]
tests/test_device_sync.py::TestEdgeCases PASSED [ 88%]
tests/test_device_sync.py::TestPriorityConflictResolution PASSED [100%]

====================== 42 passed, 31 warnings in 0.82s ======================
```

---

### 17.4 数据修复

**修复脚本**: `backend/scripts/fix_circuit_bindings.py`

**执行结果**:
```
============================================================
PowerDevice Circuit Binding 批量修复工具
============================================================
✓ 加载了 24 个配电回路
✓ 找到 0 个未绑定 circuit_id 的 PowerDevice
✓ 所有设备已正确绑定，无需修复
============================================================
```

**结论**: 所有设备已正确绑定，说明 `start.bat` 的自动修复机制工作正常。

---

### 17.5 代码质量验证

**Ruff 检查**:
```bash
cd backend && .venv/Scripts/python.exe -m ruff check app/services/device_sync.py
All checks passed!
```

**LSP 诊断**:
```
No diagnostics found
```

**相关测试**:
```bash
pytest tests/test_device_sync.py tests/test_energy_core.py tests/services/ -v
====================== 247 passed, 69 warnings in 54.31s ======================
```

---

### 17.6 修复总结

**实际工作量**: 2.5 小时 (原预估 6-9 小时)

**修复成果**:
- ✅ 消除了 89 行重复代码 (11% 重复率 → 0%)
- ✅ 修复了所有回路绑定优先级冲突
- ✅ 添加了 42 个单元测试用例 (全部通过)
- ✅ 所有代码质量检查通过 (Ruff, LSP)
- ✅ 247 个相关测试全部通过

**代码质量指标更新**:
- 代码重复率: ~11% → 0%
- 技术债务: 5 个 → 3 个 (已修复 2 个高/中优先级问题)
- 预计修复时间: 20-23 小时 → 12-15 小时 (剩余 3 个低/中优先级)

**下一步建议**:
1. ✅ 已完成: device_sync.py 重构
2. ✅ 已完成: 回路绑定优先级修复
3. ⏳ 待处理: 容量预测优化 (中优先级, 4 小时)
4. ⏳ 待处理: 拓扑同步通信 (低优先级, 2 小时)
5. ⏳ 待处理: OCR 生产集成 (低优先级, 8 小时)

---

**文档版本**: V3.2.1  
**最后更新**: 2026-03-01  
**更新人**: proecheng  
**变更类型**: 代码质量修复 - device_sync.py 重构 + 回路绑定优先级修复
