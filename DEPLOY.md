# 算力中心智能监控系统 - 部署指南

## 〇、数据模拟采集说明

### 工作原理

系统内置了 **数据模拟采集器**，会在后端服务启动时自动运行，无需额外配置。

```
后端启动 → 自动启动模拟器 → 每5秒采集一次 → 更新实时数据 + 保存历史记录
```

### 模拟器功能

| 功能 | 说明 |
|------|------|
| **实时数据模拟** | 每5秒为52个点位生成模拟数据 |
| **数据波动** | AI点位在量程范围内小幅波动（±2%） |
| **状态模拟** | DI点位有0.5%概率触发告警状态 |
| **历史存储** | AI点位数据自动存入 point_history 表 |
| **告警检测** | 触发阈值时自动生成告警记录 |
| **WebSocket推送** | 实时数据通过 WebSocket 推送到前端 |

### 使用方式

**自动模式（默认）：**
- 启动后端服务后，模拟器自动运行
- 无需任何额外操作

**查看运行状态：**
```bash
# 后端启动日志会显示
数据采集模拟器启动，采集间隔: 5秒
```

**验证数据更新：**
```bash
# 查看实时数据是否在更新
curl http://localhost:8080/api/v1/realtime/1
```

### 配置采集间隔

如需修改采集间隔，编辑 `backend/app/main.py`:

```python
# 第134行，修改 interval 参数（单位：秒）
simulator_task = asyncio.create_task(simulator.start(interval=5))
```

### 历史数据说明

| 数据类型 | 来源 | 时间范围 |
|----------|------|----------|
| 静态历史数据 | init_history.py 脚本预生成 | 过去30天 |
| 动态实时数据 | 模拟器运行时自动生成 | 服务启动后持续生成 |

---

## 一、发布文件清单

### 1.1 必须文件

```
mytest1/
├── backend/                    # 后端服务
│   ├── app/                    # 应用代码
│   ├── dcim.db                 # SQLite数据库（含模拟数据）
│   ├── requirements.txt        # Python依赖
│   └── run.py                  # 启动脚本
├── frontend/                   # 前端应用
│   ├── dist/                   # 构建产物（需要先构建）
│   └── ...
└── start.bat / start.sh        # 一键启动脚本
```

### 1.2 数据库包含的模拟数据

| 表名 | 记录数 | 说明 |
|------|--------|------|
| points | 52 | 监测点位配置 |
| point_history | 1,072,968 | 30天历史数据 |
| point_realtime | 52 | 实时数据 |
| pue_history | 720 | PUE历史 |
| energy_hourly | 13,680 | 小时能耗 |
| energy_daily | 570 | 日能耗 |
| transformers | 1 | 变压器 |
| distribution_panels | 8 | 配电柜 |
| power_devices | 19 | 用电设备 |

---

## 二、服务器环境要求

### 2.1 系统要求
- 操作系统：Windows Server 2016+ / Ubuntu 20.04+
- 内存：4GB+（推荐8GB）
- 磁盘：500MB+ 可用空间

### 2.2 软件要求
- Python 3.10+
- Node.js 18+（如需重新构建前端）
- Nginx（可选，用于生产部署）

---

## 三、部署步骤

### 3.1 Windows 服务器

#### 方式一：使用一键启动脚本
```batch
# 1. 将整个 mytest1 文件夹复制到服务器

# 2. 安装 Python 依赖
cd mytest1\backend
pip install -r requirements.txt

# 3. 构建前端（如果没有 dist 目录）
cd mytest1\frontend
npm install
npm run build

# 4. 启动服务
cd mytest1
start.bat
```

#### 方式二：分别启动

**启动后端：**
```batch
cd mytest1\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**启动前端：**
```batch
cd mytest1\frontend
npm run preview -- --host 0.0.0.0 --port 3000
```

### 3.2 Linux 服务器

```bash
# 1. 复制文件到服务器
scp -r mytest1 user@server:/opt/

# 2. 安装后端依赖
cd /opt/mytest1/backend
pip3 install -r requirements.txt

# 3. 构建前端
cd /opt/mytest1/frontend
npm install
npm run build

# 4. 启动后端（使用 nohup 后台运行）
cd /opt/mytest1/backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > backend.log 2>&1 &

# 5. 使用 Nginx 部署前端静态文件
```

---

## 四、Nginx 配置（生产环境推荐）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /opt/mytest1/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8080/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 五、使用 Docker 部署（可选）

### 5.1 Dockerfile - 后端

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/ .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 5.2 Dockerfile - 前端

```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY frontend/ .
RUN npm install && npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 5.3 docker-compose.yml

```yaml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8080:8080"
    volumes:
      - ./backend/dcim.db:/app/dcim.db

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend
```

---

## 六、验证部署

### 6.1 检查服务状态

```bash
# 后端健康检查
curl http://localhost:8080/api/health
# 预期: {"status":"healthy"}

# API 测试
curl http://localhost:8080/api/stats
```

### 6.2 登录系统

- 访问地址：http://服务器IP:3000（开发模式）或 http://服务器IP（Nginx）
- 默认账户：**admin**
- 默认密码：**admin123**

---

## 七、常见问题

### Q1: 端口被占用
```bash
# Windows
netstat -ano | findstr :8080
taskkill /PID <进程ID> /F

# Linux
lsof -i:8080
kill -9 <进程ID>
```

### Q2: 数据库文件路径问题
确保 `backend/.env` 中的数据库路径正确：
```
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
```

### Q3: 跨域问题
后端已配置 CORS 允许所有来源，如需限制请修改 `app/main.py`

### Q4: 模拟器不工作
检查后端日志是否有"数据采集模拟器启动"字样，如没有：
```bash
# 检查 points 表是否有数据
sqlite3 backend/dcim.db "SELECT COUNT(*) FROM points"
# 应该返回 52
```

### Q5: 想要停止模拟数据生成
编辑 `backend/app/main.py`，注释掉模拟器启动代码：
```python
# 第134行注释掉
# simulator_task = asyncio.create_task(simulator.start(interval=5))
```

---

## 八、数据备份

```bash
# 备份数据库
cp backend/dcim.db backend/dcim.db.backup.$(date +%Y%m%d)

# 恢复数据库
cp backend/dcim.db.backup.20260114 backend/dcim.db
```

---

*部署文档 - 算力中心智能监控系统 V2.3.3*
