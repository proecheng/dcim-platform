# 后端架构文档 - 算力中心智能监控系统 (DCIM)

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行环境 |
| FastAPI | 0.109.0 | Web 框架 |
| SQLAlchemy | 2.0.25 | ORM |
| Pydantic | 2.5.3 | 数据验证 |
| aiosqlite | 0.19.0 | 异步 SQLite 驱动 |
| Alembic | 1.13.1 | 数据库迁移 |
| PyTorch | 2.0+ | 机器学习（可选） |
| Uvicorn | 0.27.0 | ASGI 服务器 |
| python-jose | 3.3.0 | JWT 认证 |
| passlib[bcrypt] | 1.7.4 | 密码哈希 |

## 应用架构

```
backend/app/
├── main.py           # FastAPI 应用入口 + 生命周期管理
├── core/             # 核心基础设施
│   ├── config.py     # 应用配置 (Pydantic Settings)
│   ├── database.py   # 数据库连接 + 初始化
│   ├── security.py   # JWT + 密码哈希 + 权限装饰器
│   └── logging.py    # 日志配置
├── models/           # SQLAlchemy ORM 模型 (13个文件)
├── schemas/          # Pydantic 验证方案 (18个文件)
├── api/              # REST API 路由
│   ├── deps.py       # 依赖注入
│   └── v1/           # v1 API (31个端点)
├── services/         # 业务逻辑 (30+个文件)
│   └── analysis_plugins/  # 分析插件系统
├── ml_models/        # 机器学习模型 (GNN/RL/Transformer)
├── tools/            # 工具脚本
├── db/               # 数据初始化
└── data/             # 静态数据文件
```

## 系统启动流程

### main.py 生命周期

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === 启动阶段 ===
    # 1. 数据库初始化 (创建所有表)
    await init_db()
    # 2. 默认数据初始化
    #    - 创建 admin/admin123 管理员账户
    #    - 初始化角色权限
    #    - 初始化系统配置和数据字典
    # 3. 启动数据模拟器 (后台任务，每5秒采集)
    simulator.start()
    # 4. 打印启动信息
    yield
    # === 关闭阶段 ===
    simulator.stop()
```

### 启动命令

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## API 路由结构

### 认证与用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | OAuth2 表单登录 |
| POST | `/api/v1/auth/refresh` | Token 刷新 |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |
| GET | `/api/v1/users` | 用户列表 |
| POST | `/api/v1/users` | 创建用户 |
| PUT | `/api/v1/users/{id}` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | 删除用户 |
| PUT | `/api/v1/users/password` | 修改密码 |

### 监控核心

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/devices` | 设备列表 |
| POST | `/api/v1/devices` | 创建设备 |
| GET | `/api/v1/points` | 点位列表 |
| POST | `/api/v1/points` | 创建点位 |
| GET | `/api/v1/realtime` | 实时数据 |
| GET | `/api/v1/realtime/summary` | 实时摘要 |
| POST | `/api/v1/realtime/control` | 下发控制命令 |
| GET | `/api/v1/history` | 历史数据查询 |
| GET | `/api/v1/alarms` | 告警列表 |
| POST | `/api/v1/alarms/{id}/ack` | 确认告警 |
| POST | `/api/v1/alarms/{id}/resolve` | 解决告警 |
| GET | `/api/v1/thresholds` | 告警阈值 |

### 能源管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/energy/power-devices` | 用电设备列表 |
| GET | `/api/v1/energy/realtime-power` | 实时功率 |
| GET | `/api/v1/energy/pue` | PUE 数据 |
| GET | `/api/v1/energy/statistics` | 能耗统计 |
| GET | `/api/v1/energy/suggestions` | 节能建议 |
| GET | `/api/v1/energy/topology` | 配电拓扑 |
| POST | `/api/v1/energy/topology/node` | 创建拓扑节点 |
| GET | `/api/v1/demand/*` | 需量分析 |
| GET | `/api/v1/dispatch/*` | 调度管理 |
| GET | `/api/v1/pricing/*` | 电价管理 |
| GET | `/api/v1/optimization/*` | 优化管理 |
| GET | `/api/v1/opportunities/*` | 节能机会 |
| GET | `/api/v1/execution/*` | 执行计划 |
| GET | `/api/v1/regulation/*` | 设备调节 |
| GET | `/api/v1/proposal/*` | 节能方案 |
| GET | `/api/v1/vpp/*` | VPP 虚拟电厂 |

### 系统管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/config` | 系统配置 |
| GET | `/api/v1/statistics` | 系统统计 |
| GET | `/api/v1/reports` | 报表管理 |
| GET | `/api/v1/logs` | 操作日志 |
| GET | `/api/v1/monitoring` | 系统监控 |
| GET | `/api/v1/floor-map` | 楼层地图 |

### WebSocket 端点

| 端点 | 用途 | 认证 |
|------|------|------|
| `/ws/realtime` | 实时点位数据推送 | JWT Token |
| `/ws/alarms` | 告警事件推送 | JWT Token |
| `/ws/system` | 系统状态通知 | JWT Token |

## 数据库模型

### 核心模型 (50+ 表)

#### 用户与权限

```
User (users)
├── id, username (UNIQUE), hashed_password
├── real_name, email, phone, avatar
├── role (admin/operator/viewer)
├── department, is_active
├── last_login_at, created_at, updated_at
└── permissions (JSON) - 权限列表
```

#### 设备与点位

```
Device (devices)                    Point (points)
├── device_code (UNIQUE)           ├── point_code (UNIQUE)
├── device_name, device_type       ├── point_name, point_type (AI/DI/AO/DO/CALC)
├── area_code, manufacturer        ├── device_type, area_code, unit
├── model, serial_number           ├── min_range, max_range, precision
├── status, location_x/y           ├── collect_interval, store_interval
└── is_enabled, created_at         ├── is_virtual, calc_formula
                                   └── is_enabled, created_at

PointRealtime (point_realtime)      PointHistory (point_history)
├── point_id (FK)                  ├── point_id (FK)
├── value, value_text              ├── value, quality
├── quality, status                ├── min_value, max_value, avg_value
├── alarm_level                    ├── recorded_at
└── updated_at                     └── 索引: (point_id, recorded_at)
```

#### 告警系统

```
AlarmThreshold (alarm_thresholds)   Alarm (alarms)
├── point_id (FK)                  ├── alarm_no (UNIQUE)
├── alarm_level (1-4)              ├── point_id, alarm_level
├── condition (gt/lt/eq/ne/gte/lte)├── alarm_type, alarm_message
├── value, duration                ├── trigger_value, threshold_value
└── is_enabled                     ├── status (active/acknowledged/resolved)
                                   ├── acknowledged_by, resolved_by
AlarmRule (alarm_rules)            └── duration_seconds, created_at
├── rule_name, rule_type
├── condition_expr                 AlarmShield (alarm_shields)
└── alarm_level, is_enabled        ├── point_id, alarm_level
                                   ├── start_time, end_time
AlarmDailyStats (alarm_daily_stats)└── reason, created_by
├── stat_date, point_id
└── total_count, ack_count, resolve_count
```

#### 能源管理 (核心)

```
PowerDevice (power_devices)         Transformer (transformers)
├── device_code (UNIQUE)           ├── transformer_code (UNIQUE)
├── rated_power, rated_voltage     ├── rated_capacity (kVA)
├── power_factor, efficiency       ├── voltage_high/low, efficiency
├── is_it_load, is_critical        ├── no_load_loss, load_loss
├── monitor_device_id (FK)         └── declared_demand, demand_type
└── power/energy/voltage_point_id

MeterPoint (meter_points)           DistributionPanel (distribution_panels)
├── meter_code (UNIQUE)            ├── panel_code (UNIQUE)
├── transformer_id (FK)            ├── panel_type (main/sub/ups_input/ups_output)
├── ct_ratio, pt_ratio             ├── parent_panel_id (FK)
├── declared_demand                └── transformer_id, meter_point_id
└── customer_no, pricing_config_id

DistributionCircuit (distribution_circuits)
├── circuit_code (UNIQUE), panel_id (FK)
├── rated_current, breaker_type
├── load_type (ups/hvac/it/lighting/general/emergency)
├── is_shiftable, shift_priority
└── min_runtime_hours
```

#### 时序数据

```
PowerCurveData (15分钟粒度)     EnergyHourly / EnergyDaily / EnergyMonthly
├── meter_point_id, device_id   ├── device_id (FK)
├── active/reactive/apparent    ├── total_energy, max_power, avg_power
├── power_factor                ├── peak/normal/valley_energy
├── cumulative/incremental      ├── energy_cost, pue
└── time_period (尖/峰/平/谷)   └── stat_time/stat_date/stat_year+month

PUEHistory                       DemandHistory (月度需量统计)
├── total_power, it_power       ├── meter_point_id, stat_year/month
├── cooling_power               ├── declared/max/avg_demand
├── pue 值                      ├── over_declared_times
└── record_time                 └── demand_cost, over_demand_penalty

Demand15MinData (15分钟需量)
├── meter_point_id, timestamp
├── average/max/min_power, rolling_demand
└── is_peak_period, is_over_declared
```

#### 节能方案 (V2.4+)

```
EnergySavingProposal (方案主表)     ProposalMeasure (措施表)
├── proposal_code (UNIQUE)         ├── proposal_id (FK, CASCADE)
├── proposal_type (A/B)            ├── measure_code, regulation_object
├── template_id (A1-A5, B1)       ├── current_state, target_state (JSON)
├── total_benefit, total_investment├── annual_benefit, investment
└── status                         └── execution_status

EnergyOpportunity (V2.5机会)       OpportunityMeasure (机会措施)
├── category (1-4)                 ├── opportunity_id (FK, CASCADE)
├── potential_saving               ├── measure_type, execution_mode
├── source_plugin                  ├── selected_devices (JSON)
└── status                         └── annual_benefit, confidence

ExecutionPlan → ExecutionTask → ExecutionResult (执行链)
```

#### V3.0 电费综合优化

```
DispatchableDevice (可调度设备)     StorageSystemConfig (储能系统)
├── device_type (6类负荷分类)       ├── capacity (kWh)
│   shiftable/curtailable/         ├── max_charge/discharge_power
│   modulating/generation/         └── charge/discharge_efficiency
│   storage/rigid
├── rated_power, min/max_power     PVSystemConfig (光伏系统)
└── priority (1-10)                ├── rated_capacity (kWp)
                                   └── efficiency

DispatchSchedule (调度计划)         OptimizationResult (优化结果)
├── schedule_date, device_id       ├── result_date, optimization_type
├── time_slot (0-95, 15分钟)       ├── objective_value, solve_time
├── action, power_setpoint         └── expected/actual_saving
└── expected_saving, status
```

## 服务层架构

### 核心服务

| 服务 | 文件 | 职责 |
|------|------|------|
| DataSimulator | simulator.py | 模拟数据采集 (每5秒) |
| ConnectionManager | websocket.py | WebSocket 连接管理 |
| PowerDeviceService | power_device.py | 用电设备 CRUD |
| EnergyTopologyService | energy_topology.py | 配电拓扑管理 |
| EnergyAnalysisService | energy_analysis.py | 能源分析 (需量/PUE/负荷) |
| VPPCalculator | vpp_calculator.py | 虚拟电厂分析 |
| Optimizer | optimizer.py | 电费优化 (日前/实时) |
| RealTimeDispatch | realtime_dispatch.py | 实时调度 |

### 节能引擎

| 服务 | 文件 | 职责 |
|------|------|------|
| TemplateGenerator | template_generator.py | 方案模板生成 (A1-A5, B1) |
| ProposalExecutor | proposal_executor.py | 方案执行管理 |
| SuggestionEngine | suggestion_engine.py | 节能建议引擎 |
| OpportunityEngine | opportunity_engine.py | 节能机会识别 (V2.5) |
| ForecastingService | forecasting.py | 负荷预测 (PyTorch) |

### 分析插件系统

```python
# 基类
class AnalysisPlugin:
    def analyze() -> dict
    def get_metadata() -> dict

# 注册表
class PluginRegistry:
    def register(plugin)
    def get(plugin_id)
    def run_all()
```

**6个内置插件:**

| 插件 | 功能 |
|------|------|
| peak_valley.py | 峰谷套利分析 |
| demand_optimization.py | 需量优化分析 |
| pue_optimization.py | PUE优化分析 |
| power_factor.py | 功率因数分析 |
| load_shifting.py | 负荷转移分析 |
| equipment_efficiency.py | 设备效率分析 |

## 机器学习模块

```
ml_models/
├── config.py               # ML 配置
├── gnn/                    # 图神经网络
│   ├── graph_builder.py    # 设备拓扑图构建
│   ├── model.py            # GNN 模型定义
│   └── predictor.py        # 预测器
├── rl/                     # 强化学习
│   ├── environment.py      # 调度环境
│   ├── agent.py            # RL 代理
│   ├── ppo.py              # PPO 算法
│   └── actor_critic.py     # Actor-Critic
└── transformer/            # Transformer
    ├── dataset.py          # 时序数据集
    ├── model.py            # 模型定义
    └── predictor.py        # 预测器
```

## 认证与权限

### JWT 认证流程

1. 登录 → `POST /api/v1/auth/login` (OAuth2 表单)
2. 验证密码 → bcrypt 哈希比较
3. 生成 JWT Token → 包含 user_id, role, permissions
4. 客户端携带 `Authorization: Bearer <token>`
5. 每个请求验证 Token → `get_current_user` 依赖

### RBAC 权限模型

```python
# 角色权限映射
ADMIN_PERMISSIONS = ["user:*", "point:*", "config:*", "report:*"]
OPERATOR_PERMISSIONS = ["point:read/write", "alarm:read/ack", "report:read/write"]
VIEWER_PERMISSIONS = ["point:read", "alarm:read", "report:read"]

# 权限装饰器
require_admin = require_role(["admin"])
require_operator = require_role(["admin", "operator"])
require_viewer = require_role(["admin", "operator", "viewer"])
```

### 依赖注入模式

```python
@router.get("/points")
async def get_points(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # db 和 current_user 自动注入
```

## 数据库迁移

### Alembic 配置

```bash
# 创建迁移
alembic revision --autogenerate -m "描述"
# 执行迁移
alembic upgrade head
# 回滚
alembic downgrade -1
```

### 当前最新迁移

**Revision**: `46e4ea651319_add_vpp_tables`
- 新增: adjustable_loads, electricity_bills, electricity_prices, load_curves, vpp_configs

## 关键统计

| 指标 | 数量 |
|------|------|
| 数据库表 | 50+ |
| API 端点 | 31+ |
| SQLAlchemy 模型 | 13 文件 |
| Pydantic Schema | 18 文件 |
| 服务类 | 30+ |
| 分析插件 | 6 |
| WebSocket 频道 | 3 |
| 用户角色 | 3 |
| ML 模型类型 | 3 (GNN/RL/Transformer) |

---

*最后更新: 2026-02-01*
