# Project Context - 算力中心智能监控系统 (DCIM)

> LLM-optimized context for AI-assisted development
> Generated: 2026-02-03 | Updated: 2026-02-17

## System Identity

DCIM (Data Center Infrastructure Management) - 数据中心基础设施管理系统。实时监控、告警、能源优化、3D数字孪生、资产运维一体化平台。

## Architecture

```
Browser ──HTTP/WS──> Vite Dev(3000) / Express Proxy(3000) ──> FastAPI(8080) ──> SQLite/PostgreSQL
```

| Layer | Stack | Port |
|-------|-------|------|
| Frontend | Vue 3.4 + TypeScript 5.9 + Vite 5 + Element Plus 2.5 | 3000 |
| Backend | FastAPI 0.109 + SQLAlchemy 2.0 (async) + Pydantic 2.5 | 8080 |
| Proxy | Express 4.18 + http-proxy-middleware (production only) | 3000 |
| DB | SQLite+aiosqlite (dev) / PostgreSQL (prod) | - |
| ML | PyTorch 2.0+ (optional, conditional import) | - |

## Critical Patterns

### Backend

**Config singleton** - Always use `@lru_cache()`:
```python
from app.core.config import get_settings
settings = get_settings()
```

**Async DB sessions** - SQLAlchemy 2.0 async pattern:
```python
from app.core.database import async_session
async with async_session() as session:
    result = await session.execute(select(Model))
```

**Dependency injection for routes**:
```python
from app.api.deps import get_current_user
@router.get("/")
async def endpoint(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
```

**ML conditional loading** - torch may not be installed:
```python
try:
    from .ml import router as ml_router
    _ml_available = True
except ImportError:
    _ml_available = False
```

**API route registration** - All routes in `backend/app/api/v1/__init__.py`, prefix `/api/v1`:
```python
api_router.include_router(xxx_router, prefix="/xxx", tags=["标签"])
```

**Auth** - JWT (HS256) via `python-jose`, passwords via `passlib[bcrypt]`. Roles: `admin` / `operator` / `viewer`.

**WebSocket auth** - Token via query parameter:
```
ws://localhost:8080/ws/realtime?token={jwt}
```

### Frontend

**Auto-imports enabled** - Vue/Pinia APIs and Element Plus components auto-imported via `unplugin-auto-import`. No need to manually import `ref`, `computed`, `onMounted`, etc.

**Path alias** - `@` maps to `frontend/src/`.

**API proxy (dev)** - Vite proxies `/api` → `http://localhost:8080`, `/ws` → `ws://localhost:8080`.

**Dark theme default** - App applies `dark` class globally, Element Plus dark overrides active.

**State management** - 7 Pinia stores:
- `useUserStore` - Auth, token, permissions (RBAC)
- `useAppStore` - Theme, sidebar, tabs, loading
- `useAlarmStore` - Active alarms, alarm counts
- `useRealtimeStore` - Real-time point data (Map<id, data>)
- `useEnergyStore` - Power data, PUE, suggestions
- `useBigscreenStore` - 3D scene mode, layers, panels
- `useOpportunityStore` - Energy savings opportunities, execution plans

**Component conventions** - `<script setup lang="ts">` + Composition API. All `.vue` files use Chinese comments.

## Directory Map

```
frontend/src/
├── api/modules/          # 27 API modules (energy.ts is 2239 lines, largest)
├── components/
│   ├── common/           # 12 shared components (DataTable, SearchForm, etc.)
│   ├── charts/           # 6 ECharts wrappers
│   ├── bigscreen/        # 17 Three.js 3D + panels
│   ├── energy/           # 24 energy management components
│   ├── monitor/          # 4 monitoring widgets
│   └── floor-layouts/    # 6 floor layout components (B1, F1, F2, F3)
├── composables/          # 15 core + 12 bigscreen composables
├── stores/               # 7 Pinia stores
├── views/                # 23 page views
├── types/                # TypeScript definitions (theme, bigscreen, etc.)
├── utils/three/          # 8 Three.js helpers
└── router/index.ts       # Route definitions with auth guard

backend/app/
├── api/v1/               # 32 route modules (30 active + ml conditional + optimization TODO)
├── models/               # 16 model files → 70+ tables
├── schemas/              # 18 schema files → 60+ Pydantic models
├── services/             # 42 service modules
│   └── analysis_plugins/ # 6 plugins + base + registry + manager
├── ml_models/            # 12 files: transformer/, gnn/, rl/
├── core/
│   ├── config.py         # Settings (pydantic-settings, .env)
│   ├── database.py       # Async engine + session factory
│   ├── security.py       # JWT + bcrypt + OAuth2
│   └── logging.py        # Logging config
└── main.py               # App entry, lifespan, WebSocket routes
```

## Key Routes (Frontend)

| Path | View | Description |
|------|------|-------------|
| `/login` | login/index.vue | Login (no auth required) |
| `/dashboard` | dashboard/index.vue | Monitoring dashboard |
| `/devices` | device/index.vue | Point management |
| `/alarms` | alarm/index.vue | Alarm management |
| `/energy/monitor` | energy/monitor.vue | Power monitoring |
| `/energy/topology` | energy/topology.vue | Distribution topology (2249 lines) |
| `/energy/analysis` | energy/analysis.vue | Energy saving center (1602 lines) |
| `/energy/config` | energy/config.vue | Distribution config |
| `/energy/regulation` | energy/regulation.vue | Load regulation |
| `/energy/execution` | energy/execution.vue | Execution management |
| `/bigscreen` | bigscreen/index.vue | 3D digital twin (no auth) |
| `/capacity` | capacity/index.vue | Capacity management |
| `/asset/list` | asset/index.vue | Asset ledger |
| `/vpp/analysis` | vpp/VPPAnalysis.vue | Virtual power plant |

## API Prefix Convention

All REST: `/api/v1/{module}`. Key modules:

| Prefix | Module | Key Operations |
|--------|--------|----------------|
| `/auth` | Authentication | login, logout, refresh, me |
| `/users` | User CRUD | RBAC roles |
| `/devices` | Device tree | Status summary |
| `/points` | Point CRUD | Virtual formulas, grouping |
| `/realtime` | Live data | Summary, control commands |
| `/alarms` | Alarm CRUD | Acknowledge, resolve, statistics |
| `/energy` | Energy management | Topology, PUE, pricing, suggestions |
| `/opportunities` | Energy savings | Dashboard, simulation, device selection |
| `/execution` | Execution plans | Tasks, results tracking |
| `/demand` | Demand management | Alerts, control |
| `/dispatch` | Schedulable resources | Device configs |
| `/topology` | Topology editing | Node CRUD, sync |
| `/trace` | Data traceability | Trace tree, source mapping (Patent S1) |
| `/ml` | ML optimization | Predict, train (conditional, needs torch) |
| `/proposals` | Saving proposals | Templates, generate, execute, monitor |
| `/vpp` | Virtual power plant | Analysis, calculation |

## Database Model Groups

| Group | Tables | Key Models |
|-------|--------|------------|
| Auth | 3 | User, RolePermission, UserLoginHistory |
| Device | 1 | Device (types: UPS/AC/PDU/TH/DOOR/SMOKE/WATER) |
| Points | 4 | Point, PointRealtime, PointGroup, PointGroupMember |
| Alarms | 5 | Alarm, AlarmThreshold, AlarmRule, AlarmShield, AlarmDailyStats |
| History | 3 | PointHistory, PointHistoryArchive, PointChangeLog |
| Energy (core) | 20+ | Transformer, MeterPoint, DistributionPanel, DistributionCircuit, PowerDevice, PowerCurveData, DemandHistory, EnergyHourly/Daily/Monthly, ElectricityPricing, PUEHistory, EnergySuggestion, EnergyOpportunity, ExecutionPlan/Task/Result |
| V3 Dispatch | 5+ | DispatchableDevice, StorageSystemConfig, PVSystemConfig, DispatchSchedule, RealtimeMonitoring |
| V3.2 RL | 4+ | MeasureBaseline, MonitoringRecord, EffectReport, RLOptimizationHistory |
| Asset | 6 | Cabinet, Asset, AssetLifecycle, MaintenanceRecord, AssetInventory |
| Capacity | 6 | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity, CapacityPlan |
| Operations | 4 | WorkOrder, WorkOrderLog, InspectionPlan/Task, KnowledgeBase |
| VPP | 5 | ElectricityBill, LoadCurve, ElectricityPrice, AdjustableLoad, VPPConfig |
| Trace | 4 | DataSourceMapping, TraceRecord, TraceTree, TemplateParameter |
| System | 5 | SystemConfig, Dictionary, License, ReportTemplate, ReportRecord, OperationLog, SystemLog |

## WebSocket Channels

| Channel | URL | Purpose |
|---------|-----|---------|
| realtime | `/ws/realtime?token=xxx` | Point data push (5s interval) |
| alarms | `/ws/alarms?token=xxx` | Alarm notifications |
| system | `/ws/system?token=xxx` | System status |

## Data Simulator

Backend auto-starts simulator on launch (`SIMULATION_ENABLED=true` default):
- AI points: fluctuate within range (+-2%)
- DI points: 0.5% chance of alarm trigger
- Saves to `point_history` table every 5 seconds
- Broadcasts via WebSocket

## Analysis Plugins (6)

Registered in `services/analysis_plugins/`:
1. `load_shifting` - Peak-valley load shifting
2. `demand_optimization` - Demand optimization
3. `peak_valley` - Peak-valley arbitrage
4. `power_factor` - Power factor correction
5. `pue_optimization` - PUE optimization
6. `equipment_efficiency` - Equipment efficiency

Interface: `AnalysisPlugin.analyze(context: AnalysisContext) -> List[SuggestionResult]`

## ML Modules (conditional, needs torch)

- **Transformer** (`ml_models/transformer/`) - Time series prediction (S2-TF)
- **GNN** (`ml_models/gnn/`) - Graph neural network for topology analysis (S2-GNN)
- **RL/PPO** (`ml_models/rl/`) - Adaptive reinforcement learning optimization (S5)

Unified via `MLEnergySavingService` in `services/ml_service.py`.

## Critical Implementation Rules

### 依赖版本锁定（必须遵守）

- **bcrypt 必须锁定 4.0.1** — `bcrypt>=5.0` 与 `passlib 1.7.4` 不兼容，会导致登录 500 错误
- **不要升级 passlib** — 当前 `passlib[bcrypt]==1.7.4` 是最后稳定版本
- **torch 是可选依赖** — 不要在非 ML 功能中引入 torch/numpy 依赖

### TypeScript 配置（前端）

- `strict: false` — 项目未启用严格模式，不要添加严格类型检查
- 无 ESLint/Prettier — 项目未配置代码检查工具，遵循现有代码风格即可
- `target: ES2020`, `module: ESNext`, `moduleResolution: bundler`
- `skipLibCheck: true` — 跳过第三方库类型检查
- `noUnusedLocals: false`, `noUnusedParameters: false` — 允许未使用变量

### 前端构建注意事项

- `start.bat` 使用 proxy + 静态文件模式，**不会自动热更新前端代码**
- 修改前端代码后必须 `cd frontend && npm run build` 然后强制刷新浏览器
- 开发时推荐使用 `npm run dev`（Vite 开发服务器，端口 5173，自动热更新）
- Vite `allowedHosts` 包含 `powerlab.cn`（生产域名）

### 测试规则

- 后端测试：`pytest`，配置 `asyncio_mode = auto`（自动异步测试）
- `pythonpath = . ..` — 测试可以从项目根目录和上级目录导入
- 测试文件位于 `backend/tests/`，按 `api/` 和 `services/` 分组
- 前端无测试框架配置

### 安全规则（不可忽略）

- `SECRET_KEY` 使用 `secrets.token_urlsafe(64)` 自动生成，生产环境必须通过环境变量设置
- 开发环境 token 过期时间 480 分钟（8小时），生产环境应改为 30 分钟
- CORS 仅允许 `localhost:5173` 和 `localhost:3000`
- WebSocket 认证通过 query parameter 传递 JWT，不是 header

### 端口管理

- 启动前必须检查端口占用：`netstat -ano | findstr ":8080"` 和 `:3000`
- 如果端口被占用，先 `taskkill /F /PID <pid>` 清理
- 启动顺序：先后端(8080) → 等待就绪 → 再代理(3000)

## Conventions

- **Language**: All code comments, commit messages, documentation in Chinese
- **Frontend style**: Dark theme, Chinese font (Microsoft YaHei)
- **Backend responses**: `ResponseModel[T]` wrapper with `code`, `message`, `data`
- **Pagination**: `PageParams` (page, page_size) → `PageResponse[T]` (items, total, total_pages)
- **Naming**: Python snake_case, TypeScript camelCase, Vue PascalCase components
- **DB migrations**: Alembic (`backend/alembic/`)
- **Config**: `.env` file, `pydantic-settings` BaseSettings

## Startup

```bash
# Backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Frontend (dev)
cd frontend && npm run dev

# One-click (Windows)
start.bat

# Docker
docker-compose up -d
```

Default login: `admin` / `admin123`

| URL | Service |
|-----|---------|
| http://localhost:3000 | System entry |
| http://localhost:3000/bigscreen | 3D digital twin |
| http://localhost:8080/docs | Swagger API docs |

## Version History

| Version | Features |
|---------|----------|
| V1.0 | Basic monitoring, alarms, device management |
| V2.0 | Energy management, PUE monitoring |
| V2.1-2.8 | Distribution system, load shifting, topology editing |
| V3.0 | Comprehensive electricity optimization, schedulable devices |

## Known TODOs

- `optimization.py` route disabled (needs numpy install): day-ahead dispatch optimization
- ML routes conditional (needs torch install)
- Production: change `debug=False`, `access_token_expire_minutes=30`, set `SECRET_KEY` env var

## Critical Don't-Miss Rules

### 反模式（AI 代理必须避免）

- **不要升级 bcrypt 到 5.x** — 会破坏登录功能
- **不要在前端手动 import Vue/Pinia API** — 已配置自动导入，重复导入会报错
- **不要使用 `datetime.utcnow()`** — 已在代码中使用但 Python 3.12+ 已弃用，新代码应使用 `datetime.now(timezone.utc)`
- **不要在非 ML 路由中 import torch** — 必须使用 try/except 条件导入
- **不要硬编码数据库 URL** — 必须通过 `get_settings()` 获取
- **不要在路由函数中直接创建 DB session** — 必须通过 `Depends(get_db)` 注入
- **不要忘记 `await`** — 所有数据库操作都是异步的
- **不要在 `start.bat` 模式下期望前端热更新** — 必须手动 build

### 边界情况

- 模拟器每 5 秒生成数据，高频写入 `point_history` 表，注意性能
- `max_points=100` 限制了监控点位数量，超出需要修改 license 配置
- Element Plus 组件自动导入，但图标需要手动从 `@element-plus/icons-vue` 导入
- Three.js 3D 场景在 `/bigscreen` 路由，不需要认证

---

## 项目文档参考

完整项目文档位于 `docs/` 目录：

| 文档 | 路径 | 内容 |
|------|------|------|
| 文档索引 | `docs/index.md` | 所有文档的入口 |
| 前端架构 | `docs/architecture-frontend.md` | Vue 3 前端架构详解 |
| 后端架构 | `docs/architecture-backend.md` | FastAPI 后端架构详解 |
| API 契约 | `docs/api-contracts-backend.md` | 47 个 API 模块端点清单 |
| 数据模型 | `docs/data-models-backend.md` | 100+ 模型类详解 |
| 组件清单 | `docs/component-inventory-frontend.md` | 74 组件 + 8 Store + 60 页面 |
| 集成架构 | `docs/integration-architecture.md` | 前端→代理→后端通信 |
| 开发指南 | `docs/development-guide.md` | 环境搭建和常用命令 |

---

## Usage Guidelines

**For AI Agents:**
- 实现代码前必须阅读本文件
- 严格遵守所有规则，尤其是依赖版本锁定和反模式
- 不确定时选择更保守的方案
- 发现新模式时更新本文件

**For Humans:**
- 保持本文件精简，聚焦于 AI 代理需要的信息
- 技术栈变更时及时更新
- 定期审查，移除过时规则

Last Updated: 2026-02-17
