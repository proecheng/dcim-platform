# 部署指南 - 算力中心智能监控系统 (DCIM)

## 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端浏览器                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                 Nginx / Proxy 服务 (端口 3000/80)           │
│  • 静态文件服务 (前端 dist/)                                │
│  • API 反向代理 (/api → backend:8080)                       │
│  • WebSocket 代理 (/ws → backend:8080)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI 后端服务 (端口 8080/8000)              │
│  • REST API 服务                                            │
│  • WebSocket 实时推送                                       │
│  • 数据模拟器                                               │
│  • 机器学习引擎                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SQLite 数据库                              │
│                   (dcim.db 文件)                            │
└─────────────────────────────────────────────────────────────┘
```

## 部署方式

### 方式一：Docker Compose 部署（推荐）

#### 1. 准备环境

```bash
# 确保已安装 Docker 和 Docker Compose
docker --version
docker-compose --version
```

#### 2. 配置环境变量

创建 `.env` 文件（可选）:
```env
SECRET_KEY=your-production-secret-key
```

#### 3. 构建并启动

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

#### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8000/api/health
# 预期: {"status":"healthy"}
```

#### 5. 访问系统

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:80 |
| API 文档 | http://localhost:8000/docs |

### 方式二：手动部署（Windows 服务器）

#### 1. 安装依赖

```batch
REM 安装 Python 3.11+
REM 安装 Node.js 18+

REM 验证安装
python --version
node --version
```

#### 2. 后端部署

```batch
cd backend

REM 创建虚拟环境
python -m venv .venv
call .venv\Scripts\activate

REM 安装依赖
pip install -r requirements.txt

REM 初始化数据库
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

REM 启动服务（生产模式）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

#### 3. 前端构建

```batch
cd frontend

REM 安装依赖
npm install

REM 构建生产版本
npm run build

REM 构建产物在 dist/ 目录
```

#### 4. 代理服务

```batch
cd proxy

REM 安装依赖
npm install

REM 启动代理
node server.js
```

### 方式三：手动部署（Linux 服务器）

#### 1. 安装依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv nodejs npm

# 验证安装
python3 --version
node --version
```

#### 2. 后端部署

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 后台启动
nohup uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4 > backend.log 2>&1 &
```

#### 3. 前端构建与 Nginx 配置

```bash
cd frontend
npm install
npm run build
```

Nginx 配置 (`/etc/nginx/sites-available/dcim`):

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /opt/mytest1/frontend/dist;
    index index.html;

    # 前端 SPA 路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理
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

    # 静态资源缓存
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

启用配置:
```bash
sudo ln -s /etc/nginx/sites-available/dcim /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 使用 systemd 管理服务

创建服务文件 `/etc/systemd/system/dcim-backend.service`:

```ini
[Unit]
Description=DCIM Backend Service
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

启用服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dcim-backend
sudo systemctl start dcim-backend
sudo systemctl status dcim-backend
```

## 数据库配置

### SQLite（默认）

默认使用 SQLite，数据库文件位于 `backend/dcim.db`。

### PostgreSQL（生产推荐）

1. 安装 PostgreSQL 并创建数据库:
```sql
CREATE DATABASE dcim;
CREATE USER dcim_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dcim TO dcim_user;
```

2. 修改环境变量:
```env
DATABASE_URL=postgresql+asyncpg://dcim_user:your_password@localhost/dcim
```

3. 安装 PostgreSQL 驱动:
```bash
pip install asyncpg
```

## 数据备份

### SQLite 备份

```bash
# 备份
cp backend/dcim.db backend/dcim.db.backup.$(date +%Y%m%d)

# 恢复
cp backend/dcim.db.backup.20260201 backend/dcim.db
```

### Docker 卷备份

```bash
# 备份
docker run --rm -v dcim-backend-data:/data -v $(pwd):/backup alpine tar czf /backup/dcim-data.tar.gz /data

# 恢复
docker run --rm -v dcim-backend-data:/data -v $(pwd):/backup alpine tar xzf /backup/dcim-data.tar.gz -C /
```

## 安全配置

### 生产环境必须配置

1. **修改 SECRET_KEY**
```env
SECRET_KEY=your-very-long-random-secret-key-at-least-32-chars
```

2. **限制 CORS 来源**
```env
CORS_ORIGINS=https://your-domain.com
```

3. **禁用调试模式**
```env
DEBUG=false
```

4. **修改默认密码**
登录后立即修改 admin 账户密码。

### HTTPS 配置

使用 Certbot 获取免费 SSL 证书:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 监控与日志

### 日志位置

| 服务 | 日志文件 |
|------|----------|
| 后端 | `backend/backend.log` |
| Nginx | `/var/log/nginx/access.log`, `/var/log/nginx/error.log` |
| Docker | `docker-compose logs -f` |

### 健康检查

```bash
# 后端健康检查
curl http://localhost:8080/api/health

# 系统统计
curl http://localhost:8080/api/stats
```

## 常见问题

### 数据库迁移失败

```bash
cd backend
alembic upgrade head
```

### 端口被占用

```bash
# 查找占用进程
lsof -i:8080
# 终止进程
kill -9 <PID>
```

### Docker 构建失败

```bash
# 清理并重建
docker-compose down -v
docker system prune -f
docker-compose up -d --build
```

## 发布文件清单

```
mytest1/
├── backend/
│   ├── app/                    # 应用代码（必需）
│   ├── alembic/                # 数据库迁移（必需）
│   ├── requirements.txt        # Python 依赖（必需）
│   ├── dcim.db                 # SQLite 数据库（可选，首次自动创建）
│   └── Dockerfile
├── frontend/
│   ├── dist/                   # 构建产物（必需，需先构建）
│   └── nginx.conf              # Nginx 配置
├── proxy/
│   ├── server.js               # 代理服务
│   └── package.json
├── docker-compose.yml
├── start.bat
└── start.sh
```

---

*最后更新: 2026-02-01*
