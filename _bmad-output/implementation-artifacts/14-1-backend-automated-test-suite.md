# Story 14.1: 后端自动化测试套件

## 状态: 审查通过，待实施

## 故事

As a 开发者,
I want 核心模块有完整的自动化测试,
So that 代码变更不会导致功能回归。

## 验收标准 (AC)

### AC1: 异步测试基础设施
- Given 测试框架已配置（pytest + httpx AsyncClient + pytest-asyncio + pytest-cov）
- When 运行 `cd backend && pytest tests/`
- Then conftest.py 提供异步数据库 fixture（使用 aiosqlite 内存数据库 + StaticPool 确保连接共享）
- And 提供 AsyncClient fixture（基于 httpx.AsyncClient + ASGITransport，禁用 lifespan 避免后台任务干扰）
- And 提供认证 fixture（通过 `app.dependency_overrides` mock `get_current_user` 和 `require_admin` 等依赖）
- And engine fixture 使用 module scope，db_session fixture 使用 function scope + 事务回滚
- And WebSocket 相关服务（ws_manager.broadcast 等）在测试中通过 mock 隔离

### AC2: 认证模块测试
- Given 测试数据库中有 admin 用户
- When 运行认证相关测试
- Then 覆盖：POST /api/v1/auth/login（正确密码 → 200 + token，错误密码 → 401）
- And 覆盖：GET /api/v1/auth/me（有效 token → 200 + 用户信息，无 token → 401）
- And 覆盖：POST /api/v1/auth/refresh（有效 refresh token → 新 token）
- And 覆盖：角色权限验证（admin 可访问管理接口，viewer 不可）

### AC3: 告警模块测试
- Given 测试数据库中有设备和点位数据
- When 运行告警相关测试
- Then 覆盖：GET /api/v1/alarms（列表查询 + 分页 + 筛选）
- And 覆盖：PUT /api/v1/alarms/{id}/acknowledge（确认告警）
- And 覆盖：PUT /api/v1/alarms/{id}/resolve（解决告警）
- And 覆盖：GET /api/v1/alarms/statistics（告警统计）
- And 覆盖：阈值配置 CRUD
- And WebSocket 广播调用通过 `@patch` mock 隔离

### AC4: 能源模块测试
- Given 测试数据库中有能源设备和配电拓扑数据
- When 运行能源相关测试
- Then 覆盖：GET /api/v1/energy/pue（PUE 查询）
- And 覆盖：GET /api/v1/energy/statistics/daily（日统计）
- And 覆盖：GET /api/v1/energy/statistics/monthly（月统计）
- And 覆盖：GET /api/v1/energy/realtime/summary（实时汇总）
- And 覆盖：能源建议 CRUD + 状态流转（accept/reject/complete）

### AC5: 资产与运维模块测试
- Given 测试数据库中有资产和机柜数据
- When 运行资产运维相关测试
- Then 覆盖：资产 CRUD（创建/查询/更新/删除）
- And 覆盖：资产生命周期记录
- And 覆盖：工单 CRUD + 状态流转
- And 覆盖：巡检计划和任务

### AC6: 测试通过率和覆盖率
- Given 所有测试编写完成
- When 运行 `pytest tests/ -v --cov=app --cov-report=term-missing`
- Then 所有新增测试通过（0 failures）
- And 核心模块（auth, alarms, energy, assets, operations）覆盖率 ≥ 80%
- And 现有 75 个测试文件不受影响（不破坏现有测试）

## 技术说明

### 对抗性审查关键发现（已纳入）

1. **Lifespan 隔离（阻塞性）**: `app.main.app` 的 lifespan 会启动真实数据库、Redis、7+ 后台任务。AsyncClient 必须禁用 lifespan 来避免副作用。
2. **pytest-asyncio 缺失**: `requirements.txt` 中未声明 `pytest-asyncio`，必须添加。
3. **aiosqlite 内存数据库连接共享**: 使用 `StaticPool` + `connect_args={"check_same_thread": False}` 确保多连接共享同一内存数据库。
4. **现有测试兼容性**: 现有 70+ 个测试文件自带 fixture（自给自足模式），重写根 conftest 影响极小。保留旧的同步 fixture 以兼容。

### 异步测试基础设施设计

```python
# conftest.py 核心设计
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite://"

@pytest.fixture(scope="module")
async def async_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(async_engine):
    session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

### 关键依赖（需添加到 requirements.txt）

- `pytest-asyncio>=0.23.0` — 异步测试支持
- `pytest-cov>=4.1.0` — 覆盖率测量

### 测试文件组织

新增测试文件放在 `tests/` 根目录，与现有 70+ 个文件保持一致：

```
backend/tests/
├── conftest.py                    # 更新：添加异步 fixtures（保留旧同步 fixtures）
├── test_auth_core.py              # AC2: 认证 API 测试
├── test_alarm_core.py             # AC3: 告警 API 测试
├── test_energy_core.py            # AC4: 能源 API 测试
├── test_asset_core.py             # AC5: 资产 API 测试
├── test_operations_core.py        # AC5: 运维（工单+巡检）测试
├── ... (现有 75 个文件不动)
```

### 数据准备策略

每个测试模块在 module-scope fixture 中创建所需的基础数据（设备、点位、用户等），通过 function-scope session 的事务回滚实现测试隔离。

### 不在范围内

- 前端测试（Story 14.4 覆盖）
- ML 模块测试（torch 可选依赖）
- WebSocket 端到端测试（需要特殊客户端）
- 性能测试 / 负载测试
- 现有 75 个测试文件的重构

## FR 追溯

- FR83: 自动化测试覆盖率
- Architecture: 后端三层架构（API → Service → Data）

## 依赖

- 无前置依赖（可独立开发）
- 注意：认证测试中如涉及 UserSession 模型（Story 13-2），需确认该模型已存在
