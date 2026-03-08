# 部署指南

本文档提供算力中心智能监控系统 (DCIM) 的完整部署流程，涵盖开发、测试、生产环境的部署方案。

## 环境要求

### 硬件要求

| 环境 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 开发 | 2 核 | 4 GB | 20 GB | 本地开发测试 |
| 测试 | 4 核 | 8 GB | 50 GB | 集成测试环境 |
| 生产 | 8 核 | 16 GB | 200 GB | 推荐 SSD，支持 1000+ 点位 |

### 软件要求

| 组件 | 版本 | 必需 | 说明 |
|------|------|------|------|
| Python | 3.9+ | ✅ | 后端运行环境 |
| Node.js | 18+ | ✅ | 前端构建工具 |
| SQLite | 3.35+ | ✅ | 默认数据库 |
| PostgreSQL | 13+ | ⬜ | 生产环境推荐 |
| Redis | 6.0+ | ⬜ | 缓存加速（可选） |
| MQTT Broker | 3.1+ | ⬜ | 设备通信（可选） |

### 操作系统

- Windows 10/11 或 Windows Server 2019+
- Ubuntu 20.04+ / Debian 11+
- CentOS 8+ / Rocky Linux 8+

## 快速部署

### 方式一: 一键启动脚本（开发环境）

**Windows:**
```bash
# 1. 克隆代码
git clone <repository-url>
cd dcim

# 2. 一键启动
start.bat
```

**Linux/Mac:**
```bash
# 1. 克隆代码
git clone <repository-url>
cd dcim

# 2. 赋予执行权限
chmod +x start.sh

# 3. 一键启动
./start.sh
```

启动后访问:
- 前端: http://localhost:3000
- 后端 API: http://localhost:8080
- API 文档: http://localhost:8080/docs

默认账户: `admin` / `admin123`

### 方式二: Docker 部署（推荐生产环境）

```bash
# 1. 克隆代码
git clone <repository-url>
cd dcim

# 2. 构建并启动容器
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

## 手动部署

### 后端部署

#### 1. 创建虚拟环境

**Windows:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# 如需机器学习功能（可选）
pip install torch torchvision
```

#### 3. 配置环境变量

创建 `.env` 文件（参考 `.env.example`）:

```env
# 应用配置
APP_NAME=算力中心智能监控系统
APP_VERSION=3.2.0
DEBUG=false

# 服务器配置
HOST=0.0.0.0
PORT=8080

# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
# 生产环境推荐 PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dcim

# JWT 配置（必须修改）
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS 配置
CORS_ORIGINS=http://localhost:3000,http://your-domain.com

# 数据采集配置
COLLECT_INTERVAL=10
DATA_RETENTION_DAYS=30

# 模拟模式（生产环境关闭）
SIMULATION_ENABLED=false
DEMO_ENABLED=false
SIMULATION_INTERVAL=5

# 授权配置
LICENSE_KEY=DEMO-0000-0000-0000
MAX_POINTS=1000

# Redis 配置（可选）
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0

# MQTT 配置（可选）
MQTT_ENABLED=false
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=dcim-backend
```

#### 4. 初始化数据库

```bash
# 运行数据库迁移
alembic upgrade head

# 如果没有 alembic 迁移文件，首次启动会自动创建表
```

#### 5. 启动后端服务

**开发模式:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**生产模式:**
```bash
# 使用 Gunicorn + Uvicorn Workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### 前端部署

#### 1. 安装依赖

```bash
cd frontend
npm install
```

#### 2. 配置环境变量

创建 `.env.production` 文件:

```env
# API 地址
VITE_API_BASE_URL=http://your-domain.com:8080/api/v1
VITE_WS_URL=ws://your-domain.com:8080/ws

# 应用配置
VITE_APP_TITLE=算力中心智能监控系统
VITE_APP_VERSION=3.2.0
```

#### 3. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录。

#### 4. 部署静态文件

**方式 A: 使用 Nginx**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/dcim/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

**方式 B: 使用 Express 代理（已内置）**

```bash
cd proxy
npm install
node server.js
```

## 数据库配置

### SQLite（默认）

适用于开发和小规模部署（< 500 点位）。

```env
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
```

### PostgreSQL（推荐生产环境）

适用于大规模部署（> 500 点位）。

#### 1. 安装 PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**CentOS/Rocky:**
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 2. 创建数据库和用户

```bash
sudo -u postgres psql

CREATE DATABASE dcim;
CREATE USER dcim_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dcim TO dcim_user;
\q
```

#### 3. 配置连接

```env
DATABASE_URL=postgresql+asyncpg://dcim_user:your_password@localhost:5432/dcim
```

#### 4. 启用 TimescaleDB（可选，用于时序数据优化）

```bash
# 安装 TimescaleDB 扩展
sudo apt install postgresql-14-timescaledb

# 启用扩展
sudo -u postgres psql -d dcim
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

```env
TIMESCALEDB_ENABLED=true
```

## 可选组件配置

### Redis 缓存

提升实时数据查询性能。

#### 1. 安装 Redis

**Ubuntu/Debian:**
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

#### 2. 配置连接

```env
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

### MQTT Broker

用于设备数据采集。

#### 1. 安装 Mosquitto

**Ubuntu/Debian:**
```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

**Docker:**
```bash
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto
```

#### 2. 配置连接

```env
MQTT_ENABLED=true
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
MQTT_CLIENT_ID=dcim-backend
```

## 生产环境最佳实践

### 安全配置

1. **修改默认密码**
   - 登录后立即修改 `admin` 账户密码
   - 设置强密码策略（在系统设置中配置）

2. **生成安全密钥**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   将生成的密钥设置为 `SECRET_KEY`

3. **配置 HTTPS**
   - 使用 Nginx 配置 SSL 证书
   - 强制 HTTPS 重定向

4. **限制 CORS 来源**
   ```env
   CORS_ORIGINS=https://your-domain.com
   ```

5. **关闭调试模式**
   ```env
   DEBUG=false
   ```

### 性能优化

1. **数据库连接池**
   - SQLAlchemy 默认连接池大小: 5
   - 高并发场景可增加到 20-50

2. **启用 Redis 缓存**
   - 实时数据缓存 TTL: 10 秒
   - 统计数据缓存 TTL: 5 分钟

3. **配置数据保留策略**
   ```env
   DATA_RETENTION_DAYS=90
   ```
   定期清理历史数据，避免数据库膨胀

4. **使用 CDN**
   - 静态资源（JS/CSS/图片）使用 CDN 加速

### 监控与日志

1. **应用日志**
   - 后端日志位置: `backend/logs/`
   - 日志级别: INFO（生产）/ DEBUG（开发）

2. **系统监控**
   - CPU/内存/磁盘使用率
   - 数据库连接数
   - API 响应时间

3. **告警通知**
   - 配置邮件/短信告警
   - 监控服务可用性

### 备份策略

1. **数据库备份**
   ```bash
   # SQLite
   cp dcim.db dcim.db.backup.$(date +%Y%m%d)

   # PostgreSQL
   pg_dump -U dcim_user dcim > dcim_backup_$(date +%Y%m%d).sql
   ```

2. **自动备份脚本**
   ```bash
   # 每天凌晨 2 点备份
   0 2 * * * /path/to/backup.sh
   ```

3. **备份保留策略**
   - 每日备份保留 7 天
   - 每周备份保留 4 周
   - 每月备份保留 12 个月

## Docker 部署详解

### Dockerfile 配置

**后端 Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**前端 Dockerfile:**
```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql+asyncpg://dcim:dcim@db:5432/dcim
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./backend:/app
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=dcim
      - POSTGRES_USER=dcim
      - POSTGRES_PASSWORD=dcim
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  postgres_data:
```

### Docker 常用命令

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启服务
docker-compose restart backend

# 停止服务
docker-compose down

# 清理数据（谨慎使用）
docker-compose down -v
```

## 常见部署问题

### 1. 端口被占用

**症状:** 启动失败，提示端口 8080 或 3000 已被占用。

**解决方法:**
```bash
# Windows
netstat -ano | findstr ":8080"
taskkill /F /PID <PID>

# Linux
lsof -i :8080
kill -9 <PID>
```

### 2. 数据库连接失败

**症状:** 后端启动报错 `could not connect to database`。

**检查清单:**
- 数据库服务是否启动
- 连接字符串是否正确
- 用户名密码是否正确
- 防火墙是否开放端口

### 3. 前端无法访问后端 API

**症状:** 前端页面空白，控制台报 CORS 错误。

**解决方法:**
- 检查 `CORS_ORIGINS` 配置
- 确认后端服务正常运行
- 检查 Nginx 代理配置

### 4. WebSocket 连接失败

**症状:** 实时数据不更新。

**解决方法:**
- 检查 Nginx WebSocket 代理配置
- 确认防火墙允许 WebSocket 连接
- 检查 JWT Token 是否有效

### 5. 静态文件 404

**症状:** 前端页面样式丢失。

**解决方法:**
- 检查 Nginx root 路径配置
- 确认 `npm run build` 成功执行
- 检查文件权限

## 升级指南

### 从 V2.x 升级到 V3.x

1. **备份数据**
   ```bash
   cp dcim.db dcim.db.backup
   ```

2. **更新代码**
   ```bash
   git pull origin main
   ```

3. **更新依赖**
   ```bash
   cd backend
   pip install -r requirements.txt

   cd ../frontend
   npm install
   ```

4. **运行数据库迁移**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **重启服务**
   ```bash
   # 停止旧服务
   stop.bat

   # 启动新服务
   start.bat
   ```

## 性能基准

| 指标 | SQLite | PostgreSQL |
|------|--------|------------|
| 点位数量 | < 500 | > 1000 |
| 并发用户 | < 10 | > 50 |
| 数据写入 | 100 条/秒 | 1000 条/秒 |
| 查询响应 | < 100ms | < 50ms |
| 内存占用 | 500 MB | 1 GB |

## 定时任务配置

系统使用 APScheduler 管理定时任务，包括数据模拟、时间窗口调参分析等。

### 时间窗口调参定时任务

**任务说明**: 每天凌晨 2:00 自动分析各设备类型的告警持续时长，生成时间窗口调整建议。

**配置位置**: `backend/app/scheduler/jobs.py`

**默认配置**:
```python
# 每天凌晨 2:00 执行
scheduler.add_job(
    time_window_tuning_job,
    trigger='cron',
    hour=2,
    minute=0,
    id='time_window_tuning',
    replace_existing=True,
    misfire_grace_time=300  # 5分钟容错时间
)
```

**修改执行时间**:

编辑 `backend/app/scheduler/jobs.py`，修改 `hour` 和 `minute` 参数：

```python
# 示例：改为每天凌晨 3:30 执行
scheduler.add_job(
    time_window_tuning_job,
    trigger='cron',
    hour=3,
    minute=30,
    id='time_window_tuning',
    replace_existing=True,
    misfire_grace_time=300
)
```

**禁用定时任务**:

在 `backend/app/scheduler/jobs.py` 中注释掉相关代码：

```python
# scheduler.add_job(
#     time_window_tuning_job,
#     trigger='cron',
#     hour=2,
#     minute=0,
#     id='time_window_tuning',
#     replace_existing=True,
#     misfire_grace_time=300
# )
```

**手动触发**:

管理员可以在前端页面手动触发分析：
1. 登录系统（管理员账号）
2. 进入"策略域 > 智能诊断 > 时间窗口调参"页面
3. 点击"触发分析"按钮

**日志查看**:

定时任务执行日志位于 `backend/logs/app.log`：

```bash
# 查看最近的调参任务日志
tail -f backend/logs/app.log | grep "time_window_tuning"
```

**注意事项**:
- 定时任务需要至少 30 条准确诊断样本才会生成调整建议
- 调整建议需要管理员审批后才会生效
- 系统会通过邮件和 WebSocket 通知管理员审批
- 建议在业务低峰期（凌晨）执行，避免影响系统性能

## 技术支持

如遇到部署问题，请参考:
- [故障排查手册](troubleshooting-guide.md)
- [开发指南](development-guide.md)
- [API 文档](http://localhost:8080/docs)

或联系技术支持团队。
