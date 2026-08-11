"""联动恢复引擎 API 测试 — Story 9-4"""

import uuid
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.linkage import (
    LinkagePolicy,
    LinkageAction,
    LinkageExecution,
    LinkageLog,
    LinkageRecovery,
    LinkageRecoveryLog,
)
from app.models.user import User, UserSession
from app.api.deps import get_db, require_admin, require_operator, require_viewer
from app.engines.recovery_engine import RecoveryEngine, RECOVERY_COMMAND_MAP, RECOVERY_ORDER
from tests.conftest import _create_test_token, auth_headers


# ============================================================
# Fixtures
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


@pytest.fixture(scope="module")
async def admin_token(session_factory):
    async with session_factory() as session:
        admin = User(
            username="recovery_admin",
            password_hash="test-only",
            real_name="联动恢复管理员",
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()
        jti = uuid.uuid4().hex
        session.add(UserSession(user_id=admin.id, token_jti=jti, is_active=True))
        await session.commit()
        return _create_test_token(admin.username, jti)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # FK 约束顺序清理
        await session.execute(delete(LinkageRecoveryLog))
        await session.execute(delete(LinkageRecovery))
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
async def client(app, admin_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=auth_headers(admin_token),
    ) as c:
        yield c


@pytest.fixture
async def seed_execution(db_session):
    """创建测试策略 + 执行记录 + 日志"""
    policy = LinkagePolicy(
        name="消防联动测试",
        trigger_type="alarm.triggered",
        trigger_condition={"alarm_level": "critical"},
        priority="fire_signal",
        is_enabled=True,
        is_system=True,
    )
    db_session.add(policy)
    await db_session.flush()

    execution = LinkageExecution(
        policy_id=policy.id,
        event_id="EVT-TEST-001",
        trigger_source="smoke_detector_01",
        trigger_event="alarm.triggered",
        status="completed",
    )
    db_session.add(execution)
    await db_session.flush()

    # 成功的 MQTT_COMMAND 日志
    log1 = LinkageLog(
        execution_id=execution.id,
        action_id=1,
        action_type="MQTT_COMMAND",
        action_config={"command": "shutdown", "target_type": "NON_CRITICAL_POWER", "message": "关闭非关键负载"},
        status="success",
    )
    log2 = LinkageLog(
        execution_id=execution.id,
        action_id=2,
        action_type="MQTT_COMMAND",
        action_config={"command": "activate", "target_type": "EMERGENCY_LIGHTING", "message": "启动应急照明"},
        status="success",
    )
    # 通知日志（恢复时应跳过）
    log3 = LinkageLog(
        execution_id=execution.id,
        action_id=3,
        action_type="ALARM_NOTIFY",
        action_config={"message": "消防告警通知"},
        status="success",
    )
    # 失败日志（恢复时应跳过 — M1）
    log4 = LinkageLog(
        execution_id=execution.id,
        action_id=4,
        action_type="MQTT_COMMAND",
        action_config={"command": "cutoff", "target_type": "HVAC", "message": "关闭空调"},
        status="failed",
    )
    db_session.add_all([log1, log2, log3, log4])
    await db_session.commit()
    return execution


# ============================================================
# Tests — 单元测试: RecoveryEngine.generate_recovery_steps
# ============================================================

BASE_URL = "/api/v1/linkage"


@pytest.mark.anyio
async def test_generate_recovery_steps_basic(seed_execution, db_session):
    """生成恢复步骤: 仅成功日志生成步骤, ALARM_NOTIFY 跳过, 失败日志跳过, 按 RECOVERY_ORDER 排序"""
    result = await db_session.execute(select(LinkageLog).where(LinkageLog.execution_id == seed_execution.id))
    logs = result.scalars().all()
    log_dicts = [{"action_type": l.action_type, "action_config": l.action_config, "status": l.status} for l in logs]

    engine = RecoveryEngine()
    steps = engine.generate_recovery_steps(log_dicts)

    # 4 条日志 → 只有 log1(shutdown/success) 和 log2(activate/success) 生成步骤
    assert len(steps) == 2

    # 按 RECOVERY_ORDER: EMERGENCY_LIGHTING=2 < NON_CRITICAL_POWER=3
    assert steps[0]["target_type"] == "EMERGENCY_LIGHTING"
    assert steps[0]["recovery_command"] == "deactivate"
    assert steps[0]["step_order"] == 1

    assert steps[1]["target_type"] == "NON_CRITICAL_POWER"
    assert steps[1]["recovery_command"] == "start"
    assert steps[1]["step_order"] == 2


@pytest.mark.anyio
async def test_generate_recovery_steps_empty():
    """无可恢复日志 → 空列表"""
    engine = RecoveryEngine()

    # 全部失败
    logs = [
        {"action_type": "MQTT_COMMAND", "action_config": {"command": "shutdown"}, "status": "failed"},
        {"action_type": "MQTT_COMMAND", "action_config": {"command": "cutoff"}, "status": "timeout"},
    ]
    assert engine.generate_recovery_steps(logs) == []

    # 空列表
    assert engine.generate_recovery_steps([]) == []


@pytest.mark.anyio
async def test_generate_recovery_steps_video_popup_skipped():
    """VIDEO_POPUP 动作类型应被跳过 (H1)"""
    engine = RecoveryEngine()
    logs = [
        {"action_type": "VIDEO_POPUP", "action_config": {"camera_id": "cam01"}, "status": "success"},
        {
            "action_type": "MQTT_COMMAND",
            "action_config": {"command": "shutdown", "target_type": "HVAC"},
            "status": "success",
        },
    ]
    steps = engine.generate_recovery_steps(logs)
    assert len(steps) == 1
    assert steps[0]["action_type"] == "MQTT_COMMAND"
    assert steps[0]["recovery_command"] == "start"


@pytest.mark.anyio
async def test_recovery_command_map_correctness():
    """验证 RECOVERY_COMMAND_MAP 所有条目正确"""
    expected = {
        ("MQTT_COMMAND", "shutdown"): "start",
        ("MQTT_COMMAND", "start"): "stop",
        ("MQTT_COMMAND", "cutoff"): "restore",
        ("MQTT_COMMAND", "unlock"): "lock",
        ("MQTT_COMMAND", "activate"): "deactivate",
        ("VIDEO_RECORD", None): "stop",
    }
    assert RECOVERY_COMMAND_MAP == expected


@pytest.mark.anyio
async def test_recovery_order():
    """验证 RECOVERY_ORDER 值"""
    assert RECOVERY_ORDER["ACCESS_CONTROL"] == 1
    assert RECOVERY_ORDER["EMERGENCY_LIGHTING"] == 2
    assert RECOVERY_ORDER["NON_CRITICAL_POWER"] == 3
    assert RECOVERY_ORDER["HVAC"] == 4
    assert RECOVERY_ORDER["EXHAUST_FAN"] == 5
    assert len(RECOVERY_ORDER) == 5


# ============================================================
# Tests — API 集成测试
# ============================================================


@pytest.mark.anyio
async def test_list_recoverable_executions(client, seed_execution):
    """GET /executions/recoverable 返回 completed/partial_failure 执行记录"""
    resp = await client.get(f"{BASE_URL}/executions/recoverable")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    # seed_execution 状态为 completed，应出现在列表中
    ids = [item["id"] for item in data["items"]]
    assert seed_execution.id in ids


@pytest.mark.anyio
async def test_create_recovery_auto(client, seed_execution):
    """POST /executions/{id}/recover mode=auto → 返回 recovery_id 和 steps_count"""
    with patch("app.api.v1.linkage.asyncio.create_task"):
        resp = await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "recovery_id" in data
    assert data["steps_count"] == 2
    assert data["message"] == "恢复已发起"


@pytest.mark.anyio
async def test_create_recovery_manual(client, seed_execution):
    """POST /executions/{id}/recover mode=manual → 恢复记录 status=executing"""
    resp = await client.post(
        f"{BASE_URL}/executions/{seed_execution.id}/recover",
        json={"mode": "manual"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recovery_id" in data
    assert data["steps_count"] == 2


@pytest.mark.anyio
async def test_create_recovery_not_found(client):
    """POST /executions/99999/recover → 404"""
    resp = await client.post(
        f"{BASE_URL}/executions/99999/recover",
        json={"mode": "auto"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_recovery_duplicate(client, seed_execution):
    """重复创建恢复 → 400"""
    # 第一次创建
    with patch("app.api.v1.linkage.asyncio.create_task"):
        resp1 = await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )
    assert resp1.status_code == 200

    # 第二次创建 → 400
    with patch("app.api.v1.linkage.asyncio.create_task"):
        resp2 = await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )
    assert resp2.status_code == 400
    assert "已有活跃的恢复任务" in resp2.json()["detail"]


@pytest.mark.anyio
async def test_list_recoveries(client, seed_execution):
    """GET /recoveries 返回分页列表"""
    # 先创建一条恢复记录
    with patch("app.api.v1.linkage.asyncio.create_task"):
        await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )

    resp = await client.get(f"{BASE_URL}/recoveries")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_get_recovery_detail(client, seed_execution, db_session):
    """GET /recoveries/{id} 返回恢复记录含 logs"""
    # 创建恢复
    with patch("app.api.v1.linkage.asyncio.create_task"):
        create_resp = await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )
    recovery_id = create_resp.json()["recovery_id"]

    resp = await client.get(f"{BASE_URL}/recoveries/{recovery_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == recovery_id
    assert data["execution_id"] == seed_execution.id
    assert data["mode"] == "auto"
    assert data["status"] == "executing"
    assert len(data["logs"]) == 2


@pytest.mark.anyio
async def test_get_recovery_not_found(client):
    """GET /recoveries/99999 → 404"""
    resp = await client.get(f"{BASE_URL}/recoveries/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_skip_step(client, seed_execution):
    """POST /recoveries/{id}/step/{order}/skip → 200, 步骤状态变为 skipped"""
    from app.engines.recovery_engine import recovery_engine

    # 创建 manual 恢复
    resp = await client.post(
        f"{BASE_URL}/executions/{seed_execution.id}/recover",
        json={"mode": "manual"},
    )
    recovery_id = resp.json()["recovery_id"]

    # 跳过第 1 步 — mock skip_step 因为它使用全局 async_session
    with patch.object(recovery_engine, "skip_step", new_callable=AsyncMock, return_value=True):
        skip_resp = await client.post(f"{BASE_URL}/recoveries/{recovery_id}/step/1/skip")
    assert skip_resp.status_code == 200
    assert skip_resp.json()["message"] == "步骤已跳过"


@pytest.mark.anyio
async def test_execute_step(client, seed_execution):
    """POST /recoveries/{id}/step/{order}/execute → 200"""
    from app.engines.recovery_engine import recovery_engine

    # 创建 manual 恢复
    resp = await client.post(
        f"{BASE_URL}/executions/{seed_execution.id}/recover",
        json={"mode": "manual"},
    )
    recovery_id = resp.json()["recovery_id"]

    # 执行第 1 步 — mock execute_single_step
    with patch.object(recovery_engine, "execute_single_step", new_callable=AsyncMock, return_value=True):
        exec_resp = await client.post(f"{BASE_URL}/recoveries/{recovery_id}/step/1/execute")
    assert exec_resp.status_code == 200
    assert exec_resp.json()["message"] == "步骤执行完成"


@pytest.mark.anyio
async def test_recoverable_excludes_recovered(client, seed_execution):
    """创建恢复后, 该执行记录不再出现在可恢复列表中"""
    # 创建恢复
    with patch("app.api.v1.linkage.asyncio.create_task"):
        await client.post(
            f"{BASE_URL}/executions/{seed_execution.id}/recover",
            json={"mode": "auto"},
        )

    # 查询可恢复列表 — seed_execution 不应出现
    resp = await client.get(f"{BASE_URL}/executions/recoverable")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert seed_execution.id not in ids
