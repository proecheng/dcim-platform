# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

算力中心智能监控系统 (DCIM) - 数据中心基础设施管理系统，含实时监控、告警、能源管理、3D 数字孪生等功能。

## 服务启动与停止

### 启动/停止流程（重要）

**端口**: 后端 8080, 代理 3000。启动前必须确保端口空闲。

```bash
# 停止所有服务（推荐在每次启动前执行）
stop.bat

# 一键启动（Windows）- 已内置端口清理逻辑
start.bat
```

### Claude Code 启动服务规范

**Claude Code 在终端启动后端/前端服务时，必须遵循以下流程：**

1. **先检查端口占用**：`netstat -ano | findstr ":8080" | findstr "LISTENING"` 和 `:3000`
2. **如果端口被占用，先清理**：用 `taskkill /F /PID <pid>` 杀掉占用进程
3. **等待端口释放**：清理后等待 2-3 秒再启动
4. **启动后端**：`cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080`
5. **等待后端就绪**：启动后等待 5-6 秒，或检测 8080 端口可用
6. **启动代理**：`cd proxy && node server.js`
7. **不要重复启动**：如果服务已在运行且端口正常，不要重复启动

### 前端代码修改后的构建规范（重要）

**`start.bat` 使用 proxy + 静态文件模式，不会自动热更新前端代码！**

修改前端代码后，必须检查并重新构建：

```bash
# 1. 检查 dist 是否过期（比较时间戳）
ls -la frontend/dist/index.html    # 查看构建时间
ls -la frontend/src/views/xxx.vue  # 查看源码修改时间

# 2. 如果源码比 dist 新，必须重新构建
cd frontend && npm run build

# 3. 刷新浏览器（Ctrl+Shift+R 强制刷新）
```

**开发模式（推荐用于前端开发）：**
```bash
# 使用 Vite 开发服务器，自动热更新
cd frontend && npm run dev
# 访问 http://localhost:5173（Vite 默认端口）
```

| 启动方式 | 前端更新方式 | 适用场景 |
|---------|------------|---------|
| `start.bat` | 需手动 `npm run build` | 演示、测试后端 |
| `npm run dev` | 自动热更新 | 前端开发 |

### 常用开发命令

```bash
# 后端 (FastAPI, 端口 8080)
cd backend
.venv\Scripts\activate             # Windows（Linux: source .venv/bin/activate）
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 前端 (Vue 3, 端口 3000)
cd frontend
npm install
npm run dev                        # 开发服务器（自动代理 /api → 8080）
npm run build                      # 生产构建
npm run typecheck                  # TypeScript 类型检查

# 后端测试
cd backend
pytest                             # 全部测试
pytest tests/api/                  # API 测试
pytest tests/services/             # 服务层测试
pytest tests/api/test_auth.py      # 单个测试文件
pytest tests/ -k "test_login"      # 按名称匹配单个测试

# 数据库迁移 (Alembic)
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
```

## 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 (Swagger) | http://localhost:8080/docs |

默认管理员: admin / admin123

---

## 架构

```
浏览器 ──HTTP/WS──> Vite Dev(3000) 或 Express Proxy(3000) ──> FastAPI(8080) ──> SQLite/PostgreSQL
```

### 三层架构

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| **前端** | Vue 3 + TypeScript + Vite + Element Plus | ECharts 图表, Three.js 3D |
| **代理** | 开发: Vite proxy / 生产: Express (proxy/) | 静态文件 + API/WS 转发 |
| **后端** | FastAPI + SQLAlchemy 2.0 (异步) | JWT 认证, RBAC 权限, WebSocket |

### 核心功能模块

- **环境监控** - 实时数据采集 (5秒), WebSocket 推送
- **告警管理** - 4 级告警, 声音通知
- **能源管理** - PUE 监控, 配电拓扑, 需量管理
- **节能优化** - 6 种分析插件
- **3D 数字孪生** - Three.js 模型, 热力图
- **资产运维** - 资产台账, 工单, 巡检, 知识库

---

## 项目结构

```
frontend/src/
├── api/modules/       # API 模块
├── components/        # 组件库 (common/, charts/, energy/, bigscreen/)
├── composables/       # 组合式函数
├── stores/            # Pinia (user, app, alarm, realtime, energy, opportunity, bigscreen)
├── views/             # 页面视图
└── router/            # 路由配置

backend/app/
├── api/v1/            # REST API 路由 (30+ 个模块)
├── models/            # SQLAlchemy ORM 模型
├── schemas/           # Pydantic Schema
├── services/          # 业务服务
│   └── analysis_plugins/  # 分析插件
├── ml_models/         # 机器学习模型 (可选, 需 torch)
└── core/              # 配置、数据库、安全
```

---

## 关键开发模式

### 后端

**配置单例** - 使用 `@lru_cache()` 确保配置唯一:
```python
from app.core.config import get_settings
settings = get_settings()
```

**异步数据库** - SQLAlchemy 2.0 异步模式:
```python
from app.core.database import async_session
async with async_session() as session:
    result = await session.execute(select(User))
```

**WebSocket 认证** - JWT token 通过 query 参数传递:
```javascript
new WebSocket(`ws://localhost:8080/ws/realtime?token=${jwt_token}`)
```

**ML 模块条件加载** - torch 未安装时跳过:
```python
# backend/app/api/v1/__init__.py
try:
    from .ml import router as ml_router
    _ml_available = True
except ImportError:
    _ml_available = False
```

### 前端

**自动导入** - Vue/Pinia API 和 Element Plus 组件无需手动 import (unplugin-auto-import):
```vue
<script setup lang="ts">
// ref, computed, onMounted 等自动可用
const count = ref(0)
</script>
```

**API 代理** - 开发时 Vite 自动代理 `/api` 和 `/ws` 到后端 (vite.config.ts)

### WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送 |
| alarms | `/ws/alarms?token=xxx` | 告警通知 |
| system | `/ws/system?token=xxx` | 系统状态 |

---

## 数据模拟器

后端启动时自动运行数据模拟器 (可通过 `SIMULATION_ENABLED=false` 关闭):
- 每 5 秒为点位生成模拟数据
- AI 点位在量程范围内小幅波动 (±2%)
- DI 点位有 0.5% 概率触发告警
- 自动保存到 point_history 表

---

## 语言要求

**强制使用中文**: 对话交流、技术文档、代码注释、Git 提交信息。

---

## 详细文档

`docs/project-knowledge/` 包含完整项目文档: 架构、开发指南、部署指南等。

*最后更新: 2026-02-03*
