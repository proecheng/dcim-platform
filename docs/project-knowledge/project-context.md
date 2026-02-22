---
project_name: 'admin'
user_name: 'proecheng'
date: '2026-02-21'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'conventions', 'critical_rules']
existing_patterns_found: 142
status: 'complete'
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

### Backend (Python 3.11+)

| Core | Version | Notes |
|------|---------|-------|
| FastAPI | 0.109.0 | |
| uvicorn | 0.27.0 | standard extras |
| SQLAlchemy | 2.0.25 | async mode (aiosqlite / asyncpg) |
| Pydantic | 2.5.3 | |
| pydantic-settings | 2.1.0 | `.env` config |
| Alembic | 1.13.1 | DB migrations |

| Auth | Version | Notes |
|------|---------|-------|
| python-jose | 3.3.0 | JWT HS256 |
| passlib | 1.7.4 | **DO NOT upgrade** |
| bcrypt | **4.0.1** | **MUST lock — bcrypt>=5.0 breaks passlib, causes login 500** |

| Database | Version | Notes |
|----------|---------|-------|
| aiosqlite | 0.19.0 | Dev DB |
| asyncpg | 0.29.0 | Prod PostgreSQL async driver |
| psycopg2-binary | 2.9.9 | Alembic migrations only |
| TimescaleDB | pg16 (Docker) | Optional, `TIMESCALEDB_ENABLED` flag |

| Infrastructure (optional, auto-degrade) | Version | Notes |
|------------------------------------------|---------|-------|
| Redis | 7 Alpine (Docker) | Cache, graceful degradation when unavailable |
| EMQX | 5 (Docker) | MQTT broker, TCP:1883 / WS:8083 / Dashboard:18083 |

| Tools | Version | Notes |
|-------|---------|-------|
| ruff | 0.15.2 | Linter+Formatter, `line-length=120`, `target-version="py311"` |
| pytest | >=7.4.0 | `asyncio_mode=auto` |
| pytest-asyncio | >=0.23.0 | |
| numpy | >=1.24.0 | Capacity prediction, load forecasting |
| httpx | >=0.25.0 | Linkage engine webhooks |
| reportlab | >=4.0 | PDF generation |
| openpyxl | 3.1.2 | Excel export |
| APScheduler | 3.10.4 | Scheduled tasks |
| PyYAML | >=6.0 | Fire protection / diagnosis YAML configs |

| ML (conditional, needs torch) | Notes |
|-------------------------------|-------|
| torch 2.0+ | `try/except ImportError` pattern, NEVER import unconditionally |

### Frontend (Node.js 18+)

| Core | Version | Notes |
|------|---------|-------|
| Vue | 3.4.15 | Composition API + `<script setup lang="ts">` |
| TypeScript | 5.9.3 | `strict: false`, `target: ES2020` |
| Vite | 5.0.11 | Dev server port **3000** (configured, NOT default 5173) |
| Element Plus | 2.5.3 | Auto-imported via unplugin |
| Pinia | 2.1.7 | 10 stores |
| vue-router | 4.2.5 | |
| axios | 1.6.5 | baseURL `/api` (relative), timeout 10s |

| Visualization | Version | Notes |
|---------------|---------|-------|
| ECharts | 5.6.0 | via vue-echarts 6.7.3 |
| Three.js | 0.182.0 | 3D digital twin (`/bigscreen`) |
| GSAP | 3.14.2 | Animations |

| Styling | Version | Notes |
|---------|---------|-------|
| sass | 1.70.0 | SCSS, dark-tech theme, 2.5D mixin system |
| Google Fonts | external | Rajdhani, Orbitron, Share Tech Mono — **may fail offline/China mainland** |

| Testing | Version | Notes |
|---------|---------|-------|
| vitest | 4.0.18 | `jsdom` env, `globals: true`, 100+ test files |
| @vue/test-utils | 2.4.6 | |
| axios-mock-adapter | 2.1.0 | |

| Linting | Version | Notes |
|---------|---------|-------|
| ESLint | 10.0.0 | Flat config (`eslint.config.js`) |
| typescript-eslint | 8.56.0 | `no-explicit-any: off` |
| eslint-plugin-vue | 10.8.0 | `multi-word-component-names: off` |

### Proxy (Production only)

| Dep | Version | Notes |
|-----|---------|-------|
| Express | 4.18.2 | Static files + API/WS forwarding |
| http-proxy-middleware | 2.0.6 | |
| cors | 2.8.5 | **`origin: '*'` — security risk, contradicts backend strict CORS** |

### Docker Production Stack

| Service | Image | Port |
|---------|-------|------|
| PostgreSQL + TimescaleDB | `timescale/timescaledb:latest-pg16` | 5432 |
| Redis | `redis:7-alpine` | 6379 |
| EMQX MQTT | `emqx/emqx:5` | 1883/8083/18083 |
| Backend | custom Dockerfile | 8080 |
| Nginx (frontend) | custom Dockerfile | 80 → 3000 |

### Key Version Constraints

- **bcrypt MUST be 4.0.1** — bcrypt>=5.0 incompatible with passlib 1.7.4, breaks login
- **DO NOT upgrade passlib** — 1.7.4 is the last stable version
- **torch is optional** — NEVER import in non-ML code, use `try/except ImportError`
- **Python 3.11+** — ruff target-version confirms; `datetime.utcnow()` deprecated in 3.12+, existing code still uses it, new code should use `datetime.now(timezone.utc)`
- **Redis/MQTT optional in dev** — auto-degrade when unavailable; required in Docker production
- **Vite dev port is 3000** (configured in vite.config.ts), conflicts with proxy — cannot run both simultaneously
- **Google Fonts external dependency** — Rajdhani/Orbitron/Share Tech Mono loaded from CDN, may fail in restricted networks

---

## Language-Specific Rules

### Python

#### Async Database Pattern (CRITICAL)

Two `get_db()` exist — use the correct one:

| Location | Auto-commit | Use in |
|----------|-------------|--------|
| `api/deps.py` | **NO** — only yield + close | Routes (`Depends(get_db)`) — manual `await db.commit()` for writes |
| `core/database.py` | **YES** — commit + rollback + close | Non-route: lifespan, background tasks, WebSocket handlers |

```python
# Route pattern (deps.py get_db — NO auto-commit)
@router.post("")
async def create_item(data: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(**data.model_dump())
    db.add(item)
    await db.commit()  # MUST commit manually
    return item

# Background task pattern (database.py async_session — auto-commit)
async with async_session() as session:
    result = await session.execute(select(Model))
    # auto-commit on exit if no exception
```

#### Dependency Injection Hierarchy

```python
from ..api.deps import get_db, get_current_user, require_admin, require_operator, require_viewer

# Permission levels (inclusive):
# require_admin    → admin only
# require_operator → admin + operator
# require_viewer   → admin + operator + viewer

# Multi-site access:
# get_user_site_ids() → admin returns None (no filter), others return [site_id, ...]
# require_site_access(site_id) → validates user can access specific site
```

#### Model Definition Pattern

```python
from ..core.database import Base

class MyModel(Base):
    __tablename__ = "my_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="名称")  # Chinese comment
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")  # Function ref, NOT datetime.now()
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

- Uses `Column()` declarative style (SQLAlchemy 1.x compat, still supported in 2.0)
- `default=datetime.now` — function reference (called per-row), NOT `datetime.now()` (fixed at import)
- All fields have `comment` parameter in Chinese
- Foreign keys use string table name: `ForeignKey("users.id")`

#### Schema Definition Pattern

```python
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic V2 style

    id: int
    name: str
    is_active: Optional[bool] = None  # Optional fields with default None
    created_at: Optional[datetime] = None
```

#### New API Module Checklist (4 steps)

1. `models/my_module.py` → Define SQLAlchemy models, export in `models/__init__.py`
2. `schemas/my_module.py` → Define Pydantic schemas
3. `services/my_module_service.py` → Business logic
4. `api/v1/my_module.py` → Routes, then register in `api/v1/__init__.py`:
   ```python
   from .my_module import router as my_module_router
   api_router.include_router(my_module_router, prefix="/my-module", tags=["我的模块"])
   ```

#### Type Annotations

- New code: Python 3.9+ built-in generics — `list[str]`, `dict[str, int]`, `tuple[str, str]`
- Old code still uses `typing.List`, `typing.Dict` — don't mix in same file
- `Optional[T]` still used (equivalent to `T | None`)

#### Logging

```python
# CORRECT — lazy formatting
logger.warning("操作失败 key=%s: %s", key, error)

# WRONG — eager f-string (evaluates even if log level disabled)
logger.warning(f"操作失败 key={key}: {error}")
```

#### Ruff Special Rules

- `E711` ignored — SQLAlchemy uses `== None`: `where(User.deleted_at == None)`
- `E712` ignored — SQLAlchemy uses `== True/False`: `where(User.is_active == True)`
- `F811` ignored — Intentional schema redefinition
- Double quotes (`quote-style = "double"`)
- Line length 120
- isort: `known-first-party = ["app"]`

#### Import Conventions

```python
# First-party
from app.core.config import get_settings
from app.models import User, Alarm

# Delayed import (avoid circular dependency)
async def get_current_user(...):
    from ..models.user import User  # Inside function

# Conditional import (ML)
try:
    from .ml import router as ml_router
    _ml_available = True
except ImportError:
    _ml_available = False
```

#### Error Handling in Background Tasks

```python
# Pattern: try/except + logger.warning, never break the loop
async def _background_loop():
    while True:
        try:
            async with async_session() as session:
                await do_work(session)
        except Exception as e:
            logger.warning("任务失败: %s", e)  # warn, don't crash
        await asyncio.sleep(interval)
```

#### Security Notes

- Login rate limiter is **in-memory** — resets on restart, not shared across instances
- JWT tamper detection writes `OperationLog` but `except Exception: pass` on log failure
- `datetime.utcnow()` still used in `security.py` and `auth.py` — new code MUST use `datetime.now(timezone.utc)`

### TypeScript / Vue

#### Auto-Import (CRITICAL)

```vue
<script setup lang="ts">
// ✅ CORRECT — auto-imported, do NOT manually import
const count = ref(0)
const doubled = computed(() => count.value * 2)
onMounted(() => { ... })

// ✅ CORRECT — Element Plus components auto-imported in <template>
// ❌ WRONG — do NOT import: import { ElButton } from 'element-plus'

// ✅ CORRECT — Icons MUST be manually imported
import { Monitor, Warning } from '@element-plus/icons-vue'
</script>
```

- `auto-imports.d.ts` and `components.d.ts` are auto-generated — **NEVER edit manually**
- Vue API (`ref`, `computed`, `watch`, `onMounted`, etc.) — auto-imported
- Pinia API (`defineStore`, `storeToRefs`) — auto-imported
- Element Plus components — auto-imported in templates
- Element Plus icons — **MUST manually import** from `@element-plus/icons-vue`

#### Component Convention

```vue
<script setup lang="ts">
// Chinese comments throughout
// Composition API only
</script>

<template>
  <!-- Element Plus components available without import -->
</template>

<style scoped lang="scss">
// SCSS required (sass installed)
// Use dark-tech theme variables via @use
</style>
```

#### Store Pattern (Two styles — use Setup Store for new code)

```typescript
// ✅ NEW CODE — Setup Store
export const useMyStore = defineStore('my-store', () => {
  const data = ref<MyType[]>([])
  const loading = ref(false)

  const total = computed(() => data.value.length)

  async function fetchData() { ... }

  return { data, loading, total, fetchData }
})

// ⚠️ OLD CODE — Options Store (don't convert, but don't create new ones)
export const useOldStore = defineStore('old', {
  state: () => ({ ... }),
  getters: { ... },
  actions: { ... },
})
```

#### API Call Pattern

```typescript
import request from '@/utils/request'

// API function — return type is DATA directly (axios interceptor strips wrapper)
export function getAlarms(params: AlarmQueryParams): Promise<PageResponse<AlarmInfo>> {
  return request.get('/v1/alarms', { params })
}

// Usage — res IS the data, NOT AxiosResponse
const res = await getAlarms({ page: 1 })
console.log(res.items)  // ✅ Direct access
// console.log(res.data.items)  // ❌ WRONG — no .data wrapper
```

- baseURL is `/api` (relative) → full path: `/api/v1/xxx`
- Token auto-attached via `Authorization: Bearer {token}`
- 401 on public pages (`requiresAuth: false`) → silent ignore
- 401 on auth pages → clear token, redirect to `/login`

#### API Module Export — Check for Name Conflicts

`api/modules/index.ts` uses selective re-export with renames to avoid conflicts:
```typescript
export { getAlarmList as getAlarms } from './alarm'
export { getPointStatistics as getHistoryStatistics } from './history'
```
**When adding new API functions, ALWAYS check `index.ts` for naming conflicts.**

#### Graceful Degradation (Dual-Layer State)

```typescript
// Layer 1: Reactive object (safe before Pinia init — used in axios interceptor)
import { degradationFlags } from '@/stores/degradation'
degradationFlags.redisDown = true  // Can write anytime

// Layer 2: Pinia store (used in components)
const store = useDegradationStore()
store.syncFromFlags()  // Sync from Layer 1 in onMounted
```

#### WebSocket URL Construction

```typescript
// Auto-detects protocol and host — NEVER hardcode
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const host = window.location.host
const wsUrl = `${protocol}//${host}/ws/realtime?token=${token}`
```

5 WebSocket channels: `realtime`, `alarms`, `control`, `system`, `linkage`

#### Frontend Logging

```typescript
import { logger } from '@/utils/logger'
// or
import { createLogger } from '@/utils/logger'
const log = createLogger('MyModule')

log.info('数据加载完成', data)   // Dev only
log.error('加载失败', error)     // Dev + Prod
// Prefer logger over console.log for new code
```

#### Frontend Testing Pattern

```typescript
// Tests use defineComponent to create simplified components — NOT direct .vue import
const SimplifiedComponent = defineComponent({
  setup() {
    const data = ref({ ... })
    return { data }
  },
  template: `<div>{{ data.value }}</div>`
})

// Pinia in tests
beforeEach(() => {
  setActivePinia(createPinia())
})

// Element Plus stubs already defined in setup.ts — don't redefine
// asyncio_mode=auto (backend) — no @pytest.mark.asyncio needed
```

#### TypeScript Config Reminders

- `strict: false` — do NOT add strict type checks
- `noUnusedLocals: false` — unused variables allowed
- `@` alias → `src/`
- `skipLibCheck: true` — skip third-party type checks

---

## Framework-Specific Rules

### FastAPI

#### Route Registration

All routes registered in `api/v1/__init__.py`. New modules MUST specify prefix here:

```python
from .my_module import router as my_module_router
api_router.include_router(my_module_router, prefix="/my-module", tags=["我的模块"])
```

Do NOT define prefix inside the route file itself (some legacy routes do this — don't follow that pattern).

#### Response Models

```python
from ..schemas.common import PageResponse, ResponseModel, SuccessResponse, ErrorResponse

# List endpoint
@router.get("", response_model=PageResponse[AlarmInfo])

# Single item
@router.get("/{id}", response_model=AlarmInfo)

# Action endpoint
@router.post("/{id}/acknowledge", response_model=SuccessResponse)
```

- `ResponseModel[T]` — `{ code: 0, message: "success", data: T }`
- `PageResponse[T]` — `{ items: T[], total, page, page_size }` + computed `pages` property
- `ErrorResponse` — `{ code, message, detail }`

#### Pagination Pattern

```python
@router.get("", response_model=PageResponse[ItemInfo])
async def get_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),  # underscore = unused but enforces auth
):
    query = select(Item)
    # ... filters ...
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0
    items = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return PageResponse(items=items.scalars().all(), total=total, page=page, page_size=page_size)
```

### Backend Architecture Layers

#### engines/ vs services/ (CRITICAL distinction)

| Layer | Pattern | State | Lifecycle | Examples |
|-------|---------|-------|-----------|----------|
| `engines/` | Event-driven, pub/sub | In-memory cache, always-on | Lifespan-scoped (start→stop) | alarm_engine, linkage_engine, diagnosis_engine, event_bus |
| `services/` | Request-driven, stateless | No state (or singleton) | Per-request or singleton | simulator, websocket, analysis_plugins |

- Engines subscribe to `event_bus` and react to events
- Services are called directly from routes or engines
- New real-time/event-driven logic → `engines/`
- New business logic → `services/`

#### Adding Background Tasks

New background tasks go in `main.py` `lifespan()`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing init ...

    # Add new background task
    async def _my_task_loop():
        await asyncio.sleep(60)  # Initial delay
        while True:
            try:
                async with async_session() as session:
                    await my_task(session)
            except Exception as e:
                logger.warning("任务失败: %s", e)
            await asyncio.sleep(3600)  # Interval

    my_task_handle = asyncio.create_task(_my_task_loop())

    yield  # App runs here

    # Cleanup — cancel task
    my_task_handle.cancel()
```

#### Lifespan Init Order (DO NOT change)

1. `init_db()` → 2. `init_default_data()` → 3. `init_default_configs()` → 4. `seed_power_devices()` → 5. `seed_cooling_devices()` → 6. Redis connect → 7. `alarm_engine.load_thresholds()` → 8. Fire protection YAML sync → 9. `linkage_engine.load_policies()` + event_bus subscriptions → 10. Diagnosis YAML sync + engine start

#### YAML Config Sync Pattern

Fire protection and diagnosis rules use YAML files synced to DB on startup:

```python
# services/my_config_loader.py
async def sync_to_database(session: AsyncSession) -> None:
    """Sync YAML config to database"""
    # Read YAML → Compare with DB → Insert/Update
```

Called in `lifespan()` with try/except (failure = warning, not crash).

### Engine Patterns

#### Alarm Engine

- In-memory threshold cache: `Dict[point_id, List[ThresholdCache]]`
- Version-based refresh: every 30s `check_version()` compares DB version
- Storm suppression: 60s window per (point_id, threshold_id)
- Mass alarm detection: >50% of same device_type triggered
- Delay trigger: `delay_seconds` config
- Dead band: `dead_band` prevents threshold oscillation
- Data quality: 0=good, 1=uncertain, 2=bad

#### Linkage Engine

- Policy cache: `Dict[policy_id, dict]` (copy-on-write, pure dict not ORM objects)
- Event subscription: `event_bus.subscribe("linkage", engine.on_event)`
- Action handlers registered in `ActionHandlerRegistry`:

| Action Type | Status | Description |
|-------------|--------|-------------|
| `ALARM_NOTIFY` | ✅ | WebSocket broadcast |
| `WEBHOOK` | ✅ | HTTP POST (httpx, 10s timeout) |
| `MQTT_COMMAND` | ❌ TODO | Not implemented |
| `VIDEO_RECORD` | ✅ | Trigger recording (max 4 cameras) |
| `VIDEO_POPUP` | ✅ | WebSocket broadcast (max 9 cameras, 3x3) |

New action handler: inherit `ActionHandler` → implement `action_type` + `execute()` → register in `default_registry()`.

#### Event Bus

- Abstract `EventBus` → `InMemoryEventBus` implementation
- `Event` dataclass: `event_type`, `source`, `priority`, `payload`, `timestamp`, `is_test`
- Priority: `fire_signal` > `critical` > `normal`
- Singleton: `get_event_bus()`

### Analysis Plugin Framework

```python
# New plugin: inherit AnalysisPlugin
class MyPlugin(AnalysisPlugin):
    @property
    def name(self) -> str: return "my_plugin"

    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        # ... analysis logic ...
        return [SuggestionResult(...)]

# Register in registry.py
from .my_plugin import MyPlugin
plugins = [
    # ... existing plugins ...
    MyPlugin(),
]
```

- `PluginManager` singleton via `__new__` (not `@lru_cache`)
- 6 built-in plugins: load_shifting, demand_optimization, peak_valley, power_factor, pue_optimization, equipment_efficiency

### Two Singleton Patterns in Project

| Pattern | Used by | Example |
|---------|---------|---------|
| `@lru_cache()` | Config | `get_settings()` |
| `__new__` override | PluginManager | `PluginManager()` |
| Module-level instance | Redis, engines | `redis_service = RedisService()`, `alarm_engine = AlarmEngine()` |

### Vue Router

#### Route Domain Groups

| Domain | Purpose | Path prefixes |
|--------|---------|---------------|
| 监控域 (Monitoring) | Read-only dashboards | `/dashboard`, `/power/*`, `/cooling/*`, `/environment/*`, `/security/*`, `/alarms` |
| 管理域 (Management) | Business operations | `/energy/*`, `/asset/*`, `/operation/*`, `/vpp/*` |
| 配置域 (Configuration) | System setup | `/collection/*`, `/strategy/*`, `/system/*` |

New page placement: monitoring (read-only display) → 监控域, business ops → 管理域, system config → 配置域.

#### Adding a New Page (Checklist)

1. Create view file: `views/{domain}/{page}.vue`
2. Add route in `router/index.ts` under correct domain group
3. Add menu item in `layouts/MainLayout.vue` (routes and menus are maintained separately!)
4. For detail/sub pages: use `meta: { hidden: true }` to hide from menu

#### Route Guard

```typescript
router.beforeEach((to, from, next) => {
  // Simple token check — no role-based route guard
  if (to.meta.requiresAuth !== false && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})
```

- `createWebHistory()` — HTML5 History mode (not hash)
- Only `/login` and `/bigscreen` set `requiresAuth: false`
- ~30 legacy redirect routes exist — do NOT delete them, do NOT add new ones for new routes

### Pinia Stores (10 total)

| Store | Key Data Structure | Persistence | Special Pattern |
|-------|-------------------|-------------|-----------------|
| `useUserStore` | `UserInfo` + `token` ref | token → localStorage | Login/logout/permissions |
| `useAppStore` | Multiple refs | sidebar → localStorage | Tab system, global loading |
| `useAlarmStore` | `Alarm[]` array | soundEnabled → localStorage | Dedup by id, max 200 items (memory protection) |
| `useRealtimeStore` | `Map<number, RealtimeData>` | None | WebSocket real-time updates |
| `useEnergyStore` | Power/PUE data | None | |
| `useBigscreenStore` | 3D scene state | None | Three.js integration |
| `useOpportunityStore` | Savings opportunities | None | |
| `useDegradationStore` | 3 boolean flags | None | Dual-layer (reactive + Pinia) |
| `useSiteStore` | Multi-site data | None | |
| (index.ts) | — | — | Store registration entry |

### WebSocket

- 5 channels: `realtime`, `alarms`, `control`, `system`, `linkage`
- Backend `ws_manager.broadcast()` sends to ALL connected clients (no per-user filtering)
- Frontend `WebSocketClient` class with auto-reconnect (max 10 attempts, 3s interval, exponential backoff)
- Heartbeat: 30s interval

### Testing Structure

**Backend** (`backend/tests/`):
- 83+ test files, mostly in root: `test_{module}.py`
- Subdirs: `api/`, `services/` (some tests)
- `conftest.py` — shared fixtures
- New tests: `tests/test_{module}.py`

**Frontend** (`frontend/src/__tests__/`):
- 100+ test files organized by type:
  - `views/` — page tests (60+)
  - `components/` — component tests (20+)
  - `stores/` — store tests (8+)
  - `composables/` — composable tests (4+)
  - `router/` — route guard test
  - `layouts/` — layout test
- New tests follow same directory structure

---

## Project Conventions

### Language

- All code comments: **Chinese** (do NOT mix English)
- Git commit messages: Chinese
- API tags: Chinese (`tags=["告警管理"]`)
- DB column comments: Chinese (`comment="设备编码"`)
- Schema Field descriptions: Chinese (`Field(..., description="设备编码")`)
- Frontend UI text: Chinese
- Some legacy files have bilingual comments — don't follow, use Chinese only

### Naming

| Layer | Style | Example |
|-------|-------|---------|
| Python variable/function | snake_case | `get_alarm_list`, `alarm_engine` |
| Python class | PascalCase | `AlarmEngine`, `LinkagePolicy` |
| Python file | snake_case | `alarm_engine.py`, `energy_report_service.py` |
| TypeScript variable/function | camelCase | `getAlarms`, `alarmCount` |
| TypeScript interface/type | PascalCase | `AlarmInfo`, `PageResponse` |
| Vue component file | kebab-case (preferred) | `index.vue`, `cold-aisle.vue` |
| Vue component file (acronyms) | PascalCase allowed | `VPPAnalysis.vue` |
| API route prefix | kebab-case | `/device-templates`, `/data-quality` |
| DB table name | snake_case plural | `alarms`, `alarm_thresholds`, `user_sessions` |
| Frontend route path | kebab-case | `/cooling/cold-aisle`, `/device-manage` |
| Pinia Store | `use{Name}Store` | `useAlarmStore`, `useRealtimeStore` |
| Composable | `use{Name}` | `useWebSocket`, `usePermission` |
| API function | `get{Entity}List` | `getAlarmList`, `getDeviceList` |

### Backend Schema CRUD Convention

```python
# Base — shared fields (Create inherits)
class PowerDeviceBase(BaseModel):
    device_code: str = Field(..., description="设备编码")

# Create — inherits Base (usually just pass)
class PowerDeviceCreate(PowerDeviceBase):
    pass

# Update — independent, all fields Optional (does NOT inherit Base)
class PowerDeviceUpdate(BaseModel):
    device_name: Optional[str] = None

# Response — use {Model}Info (preferred) or {Model}Response
class PowerDeviceInfo(PowerDeviceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
```

- Response model naming: prefer `{Model}Info` over `{Model}Response`
- Schema file naming: `{module}.py` (NOT `{module}_schema.py` — legacy files exist but don't follow)
- Field descriptions in Chinese: `Field(..., description="中文描述")`

### Response Format

```python
# Success (generic)
ResponseModel[T] → { "code": 0, "message": "success", "data": T }

# Paginated list
PageResponse[T] → { "items": [...], "total": N, "page": 1, "page_size": 20 }
# Backend has computed property `pages`, frontend expects `total_pages` — known inconsistency

# Error (via HTTPException, NOT ErrorResponse model)
raise HTTPException(status_code=400, detail="错误描述")
# Returns: { "detail": "错误描述" }

# Simple success
SuccessResponse → { "message": "操作成功" }
```

### Alarm Level Convention

| Level | Chinese | Color | el-tag type | Flash |
|-------|---------|-------|-------------|-------|
| `critical` | 紧急 | `#ff4d4f` | `danger` | ✅ |
| `major` | 重要 | `#fa8c16` | `warning` | |
| `minor` | 一般/次要 | `#faad14` | `primary` | |
| `info` | 提示 | `#1890ff` | `info` | |

### Status Convention (StatusTag component)

Use `StatusTag` component for all status display (not raw `el-tag`):

| Category | Values |
|----------|--------|
| Alarm status | `active`→danger+flash, `acknowledged`→warning, `resolved`→success, `ignored`→info |
| Online status | `online`→success, `offline`→danger, `maintenance`→warning |
| Task status | `pending`→info, `processing`→primary, `completed`→success, `failed`→danger |
| Boolean | `true`/`1`→success, `false`/`0`→info |

### RBAC Permission Format

```
{resource}:{action}
```

| Role | Scope | Example permissions |
|------|-------|-------------------|
| `admin` | Full access | `user:delete`, `site:delete`, `config:write` |
| `operator` | Operations | `device:write`, `alarm:ack`, `linkage:write` |
| `viewer` | Read-only | `point:read`, `alarm:read`, `energy:read` |

Resources: `user`, `point`, `alarm`, `config`, `log`, `report`, `device`, `gateway`, `energy`, `asset`, `linkage`, `diagnosis`, `video`, `site`

### Password Policy

- Min length: 8 characters
- Min categories: 3 of 4 (uppercase, lowercase, digits, special chars)
- History: cannot reuse last 5 passwords
- Expiry: 90 days
- Policy stored in `SystemConfig` table — dynamically configurable

### Frontend Page Structure Convention

Standard list page pattern (reference: `views/alarm/index.vue`):

```
1. Statistics cards row (el-row > el-col > el-card)
2. Filter form (el-form :inline="true")
3. Data table (el-table or DataTable component)
4. Pagination
```

- All cards: `el-card shadow="hover"` (standard)
- Grid: `el-row :gutter="20"` + `el-col :span="N"` (24-column grid)
- Icons: manually import from `@element-plus/icons-vue`

### Frontend Component Import Convention

- Element Plus components: **auto-imported** (no manual import needed in templates)
- Custom common components: **manual import required**
  ```typescript
  import { DataTable, StatusTag, ExportButton } from '@/components/common'
  ```
- Element Plus icons: **manual import required**
  ```typescript
  import { Monitor, Warning, Bell } from '@element-plus/icons-vue'
  ```

### Common Components (`components/common/`)

| Component | Purpose |
|-----------|---------|
| `DataTable` | el-table wrapper with toolbar, pagination, selection, index |
| `SearchForm` | Inline search form |
| `DateRangePicker` | Date range selector |
| `ExportButton` | Data export button |
| `StatusTag` | Status display with predefined mappings |
| `ConfirmDialog` | Dangerous action confirmation |
| `DegradationBanner` | Global degradation notification |
| `AlarmSoundToggle` | Alarm sound on/off |
| `DataQualityTag` | Data quality indicator |
| `SiteSwitcher` | Multi-site switcher |

### Backend Logging Convention

```python
import logging
logger = logging.getLogger(__name__)

# Format: [2026-02-21 22:40:00] INFO [app.services.simulator:42] 消息
# Debug mode: DEBUG level
# Production: INFO level
```

### File Organization

**Backend** (4-layer separation):
```
models/{module}.py    → SQLAlchemy models
schemas/{module}.py   → Pydantic schemas
services/{module}.py  → Business logic
api/v1/{module}.py    → Routes
```

**Frontend** (by responsibility):
```
api/modules/{module}.ts    → API calls + types
stores/{module}.ts         → State management
composables/use{Name}.ts   → Reusable logic
views/{domain}/page.vue    → Page views
components/{domain}/       → Domain components
```

### Internationalization Note

- `useAppStore` has `language: 'zh-CN' | 'en-US'` — this is a **placeholder**, no i18n implementation exists
- Do NOT attempt to add English translations — project is Chinese-only

---

## Critical Implementation Rules

### ⚠️ AI Agent Top 10 Mistakes (READ FIRST)

These are the most common mistakes AI agents make in this codebase. Check EVERY time before submitting code:

| # | Mistake | Consequence | Correct Approach |
|---|---------|-------------|-----------------|
| 1 | Upgrade bcrypt to >=5.0 | Login returns 500 | **MUST keep bcrypt==4.0.1** |
| 2 | Manually import Vue/Pinia API (`import { ref } from 'vue'`) | Duplicate declarations | Auto-imported — do NOT import |
| 3 | Use `async_session()` in routes instead of `Depends(get_db)` | Wrong commit behavior | Routes: `Depends(get_db)` from `deps.py` |
| 4 | Forget to update `alembic/env.py` after new model | Migration autogenerate misses new table | Update BOTH `models/__init__.py` AND `alembic/env.py` |
| 5 | Forget to update `MainLayout.vue` after new route | Page exists but invisible in menu | Update BOTH `router/index.ts` AND `MainLayout.vue` |
| 6 | Write `default=datetime.now()` in Model | All records get same timestamp | Use `default=datetime.now` (function reference, no parentheses) |
| 7 | Import torch unconditionally | App crashes without torch installed | Use `try/except ImportError` pattern |
| 8 | Use f-string in logger | String formatted even when log level disabled | Use `logger.warning("msg %s", var)` |
| 9 | Access `res.data.items` from API call | TypeError — `res` IS the data | `res.items` directly (axios interceptor strips wrapper) |
| 10 | Delete legacy route redirects | Bookmarks and external links break | ~30 redirects exist — NEVER delete them |

### MUST DO Rules

#### Backend

1. **All DB operations MUST `await`** — SQLAlchemy 2.0 async, forgetting await = silent bugs
2. **Routes use `Depends(get_db)` from `deps.py`** — NOT `async_session()` from `database.py`
3. **New model checklist**: `models/__init__.py` export + `alembic/env.py` import + `alembic revision --autogenerate`
4. **ML imports MUST be conditional**: `try: from .ml import router; except ImportError: pass`
5. **Logger format**: `logger.warning("msg %s", var)` — lazy formatting, NOT f-string
6. **New code datetime**: `datetime.now(timezone.utc)` — NOT `datetime.utcnow()` (deprecated 3.12+)
7. **Model default**: `default=datetime.now` (function ref) — NOT `default=datetime.now()` (fixed value)
8. **Redis operations MUST silently fail**: `try/except` + return None/pass
9. **Background task errors MUST NOT crash the loop**: `try/except` + `logger.warning()`
10. **New route registration**: `api/v1/__init__.py` + `MainLayout.vue` menu

#### Frontend

1. **Vue/Pinia API auto-imported** — do NOT manually import `ref`, `computed`, `onMounted`, etc.
2. **Element Plus icons MUST be manually imported**: `import { Monitor } from '@element-plus/icons-vue'`
3. **Custom components MUST be manually imported**: `import { DataTable } from '@/components/common'`
4. **NEVER edit `auto-imports.d.ts` or `components.d.ts`** — auto-generated
5. **API return values are DATA directly** — no `.data` wrapper (axios interceptor strips it)
6. **New Store: use Setup Store pattern** — `defineStore('name', () => { ... })`
7. **New API functions: check `api/modules/index.ts` for naming conflicts** before adding
8. **After frontend changes with `start.bat`**: MUST run `npm run build` (no hot reload)

### MUST NOT DO (Anti-Patterns)

| Anti-Pattern | Why |
|-------------|-----|
| Upgrade bcrypt beyond 4.0.1 | Breaks passlib, login 500 |
| Upgrade passlib beyond 1.7.4 | Last stable version |
| `import torch` without try/except | Crashes non-ML environments |
| `default=datetime.now()` in Model | Fixed timestamp at import time |
| `logger.warning(f"...")` | Eager evaluation wastes CPU |
| `from vue import ref` in `<script setup>` | Already auto-imported |
| Edit `auto-imports.d.ts` | Auto-generated, will be overwritten |
| Delete legacy route redirects | Breaks bookmarks/external links |
| Hardcode database URL | Use `get_settings().database_url` |
| Create DB session in route function | Use `Depends(get_db)` |
| `response.data.items` in frontend | `response` IS the data already |
| Suppress type errors with `as any` | Fix the actual type issue |

### Environment Configuration Traps

| Config | Dev Default | Production MUST | Impact |
|--------|------------|-----------------|--------|
| `DEBUG` | `true` | `false` | SQL echo, log level, error detail |
| `SECRET_KEY` | Random per restart | Fixed value from `.env` | Restart invalidates ALL JWTs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` (8h) | `30` | Token theft window |
| `SIMULATION_ENABLED` | `true` | `false` | Fake data overwrites real data |
| `MAX_POINTS` | `100` | Adjust per license | Point creation rejected over limit |

**`backend/.env` contains a real SECRET_KEY and is committed to the repo** — development use only. Production MUST generate a new key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**`frontend/.env` has port 8000 (incorrect)** — but this file is NOT actually used. `utils/request.ts` uses relative `/api` path, Vite proxy handles forwarding.

### Redis Cache Key Convention

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `point:{point_id}:latest` | 60s | Latest point value (JSON) |
| `device:{device_id}:online` | 60s | Device online status |
| `alarm:stats:{alarm_level}` | 86400s (24h) | Alarm count by level |

All Redis operations silently fail when unavailable — check `redis_service.is_available` if you need to know.

### Data Flow: Simulator → Alarm → Linkage

```
simulator.collect_and_save() [every 5s]
  ├─ Generate simulated value (AI/DI/AO/DO)
  ├─ Update PointRealtime table
  ├─ Save PointHistory (AI type only)
  ├─ alarm_engine.evaluate() — threshold check
  │   ├─ Storm suppression (60s window)
  │   ├─ Mass alarm detection (>50% same device_type)
  │   ├─ Delay trigger (delay_seconds)
  │   └─ Dead band (prevent oscillation)
  ├─ Create Alarm record (if triggered)
  ├─ ws_manager.broadcast_alarm() → Frontend
  ├─ event_bus.publish("linkage") → Linkage Engine
  │   ├─ Policy matching
  │   └─ Action execution (ALARM_NOTIFY/WEBHOOK/VIDEO_RECORD/VIDEO_POPUP)
  ├─ Auto-resolve: if value safe → resolve active alarms
  ├─ Redis cache update (if available)
  └─ ws_manager.broadcast_realtime() → Frontend
```

Capacity snapshot runs every 12 cycles (~60s), independent transaction.

### Architecture Constraints

| Constraint | Impact | Workaround |
|-----------|--------|------------|
| Single-process architecture | All engines use in-memory cache, no multi-instance | Refactor to Redis cache for horizontal scaling |
| InMemoryEventBus | No cross-process events | Replace with Redis Pub/Sub or MQTT |
| In-memory rate limiter | Resets on restart, not shared across instances | Use Redis for production |
| SQLite (dev) | No concurrent writes, `database is locked` | Use PostgreSQL for production |
| WebSocket broadcast to ALL | No per-user filtering, bandwidth pressure | Add channel-based filtering |

### Alarm Auto-Recovery

When `alarm_engine.is_value_safe(point_id, value)` returns true:
1. All `status="active"` alarms for that point → `status="resolved"`
2. `resolve_type="auto"`, `resolved_at=now()`
3. `duration_seconds` calculated
4. WebSocket broadcast `{ action: "resolve", ... }`
5. Redis alarm stats decremented

### Alarm Number Format

`ALM{YYYYMMDDHHMMSS}{6-char-random-hex}` — e.g., `ALM20260221224000A3B2C1`

### WebSocket Reconnection Strategy

Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s → 30s (cap)
- Max 10 attempts
- Degradation flag set ONLY after first successful connection then disconnect (avoids banner on initial failure)

### SQLAlchemy Session Behavior

- `expire_on_commit=False` — ORM objects remain accessible after commit (no lazy-load trigger)
- `autocommit=False, autoflush=False` — explicit control
- `deps.py get_db()`: yield + close only (NO auto-commit)
- `database.py get_db()`: yield + commit + rollback + close (auto-commit)

### API Field JSON Encoding Convention (Tech Debt)

Some frontend pages store structured JSON data in backend string fields that were originally designed for plain text. AI agents MUST preserve this convention when modifying these pages.

| Page | Field | Stored JSON Structure | Purpose |
|------|-------|-----------------------|---------|
| `views/alarm/escalation.vue` | `description` (AlarmEscalationInfo) | `EscalationNode[]` — array of `{ id, order, timeout_minutes, notify_method, notify_user_ids, upgrade_level }` | Escalation chain node list |
| `views/alarm/shield.vue` | `reason` (AlarmShieldInfo) | `ShieldMeta` — `{ name, scope, scope_value, levels, reason }` | Shield scope (global/area/device_type/device), multi-level selection, display name |

Rules:
- `escalation.vue`: `JSON.stringify(form.chain)` on save → `JSON.parse(row.description)` on load. First node's `timeout_minutes` maps to API's `timeout_minutes`, all nodes' `notify_user_ids` merge to API's `notify_user_ids`.
- `shield.vue`: `JSON.stringify(meta)` on save → `JSON.parse(shield.reason)` on load. `parseMeta()` handles parse failure gracefully (falls back to plain string reason).
- Backend schemas define these as plain `str | None` — do NOT add validation that would reject JSON strings.
- `compound.vue` uses `condition_expr` field (designed for JSON) — this is NOT tech debt, it's by design.

### AI vs DI Sensor Page Pattern

Environment monitoring pages follow two distinct patterns based on sensor type:

| Aspect | AI Type (Analog Input) | DI Type (Digital Input) |
|--------|----------------------|------------------------|
| Example pages | `temperature.vue` (TH) | `water-leak.vue` (WL), `smoke-infrared.vue` (SMOKE/IR) |
| Data characteristic | Continuous numeric values | Binary state (normal/alarm) |
| Display field | `value` (number) | `value_text` (string, e.g. "正常"/"漏水") |
| Detail panel | 24h ECharts trend chart + alarm list | Alarm record list only (NO trend chart) |
| Zone card metrics | Average, max/min values | Normal count / alarm count |
| Drift detection | Yes (yellow badge, `getDriftResults` API) | No (not applicable to DI type) |
| Stat cards | 6 (includes avg temp/humidity, drift count) | 4-5 (includes 24h alarm count) |
| Composable pattern | `useTemperatureData.ts` | `useWaterLeakData.ts`, `useSmokeInfraredData.ts` |

Rules:
- Filter by `device_type`: TH (temperature/humidity), WL (water leak), SMOKE (smoke), IR (infrared), DOOR (access control)
- DI sensors: state changes trigger alarms (not threshold crossing)
- Multi-type DI pages (smoke-infrared): need separate statistics per type, extra filter dimension
- All environment pages use `page-dashboard(N)` 2.5D preset where N = stat card count

### Bigscreen deviceId Convention

The bigscreen module uses `string` type deviceId (e.g. "A-01", cabinet/device code), while standard modules use `number` type device_id (database primary key).

| Module | ID Type | Example | Source |
|--------|---------|---------|--------|
| Bigscreen store (`stores/bigscreen.ts`) | `string` | "A-01" | Cabinet/device code from 3D scene |
| Standard stores (energy, opportunity) | `number` | 42 | Database primary key |
| Backend API (`/v1/devices/{id}`) | `number` | 42 | Database primary key |

When bigscreen needs to call standard APIs (e.g. `getDeviceDetail`), use `getDeviceList({ keyword: deviceId })` to resolve string code → numeric id. The `BigscreenHistoryDialog.vue` component handles this mapping internally.

This is an intentional design difference, NOT a bug. Unifying would require rewriting the entire bigscreen data model for minimal benefit.

### Alembic Migration Gotcha

`alembic/env.py` requires explicit model imports for autogenerate. Some energy sub-models (Transformer, MeterPoint, DistributionPanel, etc.) are NOT exported from `models/__init__.py` and must be imported separately in `env.py`.

Async driver auto-conversion:
- `+aiosqlite` → removed (SQLite sync)
- `+asyncpg` → `+psycopg2` (PostgreSQL sync)
