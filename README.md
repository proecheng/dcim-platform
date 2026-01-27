# 算力中心智能监控系统 (DCIM)

数据中心基础设施管理系统，提供机房环境监控、设备管理、告警管理、历史数据分析和用电管理等功能。

## 功能特性

### 核心功能
- **监控仪表盘**: 实时展示机房环境状态、设备运行情况、告警统计
- **点位管理**: 支持 AI/DI/AO/DO 四种点位类型，最多 100 个监控点位
- **告警管理**: 多级告警（紧急/重要/次要/提示）、声音提醒、实时推送
- **历史数据**: 多维度数据查询、趋势分析、数据导出
- **系统设置**: 阈值配置、用户管理、系统日志

### 用电管理 (V2.1)
- **用电监控**: PUE 实时监测、设备功率监控、负载率分析
- **能耗统计**: 日/月能耗统计、峰谷平电费分析、同环比对比
- **节能建议**: 智能节能建议、潜力分析、节能效果跟踪

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Vue 3)                        │
│  Vue 3 + TypeScript + Element Plus + ECharts + Pinia    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                       │
│  FastAPI + SQLAlchemy + Pydantic + WebSocket            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   数据库 (SQLite)                       │
│              异步支持 (aiosqlite)                       │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求
- Python 3.9+
- Node.js 18+
- npm 或 yarn

### 方式一: 一键启动

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 方式二: 手动启动

**后端服务:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**前端服务:**
```bash
cd frontend
npm install
npm run dev
```

### 方式三: Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8080 |
| API 文档 | http://localhost:8080/docs |

## 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

## 项目结构

```
dcim/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由
│   │   │   └── v1/         # v1 版本 API
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic 模型
│   │   └── services/       # 业务服务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/           # API 模块
│   │   ├── components/    # 组件
│   │   ├── composables/   # 组合式函数
│   │   ├── layouts/       # 布局
│   │   ├── router/        # 路由
│   │   ├── stores/        # 状态管理
│   │   └── views/         # 页面
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Docker 编排
├── start.bat              # Windows 启动脚本
├── start.sh               # Linux/Mac 启动脚本
└── README.md
```

## API 模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | /api/v1/auth | 登录/登出/刷新令牌 |
| 用户 | /api/v1/users | 用户管理 |
| 设备 | /api/v1/devices | 设备管理 |
| 点位 | /api/v1/points | 点位管理 |
| 实时数据 | /api/v1/realtime | 实时数据 |
| 告警 | /api/v1/alarms | 告警管理 |
| 阈值 | /api/v1/thresholds | 阈值配置 |
| 历史 | /api/v1/history | 历史数据 |
| 报表 | /api/v1/reports | 报表管理 |
| 日志 | /api/v1/logs | 系统日志 |
| 统计 | /api/v1/statistics | 统计分析 |
| 配置 | /api/v1/configs | 系统配置 |
| 用电 | /api/v1/energy | 用电管理 |

## 用电管理 API (30+ 端点)

| 功能 | 端点 | 说明 |
|------|------|------|
| 设备管理 | GET/POST/PUT/DELETE /energy/devices | 用电设备 CRUD |
| 设备树 | GET /energy/devices/tree | 配电层级树 |
| 实时电力 | GET /energy/realtime | 实时功率数据 |
| 电力汇总 | GET /energy/realtime/summary | PUE/今日/本月 |
| PUE监测 | GET /energy/pue | 当前 PUE |
| PUE趋势 | GET /energy/pue/trend | PUE 历史趋势 |
| 日统计 | GET /energy/statistics/daily | 日能耗统计 |
| 月统计 | GET /energy/statistics/monthly | 月能耗统计 |
| 能耗汇总 | GET /energy/statistics/summary | 能耗汇总 |
| 能耗趋势 | GET /energy/statistics/trend | 能耗趋势 |
| 同环比 | GET /energy/statistics/comparison | 同比/环比 |
| 电价配置 | GET/POST/PUT/DELETE /energy/pricing | 电价 CRUD |
| 节能建议 | GET /energy/suggestions | 建议列表 |
| 接受建议 | PUT /energy/suggestions/{id}/accept | 接受 |
| 拒绝建议 | PUT /energy/suggestions/{id}/reject | 拒绝 |
| 完成建议 | PUT /energy/suggestions/{id}/complete | 完成 |
| 节能潜力 | GET /energy/saving/potential | 潜力分析 |
| 配电图 | GET /energy/distribution | 配电拓扑 |
| 导出日报 | GET /energy/export/daily | Excel/CSV |
| 导出月报 | GET /energy/export/monthly | Excel/CSV |

## 开发说明

### 后端开发
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### 前端开发
```bash
cd frontend
npm run dev
```

### 生产构建
```bash
cd frontend
npm run build
```

## 配置说明

### 后端配置 (.env)
```env
APP_NAME=算力中心智能监控系统
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
SECRET_KEY=your-secret-key
MAX_POINTS=100
```

### 前端配置 (.env)
```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## 许可证

MIT License

## 更新日志

### V2.1.0 (2026-01-13)
- 新增用电管理模块（用电监控/能耗统计/节能建议）
- 完善历史数据查询页面
- 完善系统设置页面
- 优化前端组件和样式

### V2.0.0
- 重构后端架构（FastAPI + SQLAlchemy）
- 重构前端架构（Vue 3 + TypeScript）
- 新增 WebSocket 实时推送
- 新增数据模拟器
