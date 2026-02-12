# 项目知识库索引 - 算力中心智能监控系统 (DCIM)

> 本知识库由 BMAD Document Project 工作流自动生成
> 扫描模式: exhaustive (详尽扫描)
> 生成时间: 2026-02-04 (重新扫描更新)

---

## 📋 快速导航

| 文档 | 说明 | 适用读者 |
|------|------|----------|
| [项目概览](project-overview.md) | 系统功能、技术栈、版本历史概述 | 所有人 |
| [开发指南](development-guide.md) | 环境配置、启动方式、开发工作流 | 开发者 |
| [部署指南](deployment-guide.md) | Docker/手动部署、生产配置、备份 | 运维人员 |
| [集成架构](integration-architecture.md) | 多部分通信、数据流、认证机制 | 架构师、开发者 |
| [后端架构](backend-architecture.md) | API 设计、数据模型、服务层 | 后端开发者 |
| [前端架构](frontend-architecture.md) | 组件体系、状态管理、路由 | 前端开发者 |
| [源码目录树](source-tree.md) | 完整文件结构和注释 | 开发者、维护者 |

---

## 📊 系统概要

### 技术栈

| 部分 | 核心技术 | 版本 |
|------|----------|------|
| **前端** | Vue 3 + TypeScript + Vite | 3.4.15 / 5.9.3 / 5.0.11 |
| **UI** | Element Plus + ECharts + Three.js | 2.5.3 / 5.6.0 / 0.182.0 |
| **后端** | FastAPI + SQLAlchemy + PyTorch | 0.109.0 / 2.0.25 / 2.0+ |
| **数据库** | SQLite (开发) / PostgreSQL (生产) | - |
| **代理** | Express + http-proxy-middleware | 4.18 / 2.0 |

### 规模统计 (2026-02-04 更新)

| 指标 | 数量 |
|------|------|
| **前端** | |
| Vue 文件 | 99 |
| TypeScript 文件 | 90+ |
| 代码行数 | ~55,000 |
| 页面视图 | 23 |
| 组件 | 67 |
| Composables | 19 (含 12 大屏相关) |
| API 模块 | 27 |
| Pinia Store | 7 |
| **后端** | |
| Python 文件 | ~120 |
| API 路由模块 | 32 |
| 数据库模型 | 70+ |
| Pydantic Schema | 60+ |
| 服务文件 | 53 |
| 分析插件 | 7 |
| ML 模块 | 15 (Transformer/GNN/RL) |

---

## 📁 文档详情

### 1. 项目概览 (`project-overview.md`)

**内容:**
- 系统简介和定位
- 8 大功能模块详解
- 技术架构图
- 版本迭代历史 (V1.0 → V3.0)
- 快速启动命令

**适用场景:** 了解系统全貌、向新成员介绍项目

---

### 2. 开发指南 (`development-guide.md`)

**内容:**
- 环境要求 (Python 3.11+, Node.js 18+)
- 三种启动方式 (一键脚本 / 手动 / Docker)
- 项目目录结构
- 后端开发工作流
- 前端开发工作流
- 测试方法
- 数据库迁移 (Alembic)
- 代码规范
- 常见问题

**适用场景:** 新开发者入门、日常开发参考

---

### 3. 部署指南 (`deployment-guide.md`)

**内容:**
- 部署架构图
- Docker Compose 部署 (推荐)
- Windows 手动部署
- Linux 手动部署 + Nginx 配置
- systemd 服务管理
- PostgreSQL 生产配置
- 数据备份策略
- 安全配置 (SECRET_KEY, CORS, HTTPS)
- 监控与日志

**适用场景:** 生产部署、运维管理

---

### 4. 集成架构 (`integration-architecture.md`)

**内容:**
- 多部分架构图 (浏览器→代理→后端→数据库)
- 通信矩阵 (HTTP/WebSocket/文件系统)
- Proxy 服务详解
- 前端 → 后端 API 集成
- WebSocket 实时通信 (3 个频道)
- 数据流图 (实时数据流/告警流/API 请求流)
- JWT 认证机制
- 状态管理 (7 个 Pinia Store)
- 错误处理
- 配置同步
- 性能优化

**适用场景:** 理解系统通信、集成问题排查

---

### 5. 后端架构 (`backend-architecture.md`)

**内容:**
- 技术栈详情
- 应用分层结构 (core/models/schemas/api/services/ml_models)
- 系统启动流程 (lifespan)
- API 路由结构 (31+ 端点分类列表)
- 数据库模型详解 (50+ 表)
  - 用户与权限
  - 设备与点位
  - 告警系统
  - 能源管理 (核心)
  - 时序数据
  - 节能方案
  - 电费优化
- 服务层架构 (30+ 服务)
- 分析插件系统 (6 个内置插件)
- 机器学习模块 (GNN/RL/Transformer)
- 认证与权限 (JWT + RBAC)
- 数据库迁移 (Alembic)

**适用场景:** 后端开发、API 设计、数据建模

---

### 6. 前端架构 (`frontend-architecture.md`)

**内容:**
- 技术栈详情
- 应用分层架构图
- 路由结构 (23 个页面)
- 状态管理 (7 个 Pinia Store)
- API 层 (18 个模块)
- WebSocket 通信封装
- 组合式函数 (19 个 Composables)
  - useRealtime, useAlarm, usePermission, useEnergy, useSound
  - 大屏相关 (8 个)
- 组件库 (69 个组件分类)
- 样式系统 (CSS 变量 + 主题)
- 布局系统 (MainLayout)
- 构建配置 (Vite)
- 关键业务流程

**适用场景:** 前端开发、组件设计、状态管理

---

### 7. 源码目录树 (`source-tree.md`)

**内容:**
- 完整项目目录结构
- 每个文件/目录的简要说明
- 统计摘要

**适用场景:** 快速定位文件、理解项目结构

---

## 🔧 快速参考

### 启动命令

```bash
# Windows 一键启动
start.bat

# Linux/Mac 一键启动
./start.sh

# Docker 启动
docker-compose up -d

# 手动启动后端
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080

# 手动启动前端 (开发模式)
cd frontend && npm run dev

# 手动启动代理
cd proxy && node server.js
```

### 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 | http://localhost:8080/docs |
| ReDoc | http://localhost:8080/redoc |

### 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

### 核心目录

```
mytest1/
├── frontend/src/          # 前端源码
├── backend/app/           # 后端源码
├── proxy/server.js        # 代理入口
├── docs/project-knowledge/ # 本知识库
└── docker-compose.yml     # 容器编排
```

---

## 📝 维护说明

本知识库由 **BMAD Document Project** 工作流自动生成。

**重新生成文档:**
1. 运行 `/bmad-bmm-document-project`
2. 选择项目类型和扫描级别
3. 等待扫描完成
4. 文档将生成到 `docs/project-knowledge/` 目录

**手动更新:**
直接编辑 `docs/project-knowledge/` 下的 markdown 文件。

---

*生成工具: BMAD Framework v6.0.0*
*最后更新: 2026-02-04*
