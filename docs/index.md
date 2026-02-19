# 算力中心智能监控系统 (DCIM) — 项目文档索引

> 本文档由 BMAD Document Project 工作流自动生成，基于对项目源码的穷举扫描。
> 生成时间: 2026-02-17 | 扫描模式: exhaustive | 文档语言: 中文

---

## 项目概览

算力中心智能监控系统 (DCIM) 是一套数据中心基础设施管理系统，涵盖实时环境监控、多级告警、能源管理、3D 数字孪生、资产运维等核心功能。系统采用前后端分离架构，通过 WebSocket 实现实时数据推送。

| 属性 | 值 |
|------|-----|
| 版本 | V2.3.3 |
| 默认管理员 | admin / admin123 |
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 | http://localhost:8080/docs |

---

## 快速参考 — 技术栈

| 部件 | 技术栈 | 端口 | 入口文件 |
|------|--------|------|----------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Three.js + Pinia | 3000 (dev: 5173) | `frontend/src/main.ts` |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Pydantic + JWT + WebSocket + Alembic | 8080 | `backend/app/main.py` |
| 代理 | Express.js + http-proxy-middleware + cors | 3000 | `proxy/server.js` |

### 数据库

| 类型 | 用途 | 连接方式 |
|------|------|----------|
| SQLite | 开发/演示 | `sqlite+aiosqlite:///./dcim.db` |
| PostgreSQL | 生产环境 | 配置 `DATABASE_URL` 环境变量 |
| Redis | 缓存 (可选) | `redis://localhost:6379/0` |

### 源码规模

| 指标 | 数量 |
|------|------|
| 后端 API 模块 | 47 |
| 后端数据模型 | 100+ 类 (27 文件) |
| 后端服务文件 | 60+ |
| 后端引擎文件 | 7 |
| 后端 Schema 文件 | 31 |
| 前端页面 | 60 |
| 前端组件 | 74 |
| Pinia 状态仓库 | 8 |
| 组合式函数 | 18 |
| 前端 API 模块 | 30+ |

---

## 生成的文档列表

以下文档均由穷举扫描自动生成，覆盖项目架构、API、数据模型、组件清单等各方面。

### 架构文档

| 文档 | 说明 |
|------|------|
| [项目概览](project-overview.md) | 项目整体介绍、功能模块、技术架构概述 |
| [源码树分析](source-tree-analysis.md) | 完整目录结构、文件分类统计、模块依赖关系 |
| [前端架构](architecture-frontend.md) | Vue 3 应用架构、路由设计、状态管理、组件体系 |
| [后端架构](architecture-backend.md) | FastAPI 应用架构、分层设计、引擎系统、中间件 |
| [集成架构](integration-architecture.md) | 前后端集成方式、WebSocket 通道、代理配置、认证流程 |

### API 与数据

| 文档 | 说明 |
|------|------|
| [API 契约 (后端)](api-contracts-backend.md) | 全部 47 个 API 模块的端点清单、请求/响应格式 |
| [数据模型 (后端)](data-models-backend.md) | 100+ SQLAlchemy 模型定义、表关系、字段说明 |

### 组件与开发

| 文档 | 说明 |
|------|------|
| [前端组件清单](component-inventory-frontend.md) | 74 个组件 + 60 个页面的分类清单、Props/Events 说明 |
| [开发指南](development-guide.md) | 环境搭建、开发规范、调试技巧、常见问题排查 |

### 结构化数据

| 文档 | 说明 |
|------|------|
| [项目部件定义](project-parts.json) | 多部件项目结构的 JSON 描述 (前端/后端/代理) |
| [扫描状态报告](project-scan-report.json) | 工作流执行状态、步骤完成情况、扫描统计 |

---

## 现有文档列表

以下文档为项目原有文档，非本次工作流生成：

| 文档 | 位置 | 说明 |
|------|------|------|
| [README](../README.md) | 项目根目录 | 项目介绍、快速开始、API 模块列表 |
| [CLAUDE.md](../CLAUDE.md) | 项目根目录 | AI 辅助开发指南、架构说明、开发规范 |
| [DEPLOY.md](../DEPLOY.md) | 项目根目录 | 部署指南 |
| [用户使用说明书](用户使用说明书.md) | docs/ | 完整用户手册 |
| [设备调节能力配置指南](设备调节能力配置指南.md) | docs/ | 设备配置说明 |
| [负荷转移系统技术文档](负荷转移系统技术文档.md) | docs/ | 负荷转移技术详情 |
| [项目知识库](project-knowledge/) | docs/project-knowledge/ | 详细项目文档集 |

---

## 快速开始指南

### 一键启动 (Windows)

```bash
# 启动所有服务
start.bat

# 停止所有服务
stop.bat
```

启动后访问 http://localhost:3000，使用 admin / admin123 登录。

### 手动启动

```bash
# 1. 启动后端 (端口 8080)
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 2. 启动前端开发服务器 (端口 5173，自动代理到后端)
cd frontend
npm install
npm run dev
```

### 生产构建

```bash
# 构建前端静态文件
cd frontend && npm run build

# 通过 Express 代理提供服务 (端口 3000)
cd proxy && node server.js
```

---

## AI 辅助开发指南

本项目配置了 `CLAUDE.md` 文件，为 AI 编码助手提供项目上下文。关键要点：

- **语言要求**: 对话、文档、注释、提交信息均使用中文
- **服务启动**: 启动前必须检查端口占用 (8080/3000)
- **前端热更新**: `start.bat` 模式需手动 `npm run build`；开发模式 (`npm run dev`) 自动热更新
- **已知问题**: `bcrypt` 必须锁定为 4.0.1 版本以兼容 `passlib`
- **ML 模块**: `torch` 为可选依赖，未安装时自动跳过
- **数据库迁移**: 使用 Alembic (`alembic upgrade head`)
- **WebSocket 认证**: JWT token 通过 query 参数传递

详见 [CLAUDE.md](../CLAUDE.md)。

---

## 核心功能模块速查

| 功能域 | 前端页面 | 后端 API | 数据模型 |
|--------|----------|----------|----------|
| 环境监控 | Dashboard, MonitorView | realtime, points, devices | Point, Device, PointHistory |
| 告警管理 | AlarmView, AlarmRules | alarms, alarm_rules | Alarm, AlarmRule, AlarmConfig |
| 能源管理 | EnergyDashboard, PUE, Distribution | energy (30+ 端点) | EnergyDevice, PUERecord, EnergyStatistics (43 模型) |
| 节能优化 | OpportunityView, AnalysisPlugins | opportunities, analysis | Opportunity, AnalysisPlugin |
| 3D 数字孪生 | BigScreen, ThreeScene | bigscreen | BigScreenConfig |
| 资产运维 | AssetView, WorkOrder, Inspection | assets, work_orders, inspections | Asset, WorkOrder, InspectionPlan |
| 系统管理 | UserManage, RoleManage, Settings | users, roles, auth, configs | User, Role, Permission |

---

*本索引文档由 BMAD Document Project 工作流生成 — 扫描级别: exhaustive*
