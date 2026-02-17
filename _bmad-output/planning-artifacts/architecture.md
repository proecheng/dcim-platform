---
stepsCompleted: [tech-stack, architecture-pattern, data-architecture, api-design, deployment, protocol-adapters, linkage-engine, video-integration, physical-topology, nfr-support]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, _bmad-output/planning-artifacts/product-brief.md, docs/project-knowledge/project-context.md, docs/project-knowledge/backend-architecture.md, docs/project-knowledge/frontend-architecture.md, docs/project-knowledge/integration-architecture.md]
workflowType: 'architecture'
project_name: 'DCIM'
user_name: 'proecheng'
date: '2026-02-15'
---

# Architecture Decision Document - DCIM 算力中心智能监控系统

**Author:** proecheng
**Date:** 2026-02-15
**Status:** 完整版（基于 PRD 2026-02-15 全面重建）

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
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────────────────┐ │
│  │ 数据质量 │ │ 定时任务 │ │         MQTT 客户端（订阅网关数据）       │ │
│  └──────────┘ └──────────┘ └──────────────────────────────────────────┘ │
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
| 应用服务层 | 业务逻辑、API、实时处理 | FastAPI + 内嵌 MQTT 客户端 + 联动引擎 + 告警引擎 |
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
│   └── data_quality.py      # 数据质量检测
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

### 3.2 现有模型扩展字段

| 模型 | 新增字段 | 说明 |
|------|---------|------|
| Point | `data_quality` | 数据质量标记（正常/不可靠/疑似漂移） |
| Point | `gateway_id`, `datasource_id` | 关联到采集网关和数据源 |
| Device | `site_id`, `template_id` | 关联到站点和设备模板 |
| PointHistory | 迁移到 TimescaleDB hypertable | `time` 列分区，启用压缩 |
| Alarm | `linkage_policy_id` | 告警触发联动策略关联 |
| Cabinet | `row_number`, `column_number`, `aisle_type`, `cooling_zone_id` | 物理拓扑空间位置 |

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

### 4.3 API 模块列表

**现有模块（29 个）：** auth, user, device, point, realtime, alarm, threshold, energy, regulation, pricing, demand, monitoring, topology, proposal, opportunities, execution, asset, operation, report, statistics, config, log, capacity, vpp, websocket, bigscreen, dispatch, load-shifting, schedule

**新增模块（8 个）：**

| 模块 | 路径前缀 | 核心端点 | 阶段 |
|------|---------|---------|------|
| 数据源管理 | `/api/v1/datasources` | CRUD、连接测试、点位批量导入（Excel）、导入预校验、写入权限管理 | MVP |
| 网关管理 | `/api/v1/gateways` | 网关列表、状态查看、远程配置下发、重启、OTA 升级触发 | MVP |
| 设备模板 | `/api/v1/device-templates` | CRUD、按厂商/型号查询、从模板创建数据源 | MVP |
| 联动策略 | `/api/v1/linkage` | 策略 CRUD、启用/禁用、手动触发测试、执行日志、恢复流程 | Phase 2 |
| 视频监控 | `/api/v1/video` | 摄像头 CRUD、NVR 管理、联动录像事件、云台控制指令转发 | Phase 2 |
| 物理拓扑 | `/api/v1/topology/physical` | 空间/制冷/三相拓扑配置、智能选址推荐 | Phase 2 |
| 站点管理 | `/api/v1/sites` | 站点 CRUD、站点切换、跨站点汇总 | 推广阶段 |
| 数据质量 | `/api/v1/data-quality` | 点位质量状态查询、漂移检测结果、质量统计 | MVP 基础版 |

**现有模块扩展：**

| 模块 | 扩展内容 |
|------|---------|
| `/api/v1/devices` | 新增 `template_id` 关联、按网关/数据源筛选、批量操作 |
| `/api/v1/points` | 新增 `data_quality` 字段返回、按网关/数据源筛选 |
| `/api/v1/alarms` | 新增联动策略关联、告警升级规则配置 |
| `/api/v1/realtime` | 数据源从 Redis 缓存读取（替代直接查库） |

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
