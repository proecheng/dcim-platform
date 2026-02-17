"""
消防分级联动策略测试
Story 9-2
"""
import pytest
import time
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.linkage import LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog
from app.models.user import User
from app.engines.event_bus import Event, EventPriority, get_event_bus
from app.engines.cross_confirmation import CrossConfirmationService, FIRE_SENSOR_TYPES
from app.services.fire_protection import load_yaml_policies, sync_to_database, reload, get_status
from app.api.deps import get_db, require_admin, require_operator, require_viewer


# ============================================================
# Fixtures（与 test_linkage.py 保持一致的内存数据库模式）
# ============================================================

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理所有联动相关表
        await session.execute(delete(LinkageLog))
        await session.execute(delete(LinkageExecution))
        await session.execute(delete(LinkageAction))
        await session.execute(delete(LinkagePolicy))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer():
    user = User()
    user.id = 2
    user.username = "test_viewer"
    user.role = "viewer"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin, mock_viewer):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_viewer

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Test: YAML 加载（纯函数，无需数据库）
# ============================================================

def test_yaml_load():
    """测试 YAML 文件解析正确性"""
    policies = load_yaml_policies()
    assert len(policies) == 3, f"应有 3 条消防策略，实际 {len(policies)}"

    # 验证预警策略
    warning_policies = [
        p for p in policies
        if p.get("trigger_condition", {}).get("fire_level") == "warning"
    ]
    assert len(warning_policies) == 2, "应有 2 条预警级策略"

    # 验证联动策略
    linkage_policies = [
        p for p in policies
        if p.get("trigger_condition", {}).get("fire_level") == "linkage"
    ]
    assert len(linkage_policies) == 1, "应有 1 条联动级策略"

    # 验证联动策略有 7 个动作
    linkage_policy = linkage_policies[0]
    assert len(linkage_policy.get("actions", [])) == 7, "联动策略应有 7 个动作"

    # 验证优先级
    assert linkage_policy["priority"] == "fire_signal"
    for wp in warning_policies:
        assert wp["priority"] == "critical"


# ============================================================
# Test: 数据库同步
# ============================================================

@pytest.mark.anyio
async def test_sync_to_database(db_session):
    """测试首次同步创建策略，重复同步跳过"""
    # 首次同步
    count1 = await sync_to_database(db_session)
    assert count1 == 3, f"首次同步应创建 3 条策略，实际 {count1}"

    # 验证数据库中有 3 条系统策略
    result = await db_session.execute(
        select(LinkagePolicy).where(LinkagePolicy.is_system == True)  # noqa: E712
    )
    policies = result.scalars().all()
    assert len(policies) == 3

    # 重复同步应跳过
    count2 = await sync_to_database(db_session)
    assert count2 == 0, f"重复同步应跳过，实际创建 {count2}"


# ============================================================
# Test: 重载
# ============================================================

@pytest.mark.anyio
async def test_reload(db_session):
    """测试重载删除旧策略并重新创建"""
    # 首次同步
    await sync_to_database(db_session)

    # 验证有 3 条
    result = await db_session.execute(
        select(LinkagePolicy).where(LinkagePolicy.is_system == True)  # noqa: E712
    )
    assert len(result.scalars().all()) == 3

    # 重载
    count = await reload(db_session)
    assert count == 3, f"重载应重新创建 3 条策略，实际 {count}"

    # 验证仍然有 3 条
    result = await db_session.execute(
        select(LinkagePolicy).where(LinkagePolicy.is_system == True)  # noqa: E712
    )
    assert len(result.scalars().all()) == 3


# ============================================================
# Test: 交叉确认
# ============================================================

@pytest.mark.anyio
async def test_cross_confirmation():
    """测试单传感器不触发交叉确认，多传感器触发"""
    service = CrossConfirmationService()

    published_events = []

    async def mock_publish(channel, event):
        published_events.append(event)

    # 模拟事件总线
    with patch.object(get_event_bus(), "publish", side_effect=mock_publish):
        # 单传感器触发 — 不应产生交叉确认
        event1 = Event(
            event_type="alarm.triggered",
            source="alarm_engine",
            priority=EventPriority.critical,
            payload={
                "device_type": "SMOKE",
                "zone": "A1",
                "alarm_type": "threshold",
                "alarm_level": "critical",
            },
        )
        await service.on_alarm_event(event1)
        assert len(published_events) == 0, "单传感器不应触发交叉确认"

        # 同区域不同类型传感器触发 — 应产生交叉确认
        event2 = Event(
            event_type="alarm.triggered",
            source="alarm_engine",
            priority=EventPriority.critical,
            payload={
                "device_type": "VESDA",
                "zone": "A1",
                "alarm_type": "threshold",
                "alarm_level": "critical",
            },
        )
        await service.on_alarm_event(event2)
        assert len(published_events) == 1, "多传感器应触发交叉确认"

        # 验证交叉确认事件
        fire_event = published_events[0]
        assert fire_event.priority == EventPriority.fire_signal
        assert fire_event.payload["device_type"] == "CROSS_CONFIRMED"
        assert fire_event.payload["zone"] == "A1"


# ============================================================
# Test: 防重入
# ============================================================

@pytest.mark.anyio
async def test_cross_confirmation_anti_reentrant():
    """测试 CROSS_CONFIRMED 事件不会再次进入交叉确认"""
    service = CrossConfirmationService()

    published_events = []

    async def mock_publish(channel, event):
        published_events.append(event)

    with patch.object(get_event_bus(), "publish", side_effect=mock_publish):
        # CROSS_CONFIRMED 事件应被忽略
        event = Event(
            event_type="alarm.triggered",
            source="cross_confirmation",
            priority=EventPriority.fire_signal,
            payload={
                "device_type": "CROSS_CONFIRMED",
                "zone": "A1",
            },
        )
        await service.on_alarm_event(event)
        assert len(published_events) == 0, "CROSS_CONFIRMED 事件不应触发交叉确认"


# ============================================================
# Test: 重试机制（直接操作缓存验证）
# ============================================================

@pytest.mark.anyio
async def test_retry_count_in_cache(db_session):
    """测试 load_policies 缓存包含 retry_count"""
    from app.engines.linkage_engine import linkage_engine
    from app.engines import linkage_engine as le_module

    # 创建带 retry_count 的策略
    policy = LinkagePolicy(
        name="测试重试策略",
        trigger_type="alarm.triggered",
        trigger_condition={"alarm_level": "critical"},
        priority="normal",
        is_enabled=True,
        is_system=False,
    )
    db_session.add(policy)
    await db_session.flush()

    action = LinkageAction(
        policy_id=policy.id,
        action_type="ALARM_NOTIFY",
        action_config={"message": "测试"},
        sort_order=0,
        timeout_seconds=3,
        retry_count=1,
    )
    db_session.add(action)
    await db_session.commit()

    # patch async_session 让 load_policies 使用测试数据库
    class _FakeCtx:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *args):
            pass

    with patch.object(le_module, "async_session", return_value=_FakeCtx()):
        await linkage_engine.load_policies()

    # 验证缓存中包含 retry_count
    cache = linkage_engine._policy_cache
    found = False
    for policy_data in cache.values():
        if policy_data["name"] == "测试重试策略":
            actions = policy_data["actions"]
            assert len(actions) == 1
            assert actions[0]["retry_count"] == 1, "缓存应包含 retry_count"
            found = True
            break
    assert found, "未找到测试重试策略"

    # 清理缓存
    linkage_engine._policy_cache.clear()


# ============================================================
# Test: 消防策略 API
# ============================================================

@pytest.mark.anyio
async def test_fire_protection_status(client):
    """测试 status 端点"""
    resp = await client.get("/api/v1/linkage/fire-protection/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "yaml_exists" in data
    assert data["yaml_exists"] is True


@pytest.mark.anyio
async def test_fire_protection_reload(client, db_session):
    """测试 reload 端点"""
    from app.engines.linkage_engine import linkage_engine
    from app.engines import linkage_engine as le_module

    # patch linkage_engine.reload_policies 避免它内部调用 async_session
    class _FakeCtx:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *args):
            pass

    with patch.object(le_module, "async_session", return_value=_FakeCtx()):
        resp = await client.post("/api/v1/linkage/fire-protection/reload")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3

    # 验证策略列表中有系统策略
    resp = await client.get("/api/v1/linkage/policies", params={"is_enabled": True})
    assert resp.status_code == 200
    policies = resp.json()["items"]
    system_policies = [p for p in policies if p["is_system"]]
    assert len(system_policies) >= 3
