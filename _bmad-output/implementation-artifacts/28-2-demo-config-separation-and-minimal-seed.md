# Story 28.2: Demo 配置分离与最小化种子

**Epic:** Epic 28 - Demo 系统解耦与数据隔离
**Story ID:** 28-2-demo-config-separation-and-minimal-seed
**优先级:** P0（核心路径）
**估算:** 中等复杂度
**依赖:** 无
**阻塞:** Story 28.3（主系统与 Demo 代码解耦）

---

## 用户故事

**As a** 部署工程师,
**I want** 系统在非 demo 模式下也能正常启动并提供基础功能,
**So that** 真实环境部署时不依赖 demo 数据，同时有最小化的基础配置。

---

## 业务价值

### 问题陈述
当前系统启动依赖 demo 数据，导致：
1. 真实环境部署时必须先加载 demo 数据再清理，流程繁琐
2. `DEMO_ENABLED` 和 `SIMULATION_ENABLED` 逻辑耦合，无法独立控制
3. 缺少最小化种子，系统无法在"空白"状态下启动
4. 部署工程师无法快速验证系统基础功能（不依赖 demo 数据）

### 解决方案
引入三层配置体系：
- **Seed 层（最小化种子）:** 创建系统运行所需的最小配置（站点、机房、电价、告警级别）
- **Demo 层（演示数据）:** 在 seed 基础上加载完整 demo 数据（设备、点位、历史数据）
- **Simulation 层（数据模拟器）:** 为点位生成模拟数据（可独立于 demo 启用）

### 预期收益
- 真实环境部署时只需 `SEED_ENABLED=true`，无需加载和清理 demo 数据
- Demo 和 Simulation 可独立控制，支持"真实设备 + 模拟数据"等组合场景
- 系统启动逻辑清晰，易于维护和扩展

---

## Acceptance Criteria

### AC-1: 配置项拆分
- **Given** 系统配置文件 `.env`
- **When** 配置以下三个独立开关：
  ```env
  SEED_ENABLED=true       # 最小化种子
  DEMO_ENABLED=false      # Demo 数据
  SIMULATION_ENABLED=false # 数据模拟器
  ```
- **Then** 系统启动时按照 `seed → demo → simulation` 的顺序执行
- **And** 每个开关可独立控制，互不影响

### AC-2: 最小化种子实现
- **Given** `SEED_ENABLED=true, DEMO_ENABLED=false, SIMULATION_ENABLED=false`
- **When** 系统启动
- **Then** 执行 `minimal_seed.py`，创建以下最小配置：
  - **默认站点:** 站点名称可通过 `DEFAULT_SITE_NAME` 配置（默认"默认站点"）
  - **基础空间结构:** 1 个 Floor（"1F"）+ 1 个 Room（"机房A"），数量可通过 `DEFAULT_FLOOR_COUNT` 和 `DEFAULT_ROOM_COUNT` 配置
  - **默认电价配置:** 分时电价模板（峰/平/谷三档，价格可配置）
  - **默认告警级别配置:** critical/major/minor/info 四级
  - **不创建设备和点位**
- **And** 种子数据标记为 `data_source='seed'`（为 Story 28.1 预留）
- **And** 种子执行幂等（重复执行不报错，检测到已存在则跳过）

### AC-3: 系统基础功能验证
- **Given** 只启用 `SEED_ENABLED=true`
- **When** 访问系统页面
- **Then** 以下页面可正常访问：
  - 登录页（`/login`）
  - 仪表盘（`/dashboard`）— 显示空数据状态
  - 空间拓扑页（`/asset/spatial`）— 显示默认站点和机房结构
  - 设备管理页（`/collection/device-manage`）— 显示空列表，引导用户"添加设备"或"接入网关"
  - 点位管理页（`/collection/devices`）— 显示空列表
- **And** 页面不报错，不显示 demo 数据

### AC-4: Demo 数据分层加载
- **Given** `SEED_ENABLED=true, DEMO_ENABLED=true, SIMULATION_ENABLED=false`
- **When** 系统启动
- **Then** 先执行 `minimal_seed.py`，再执行 demo 数据加载
- **And** Demo 数据在 seed 基础上创建设备和点位
- **And** Demo 数据标记为 `data_source='demo'`（为 Story 28.1 预留）

### AC-5: Simulation 独立控制
- **Given** `SEED_ENABLED=true, DEMO_ENABLED=true, SIMULATION_ENABLED=true`
- **When** 系统启动
- **Then** 模拟器为 demo 点位生成模拟数据
- **And** `SIMULATION_ENABLED=false` 时模拟器不启动，但 demo 数据仍然加载
- **And** 支持"真实设备 + 模拟数据"场景（`DEMO_ENABLED=false, SIMULATION_ENABLED=true`，模拟器为真实点位生成数据）

### AC-6: 配置逻辑解耦
- **Given** `backend/app/demo/config.py`
- **When** 检查代码
- **Then** 移除 `demo_enabled or simulation_enabled` 的合并逻辑
- **And** `demo_enabled` 和 `simulation_enabled` 作为独立配置项
- **And** `seed_enabled` 作为新增配置项

### AC-7: 启动流程重构
- **Given** `backend/app/demo/lifecycle.py`
- **When** 系统启动
- **Then** 启动流程按以下顺序执行：
  1. **Seed 阶段:** 如果 `SEED_ENABLED=true`，执行 `minimal_seed.py`
  2. **Demo 阶段:** 如果 `DEMO_ENABLED=true`，执行 demo 数据加载
  3. **Simulation 阶段:** 如果 `SIMULATION_ENABLED=true`，启动模拟器
- **And** 每个阶段独立，前一阶段失败不影响后续阶段（记录错误日志）
- **And** 启动日志清晰标识每个阶段的执行状态

### AC-8: 文档更新
- **Given** `.env.example` 文件
- **When** 查看配置说明
- **Then** 包含以下配置项说明：
  ```env
  # === 数据初始化配置 ===
  # SEED_ENABLED: 启用最小化种子（站点、机房、电价、告警级别）
  # DEMO_ENABLED: 启用 Demo 数据（设备、点位、历史数据）
  # SIMULATION_ENABLED: 启用数据模拟器（为点位生成模拟数据）
  SEED_ENABLED=true
  DEMO_ENABLED=true
  SIMULATION_ENABLED=true

  # === Seed 配置 ===
  DEFAULT_SITE_NAME=默认站点
  DEFAULT_FLOOR_COUNT=1
  DEFAULT_ROOM_COUNT=1
  ```

---

## 技术设计

### 架构变更

#### 当前架构（问题）
```
main.py:lifespan()
  └─> if demo_enabled or simulation_enabled:
        └─> demo/lifecycle.py:initialize_demo_system()
              ├─> load_demo_data()  # 加载设备+点位
              └─> start_simulator()  # 启动模拟器
```

**问题:**
- `demo_enabled` 和 `simulation_enabled` 逻辑耦合
- 缺少最小化种子，无法在"空白"状态下启动
- 无法独立控制 demo 和 simulation

#### 目标架构（解决方案）
```
main.py:lifespan()
  ├─> if seed_enabled:
  │     └─> seeds/minimal_seed.py:run_minimal_seed()
  │           ├─> create_default_site()
  │           ├─> create_default_floors_and_rooms()
  │           ├─> create_default_pricing()
  │           └─> create_default_alarm_levels()
  │
  ├─> if demo_enabled:
  │     └─> demo/lifecycle.py:load_demo_data()
  │           ├─> create_demo_devices()
  │           └─> create_demo_points()
  │
  └─> if simulation_enabled:
        └─> demo/lifecycle.py:start_simulator()
              └─> simulate_point_data()
```

**优势:**
- 三层独立，职责清晰
- 支持多种组合场景
- 易于扩展和维护

### 数据模型

#### Site（站点）
```python
# 最小化种子创建
site = Site(
    name=settings.default_site_name,  # 可配置
    code="DEFAULT",
    data_source="seed"  # 标记来源
)
```

#### Floor/Room（楼层/机房）
```python
# 最小化种子创建
floor = Floor(
    site_id=site.id,
    name="1F",
    floor_number=1,
    data_source="seed"
)

room = Room(
    site_id=site.id,
    floor_id=floor.id,
    name="机房A",
    code="ROOM_A",
    data_source="seed"
)
```

#### PricingScheme（电价配置）
```python
# 最小化种子创建
pricing = PricingScheme(
    name="默认分时电价",
    scheme_type="time_of_use",
    data={
        "peak": {"price": 1.2, "hours": [9, 10, 11, 18, 19, 20]},
        "flat": {"price": 0.8, "hours": [7, 8, 12, 13, 14, 15, 16, 17, 21, 22]},
        "valley": {"price": 0.4, "hours": [0, 1, 2, 3, 4, 5, 6, 23]}
    },
    data_source="seed"
)
```

#### AlarmLevel（告警级别）
```python
# 最小化种子创建（如果使用数据库表存储）
alarm_levels = [
    {"level": "critical", "priority": 1, "color": "#f56c6c"},
    {"level": "major", "priority": 2, "color": "#e6a23c"},
    {"level": "minor", "priority": 3, "color": "#409eff"},
    {"level": "info", "priority": 4, "color": "#909399"}
]
```

### 配置项设计

#### backend/app/core/config.py
```python
class Settings(BaseSettings):
    # === 数据初始化配置 ===
    seed_enabled: bool = Field(default=True, env="SEED_ENABLED")
    demo_enabled: bool = Field(default=False, env="DEMO_ENABLED")
    simulation_enabled: bool = Field(default=False, env="SIMULATION_ENABLED")

    # === Seed 配置 ===
    default_site_name: str = Field(default="默认站点", env="DEFAULT_SITE_NAME")
    default_floor_count: int = Field(default=1, env="DEFAULT_FLOOR_COUNT")
    default_room_count: int = Field(default=1, env="DEFAULT_ROOM_COUNT")

    # === 电价配置 ===
    default_peak_price: float = Field(default=1.2, env="DEFAULT_PEAK_PRICE")
    default_flat_price: float = Field(default=0.8, env="DEFAULT_FLAT_PRICE")
    default_valley_price: float = Field(default=0.4, env="DEFAULT_VALLEY_PRICE")
```

### 启动流程设计

#### backend/app/main.py
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()

    # 1. Seed 阶段
    if settings.seed_enabled:
        logger.info("=== Seed 阶段：执行最小化种子 ===")
        try:
            from app.seeds.minimal_seed import run_minimal_seed
            await run_minimal_seed()
            logger.info("✓ 最小化种子执行成功")
        except Exception as e:
            logger.error(f"✗ 最小化种子执行失败: {e}")

    # 2. Demo 阶段
    if settings.demo_enabled:
        logger.info("=== Demo 阶段：加载 Demo 数据 ===")
        try:
            from app.demo.lifecycle import load_demo_data
            await load_demo_data()
            logger.info("✓ Demo 数据加载成功")
        except Exception as e:
            logger.error(f"✗ Demo 数据加载失败: {e}")

    # 3. Simulation 阶段
    if settings.simulation_enabled:
        logger.info("=== Simulation 阶段：启动数据模拟器 ===")
        try:
            from app.demo.lifecycle import start_simulator
            await start_simulator()
            logger.info("✓ 数据模拟器启动成功")
        except Exception as e:
            logger.error(f"✗ 数据模拟器启动失败: {e}")

    yield

    # 关闭模拟器
    if settings.simulation_enabled:
        from app.demo.lifecycle import stop_simulator
        await stop_simulator()
```

### 最小化种子实现

#### backend/app/seeds/minimal_seed.py
```python
"""最小化种子 - 创建系统运行所需的最小配置"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import async_session
from app.core.config import get_settings
from app.models import Site, Floor, Room, PricingScheme
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

async def run_minimal_seed():
    """执行最小化种子（幂等）"""
    async with async_session() as session:
        # 1. 创建默认站点
        site = await _create_default_site(session)

        # 2. 创建基础空间结构
        await _create_default_floors_and_rooms(session, site.id)

        # 3. 创建默认电价配置
        await _create_default_pricing(session)

        # 4. 创建默认告警级别配置（如果使用数据库表）
        # await _create_default_alarm_levels(session)

        await session.commit()
        logger.info("最小化种子执行完成")

async def _create_default_site(session: AsyncSession) -> Site:
    """创建默认站点（幂等）"""
    result = await session.execute(
        select(Site).where(Site.code == "DEFAULT")
    )
    site = result.scalar_one_or_none()

    if site:
        logger.info(f"默认站点已存在: {site.name}")
        return site

    site = Site(
        name=settings.default_site_name,
        code="DEFAULT",
        address="",
        data_source="seed"
    )
    session.add(site)
    await session.flush()
    logger.info(f"创建默认站点: {site.name}")
    return site

async def _create_default_floors_and_rooms(session: AsyncSession, site_id: int):
    """创建基础空间结构（幂等）"""
    for floor_num in range(1, settings.default_floor_count + 1):
        # 检查楼层是否存在
        result = await session.execute(
            select(Floor).where(
                Floor.site_id == site_id,
                Floor.floor_number == floor_num
            )
        )
        floor = result.scalar_one_or_none()

        if not floor:
            floor = Floor(
                site_id=site_id,
                name=f"{floor_num}F",
                floor_number=floor_num,
                data_source="seed"
            )
            session.add(floor)
            await session.flush()
            logger.info(f"创建楼层: {floor.name}")

        # 创建机房
        for room_num in range(1, settings.default_room_count + 1):
            result = await session.execute(
                select(Room).where(
                    Room.site_id == site_id,
                    Room.floor_id == floor.id,
                    Room.code == f"ROOM_{chr(64 + room_num)}"
                )
            )
            room = result.scalar_one_or_none()

            if not room:
                room = Room(
                    site_id=site_id,
                    floor_id=floor.id,
                    name=f"机房{chr(64 + room_num)}",
                    code=f"ROOM_{chr(64 + room_num)}",
                    data_source="seed"
                )
                session.add(room)
                logger.info(f"创建机房: {room.name}")

async def _create_default_pricing(session: AsyncSession):
    """创建默认电价配置（幂等）"""
    result = await session.execute(
        select(PricingScheme).where(PricingScheme.name == "默认分时电价")
    )
    pricing = result.scalar_one_or_none()

    if pricing:
        logger.info("默认电价配置已存在")
        return

    pricing = PricingScheme(
        name="默认分时电价",
        scheme_type="time_of_use",
        data={
            "peak": {
                "price": settings.default_peak_price,
                "hours": [9, 10, 11, 18, 19, 20]
            },
            "flat": {
                "price": settings.default_flat_price,
                "hours": [7, 8, 12, 13, 14, 15, 16, 17, 21, 22]
            },
            "valley": {
                "price": settings.default_valley_price,
                "hours": [0, 1, 2, 3, 4, 5, 6, 23]
            }
        },
        data_source="seed"
    )
    session.add(pricing)
    logger.info("创建默认电价配置")
```

---

## 涉及文件

### 新建文件
- `backend/app/seeds/minimal_seed.py` — 最小化种子实现
- `backend/app/seeds/__init__.py` — Seeds 模块初始化

### 修改文件
- `backend/app/core/config.py` — 新增 `seed_enabled` 等配置项
- `backend/app/main.py` — lifespan 函数适配分层启动
- `backend/app/demo/lifecycle.py` — 拆分 `load_demo_data()` 和 `start_simulator()`
- `backend/app/demo/config.py` — 移除合并逻辑
- `.env.example` — 新增配置项说明
- `CLAUDE.md` — 更新启动流程说明

---

## 测试策略

### 单元测试
- `tests/seeds/test_minimal_seed.py` — 测试种子幂等性、配置项生效

### 集成测试
- `tests/integration/test_startup_scenarios.py` — 测试不同配置组合的启动场景：
  - Seed only: `SEED_ENABLED=true, DEMO_ENABLED=false, SIMULATION_ENABLED=false`
  - Seed + Demo: `SEED_ENABLED=true, DEMO_ENABLED=true, SIMULATION_ENABLED=false`
  - Seed + Demo + Simulation: 全部启用
  - Demo + Simulation (无 Seed): 验证向后兼容性

### 手动测试
- 验证空白状态下页面可访问性
- 验证设备/点位页面的空状态引导
- 验证 demo 数据加载后的数据完整性

---

## 风险与缓解

### 风险 1: 向后兼容性
**描述:** 现有部署可能依赖 `DEMO_ENABLED` 的旧行为
**缓解:**
- 保持 `DEMO_ENABLED` 默认值为 `false`（生产环境安全）
- 在 `.env.example` 中明确说明新旧配置的对应关系
- 提供迁移指南

### 风险 2: 种子数据冲突
**描述:** 最小化种子可能与现有数据冲突
**缓解:**
- 种子执行幂等，检测到已存在则跳过
- 使用唯一标识（如 `code="DEFAULT"`）避免重复创建
- 记录详细日志，便于排查问题

### 风险 3: 配置项过多
**描述:** 新增多个配置项，增加配置复杂度
**缓解:**
- 提供合理的默认值
- 在 `.env.example` 中提供详细说明和示例
- 在文档中提供常见场景的配置模板

---

## NFR 追溯

- **NFR-M1 (可维护性):** 配置逻辑解耦，职责清晰
- **NFR-M3 (部署灵活性):** 支持多种部署场景（纯 seed、seed+demo、全功能）
- **NFR-P1 (性能):** 最小化种子减少启动时间（不加载 demo 数据）

---

## 参考文档

- `docs/demo-system-audit.md` — Demo 系统审查报告（方案 I）
- `architecture.md` Section 20 — Demo 系统架构
- `backend/app/demo/lifecycle.py` — 当前 demo 启动逻辑

---

**生成时间:** 2026-03-05
**生成工具:** BMAD Method v6.0.4
**Co-Authored-By:** Claude Opus 4.6 <noreply@anthropic.com>
