# CLAUDE.md - 算力中心智能监控系统 (DCIM)

> 本文件为 Claude Code 提供项目开发指导信息

## 快速参考

### 常用开发命令

```bash
# === 一键启动 ===
start.bat                          # Windows 一键启动
./start.sh                         # Linux/Mac 一键启动
docker-compose up -d               # Docker 启动

# === 后端 (FastAPI) ===
cd backend
python -m venv .venv               # 创建虚拟环境
.venv\Scripts\activate             # Windows 激活
source .venv/bin/activate          # Linux/Mac 激活
pip install -r requirements.txt    # 安装依赖
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080  # 开发服务器
python run.py                      # 使用启动脚本

# === 前端 (Vue 3) ===
cd frontend
npm install                        # 安装依赖
npm run dev                        # 开发服务器 (端口 3000)
npm run build                      # 生产构建
npm run build:check                # 类型检查 + 构建
npm run typecheck                  # 仅类型检查
npm run preview                    # 预览生产构建

# === 数据库迁移 (Alembic) ===
cd backend
alembic revision --autogenerate -m "描述"  # 创建迁移
alembic upgrade head               # 应用迁移
alembic downgrade -1               # 回滚一步
```

### 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 (Swagger) | http://localhost:8080/docs |
| API 文档 (ReDoc) | http://localhost:8080/redoc |

### 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

---

## 高层架构

```
浏览器 ──HTTP/WS──> 代理 (Express:3000) ──> 后端 (FastAPI:8080) ──> 数据库 (SQLite/PostgreSQL)
```

### 三层架构

| 层级 | 技术栈 | 职责 |
|------|--------|------|
| **前端** | Vue 3 + TypeScript + Vite + Element Plus | 23 页面, 69 组件, 7 Pinia Store |
| **代理** | Express + http-proxy-middleware | 静态文件 + API/WS 转发 |
| **后端** | FastAPI + SQLAlchemy 2.0 + PyTorch | 31+ API 端点, 50+ 数据库表, 3 ML 模型 |

### 核心功能模块

1. **环境监控** - 实时数据采集 (5秒), WebSocket 推送
2. **告警管理** - 4 级告警, 声音通知, 告警屏蔽
3. **能源管理** - PUE 监控, 配电拓扑, 需量管理
4. **节能优化** - 6 种分析插件, 方案模板 (A1-A5, B1)
5. **电费优化** - 6 类可调度负荷, 96 时段调度
6. **VPP 虚拟电厂** - 负荷分析, 投资回报
7. **3D 数字孪生** - Three.js 模型, 热力图, 4 种主题
8. **资产运维** - 资产台账, 工单, 巡检, 知识库

---

## 项目结构

```
mytest1/
├── frontend/                    # Vue 3 前端
│   └── src/
│       ├── api/modules/         # API 模块 (18个)
│       ├── components/          # 组件库 (69个)
│       ├── composables/         # 组合式函数 (19个)
│       ├── stores/              # Pinia Store (7个)
│       ├── views/               # 页面视图 (23个)
│       ├── router/              # 路由配置
│       ├── layouts/             # 布局组件
│       └── utils/               # 工具函数
├── backend/                     # FastAPI 后端
│   └── app/
│       ├── api/v1/              # REST API 路由 (31+端点)
│       ├── models/              # ORM 模型 (50+表)
│       ├── schemas/             # Pydantic Schema
│       ├── services/            # 业务服务 (30+)
│       │   └── analysis_plugins/  # 分析插件 (6个)
│       ├── ml_models/           # 机器学习 (GNN/RL/Transformer)
│       └── core/                # 核心配置
├── proxy/                       # Express 代理
│   └── server.js
├── docs/project-knowledge/      # 项目知识库文档
├── docker-compose.yml
├── start.bat / start.sh
└── CLAUDE.md                    # 本文件
```

---

## 开发规范

### 后端开发

- **框架**: FastAPI + SQLAlchemy 2.0 (异步)
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **认证**: JWT + OAuth2 + bcrypt
- **权限**: RBAC 角色权限模型
- **迁移**: Alembic 管理数据库迁移

**API 路由结构**:
- 认证: `/api/v1/auth`
- 用户: `/api/v1/users`
- 设备: `/api/v1/devices`
- 点位: `/api/v1/points`
- 实时: `/api/v1/realtime`
- 告警: `/api/v1/alarms`
- 能源: `/api/v1/energy`
- 拓扑: `/api/v1/topology`
- 调度: `/api/v1/dispatch`
- VPP: `/api/v1/vpp`

### 前端开发

- **框架**: Vue 3.4 + TypeScript + Vite
- **UI**: Element Plus 2.5 + ECharts 5.6 + Three.js 0.182
- **状态**: Pinia (7个 Store: user, app, alarm, realtime, energy, opportunity, bigscreen)
- **样式**: SCSS + CSS Variables (深色科技风主题)

**组件分类**:
- `components/common/` - 通用组件
- `components/charts/` - ECharts 图表
- `components/energy/` - 能源管理组件 (24个)
- `components/bigscreen/` - 大屏组件 (30+)
- `components/monitor/` - 监控组件

### WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime` | 实时数据推送 |
| alarms | `/ws/alarms` | 告警通知 |
| system | `/ws/system` | 系统状态 |

---

## 关键业务流程

### 认证流程
```
登录 → JWT Token → localStorage → 请求自动携带 Bearer Token → 401 时自动跳转登录
```

### 能源数据加载
```
页面加载 → useEnergy().loadAllData() → 并发获取多项数据 → 启动轮询/WebSocket
```

### 告警处理
```
WebSocket 告警 → 按级别播放声音 → 显示通知 → 用户确认/解决
```

---

## 测试

```bash
# 后端测试
cd backend
pytest                            # 运行所有测试
pytest tests/api/                 # API 测试
pytest tests/services/            # 服务测试

# 前端类型检查
cd frontend
npm run typecheck
```

---

## 环境配置

### 后端 (.env)
```env
APP_NAME=算力中心智能监控系统
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
SECRET_KEY=your-secret-key
MAX_POINTS=100
```

### 前端 (.env)
```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

---

## 数据模拟器

系统内置数据模拟采集器，后端启动时自动运行:
- 每 5 秒为 52 个点位生成模拟数据
- AI 点位在量程范围内小幅波动 (±2%)
- DI 点位有 0.5% 概率触发告警
- 自动保存历史记录到 point_history 表

---

## 语言要求

**强制使用中文**进行:
- 对话交流
- 技术说明和文档
- 代码注释
- Git 提交信息

---

## 详细文档

完整项目文档位于 `docs/project-knowledge/`:
- `index.md` - 主索引
- `project-overview.md` - 项目概览
- `backend-architecture.md` - 后端架构
- `frontend-architecture.md` - 前端架构
- `integration-architecture.md` - 集成架构
- `development-guide.md` - 开发指南
- `deployment-guide.md` - 部署指南
- `source-tree.md` - 完整源码树

---

*最后更新: 2026-02-01*
