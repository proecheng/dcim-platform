---
stepsCompleted: [tech-stack, architecture-pattern, data-architecture, api-design, deployment]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, docs/project-knowledge/backend-architecture.md, docs/project-knowledge/frontend-architecture.md, docs/project-knowledge/integration-architecture.md]
---

# Architecture Document - DCIM 算力中心智能监控系统

**Author:** proecheng
**Date:** 2026-02-12
**Status:** 棕地补全（基于现有代码库逆向文档化）

---

## 1. 技术栈决策

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
| 数据库 | SQLite (dev) / PostgreSQL (prod) | — | 开发简单 / 生产可靠 |
| 迁移 | Alembic | 1.13.1 | SQLAlchemy 官方迁移工具 |
| 认证 | JWT (python-jose) + bcrypt | — | 无状态认证、密码安全 |
| WebSocket | websockets | 12.0 | 实时数据推送 |
| 定时任务 | APScheduler | 3.10.4 | 数据模拟器、定时统计 |
| 代理 | Express + http-proxy-middleware | 4.18 / 2.0 | 生产环境静态文件 + API 转发 |
| ML (可选) | PyTorch | 2.0+ | 条件加载，未安装时跳过 |

## 2. 架构模式

### 整体架构

```
浏览器 ──HTTP/WS──> Vite Dev(3000) 或 Express Proxy(3000) ──> FastAPI(8080) ──> SQLite/PostgreSQL
```

### 后端分层

```
app/
├── core/           # 基础设施层：配置、数据库、安全
├── models/         # 数据层：SQLAlchemy ORM 模型 (70+)
├── schemas/        # 接口层：Pydantic 请求/响应模型 (60+)
├── api/v1/         # 路由层：REST API 端点 (29 个模块)
├── services/       # 业务层：业务逻辑服务 (53 个)
│   └── analysis_plugins/  # 插件系统：6 个分析插件
└── ml_models/      # ML 层：可选机器学习模块
```

### 前端分层

```
src/
├── api/modules/    # API 层：27 个模块，Axios 封装
├── stores/         # 状态层：7 个 Pinia Store
├── composables/    # 逻辑层：6 个组合式函数
├── components/     # 组件层：66 个组件
├── views/          # 页面层：23 个页面视图
└── router/         # 路由层：路由配置 + 守卫
```

## 3. 数据架构

### 核心数据模型分组

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

### 数据库迁移策略

- 使用 Alembic 管理所有 schema 变更
- 开发环境使用 SQLite（文件：dcim.db）
- 生产环境使用 PostgreSQL
- 启动时自动创建表和初始数据（admin 用户、默认配置）

## 4. API 设计

### 认证

- POST `/api/v1/auth/login` — 登录获取 JWT
- POST `/api/v1/auth/refresh` — 刷新 token
- GET `/api/v1/auth/me` — 获取当前用户信息
- WebSocket 认证通过 query 参数：`?token=xxx`

### WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送 (5s) |
| alarms | `/ws/alarms?token=xxx` | 告警通知 |
| system | `/ws/system?token=xxx` | 系统状态 |

> 注意：`ConnectionManager` 内部字典中存在一个未使用的 `"control"` 键，实际路由使用 `"system"`。

### API 模块列表（29 个，28 个常驻 + 1 个条件加载）

auth, user, device, point, realtime, alarm, threshold, energy, regulation, pricing, demand, monitoring, topology, proposal, opportunities, execution, asset, operation, report, statistics, config, log, capacity, vpp, websocket, bigscreen, dispatch, load-shifting, schedule

> optimization 路由已注释（需 numpy），ml 路由条件加载（需 torch）

## 5. 部署架构

### 开发环境

```bash
# 后端
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 前端（Vite dev server，自动代理 /api → 8080）
cd frontend && npm run dev

# 或一键启动
start.bat  # Express proxy + 静态文件模式
```

### 生产环境（Docker Compose）

```yaml
services:
  backend:   # Python 3.11-slim, uvicorn, port 8000 (Dockerfile 默认)
  frontend:  # Node 18 build → Nginx 静态服务
```

> 注意：Dockerfile 默认端口为 8000，开发环境（start.bat/CLAUDE.md）使用 8080。部署时需统一。

## 6. 关键架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 异步 vs 同步 | 全异步 | WebSocket + 高并发数据采集需要 |
| ORM vs 原生 SQL | SQLAlchemy 2.0 async | 类型安全、迁移管理、关系映射 |
| 状态管理 | Pinia (非 Vuex) | Vue 3 原生支持、TypeScript 友好 |
| 组件导入 | unplugin-auto-import | 减少样板代码、提升开发效率 |
| ML 加载 | 条件导入 | torch 未安装时不影响核心功能 |
| 配置管理 | @lru_cache 单例 | 确保配置全局唯一 |

## 7. 安全架构

| 层面 | 机制 | 说明 |
|------|------|------|
| 认证 | JWT Bearer Token | python-jose 签发，query 参数传递给 WebSocket |
| 授权 | RBAC 三级角色 | admin/operator/viewer，通过 FastAPI Depends 注入 |
| 密码 | bcrypt 哈希 | passlib + bcrypt==4.0.1（锁定版本避免兼容问题） |
| 限流 | 登录接口 5次/分钟 | 防暴力破解 |
| CORS | FastAPI CORSMiddleware | 开发环境允许 localhost |
| 输入验证 | Pydantic v2 | 所有请求体自动验证 |

## 8. 错误处理策略

- 后端：FastAPI 全局异常处理器，统一返回 `{"detail": "错误信息"}` 格式
- 前端：Axios 响应拦截器，401 自动登出，其他错误 Element Plus Message 提示
- WebSocket：连接断开自动重连（前端 useWebSocket composable）
- 数据库：SQLAlchemy session 异常自动回滚
