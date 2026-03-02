# 算力中心智能监控系统 - 部署指南

> 版本: V3.0 | 日期: 2026-02-24

---

## 目录

1. [数据模拟与采集说明](#数据模拟与采集说明)
2. [发布文件清单](#发布文件清单)
3. [服务器环境要求](#服务器环境要求)
4. [部署步骤](#部署步骤)
5. [Nginx 配置](#nginx-配置)
6. [数据库配置](#数据库配置)
7. [环境变量说明](#环境变量说明)
8. [安全配置](#安全配置)
9. [数据备份](#数据备份)
10. [监控与日志](#监控与日志)
11. [常见问题](#常见问题)

---

## 数据模拟与采集说明

系统内置数据模拟器，后端启动时自动运行（可通过环境变量 `SIMULATION_ENABLED=false` 关闭）。

| 项目 | 说明 |
|------|------|
| 采集周期 | 默认每 10 秒采集一次（`COLLECT_INTERVAL` 控制），模拟数据间隔 5 秒（`SIMULATION_INTERVAL` 控制） |
| AI 点位 | 在量程范围内小幅波动（±2%），模拟真实传感器数据 |
| DI 点位 | 有 0.5% 概率触发状态变化，模拟开关量告警 |
| 数据存储 | 自动保存到 `point_history` 表 |
| 数据保留 | 默认保留 30 天（`DATA_RETENTION_DAYS` 控制） |
| 最大点位数 | 默认 100 个（`MAX_POINTS` 控制） |

生产环境部署时，建议关闭模拟器并接入真实采集网关（支持 Modbus TCP/RTU、SNMP v2c/v3、MQTT、HTTP/REST、BACnet/IP、OPC-UA 等协议）。

---

## 发布文件清单

```
mytest1/
├── backend/
│   ├── app/                    # 后端应用代码（必需）
│   ├── alembic/                # 数据库迁移脚本（必需）
│   ├── alembic.ini             # Alembic 配置（必需）
│   ├── gateway/                # 采集网关模块（必需，含多协议适配器）
│   │   ├── adapters/           # 协议适配器（Modbus/SNMP/MQTT/HTTP/BACnet/OPC-UA）
│   │   ├── mqtt_client.py      # MQTT 客户端
│   │   ├── scheduler.py        # 采集调度器
│   │   └── requirements.txt    # 网关额外依赖
│   ├── requirements.txt        # Python 依赖清单（必需）
│   ├── requirements-ml.txt     # 机器学习可选依赖（可选，需 torch）
│   ├── .env.example            # 后端环境变量模板
│   ├── Dockerfile              # 后端容器构建文件
│   └── dcim.db                 # SQLite 数据库（可选，首次启动自动创建）
├── frontend/
│   ├── src/                    # 前端源码（开发时需要）
│   ├── dist/                   # 前端构建产物（部署必需，需先执行 npm run build）
│   ├── nginx.conf              # Nginx 配置模板（Docker 部署用）
│   ├── Dockerfile              # 前端容器构建文件
│   └── package.json            # 前端依赖清单
├── proxy/
│   ├── server.js               # Express 代理服务（一键启动使用）
│   └── package.json            # 代理依赖清单
├── deploy/
│   └── nginx/
│       ├── dcim.conf           # 生产 Nginx HTTPS 配置模板
│       └── deploy-https.sh     # HTTPS 部署脚本
├── docker-compose.yml          # Docker Compose 编排文件
├── .env.example                # Docker Compose 环境变量模板
├── start.bat                   # Windows 一键启动脚本
├── start.sh                    # Linux/Mac 一键启动脚本
└── stop.bat                    # Windows 停止脚本
```

---

## 服务器环境要求

### Docker Compose 部署（推荐）

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Linux（Ubuntu 20.04+）/ Windows Server 2019+ | Ubuntu 22.04 LTS |
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 50 GB SSD | 200 GB SSD |
| Docker | 20.10+ | 最新稳定版 |
| Docker Compose | 2.0+ | 最新稳定版 |

### 手动部署

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| Python | 3.9+ | 3.11+ |
| Node.js | 18+ | 20 LTS |
| npm | 8+ | 10+ |
| Nginx | 1.18+（Linux 手动部署时需要） | 1.24+ |

---

## 部署步骤

### 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端浏览器                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP / WebSocket
┌─────────────────────────────────────────────────────────────┐
│                Nginx / Proxy 服务（端口 3000/80）            │
│  • 静态文件服务（前端 dist/）                                │
│  • API 反向代理（/api → backend:8080）                       │
│  • WebSocket 代理（/ws → backend:8080）                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI 后端服务（端口 8080）                    │
│  • REST API 服务                                            │
│  • WebSocket 实时推送                                       │
│  • 数据模拟器 / 采集引擎                                     │
│  • 机器学习引擎（可选）                                      │
└─────────────────────────────────────────────────────────────┘
                    │              │              │
                    ▼              ▼              ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │PostgreSQL│  │  Redis   │  │   EMQX   │
            │TimescaleDB│  │  缓存    │  │ MQTT代理 │
            │  :5432   │  │  :6379   │  │  :1883   │
            └──────────┘  └──────────┘  └──────────┘
```

---

### 方式一：Docker Compose 部署（推荐）

Docker Compose 编排包含 5 个服务：

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| postgres | timescale/timescaledb:latest-pg16 | 5432 | PostgreSQL + TimescaleDB 时序数据库 |
| redis | redis:7-alpine | 6379 | 缓存与消息队列 |
| emqx | emqx/emqx:5 | 1883 / 8083 / 18083 | MQTT 代理（TCP / WebSocket / 管理面板） |
| backend | FastAPI（本地构建） | 8080 | 后端 API 服务 |
| nginx | Nginx（本地构建） | 3000 → 80 | 前端静态文件 + 反向代理 |

#### 第一步：准备环境

```bash
# 确认 Docker 和 Docker Compose 已安装
docker --version
docker compose version
```

#### 第二步：配置环境变量

在项目根目录创建 `.env` 文件：

```env
# ===== 应用配置 =====
APP_NAME=算力中心智能监控系统
DEBUG=false

# ===== 数据库（PostgreSQL + TimescaleDB）=====
POSTGRES_DB=dcim
POSTGRES_USER=dcim
POSTGRES_PASSWORD=请修改为强密码
TIMESCALEDB_ENABLED=true

# ===== JWT 认证 =====
SECRET_KEY=请修改为至少32位的随机字符串
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== CORS =====
CORS_ORIGINS=http://localhost:3000

# ===== Redis =====
REDIS_PORT=6379

# ===== MQTT（EMQX）=====
MQTT_PORT=1883
MQTT_WS_PORT=8083
EMQX_DASHBOARD_PORT=18083
MQTT_USERNAME=
MQTT_PASSWORD=

# ===== 数据采集 =====
SIMULATION_ENABLED=true
COLLECT_INTERVAL=10
DATA_RETENTION_DAYS=30
MAX_POINTS=100

# ===== 端口映射 =====
BACKEND_PORT=8080
NGINX_PORT=3000
POSTGRES_PORT=5432
```

#### 第三步：构建并启动

```bash
# 构建并启动所有服务（后台运行）
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 仅查看后端日志
docker compose logs -f backend
```

#### 第四步：验证部署

```bash
# 后端健康检查
curl http://localhost:8080/api/health
# 预期返回: {"status":"healthy"}

# 检查所有服务状态
docker compose ps
# 所有服务应显示 "Up (healthy)"
```

#### 第五步：访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| 系统入口 | http://localhost:3000 | 主界面 |
| 大屏展示 | http://localhost:3000/bigscreen | 数据大屏 |
| API 文档 | http://localhost:8080/docs | Swagger 接口文档 |
| EMQX 管理面板 | http://localhost:18083 | MQTT 代理管理（默认 admin/public） |

默认管理员账户：`admin` / `admin123`

#### 停止与清理

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（会丢失所有数据）
docker compose down -v

# 重新构建（代码更新后）
docker compose up -d --build
```

---

### 方式二：一键启动（Windows / Linux / Mac）

适用于开发测试和演示环境，使用 SQLite 数据库 + Express 代理。

#### 前置条件
- Python 3.9+
- Node.js 18+
#### 启动

**Windows：**
```batch
REM 停止已有服务
stop.bat
start.bat
```

**Linux / Mac：**

```bash
chmod +x start.sh
./start.sh
```

> `start.bat` 和 `start.sh` 行为一致：自动检查环境、清理端口、安装依赖、初始化数据库、构建前端、启动后端 + 代理服务。

#### 访问地址
| 服务 | 地址 |
|------|------|
| 系统入口 | http://localhost:3000 |
| 大屏展示 | http://localhost:3000/bigscreen |
| API 文档 | http://localhost:8080/docs |
默认管理员账户：`admin` / `admin123`

> 注意：一键启动使用静态文件模式，修改前端代码后需手动执行 `cd frontend && npm run build` 并强制刷新浏览器（Ctrl+Shift+R）。开发前端建议使用 `cd frontend && npm run dev`（端口 5173，自动热更新）。

---

### 方式三：手动部署（Windows 服务器）

#### 第一步：安装依赖

```batch
REM 安装 Python 3.11+（从 python.org 下载）
REM 安装 Node.js 18+（从 nodejs.org 下载）

REM 验证安装
python --version
node --version
```

#### 第二步：部署后端

```batch
cd backend

REM 创建虚拟环境
python -m venv .venv
call .venv\Scripts\activate

REM 安装依赖
pip install -r requirements.txt

REM 初始化数据库
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

REM 运行数据库迁移
alembic upgrade head

REM 启动服务（生产模式，4 个工作进程）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

#### 第三步：构建前端

```batch
cd frontend

REM 安装依赖
npm install

REM 构建生产版本
npm run build

REM 构建产物输出到 dist/ 目录
```

#### 第四步：启动代理服务

```batch
cd proxy

REM 安装依赖
npm install

REM 启动代理（端口 3000，代理 API 到 8080）
node server.js
```

---

### 方式四：手动部署（Linux + Nginx + systemd）

#### 第一步：安装系统依赖

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm nginx

# 验证安装
python3 --version
node --version
nginx -v
```

#### 第二步：部署后端

```bash
cd /opt/mytest1/backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python3 -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

# 运行数据库迁移
alembic upgrade head
```

#### 第三步：配置 systemd 服务

创建服务文件 `/etc/systemd/system/dcim-backend.service`：

```ini
[Unit]
Description=算力中心智能监控系统 - 后端服务
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mytest1/backend
Environment=PATH=/opt/mytest1/backend/.venv/bin
ExecStart=/opt/mytest1/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable dcim-backend
sudo systemctl start dcim-backend
sudo systemctl status dcim-backend
```

#### 第四步：构建前端并配置 Nginx

```bash
cd /opt/mytest1/frontend

# 安装依赖并构建
npm install
npm run build
```

配置 Nginx（详见下一章节），然后启用：

```bash
sudo ln -s /etc/nginx/sites-available/dcim /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Nginx 配置
### Docker 部署（自动配置）

Docker Compose 部署时，Nginx 配置已内置在 `frontend/nginx.conf` 中，无需手动配置。该配置通过 Docker 内部网络代理到 `backend:8080`。

### 手动部署（HTTP）

创建配置文件 `/etc/nginx/sites-available/dcim`：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /opt/mytest1/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8080/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
    # 静态资源长期缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;
}
```

### HTTPS 配置（生产环境推荐）

项目已提供生产级 HTTPS 配置模板 `deploy/nginx/dcim.conf`，包含：

- HTTP → HTTPS 自动重定向
- TLS 1.2/1.3 安全参数
- HSTS、X-Content-Type-Options、X-Frame-Options 安全头
- WebSocket (WSS) 转发

使用方法：
```bash
# 复制配置并修改域名
sudo cp deploy/nginx/dcim.conf /etc/nginx/conf.d/dcim.conf
sudo vi /etc/nginx/conf.d/dcim.conf  # 将 dcim.powerlab.cn 替换为你的域名

# 申请 SSL 证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# 验证并重载
sudo nginx -t
sudo systemctl reload nginx
```

---

## 数据库配置

### SQLite（默认，适用于开发和小规模部署）

默认使用 SQLite，数据库文件位于 `backend/dcim.db`，首次启动自动创建。

```env
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
```

### PostgreSQL（生产环境推荐）

#### 手动安装配置

```sql
-- 创建数据库和用户
CREATE DATABASE dcim;
CREATE USER dcim_user WITH PASSWORD '请设置强密码';
GRANT ALL PRIVILEGES ON DATABASE dcim TO dcim_user;
```

环境变量配置：

```env
DATABASE_URL=postgresql+asyncpg://dcim_user:密码@localhost:5432/dcim
```

安装 Python 驱动：

```bash
pip install asyncpg
```

#### Docker Compose 方式（自动配置）

Docker Compose 部署时，PostgreSQL 由 `postgres` 服务自动提供，后端通过内部网络连接，无需额外配置。

### TimescaleDB（时序数据扩展）

Docker Compose 默认使用 `timescale/timescaledb:latest-pg16` 镜像，已内置 TimescaleDB 扩展。

启用 TimescaleDB：

```env
TIMESCALEDB_ENABLED=true
```

TimescaleDB 为 `point_history` 等时序数据表提供自动分区和高效查询，适合大规模监控数据存储场景。

---

## 环境变量说明
下表列出所有环境变量。“代码默认值”为 `config.py` 中的硬编码默认，“Docker 默认值”为 `docker-compose.yml` 中覆盖的值。

### 后端应用变量（config.py 读取）

| 变量名 | 代码默认值 | Docker 默认值 | 说明 |
|--------|------------|--------------|------|
| `APP_NAME` | 算力中心智能监控系统 | 同左 | 应用名称 |
| `APP_VERSION` | 3.0.0 | 3.0.0 | 应用版本 |
| `DEBUG` | true | false | 调试模式（生产环境必须为 false） |
| `HOST` | 0.0.0.0 | — | 服务监听地址 |
| `PORT` | 8080 | — | 服务监听端口 |
| `DATABASE_URL` | sqlite+aiosqlite:///./dcim.db | postgresql+asyncpg://... | 数据库连接字符串 |
| `TIMESCALEDB_ENABLED` | false | true | 是否启用 TimescaleDB 扩展 |
| `SECRET_KEY` | （随机生成） | change-this-to-a-secure-random-key | JWT 签名密钥（生产环境必须修改） |
| `ALGORITHM` | HS256 | HS256 | JWT 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 | 30 | 访问令牌过期时间（分钟，生产建议 30） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | 7 | 刷新令牌过期时间（天） |
| `CORS_ORIGINS` | http://localhost:5173,http://localhost:3000 | http://localhost:3000 | 允许的跨域来源（逗号分隔） |
| `COLLECT_INTERVAL` | 10 | 10 | 数据采集间隔（秒） |
| `DATA_RETENTION_DAYS` | 30 | 30 | 历史数据保留天数 |
| `SIMULATION_ENABLED` | true | true | 是否启用数据模拟器 |
| `SIMULATION_INTERVAL` | 5 | — | 模拟数据生成间隔（秒） |
| `LICENSE_KEY` | DEMO-0000-0000-0000 | — | 授权密钥 |
| `MAX_POINTS` | 100 | 100 | 最大监控点位数 |
| `REDIS_ENABLED` | true | true | 是否启用 Redis 缓存 |
| `REDIS_URL` | redis://localhost:6379/0 | redis://redis:6379/0 | Redis 连接地址 |
| `MQTT_ENABLED` | true | true | 是否启用 MQTT |
| `MQTT_HOST` | localhost | emqx | MQTT 代理地址 |
| `MQTT_PORT` | 1883 | 1883 | MQTT 端口 |
| `MQTT_USERNAME` | （空） | （空） | MQTT 用户名 |
| `MQTT_PASSWORD` | （空） | （空） | MQTT 密码 |
| `MQTT_CLIENT_ID` | dcim-backend | — | MQTT 客户端 ID |

### Docker Compose 专用变量（仅 docker-compose.yml 使用）
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BACKEND_PORT` | 8080 | 后端对外端口映射 |
| `NGINX_PORT` | 3000 | 前端对外端口映射 |
| `POSTGRES_DB` | dcim | 数据库名称 |
| `POSTGRES_USER` | dcim | 数据库用户名 |
| `POSTGRES_PASSWORD` | dcim_password | 数据库密码（生产环境必须修改） |
| `POSTGRES_PORT` | 5432 | PostgreSQL 对外端口映射 |
| `REDIS_PORT` | 6379 | Redis 对外端口映射 |
| `MQTT_WS_PORT` | 8083 | MQTT WebSocket 端口 |
| `EMQX_DASHBOARD_PORT` | 18083 | EMQX 管理面板端口 |
---
## 安全配置

### 生产环境必须执行的安全措施

#### 1. 修改 JWT 密钥

```env
# 生成随机密钥（至少 32 位）
SECRET_KEY=请替换为随机生成的强密钥字符串
```

可使用以下命令生成：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

#### 2. 修改数据库密码

```env
POSTGRES_PASSWORD=请设置强密码
```

#### 3. 限制 CORS 来源

```env
# 仅允许实际域名访问
CORS_ORIGINS=https://your-domain.com
```

#### 4. 关闭调试模式

```env
DEBUG=false
```

#### 5. 修改默认管理员密码

首次登录后，立即修改 `admin` 账户密码（默认密码：`admin123`）。

#### 6. 配置 HTTPS

生产环境强烈建议启用 HTTPS，参见 [Nginx 配置](#nginx-配置) 中的 HTTPS 部分。

#### 7. 配置 MQTT 认证

```env
MQTT_USERNAME=你的MQTT用户名
MQTT_PASSWORD=你的MQTT密码
```

---

## 数据备份

### SQLite 备份

```bash
# 备份
cp backend/dcim.db backend/dcim.db.backup.$(date +%Y%m%d)

# 恢复
cp backend/dcim.db.backup.20260222 backend/dcim.db
```

### PostgreSQL 备份（Docker Compose 环境）

```bash
# 备份数据库
docker exec dcim-postgres pg_dump -U dcim dcim > dcim_backup_$(date +%Y%m%d).sql

# 恢复数据库
docker exec -i dcim-postgres psql -U dcim dcim < dcim_backup_20260222.sql
```

### Docker 数据卷备份

```bash
# 备份 PostgreSQL 数据卷
docker run --rm -v dcim-postgres-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/postgres-data-$(date +%Y%m%d).tar.gz /data

# 备份 Redis 数据卷
docker run --rm -v dcim-redis-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/redis-data-$(date +%Y%m%d).tar.gz /data

# 备份 EMQX 数据卷
docker run --rm -v dcim-emqx-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/emqx-data-$(date +%Y%m%d).tar.gz /data

# 恢复数据卷（以 PostgreSQL 为例）
docker run --rm -v dcim-postgres-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/postgres-data-20260222.tar.gz -C /
```

### 定时备份（推荐）

创建 crontab 定时任务：

```bash
# 每天凌晨 2 点自动备份 PostgreSQL
0 2 * * * docker exec dcim-postgres pg_dump -U dcim dcim > /opt/backups/dcim_$(date +\%Y\%m\%d).sql
```

---

## 监控与日志

### 日志位置

| 服务 | 日志方式 | 查看命令 |
|------|----------|----------|
| 后端（Docker） | 容器标准输出 | `docker compose logs -f backend` |
| 后端（手动部署） | 文件 `backend/backend.log` | `tail -f backend/backend.log` |
| Nginx（Docker） | 容器标准输出 | `docker compose logs -f nginx` |
| Nginx（手动部署） | `/var/log/nginx/access.log`、`/var/log/nginx/error.log` | `tail -f /var/log/nginx/error.log` |
| PostgreSQL | 容器标准输出 | `docker compose logs -f postgres` |
| Redis | 容器标准输出 | `docker compose logs -f redis` |
| EMQX | 容器标准输出 | `docker compose logs -f emqx` |

### 健康检查

```bash
# 后端健康检查
curl http://localhost:8080/api/health

# 系统统计信息
curl http://localhost:8080/api/stats

# Docker Compose 服务状态
docker compose ps
```

### WebSocket 通道

| 通道 | 地址 | 用途 |
|------|------|------|
| 实时数据 | `/ws/realtime?token=xxx` | 监控数据实时推送 |
| 告警通知 | `/ws/alarms?token=xxx` | 告警事件推送 |
| 系统状态 | `/ws/system?token=xxx` | 系统运行状态 |

---

## 常见问题

### 1. 登录失败（500 错误）

**原因**：`bcrypt` 库版本 5.0+ 与 `passlib 1.7.4` 不兼容。

**解决方法**：

```bash
cd backend
pip install "bcrypt==4.0.1"
# 重启后端服务
```

### 2. 端口被占用

```bash
# Windows
netstat -ano | findstr ":8080" | findstr "LISTENING"
taskkill /F /PID <进程ID>

# Linux
lsof -i:8080
kill -9 <进程ID>

# 或直接运行停止脚本
stop.bat
```

### 3. 前端修改后不生效

`start.bat` 使用静态文件模式，不会自动热更新。

```bash
# 重新构建前端
cd frontend && npm run build
# 强制刷新浏览器（Ctrl+Shift+R）
```

开发前端建议使用 `npm run dev`（端口 5173，自动热更新）。

### 4. 数据库表不存在

```bash
cd backend

# 运行数据库迁移
alembic upgrade head

# 或删除 SQLite 数据库重新初始化（会丢失数据）
# Windows: del dcim.db
# Linux: rm dcim.db
# 重启后端，自动创建表和初始数据
```

### 4.1 Alembic 迁移报多 head 错误

如果 `alembic upgrade head` 报错 "Multiple head revisions"：

```bash
# 查看当前 head
alembic heads

# 合并多个 head
alembic merge heads -m "merge multiple heads"

# 再执行迁移
alembic upgrade head
```

### 5. Docker 构建失败

```bash
# 清理并重新构建
docker compose down -v
docker system prune -f
docker compose up -d --build
```

### 6. Redis / MQTT 连接失败

Docker Compose 环境下，后端通过服务名（`redis`、`emqx`）连接。确认服务健康状态：

```bash
docker compose ps
# 检查 redis 和 emqx 是否为 "Up (healthy)"
```

手动部署时，如不需要 Redis 和 MQTT，可通过环境变量关闭：

```env
REDIS_ENABLED=false
MQTT_ENABLED=false
```

### 7. TimescaleDB 扩展未生效

确认使用的是 `timescale/timescaledb:latest-pg16` 镜像，并设置：

```env
TIMESCALEDB_ENABLED=true
```

进入数据库确认扩展已安装：

```bash
docker exec -it dcim-postgres psql -U dcim -c "SELECT extname FROM pg_extension;"
# 应包含 timescaledb
```

---

*最后更新: 2026-02-24*
