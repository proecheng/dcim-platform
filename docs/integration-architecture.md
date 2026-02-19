# 集成架构

## 总体通信架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        浏览器 (Browser)                          │
│  Vue 3 + Element Plus + ECharts + Three.js                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ HTTP 请求    │  │ WebSocket    │  │ 静态资源 (HTML/JS/CSS)│    │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘    │
└─────────┼────────────────┼──────────────────────┼────────────────┘
          │                │                      │
          ▼                ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              代理层 (Proxy Layer) — 端口 3000                     │
│                                                                   │
│  开发模式: Vite Dev Server (vite.config.ts proxy 配置)            │
│  生产模式: Express.js (proxy/server.js)                           │
│                                                                   │
│  路由规则:                                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ /api/*     → http://localhost:8080/api/*   (HTTP 转发)    │    │
│  │ /ws/*      → ws://localhost:8080/ws/*      (WebSocket)    │    │
│  │ /docs      → http://localhost:8080/docs    (Swagger UI)   │    │
│  │ /openapi.json → http://localhost:8080/openapi.json        │    │
│  │ /*         → frontend/dist/index.html      (SPA 回退)     │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              后端层 (Backend Layer) — 端口 8080                    │
│                                                                   │
│  FastAPI 应用 (app/main.py)                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ CORS 中间件 (允许 localhost:5173, localhost:3000)          │    │
│  │ API v1 路由 (/api/v1/*)  — 47 个模块                      │    │
│  │ WebSocket 路由 (/ws/realtime, /ws/alarms, /ws/system)     │    │
│  │ 健康检查 (/api/health, /api/stats)                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  后台任务:                                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 数据模拟器 (5s) │ 告警引擎 (30s) │ 通信监控 (30s)         │    │
│  │ 告警升级 (60s)  │ PUE记录 (15m)  │ 能耗聚合 (30m)         │    │
│  │ 节能检测 (1h)   │ 效果追踪 (6h)                           │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              数据层 (Data Layer)                                   │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ SQLite/PG    │  │ Redis (可选)  │  │ MQTT (可选)   │           │
│  │ (主数据库)    │  │ (缓存)       │  │ (设备通信)    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

## 前端 → 代理 → 后端 通信流程

### HTTP API 调用链

```
前端组件 (Vue)
  → Pinia Store (状态管理)
    → API 模块 (frontend/src/api/modules/*.ts)
      → Axios 实例 (frontend/src/utils/request.ts)
        → HTTP 请求 /api/v1/*
          → 代理层 (Vite proxy 或 Express)
            → FastAPI 路由 (backend/app/api/v1/*.py)
              → 业务服务 (backend/app/services/*.py)
                → 数据库 (SQLAlchemy async session)
```

### WebSocket 实时数据流

```
后端模拟器 (simulator.py, 每5秒)
  → 生成模拟数据
    → 告警引擎检查 (alarm_engine.py)
      → 事件总线发布 (event_bus.py)
        → 联动引擎响应 (linkage_engine.py)
    → WebSocket 管理器广播 (websocket.py)
      → /ws/realtime 通道
        → 代理层转发
          → 前端 WebSocket 客户端 (composables/useWebSocket.ts)
            → Pinia Store 更新 (stores/realtime.ts)
              → Vue 组件响应式更新
```

### 告警处理流

```
数据采集 → 告警引擎阈值检查
  → 触发告警
    → 事件总线发布 "linkage" 事件
      → 联动引擎匹配策略
        → 交叉确认服务 (消防场景)
        → 执行联动动作
      → 诊断引擎分析
    → WebSocket 推送到前端 (/ws/alarms)
    → 告警升级引擎定时检查
```

## 代理层配置详解

### 开发模式 — Vite Dev Server

配置文件: `frontend/vite.config.ts`

```typescript
server: {
  port: 3000,
  host: '0.0.0.0',
  proxy: {
    '/api': {
      target: 'http://localhost:8080',
      changeOrigin: true
    },
    '/ws': {
      target: 'ws://localhost:8080',
      ws: true
    }
  }
}
```

特点:
- 自动热更新 (HMR)
- 前端代码修改即时生效
- 适合前端开发

### 生产模式 — Express Proxy

配置文件: `proxy/server.js`

```javascript
// API 代理
app.use('/api', createProxyMiddleware({ target: BACKEND_URL, ws: true }));
// WebSocket 代理
app.use('/ws', createProxyMiddleware({ target: BACKEND_URL, ws: true }));
// Swagger 代理
app.use('/docs', createProxyMiddleware({ target: BACKEND_URL }));
// 静态文件服务
app.use(express.static(path.join(__dirname, '..', 'frontend', 'dist')));
// SPA 回退
app.get('*', (req, res) => res.sendFile('index.html'));
```

特点:
- 服务 frontend/dist/ 静态文件
- 前端修改需重新 `npm run build`
- 适合演示和生产部署

## 认证集成

### JWT 令牌流

```
1. 用户登录
   POST /api/v1/auth/login (username + password)
   → 后端验证 → 返回 access_token + refresh_token

2. API 请求认证
   前端 Axios 拦截器自动添加 Authorization: Bearer <token>
   → 后端 OAuth2PasswordBearer 中间件验证

3. WebSocket 认证
   前端连接时传递 token 参数:
   new WebSocket(`ws://host/ws/realtime?token=${jwt_token}`)
   → 后端 verify_websocket_token() 验证

4. 令牌刷新
   access_token 过期 → 使用 refresh_token 获取新令牌
```

### CORS 配置

后端允许的前端地址 (通过环境变量配置):
- `http://localhost:5173` (Vite 开发服务器)
- `http://localhost:3000` (代理服务器)

## 数据库集成

### 异步数据库访问

```python
# 引擎创建 (core/database.py)
engine = create_async_engine(settings.database_url, echo=settings.debug)

# 会话工厂
async_session = async_sessionmaker(engine, class_=AsyncSession)

# 依赖注入
async def get_db():
    async with async_session() as session:
        yield session
```

### 数据库迁移

使用 Alembic 管理数据库迁移:
```bash
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
```

## 事件驱动架构

### 事件总线 (Event Bus)

```
事件发布者                    事件总线                    事件订阅者
┌──────────┐              ┌──────────┐              ┌──────────────────┐
│ 告警引擎  │──publish──>│ event_bus │──dispatch──>│ 联动引擎          │
│ 模拟器    │              │          │              │ 交叉确认服务      │
│ 通信监控  │              │          │              │ 诊断引擎          │
└──────────┘              └──────────┘              └──────────────────┘
```

### 引擎协作

| 引擎 | 触发方式 | 输入 | 输出 |
|------|----------|------|------|
| 告警引擎 | 数据采集时检查阈值 | 点位数据 | 告警事件 |
| 联动引擎 | 订阅事件总线 | 告警事件 | 联动动作 |
| 交叉确认 | 订阅事件总线 | 告警事件 | 确认结果 |
| 诊断引擎 | 订阅事件总线 | 告警事件 | 诊断结果 |
| 升级引擎 | 定时检查 (60s) | 未处理告警 | 升级通知 |
| 恢复引擎 | 联动执行后 | 联动记录 | 恢复动作 |

## 部署架构

### 开发环境

```
开发者机器
├── 后端: uvicorn --reload (端口 8080)
├── 前端: vite dev server (端口 3000/5173)
└── 数据库: SQLite (dcim.db)
```

### 生产环境

```
服务器
├── 后端: uvicorn (端口 8080)
├── 代理: Express proxy (端口 3000) 或 Nginx
├── 数据库: PostgreSQL
├── 缓存: Redis
└── 可选: Docker Compose 编排
```

### Docker 部署

```yaml
services:
  backend:
    build: ./backend
    ports: ["8080:8080"]
    volumes: ["./backend/dcim.db:/app/dcim.db"]
  frontend:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [backend]
```
