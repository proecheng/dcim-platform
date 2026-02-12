# 开发指南 - 算力中心智能监控系统 (DCIM)

## 环境要求

### 必需软件

| 软件 | 最低版本 | 推荐版本 | 用途 |
|------|----------|----------|------|
| Python | 3.9+ | 3.11 | 后端运行环境 |
| Node.js | 18+ | 20 LTS | 前端构建与代理服务 |
| npm | 9+ | 10+ | 前端包管理 |
| Git | 2.30+ | 最新 | 版本控制 |

### 可选软件

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker | 20.10+ | 容器化部署 |
| Docker Compose | 2.0+ | 多容器编排 |
| pnpm | 8+ | 替代 npm (更快) |
| VS Code | 最新 | 推荐 IDE |

## 快速开始

### 方式一：一键启动（推荐）

**Windows:**
```batch
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

脚本会自动：
1. 检查 Python 和 Node.js 环境
2. 安装后端 Python 依赖
3. 初始化 SQLite 数据库
4. 安装前端 npm 依赖
5. 构建前端静态文件
6. 启动后端服务 (端口 8080)
7. 启动代理服务 (端口 3000)
8. 打开浏览器

### 方式二：手动启动

#### 后端服务

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境（首次）
python -m venv .venv

# 3. 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

#### 前端服务

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器（带热重载）
npm run dev
```

#### 代理服务（可选）

```bash
# 生产模式时需要代理服务
cd proxy
npm install
npm start
```

### 方式三：Docker 部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端开发服务器 | 3000 | Vite 开发服务器 / 代理服务 |
| 后端 API | 8080 | FastAPI 服务 |
| API 文档 | 8080/docs | Swagger UI |
| API ReDoc | 8080/redoc | ReDoc 文档 |
| WebSocket | 8080/ws/* | 实时数据推送 |

## 项目结构

```
mytest1/
├── backend/           # FastAPI 后端
│   ├── app/           # 应用源码
│   │   ├── api/       # REST API 路由
│   │   ├── core/      # 核心配置
│   │   ├── models/    # SQLAlchemy 模型
│   │   ├── schemas/   # Pydantic 模式
│   │   ├── services/  # 业务逻辑
│   │   └── ml_models/ # 机器学习模型
│   ├── alembic/       # 数据库迁移
│   └── tests/         # 测试套件
│
├── frontend/          # Vue 3 前端
│   ├── src/
│   │   ├── api/       # API 调用模块
│   │   ├── components/# 可复用组件
│   │   ├── views/     # 页面组件
│   │   ├── stores/    # Pinia 状态管理
│   │   ├── composables/# 组合式函数
│   │   └── utils/     # 工具函数
│   └── public/        # 静态资源
│
├── proxy/             # Express 反向代理
├── docs/              # 项目文档
└── docker-compose.yml # Docker 编排
```

## 开发工作流

### 后端开发

1. **添加新 API 端点**
   - 在 `backend/app/api/v1/` 创建路由文件
   - 在 `backend/app/schemas/` 定义请求/响应模式
   - 在 `backend/app/api/v1/__init__.py` 注册路由

2. **添加数据模型**
   - 在 `backend/app/models/` 创建 SQLAlchemy 模型
   - 创建 Alembic 迁移：`alembic revision --autogenerate -m "描述"`
   - 执行迁移：`alembic upgrade head`

3. **添加业务服务**
   - 在 `backend/app/services/` 创建服务类
   - 在 API 路由中注入使用

### 前端开发

1. **添加新页面**
   - 在 `frontend/src/views/` 创建 Vue 组件
   - 在 `frontend/src/router/index.ts` 添加路由

2. **添加 API 调用**
   - 在 `frontend/src/api/modules/` 创建 API 模块
   - 使用 `request.ts` 工具发起请求

3. **添加状态管理**
   - 在 `frontend/src/stores/` 创建 Pinia store
   - 在 `frontend/src/stores/index.ts` 导出

## 测试

### 后端测试

```bash
cd backend

# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_integration.py

# 生成覆盖率报告
pytest --cov=app tests/
```

### 前端测试

```bash
cd frontend

# 类型检查
npm run typecheck

# 构建检查
npm run build:check
```

## 环境配置

### 后端配置 (.env)

```env
APP_NAME=算力中心智能监控系统
APP_VERSION=2.0.0
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
SECRET_KEY=your-secret-key-change-in-production
MAX_POINTS=100
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 前端配置 (.env)

```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## 数据库管理

### 初始化数据库

```bash
cd backend

# 数据库会在首次启动时自动初始化
# 手动初始化
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
```

### 数据库迁移

```bash
cd backend

# 创建迁移
alembic revision --autogenerate -m "Add new table"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 初始化示例数据

```bash
cd backend

# 初始化点位数据
python init_points.py

# 初始化历史数据（30天）
python init_history.py

# 初始化能源设备
python init_energy.py
```

## 代码规范

### 后端

- 使用 Python 3.9+ 类型注解
- 遵循 PEP 8 代码风格
- 使用 Pydantic 进行数据验证
- 异步优先 (async/await)

### 前端

- 使用 TypeScript 严格模式
- 遵循 Vue 3 Composition API 风格
- 使用 `<script setup>` 语法
- 组件命名使用 PascalCase

## 常见问题

### 端口被占用

```bash
# Windows - 查找并终止进程
netstat -ano | findstr :8080
taskkill /PID <进程ID> /F

# Linux/Mac
lsof -i:8080
kill -9 <进程ID>
```

### 数据库锁定

```bash
# 删除锁定的数据库文件重新初始化
rm backend/dcim.db
# 重启后端服务
```

### 前端构建失败

```bash
# 清除缓存重新安装
cd frontend
rm -rf node_modules
rm package-lock.json
npm install
```

## 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

---

*最后更新: 2026-02-01*
