# 开发指南

生成时间: 2026-03-17
项目版本: V4.2.0

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| npm | 9+ | 包管理 |
| Git | 2.x | 版本控制 |
| PostgreSQL | 16 (可选) | 生产数据库 |
| Redis | 7 (可选) | 缓存/分布式锁 |
| Docker | 24+ (可选) | 容器化部署 |

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd mytest1
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 注意: bcrypt 必须使用 4.0.1 版本 (与 passlib 1.7.4 兼容)
pip install "bcrypt==4.0.1"

# 数据库迁移
alembic upgrade head

# 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 开发模式 (推荐, 自动热更新)
npm run dev          # http://localhost:5173

# 或生产构建
npm run build        # 输出到 dist/
```

### 4. 一键启动 (Windows)

```bash
# 启动所有服务
start.bat            # http://localhost:3000

# 停止所有服务
stop.bat
```

## 开发模式 vs 生产模式

| 模式 | 前端 | 后端 | 前端更新 |
|------|------|------|----------|
| `npm run dev` | Vite 5173 | uvicorn 8080 | 自动热更新 |
| `start.bat` | Express 3000 | uvicorn 8080 | 需手动 `npm run build` |
| Docker Compose | Nginx 3000 | uvicorn 8080 | 需重新构建镜像 |

## 常用命令

### 后端

```bash
cd backend
.venv\Scripts\activate

# 运行测试
pytest                              # 全部测试
pytest tests/api/                   # API 测试
pytest tests/services/              # 服务层测试
pytest tests/api/test_auth.py       # 单个文件
pytest -k "test_login"              # 按名称匹配

# 数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
# 代码检查
ruff check app/
ruff format app/
```

### 前端

```bash
cd frontend

# 开发服务器
npm run dev

# 构建
npm run build

# 类型检查
npm run typecheck

# 代码检查
npm run lint
```

## 项目架构模式

### 后端分层

```
API 路由 (api/v1/) → 业务服务 (services/) → ORM 模型 (models/)
                                            → 数据库 (core/database.py)
```

- **API 层**: 路由定义、请求验证、响应格式化、RBAC 权限检查
- **服务层**: 业务逻辑、算法实现、外部服务调用
- **模型层**: 数据库表定义、关系映射

### 配置单例

```python
from app.core.config import get_settings
settings = get_settings()  # @lru_cache 确保唯一实例
```

### 异步数据库

```python
from app.core.database import async_session
async with async_session() as session:
    result = await session.execute(select(User))
```

### RBAC 权限

```python
# 三角色: admin > operator > viewer
from app.core.deps import require_admin, require_operator, require_viewer

@router.get("/", dependencies=[Depends(require_viewer)])
async def get_list(): ...

@router.post("/", dependencies=[Depends(require_operator)])
async def create_item(): ...

@router.delete("/{id}", dependencies=[Depends(require_admin)])
async def delete_item(): ...
```

### 前端自动导入

Vue/Pinia API 和 Element Plus 组件无需手动 import (unplugin-auto-import):

```vue
<script setup lang="ts">
// ref, computed, onMounted, ElMessage 等自动可用
const count = ref(0)
</script>
```

### WebSocket 认证

```javascript
new WebSocket(`ws://localhost:8080/ws/realtime?token=${jwt_token}`)
```

### API 代理

开发时 Vite 自动代理 `/api` 和 `/ws` 到后端 8080 端口 (vite.config.ts)。

## 数据模拟器

后端启动时自动运行 (可通过 `SIMULATION_ENABLED=false` 关闭):
- 每 5-10 秒为点位生成模拟数据
- AI 点位在量程范围内小幅波动 (±2%)
- DI 点位有 0.5% 概率触发告警
- 自动保存到 point_history 表

## 环境变量

关键环境变量 (`.env` 或系统环境):

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite+aiosqlite:///./dcim.db | 数据库连接 |
| SECRET_KEY | (随机生成) | JWT 签名密钥 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 480 | Token 有效期 |
| REDIS_URL | redis://localhost:6379 | Redis 连接 |
| MQTT_BROKER | localhost | MQTT 地址 |
| SIMULATION_ENABLED | true | 数据模拟器开关 |
| SEED_ENABLED | true | 种子数据开关 |
| DEMO_ENABLED | false | Demo 数据开关 |

## 常见问题

### 1. 登录失败 500 错误

bcrypt 5.0+ 与 passlib 1.7.4 不兼容。解决: `pip install "bcrypt==4.0.1"`

### 2. 端口被占用

```bash
netstat -ano | findstr ":8080" | findstr "LISTENING"
taskkill /F /PID <PID>
```

### 3. 前端修改不生效

`start.bat` 使用静态文件模式。修改后需 `cd frontend && npm run build`，或使用 `npm run dev` 开发模式。

### 4. 数据库表不存在

```bash
cd backend && alembic upgrade head
```

## 测试策略

| 层级 | 框架 | 位置 | 命令 |
|------|------|------|------|
| 后端 API | pytest + httpx | `backend/tests/api/` | `pytest tests/api/` |
| 后端服务 | pytest | `backend/tests/services/` | `pytest tests/services/` |
| 前端单元 | vitest | `frontend/src/**/*.test.ts` | `npm run test` |
| 类型检查 | vue-tsc | - | `npm run typecheck` |

## 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 | http://localhost:8080/docs |
| 开发前端 | http://localhost:5173 |

默认管理员: admin / admin123
