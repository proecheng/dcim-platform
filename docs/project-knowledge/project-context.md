# Project Context - 算力中心智能监控系统 (DCIM)

> LLM-optimized context for AI-assisted development
> Generated: 2026-02-03

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
