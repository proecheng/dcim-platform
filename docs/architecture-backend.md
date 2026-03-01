# 后端架构文档

## 技术栈概览

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.109.0 | Web 框架 (异步, 自动 OpenAPI 文档) |
| Uvicorn | 0.27.0 | ASGI 服务器 |
| SQLAlchemy | 2.0.25 | ORM (异步模式) |
| aiosqlite | 0.19.0 | SQLite 异步驱动 |
| Alembic | 1.13.1 | 数据库迁移 |
| Pydantic | 2.5.3 | 数据验证 (请求/响应模型) |
| pydantic-settings | 2.1.0 | 配置管理 |
| python-jose | 3.3.0 | JWT 令牌 |
| passlib + bcrypt | 1.7.4 / 4.0.1 | 密码哈希 |
| websockets | 12.0 | WebSocket 支持 |
| APScheduler | 3.10.4 | 定时任务 |
| openpyxl | 3.1.2 | Excel 导出 |
| reportlab | ≥4.0 | PDF 生成 |
| httpx | ≥0.25.0 | HTTP 客户端 (联动 Webhook) |
| PyYAML | ≥6.0 | YAML 配置 (消防策略) |
| torch | ≥2.0.0 | 深度学习 (可选) |

## 架构模式

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                   API 路由层 (api/v1/)                    │
│  47 个路由模块, FastAPI Router                            │
│  职责: 请求验证, 参数解析, 响应序列化                      │
│  依赖: Pydantic Schema (schemas/)                        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                   业务服务层 (services/)                   │
│  60+ 个服务文件                                           │
│  职责: 业务逻辑, 数据处理, 外部集成                        │
│  子层:                                                    │
│  ├── engines/ (7个) — 告警/联动/诊断/升级/恢复引擎         │
│  ├── analysis_plugins/ (8个) — 节能分析插件               │
│  └── tools/ (3个) — 数据模拟/生成工具                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                   数据访问层 (models/ + core/)             │
│  27 个模型文件, 100+ 个 SQLAlchemy 模型                   │
│  31 个 Pydantic Schema 文件                               │
│  职责: ORM 映射, 数据库操作, 事务管理                      │
└─────────────────────────────────────────────────────────┘
```

### 事件驱动架构

```
数据采集 → 告警引擎 → 事件总线 → 联动引擎
                                → 交叉确认服务
                                → 诊断引擎
                    → WebSocket 广播 → 前端
```

## 目录结构

```
backend/app/
├── main.py                 # 应用入口 (FastAPI 实例, 生命周期管理)
├── __init__.py
├── api/
│   └── v1/                 # API v1 路由 (47 个模块)
│       ├── __init__.py     # 路由注册中心 (api_router)
│       ├── auth.py         # 认证 (/auth)
│       ├── user.py         # 用户管理 (/users)
│       ├── device.py       # 设备管理 (/devices)
│       ├── point.py        # 点位管理 (/points)
│       ├── alarm.py        # 告警管理 (/alarms)
│       ├── energy.py       # 用电管理 (/energy)
│       ├── power.py        # 供配电 (/power)
│       ├── cooling.py      # 制冷 (/cooling)
│       ├── linkage.py      # 联动 (/linkage)
│       ├── diagnosis.py    # 诊断 (/diagnosis)
│       ├── video.py        # 视频 (/video)
│       ├── ml.py           # 深度学习 (/ml, 可选)
│       └── ... (34 个其他模块)
├── core/                   # 核心配置 (6 个文件)
│   ├── config.py           # 应用配置 (Pydantic Settings, @lru_cache 单例)
│   ├── database.py         # 异步数据库引擎 + 会话工厂
│   ├── security.py         # JWT 认证, 密码哈希, OAuth2
│   ├── redis.py            # Redis 缓存服务
│   └── logging.py          # 日志配置
├── models/                 # ORM 模型 (27 个文件, 100+ 模型)
│   ├── user.py             # User, RolePermission, UserSession 等
│   ├── point.py            # Point, PointRealtime, PointGroup
│   ├── alarm.py            # AlarmThreshold, Alarm, AlarmRule 等
│   ├── energy.py           # 43 个能源相关模型 (最大文件)
│   ├── asset.py            # Cabinet, Asset, AssetLifecycle 等
│   ├── linkage.py          # LinkagePolicy, LinkageAction 等
│   └── ... (21 个其他文件)
├── schemas/                # Pydantic 验证模型 (31 个文件)
│   ├── user.py, device.py, alarm.py, energy.py ...
│   └── common.py           # 公共 Schema (分页等)
├── services/               # 业务服务 (60+ 个文件)
│   ├── simulator.py        # 数据模拟器
│   ├── websocket.py        # WebSocket 连接管理
│   ├── energy_analysis.py  # 能源分析
│   ├── opportunity_detector.py  # 节能机会检测
│   ├── effect_tracker.py   # 效果追踪
│   ├── fire_protection.py  # 消防策略
│   ├── analysis_plugins/   # 分析插件 (8 个)
│   │   ├── base.py, registry.py, manager.py
│   │   ├── peak_valley.py, load_shifting.py
│   │   ├── equipment_efficiency.py, pue_optimization.py
│   │   ├── power_factor.py, demand_optimization.py
│   │   └── __init__.py
│   └── ... (50+ 个其他服务)
├── engines/                # 引擎层 (7 个文件)
│   ├── alarm_engine.py     # 告警引擎
│   ├── linkage_engine.py   # 联动引擎
│   ├── escalation_engine.py # 告警升级引擎
│   ├── diagnosis_engine.py # 诊断引擎
│   ├── event_bus.py        # 事件总线
│   ├── cross_confirmation.py # 交叉确认
│   ├── recovery_engine.py  # 恢复引擎
│   └── action_handlers.py  # 动作处理器
├── tools/                  # 工具
│   ├── realtime_simulator.py
│   └── demo_data_generator.py
├── data/                   # 数据初始化
│   └── building_points.py
├── db/                     # 数据库脚本
│   └── init_vpp_data.py
└── utils/                  # 工具函数
    ├── deterministic.py
    └── __init__.py
```

## API 路由架构

### 路由注册

所有路由在 `api/v1/__init__.py` 中统一注册到 `api_router`，再由 `main.py` 挂载到 `/api/v1` 前缀:

```python
# main.py
app.include_router(api_router, prefix="/api/v1")
```

47 个路由模块按业务域分组，每个模块使用独立的 `APIRouter`，带有中文标签用于 Swagger 文档分类。

完整的 API 端点清单参见 [api-contracts-backend.md](api-contracts-backend.md)。

### ML 模块条件加载

```python
try:
    from .ml import router as ml_router
    _ml_available = True
except ImportError:
    _ml_available = False

if _ml_available:
    api_router.include_router(ml_router, prefix="/ml", tags=["深度学习节能优化"])
```

## 数据库架构

### 异步引擎

```python
# core/database.py
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

### 依赖注入

```python
async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 数据库初始化

应用启动时 (`lifespan` 上下文管理器):
1. `init_db()` — 创建所有表 (`Base.metadata.create_all`)
2. `init_default_data()` — 创建默认管理员 (admin/admin123)、初始化角色权限
3. `init_default_configs()` — 初始化系统配置、数据字典
4. `seed_power_devices()` — 初始化供配电设备
5. `seed_cooling_devices()` — 初始化制冷设备

### 数据库迁移

```bash
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

完整的数据模型清单参见 [data-models-backend.md](data-models-backend.md)。

## 认证和授权

### JWT 认证流程

```
1. 登录: POST /api/v1/auth/login
   → 验证用户名密码 (passlib + bcrypt)
   → 生成 access_token (HS256, 8小时) + refresh_token (7天)
   → 记录登录历史

2. API 认证:
   → OAuth2PasswordBearer 提取 Authorization: Bearer <token>
   → jose.jwt.decode 验证签名和过期时间
   → 查询数据库确认用户存在且活跃

3. WebSocket 认证:
   → token 通过 query 参数传递: /ws/realtime?token=xxx
   → verify_websocket_token() 验证
   → 失败返回 4001 关闭连接
```

### RBAC 权限模型

| 角色 | 权限 |
|------|------|
| admin | user:read/write/delete, point:read/write/delete, alarm:read/write/ack, config:read/write, log:read, report:read/write |
| operator | point:read/write, alarm:read/ack, report:read/write |
| viewer | point:read, alarm:read, report:read |

### 配置单例

```python
@lru_cache()
def get_settings() -> Settings:
    return Settings()  # 从 .env 文件加载
```

## WebSocket 实时通信

### 三个通道

| 通道 | 路径 | 用途 | 推送频率 |
|------|------|------|----------|
| realtime | /ws/realtime | 点位实时数据 | 每 5 秒 |
| alarms | /ws/alarms | 告警通知 | 事件触发 |
| system | /ws/system | 系统状态 | 事件触发 |

### WebSocket 管理器

`services/websocket.py` 中的 `ws_manager` 管理所有连接:
- `connect(websocket, channel)` — 注册连接
- `disconnect(websocket, channel)` — 移除连接
- `broadcast(channel, data)` — 向通道所有连接广播

## 数据模拟器

### 工作原理

```
后端启动 → lifespan 中创建 asyncio.Task
  → simulator.start(interval=5)
    → 每 5 秒循环:
      → 为 52 个点位生成模拟数据
        → AI 点位: 量程内 ±2% 波动
        → DI 点位: 0.5% 概率触发告警
      → 更新 PointRealtime 表
      → 保存到 PointHistory 表
      → 告警引擎检查阈值
      → WebSocket 广播实时数据
```

### 关闭方式

环境变量 `SIMULATION_ENABLED=false` 或注释 main.py 中的启动代码。

## 后台定时任务

应用启动时通过 `asyncio.create_task` 创建:

| 任务 | 间隔 | 函数 | 说明 |
|------|------|------|------|
| 数据模拟器 | 5 秒 | simulator.start() | 模拟数据采集 |
| 告警引擎刷新 | 30 秒 | alarm_engine.check_version() | 检查阈值版本 |
| 通信监控 | 30 秒 | check_communication_status() | 检查通信中断 |
| 告警升级 | 60 秒 | check_escalations() | 检查未处理告警 |
| PUE 历史 | 15 分钟 | write_pue_history() | 记录 PUE |
| 能耗聚合 | 30 分钟 | aggregate_hourly/daily/monthly() | 能耗数据聚合 |
| 节能检测 | 1 小时 | OpportunityDetector.run_detection() | 自动检测节能机会 |
| 效果追踪 | 6 小时 | EffectTracker.run_tracking() | 追踪节能效果 |

## 引擎架构

### 事件总线 (Event Bus)

发布/订阅模式，解耦引擎间通信:

```python
event_bus = get_event_bus()
await event_bus.subscribe("linkage", linkage_engine.on_event)
await event_bus.subscribe("linkage", cross_confirmation_service.on_alarm_event)
await event_bus.subscribe("linkage", diagnosis_engine.on_alarm_event)
```

### 引擎协作流

```
告警引擎 (alarm_engine)
  ↓ 检测到阈值越限
事件总线 (event_bus) publish "linkage"
  ├→ 联动引擎 (linkage_engine) → 匹配策略 → 执行动作
  ├→ 交叉确认 (cross_confirmation) → 消防场景多源确认
  └→ 诊断引擎 (diagnosis_engine) → 故障根因分析

告警升级引擎 (escalation_engine)
  ↓ 定时检查 (60秒)
  → 未处理告警超时 → 升级告警级别 → 通知相关人员

恢复引擎 (recovery_engine)
  ↓ 联动执行完成后
  → 按逆序恢复设备状态
```

### 分析插件架构

```python
# 插件基类
class AnalysisPlugin(ABC):
    @abstractmethod
    async def analyze(self, data) -> AnalysisResult: ...

# 插件注册
registry.register("peak_valley", PeakValleyPlugin)
registry.register("load_shifting", LoadShiftingPlugin)
# ... 6 种插件

# 插件管理器
manager = PluginManager(registry)
results = await manager.run_all(data)
```

6 种分析插件:
1. 峰谷电价优化 (peak_valley)
2. 负荷转移 (load_shifting)
3. 设备效率分析 (equipment_efficiency)
4. PUE 优化 (pue_optimization)
5. 功率因数优化 (power_factor)
6. 需量优化 (demand_optimization)

## 关键设计决策

1. 全异步架构: SQLAlchemy 2.0 async + aiosqlite，所有数据库操作异步执行，避免阻塞事件循环
2. 配置单例 (@lru_cache): 确保配置对象全局唯一，避免重复解析 .env
3. 事件驱动引擎: 通过事件总线解耦告警/联动/诊断引擎，支持灵活扩展
4. ML 条件加载: torch 未安装时优雅跳过，不影响核心功能
5. 生命周期管理: 使用 FastAPI lifespan 上下文管理器统一管理启动/关闭逻辑
6. bcrypt 版本锁定: 锁定 bcrypt==4.0.1 避免与 passlib 1.7.4 的兼容性问题
7. CORS 白名单: 仅允许配置的前端地址，通过环境变量灵活配置
8. WebSocket JWT 认证: token 通过 query 参数传递，而非 header (浏览器 WebSocket API 限制)
9. 数据模拟器内置: 开发/演示环境自动生成模拟数据，无需外部数据源
10. 分析插件架构: 基于注册表的插件模式，支持动态添加新的分析算法
11. 统一入库管道: 所有数据源通过 `ingest_pipeline.py` 统一入库，确保逻辑一致性
12. 演示模块解耦: 演示模块完全独立，通过条件加载实现，不影响生产环境
13. 虚拟 Gateway 模式: 演示数据通过 `demo-gateway` 标识，走真实采集链路
## 演示模块架构
### 模块结构
演示模块完全解耦，独立于核心功能，通过条件加载实现:
```
backend/app/demo/
├── __init__.py           # 模块导出
├── config.py             # 配置检查 (is_demo_enabled)
├── lifecycle.py          # 生命周期钩子 (startup/shutdown)
├── engine.py             # 数据模拟器 (DataSimulator)
├── service.py            # 演示数据服务 (DemoDataService)
├── router.py             # API 路由 (/api/v1/demo)
└── seeds/                # 种子数据生成器
    ├── datacenter_seed.py  # 空间拓扑 (站点/楼层/房间/列)
    ├── power_seed.py       # 供配电设备 (UPS/配电柜/PDU)
    └── cooling_seed.py     # 制冷设备 (空调/传感器)
```
### 生命周期管理
演示模块通过 `lifecycle.py` 提供启动/关闭钩子，由 `main.py` 条件调用:
```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await init_db()
    await init_default_data()
    
    # 条件启动演示模块
    from app.demo.config import is_demo_enabled
    if is_demo_enabled():
        from app.demo import lifecycle
        await lifecycle.startup()
    
    yield
    
    # 关闭
    if is_demo_enabled():
        await lifecycle.shutdown()
```
### 虚拟 Gateway 模式
演示数据通过虚拟网关 `demo-gateway` 标识，走真实采集链路:
```python
# demo/engine.py
async def _generate_and_ingest(self):
    from ..services.ingest_pipeline import process_payload, IngestPoint
    
    points = []
    for point in all_points:
        value = self.generate_ai_value(point, current_value)
        points.append(
            IngestPoint(
                point_id=point.id,
                value=value,
                quality=0,
                timestamp=datetime.now(),
                status="normal",
                gateway_id="demo-gateway",  # 虚拟网关标识
                point_key=point.point_code,
                source="demo",  # 来源标识
            )
        )
    
    # 统一入库管道
    result = await process_payload(points)
```
### 4 层楼数据模型
演示系统提供完整的 4 层楼数据中心模拟环境:
| 设备类型 | 数量 | 采集点数 | 说明 |
|---------|------|---------|------|
| UPS | 8 台 | 96 点 | 每台 12 点 |
| 配电柜 | 40 台 | 400 点 | 每台 10 点 |
| PDU | 320 台 | 960 点 | 每台 3 点 |
| 精密空调 | 80 台 | 800 点 | 每台 10 点 |
| 温湿度传感器 | 160 台 | 480 点 | 每台 3 点 |
| 漏水传感器 | 20 台 | 20 点 | 每台 1 点 |
| **总计** | **628 台** | **2830 点** | |
详细架构说明参见 [演示系统架构文档](demo-architecture.md)。
## 统一入库管道
### 架构设计
所有数据源（MQTT、DemoEngine、DataSourceBridge）统一通过 `ingest_pipeline.py` 入库，确保逻辑一致性。
```
MQTT Broker → MQTT Handler → IngestPoint DTO
DemoEngine → IngestPoint DTO
DataSourceBridge → IngestPoint DTO
                ↓
    ingest_pipeline.process_payload()
                ↓
    PointDataLatest + PointRealtime + PointHistory
                ↓
            commit
                ↓
    告警引擎 → WebSocket → Redis → 联动引擎
```
### IngestPoint DTO
标准化的单点数据载荷:
```python
@dataclass
class IngestPoint:
    point_id: int              # Point 表主键
    value: float               # 数值
    quality: int = 0           # 数据质量 (0=好, 1=不确定, 2=坏)
    timestamp: Optional[datetime] = None  # 采集时间
    status: str = "normal"     # 状态
    gateway_id: Optional[str] = None  # 网关 ID
    point_key: Optional[str] = None   # 原始点位标识
    source: str = "unknown"    # 来源标识: mqtt / demo / bridge
```
### 入库流程
1. 加载点位元数据缓存（首次调用时）
2. 批量写入 `PointDataLatest`（最新值，按 gateway_id + point_key 去重）
3. 批量写入 `PointRealtime`（实时值，按 point_id 去重）
4. 批量写入 `PointHistory`（历史值，全部保留）
5. commit 事务
6. 触发告警引擎检查阈值
7. 触发 WebSocket 推送
8. 触发 Redis 缓存更新
9. 触发联动引擎执行
### 点位元数据缓存
内存缓存 `_point_meta_cache` 存储点位基本属性，避免每次查库:
```python
async def _ensure_point_cache(session: AsyncSession) -> None:
    """加载点位元数据缓存（首次调用时加载，后续跳过）"""
    global _cache_loaded
    if _cache_loaded:
        return
    result = await session.execute(
        select(
            Point.id,
            Point.point_code,
            Point.point_name,
            Point.point_type,
            Point.device_type,
            Point.device_id,
            Point.area_code,
            Point.unit,
            Point.is_enabled,
        )
    )
    for row in result.all():
        _point_meta_cache[row[0]] = {...}
    _cache_loaded = True
```
缓存失效函数 `invalidate_point_cache()` 在点位配置变更时调用。
