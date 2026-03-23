# Development & Operations Guide

**Generated**: 2026-03-23 | **Scan Level**: Exhaustive

---

## 技术栈详情

### Backend

| 依赖 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.109.0 | Web 框架 |
| Uvicorn | 0.27.0 | ASGI 服务器 |
| SQLAlchemy | 2.0.25 | ORM (异步) |
| Pydantic | 2.5.3 | 数据验证 |
| Alembic | 1.13.1 | 数据库迁移 |
| aiosqlite | 0.19.0 | SQLite 异步驱动 |
| asyncpg | 0.29.0 | PostgreSQL 异步驱动 |
| python-jose | 3.3.0 | JWT 认证 |
| passlib | 1.7.4 | 密码哈希 |
| bcrypt | 4.0.1 | (锁定! >=5.0 与 passlib 不兼容) |
| APScheduler | 3.10.4 | 定时任务 |
| websockets | 12.0 | WebSocket |
| Redis | >=5.0.0 | 缓存/分布式锁 (可选) |
| NumPy | >=1.24.0 | 数值计算 |
| SciPy | >=1.11.0 | 优化算法 |
| scikit-learn | >=1.3.0 | 异常检测 |
| NetworkX | >=3.0 | 拓扑图分析 |
| openpyxl | 3.1.2 | Excel 导出 |
| ReportLab | >=4.0 | PDF 生成 |
| WeasyPrint | >=60.0 | Markdown→PDF |
| Jinja2 | >=3.1.0 | 模板渲染 |

### Frontend

| 依赖 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4.15 | 框架 |
| TypeScript | 5.9.3 | 类型系统 |
| Vite | 5.0.11 | 构建工具 |
| Element Plus | 2.5.3 | UI 组件库 |
| Pinia | 2.1.7 | 状态管理 |
| ECharts | 5.6.0 | 图表 |
| Three.js | 0.182.0 | 3D 渲染 |
| GSAP | 3.14.2 | 动画 |
| DataV-Vue3 | 1.7.4 | 大屏数据可视化 |
| vis-network | 10.0.2 | 网络拓扑图 |
| Axios | 1.6.5 | HTTP 客户端 |
| dayjs | 1.11.10 | 日期处理 |
| marked | 17.0.4 | Markdown 渲染 |
| highlight.js | 11.11.1 | 代码高亮 |
| v-scale-screen | 2.3.0 | 大屏缩放 |

### Dev Tools

| 工具 | 版本 | 用途 |
|------|------|------|
| Vitest | 4.0.18 | 前端单元测试 |
| Vue Test Utils | 2.4.6 | Vue 测试工具 |
| ESLint | 10.0.0 | 代码检查 |
| Playwright | (root) | E2E 测试 |
| Sass | 1.70.0 | CSS 预处理 |
| unplugin-auto-import | 0.17.3 | API 自动导入 |
| unplugin-vue-components | 0.26.0 | 组件自动导入 |

### Proxy

| 依赖 | 版本 | 用途 |
|------|------|------|
| Express | 4.18 | HTTP 代理 |
| http-proxy-middleware | — | API/WS 转发 |

---

## 开发环境设置

### 前置条件

- Python 3.11+
- Node.js 18+
- Git

### 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
alembic upgrade head         # 初始化数据库
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 前端启动

```bash
cd frontend
npm install
npm run dev                  # 开发模式 (localhost:5173)
npm run build                # 生产构建
```

### 代理启动

```bash
cd proxy
npm install
node server.js               # localhost:3000
```

### 一键启动 (Windows)

```bash
start.bat     # 启动所有服务
stop.bat      # 停止所有服务
```

---

## 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI Backend | 8080 | REST API + WebSocket |
| Vite Dev Server | 5173 | 前端开发热更新 |
| Express Proxy | 3000 | 生产入口 (静态+代理) |

---

## 数据库

### 开发 (SQLite)
- 文件: `backend/dcim.db`
- 启动时自动创建表 + 种子数据

### 生产 (PostgreSQL)
- 需配置 `DATABASE_URL` 环境变量
- `alembic upgrade head` 执行迁移

### 迁移命令

```bash
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
```

---

## 测试

### 后端 (pytest)

```bash
cd backend
pytest                       # 全部 (203 个测试文件)
pytest tests/api/            # API 集成测试
pytest tests/services/       # 服务单元测试
pytest -k "test_login"       # 按名称匹配
```

### 前端 (Vitest)

```bash
cd frontend
npm run test                 # 运行测试
npm run test:watch           # 监听模式
npm run typecheck            # TypeScript 类型检查
npm run lint                 # ESLint 检查
```

### E2E (Playwright)

```bash
npx playwright test          # 从项目根目录运行
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite+aiosqlite:///dcim.db | 数据库连接 |
| SECRET_KEY | (auto-generated) | JWT 签名密钥 |
| SIMULATION_ENABLED | true | 数据模拟器开关 |
| REDIS_URL | (none) | Redis 连接 (可选) |
| ML_ENABLED | false | ML 模块开关 |

---

## WebSocket 通道

| 通道 | URL | 推送频率 | 数据格式 |
|------|-----|---------|---------|
| realtime | `/ws/realtime?token=xxx` | 5 秒 | `{point_id, value, quality, timestamp}` |
| alarms | `/ws/alarms?token=xxx` | 事件驱动 | `{action, id, alarm_no, ...}` |
| system | `/ws/system?token=xxx` | 事件驱动 | `{type, datasource_id, ...}` |

---

## 定时任务

| 任务 | 间隔 | 说明 |
|------|------|------|
| 数据模拟器 | 5 秒 | 生成模拟点位数据 |
| 通信监控 | 30 秒 | 检查数据源连通性 |
| 网关健康 | 60 秒 | 探测 MS/TP 网关 |
| SOH 计算 | 定期 | 电池健康度计算 |
| 告警升级 | 定期 | 超时告警自动升级 |
| 回滚检查 | 定期 | 预冷回滚检测 |
| 每日统计 | 每日 | 告警/能源统计汇总 |

---

## 已知问题

1. **bcrypt 版本锁定**: 必须使用 4.0.1，>=5.0 与 passlib 不兼容
2. **Gateway adapters**: 仅存在 .pyc 编译文件，源码不在仓库中
3. **ML 模块**: 条件加载，需安装 torch 才可用
