# 开发指南

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.9+ (推荐 3.10+) | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| npm | 随 Node.js | 包管理 |
| Git | 最新 | 版本控制 |

## 快速开始

### 方式一: 一键启动

```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh && ./start.sh
```

启动后访问: http://localhost:3000
默认管理员: admin / admin123

### 方式二: 手动启动

#### 后端服务 (端口 8080)

```bash
cd backend

# 创建虚拟环境 (首次)
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务 (开发模式, 自动重载)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

#### 前端服务 (端口 3000)

```bash
cd frontend

# 安装依赖 (首次)
npm install

# 开发模式 (热更新)
npm run dev

# 访问 http://localhost:3000 (Vite 代理模式)
```

### 方式三: Docker 部署

```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

## 常用开发命令

### 后端命令

```bash
cd backend

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 运行全部测试
pytest

# 运行 API 测试
pytest tests/api/

# 运行服务层测试
pytest tests/services/

# 运行单个测试文件
pytest tests/api/test_auth.py

# 按名称匹配测试
pytest tests/ -k "test_login"

# 数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
```

### 前端命令

```bash
cd frontend

# 开发服务器 (自动代理 /api → 8080)
npm run dev

# 生产构建
npm run build

# TypeScript 类型检查
npm run typecheck

# 预览构建产物
npm run preview
```

## 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 FastAPI | 8080 | API + WebSocket |
| 前端 Vite Dev | 3000 (或 5173) | 开发服务器 |
| Express Proxy | 3000 | 生产代理 |
| Redis | 6379 | 缓存 (可选) |
| MQTT | 1883 | 设备通信 (可选) |

## 访问地址

| 服务 | URL |
|------|-----|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 (Swagger) | http://localhost:8080/docs |
| API 文档 (ReDoc) | http://localhost:8080/redoc |

## 前端开发模式说明

| 启动方式 | 前端更新方式 | 适用场景 |
|---------|------------|---------|
| `start.bat` | 需手动 `npm run build` | 演示、测试后端 |
| `npm run dev` | 自动热更新 (HMR) | 前端开发 |

使用 `start.bat` 时，修改前端代码后必须:
1. `cd frontend && npm run build`
2. 浏览器 Ctrl+Shift+R 强制刷新

## 后端配置

### 环境变量 (.env)

```env
APP_NAME=算力中心智能监控系统
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
SECRET_KEY=your-secret-key
MAX_POINTS=100
SIMULATION_ENABLED=true
SIMULATION_INTERVAL=5
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
MQTT_ENABLED=true
MQTT_HOST=localhost
MQTT_PORT=1883
```

### 配置单例模式

```python
from app.core.config import get_settings
settings = get_settings()  # @lru_cache 确保单例
```

### 异步数据库访问

```python
from app.core.database import async_session
async with async_session() as session:
    result = await session.execute(select(User))
```

## 前端配置

### 环境变量 (.env)

```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

### 自动导入

Vue/Pinia API 和 Element Plus 组件无需手动 import (unplugin-auto-import):

```vue
<script setup lang="ts">
// ref, computed, onMounted 等自动可用
const count = ref(0)
</script>
```

### API 代理配置

开发时 Vite 自动代理 (vite.config.ts):
- `/api/*` → `http://localhost:8080`
- `/ws/*` → `ws://localhost:8080`

### 路径别名

`@` 映射到 `frontend/src/`

## WebSocket 开发

### 连接方式

```javascript
// JWT token 通过 query 参数传递
new WebSocket(`ws://localhost:8080/ws/realtime?token=${jwt_token}`)
```

### 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | /ws/realtime?token=xxx | 实时数据推送 (5秒间隔) |
| alarms | /ws/alarms?token=xxx | 告警通知 |
| system | /ws/system?token=xxx | 系统状态 |

## 数据模拟器

后端启动时自动运行，每 5 秒为 52 个点位生成模拟数据:
- AI 点位: 量程范围内小幅波动 (±2%)
- DI 点位: 0.5% 概率触发告警
- 自动保存到 point_history 表
- 通过 `SIMULATION_ENABLED=false` 关闭

## ML 模块 (可选)

深度学习节能优化模块需要安装 torch:

```bash
pip install torch>=2.0.0
```

未安装时自动跳过，不影响其他功能。

## 技术栈详情

### 后端依赖

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | 0.109.0 | Web 框架 |
| uvicorn | 0.27.0 | ASGI 服务器 |
| sqlalchemy | 2.0.25 | ORM (异步) |
| aiosqlite | 0.19.0 | SQLite 异步驱动 |
| alembic | 1.13.1 | 数据库迁移 |
| python-jose | 3.3.0 | JWT 令牌 |
| passlib | 1.7.4 | 密码哈希 |
| bcrypt | 4.0.1 | 密码加密 (锁定版本) |
| pydantic | 2.5.3 | 数据验证 |
| pydantic-settings | 2.1.0 | 配置管理 |
| websockets | 12.0 | WebSocket |
| apscheduler | 3.10.4 | 定时任务 |
| openpyxl | 3.1.2 | Excel 导出 |
| httpx | ≥0.25.0 | HTTP 客户端 |
| PyYAML | ≥6.0 | YAML 配置 |
| reportlab | ≥4.0 | PDF 生成 |
| torch | ≥2.0.0 | 深度学习 (可选) |

### 前端依赖

| 包 | 版本 | 用途 |
|----|------|------|
| vue | 3.4.15 | 前端框架 |
| vue-router | 4.2.5 | 路由 |
| pinia | 2.1.7 | 状态管理 |
| element-plus | 2.5.3 | UI 组件库 |
| echarts | 5.6.0 | 图表 |
| vue-echarts | 6.7.3 | ECharts Vue 封装 |
| three | 0.182.0 | 3D 渲染 |
| axios | 1.6.5 | HTTP 客户端 |
| dayjs | 1.11.10 | 日期处理 |
| gsap | 3.14.2 | 动画 |
| countup.js | 2.9.0 | 数字动画 |
| marked | 17.0.1 | Markdown 渲染 |
| highlight.js | 11.11.1 | 代码高亮 |
| v-scale-screen | 2.3.0 | 大屏缩放 |
| @kjgl77/datav-vue3 | 1.7.4 | 数据可视化 |

### 代理依赖

| 包 | 版本 | 用途 |
|----|------|------|
| express | 4.18.2 | Web 框架 |
| http-proxy-middleware | 2.0.6 | 代理中间件 |
| cors | 2.8.5 | 跨域支持 |

## 常见问题排查

### 登录失败 500 错误

原因: bcrypt 5.0+ 与 passlib 1.7.4 不兼容

```bash
cd backend
.venv\Scripts\python.exe -m pip install "bcrypt==4.0.1"
# 重启后端
```

### 端口被占用

```bash
# 查看占用
netstat -ano | findstr ":8080" | findstr "LISTENING"
netstat -ano | findstr ":3000" | findstr "LISTENING"

# 杀掉进程
taskkill /F /PID <PID>

# 或直接运行
stop.bat
```

### 前端修改不生效

使用 `start.bat` 时需手动重新构建:
```bash
cd frontend && npm run build
```
推荐使用 `npm run dev` 开发模式。

### 数据库表不存在

```bash
cd backend
alembic upgrade head
# 或删除 dcim.db 重启后端自动重建
```
