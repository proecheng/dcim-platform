# 项目知识库索引 - 算力中心智能监控系统 (DCIM)

> 本知识库由 BMAD Document Project 工作流自动生成
> 扫描模式: exhaustive (详尽扫描)
> 生成时间: 2026-03-23
> 项目版本: V4.2.0 (Epic 1-36)

---

## 项目概要

| 属性 | 值 |
|------|------|
| 项目类型 | Multi-part (3 部件) |
| 主要语言 | Python, TypeScript |
| 架构模式 | 三层架构 (前端 → 代理 → 后端) |

### 部件概览

| 部件 | 类型 | 技术栈 | 根目录 |
|------|------|--------|--------|
| backend | FastAPI 后端 | Python 3.11 / SQLAlchemy 2.0 | `backend/` |
| frontend | Vue 3 前端 | TypeScript 5.9 / Vite 5 | `frontend/` |
| proxy | Express 代理 | Node.js / Express 4.18 | `proxy/` |

### 规模统计 (2026-03-23 扫描)

| 指标 | 数量 |
|------|------|
| 后端 Python 文件 | 380 |
| API 端点模块 | 60 |
| REST API 端点 | **836** |
| ORM 数据模型 | **194** |
| Schema 文件 | 46 |
| 业务服务 | 157 |
| 数据库迁移 | 58 |
| 后端测试文件 | 203 |
| 前端 Vue/TS 文件 | 487 |
| 页面视图 | 98 |
| 可复用组件 | 90 |
| Pinia Store | 10 |
| 前端 API 模块 | 46 |
| 前端 Composable | 38 |
| 协议适配器 | 8 |
| 文档文件 | 169+ |

---

## 核心文档 (V4.2.0 — 2026-03-23 更新)

| 文档 | 说明 | 适用读者 |
|------|------|----------|
| [项目概览](project-overview.md) | 系统功能、技术栈、核心模块概述 | 所有人 |
| [系统架构](architecture-overview.md) | 整体架构设计、分层模式、技术决策 | 架构师 |
| [集成架构](integration-architecture.md) | 多部件通信、数据流、权限模型 | 架构师 |
| [源代码目录结构](source-tree.md) | ★ 完整注释源码树 + 关键指标 | 开发者 |
| [开发运维指南](dev-ops-guide.md) | ★ 环境配置、依赖版本、启动命令、测试、环境变量 | 开发者 |
| [后端 API 接口](api-contracts-backend.md) | ★ 60 模块、836 端点，按域分组 | 后端开发者 |
| [后端数据模型](data-models-backend.md) | ★ 36 文件、194 个 ORM 模型列级文档 | 后端开发者 |
| [前端组件清单](component-inventory-frontend.md) | ★ 98 页面 + 90 组件 + 10 Store + 46 API + 38 Composable | 前端开发者 |

★ = 2026-03-23 新生成/更新

## 架构文档

| 文档 | 说明 |
|------|------|
| [后端架构](backend-architecture.md) | API 设计、服务层、数据层详解 |
| [前端架构](frontend-architecture.md) | 组件体系、状态管理、路由 |
| [架构变更日志](architecture-v4.1.0-changelog.md) | V4.1.0 架构变更记录 |

## 参考文档

| 文档 | 说明 |
|------|------|
| [部署指南](deployment-guide.md) | Docker/手动部署、生产配置 |
| [遗留系统分析](legacy-system-analysis.md) | V4.0 原系统保留清单与增强策略 |
| [监测设备接口规范](device-interface-spec.md) | 14 类设备接口协议 |
| [热力学配置参考](thermal-config-reference.md) | RC 热力学模型配置参考 |
| [项目上下文](project-context.md) | AI 开发上下文摘要 |
| [大屏 PRD](prd-digital-twin-bigscreen.md) | 3D 数字孪生大屏需求文档 |
| [开发指南 (旧)](development-guide.md) | V4.1 时期开发指南 |
| [API 接口汇总 (旧)](api-contracts-summary.md) | V4.1 时期 API 文档 |
| [数据模型汇总 (旧)](data-models-summary.md) | V4.1 时期模型文档 |
| [源码目录 (旧)](source-tree-analysis.md) | V4.1 时期目录结构 |

---

## 快速参考

### 启动命令

```bash
# Windows 一键启动
start.bat            # http://localhost:3000

# 停止所有服务
stop.bat

# 手动启动后端
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 手动启动前端 (开发模式, 自动热更新)
cd frontend && npm run dev    # http://localhost:5173

# Docker 启动
docker-compose up -d
```

### 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 | http://localhost:8080/docs |
| 开发前端 | http://localhost:5173 |

### 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

---

## 维护说明

本知识库由 BMAD Document Project 工作流自动生成。

重新生成: 运行 `/bmad-bmm-document-project` 并选择扫描模式。

手动更新: 直接编辑 `docs/project-knowledge/` 下的 markdown 文件。

---

*生成工具: BMAD Framework v6.0.4*
*最后更新: 2026-03-23*
