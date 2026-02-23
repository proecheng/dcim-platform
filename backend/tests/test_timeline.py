"""事件时间线报告 API 测试 — Story 9-5"""

import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.linkage import (
    LinkagePolicy,
    LinkageAction,
    LinkageExecution,
    LinkageLog,
    LinkageRecovery,
    LinkageRecoveryLog,
)
from app.models.user import User
from app.api.deps import get_db, require_admin, require_operator, require_viewer


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
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Helper: 创建测试数据
# ============================================================

BASE_URL = "/api/v1/linkage"

T0 = datetime(2026, 2, 17, 10, 0, 0)


async def _create_execution_only(db_session) -> LinkageExecution:
    """创建仅有执行记录（无恢复）的测试数据"""
    policy = LinkagePolicy(
        name="温度告警联动",
        trigger_type="alarm.triggered",
        trigger_condition={"alarm_level": "critical"},
        priority="critical",
        is_enabled=True,
        is_system=False,
    )
    db_session.add(policy)
    await db_session.flush()

    execution = LinkageExecution(
        policy_id=policy.id,
        event_id="EVT-TL-001",
        trigger_source="temp_sensor_01",
        trigger_event={"alarm_level": "critical"},
        status="completed",
        started_at=T0,
        completed_at=T0 + timedelta(seconds=5),
        total_duration_ms=5000,
    )
    db_session.add(execution)
    await db_session.flush()

    log1 = LinkageLog(
        execution_id=execution.id,
        action_id=1,
        action_type="ALARM_NOTIFY",
        action_config={"message": "温度告警通知"},
        status="success",
        started_at=T0 + timedelta(milliseconds=100),
        completed_at=T0 + timedelta(milliseconds=300),
        duration_ms=200,
    )
    log2 = LinkageLog(
        execution_id=execution.id,
        action_id=2,
        action_type="MQTT_COMMAND",
        action_config={"command": "shutdown", "target_type": "HVAC", "target": "空调系统"},
        status="success",
        started_at=T0 + timedelta(milliseconds=400),
        completed_at=T0 + timedelta(milliseconds=900),
        duration_ms=500,
    )
    log3 = LinkageLog(
        execution_id=execution.id,
        action_id=3,
        action_type="MQTT_COMMAND",
        action_config={"command": "activate", "target_type": "EMERGENCY_LIGHTING"},
        status="failed",
        error_message="设备离线",
        started_at=T0 + timedelta(milliseconds=1000),
        completed_at=T0 + timedelta(milliseconds=1500),
        duration_ms=500,
    )
    db_session.add_all([log1, log2, log3])
    await db_session.commit()
    return execution


async def _create_execution_with_recovery(db_session) -> tuple:
    """创建含恢复记录的完整测试数据"""
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
        event_id="EVT-TL-002",
        trigger_source="smoke_detector_01",
        trigger_event={"alarm_level": "critical"},
        status="completed",
        started_at=T0,
        completed_at=T0 + timedelta(seconds=3),
        total_duration_ms=3000,
    )
    db_session.add(execution)
    await db_session.flush()

    log1 = LinkageLog(
        execution_id=execution.id,
        action_id=1,
        action_type="MQTT_COMMAND",
        action_config={"command": "shutdown", "target_type": "NON_CRITICAL_POWER"},
        status="success",
        started_at=T0 + timedelta(milliseconds=100),
        completed_at=T0 + timedelta(milliseconds=600),
        duration_ms=500,
    )
    log2 = LinkageLog(
        execution_id=execution.id,
        action_id=2,
        action_type="MQTT_COMMAND",
        action_config={"command": "activate", "target_type": "EMERGENCY_LIGHTING"},
        status="success",
        started_at=T0 + timedelta(milliseconds=700),
        completed_at=T0 + timedelta(milliseconds=1200),
        duration_ms=500,
    )
    db_session.add_all([log1, log2])
    await db_session.flush()

    recovery = LinkageRecovery(
        execution_id=execution.id,
        operator="test_admin",
        mode="auto",
        status="completed",
        started_at=T0 + timedelta(seconds=60),
        completed_at=T0 + timedelta(seconds=65),
        total_duration_ms=5000,
    )
    db_session.add(recovery)
    await db_session.flush()

    rlog1 = LinkageRecoveryLog(
        recovery_id=recovery.id,
        step_order=1,
        action_type="MQTT_COMMAND",
        target_type="EMERGENCY_LIGHTING",
        recovery_command="deactivate",
        action_config={"command": "deactivate", "target_type": "EMERGENCY_LIGHTING"},
        status="success",
        started_at=T0 + timedelta(seconds=60, milliseconds=100),
        completed_at=T0 + timedelta(seconds=62),
        duration_ms=1900,
    )
    rlog2 = LinkageRecoveryLog(
        recovery_id=recovery.id,
        step_order=2,
        action_type="MQTT_COMMAND",
        target_type="NON_CRITICAL_POWER",
        recovery_command="start",
        action_config={"command": "start", "target_type": "NON_CRITICAL_POWER"},
        status="success",
        started_at=T0 + timedelta(seconds=62, milliseconds=100),
        completed_at=T0 + timedelta(seconds=64),
        duration_ms=1900,
    )
    db_session.add_all([rlog1, rlog2])
    await db_session.commit()
    return execution, recovery


# ============================================================
# Tests — GET /timeline/{execution_id}
# ============================================================


@pytest.mark.anyio
async def test_timeline_success_execution_only(client, db_session):
    """GET /timeline/{id} — 仅执行记录，无恢复，返回 200"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["execution_id"] == execution.id
    assert data["event_id"] == "EVT-TL-001"
    assert data["policy_name"] == "温度告警联动"
    assert data["trigger_source"] == "temp_sensor_01"
    assert data["level"] == "critical"
    assert data["status"] == "completed"
    assert data["total_duration_ms"] == 5000
    # 无恢复
    assert data["recovery_time_ms"] is None
    assert data["operator"] is None


@pytest.mark.anyio
async def test_timeline_not_found(client):
    """GET /timeline/99999 → 404"""
    resp = await client.get(f"{BASE_URL}/timeline/99999")
    assert resp.status_code == 404
    assert "执行记录不存在" in resp.json()["detail"]


@pytest.mark.anyio
async def test_timeline_execution_only_events(client, db_session):
    """仅执行记录时，事件包含 trigger + action 阶段，无 recovery"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    phases = [e["phase"] for e in events]
    assert "trigger" in phases
    assert "action" in phases
    assert "recovery" not in phases


@pytest.mark.anyio
async def test_timeline_execution_only_event_count(client, db_session):
    """仅执行记录: 1 trigger + 3 action logs = 4 events"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    # 1 trigger event + 3 action logs
    assert len(events) == 4


@pytest.mark.anyio
async def test_timeline_with_recovery(client, db_session):
    """GET /timeline/{id} — 含恢复记录，返回完整时间线"""
    execution, recovery = await _create_execution_with_recovery(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["execution_id"] == execution.id
    assert data["event_id"] == "EVT-TL-002"
    assert data["policy_name"] == "消防联动测试"
    assert data["level"] == "fire_signal"
    assert data["recovery_time_ms"] == 5000
    assert data["operator"] == "test_admin"


@pytest.mark.anyio
async def test_timeline_with_recovery_includes_all_phases(client, db_session):
    """含恢复记录时，事件包含 trigger + action + recovery 三个阶段"""
    execution, _ = await _create_execution_with_recovery(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    phases = set(e["phase"] for e in events)
    assert phases == {"trigger", "action", "recovery"}


@pytest.mark.anyio
async def test_timeline_with_recovery_event_count(client, db_session):
    """含恢复: 1 trigger + 2 action + 1 恢复开始 + 2 恢复步骤 + 1 恢复完成 = 7"""
    execution, _ = await _create_execution_with_recovery(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    assert len(events) == 7


@pytest.mark.anyio
async def test_timeline_events_sorted_by_timestamp(client, db_session):
    """时间线事件按 timestamp 升序排列"""
    execution, _ = await _create_execution_with_recovery(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    timestamps = []
    for e in events:
        ts = e["timestamp"]
        if ts is not None:
            timestamps.append(ts)

    # 验证时间戳严格非递减
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1], f"事件未按时间排序: {timestamps[i - 1]} > {timestamps[i]}"


@pytest.mark.anyio
async def test_timeline_trigger_event_detail(client, db_session):
    """触发事件包含触发来源和告警级别"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    trigger_events = [e for e in events if e["phase"] == "trigger"]
    assert len(trigger_events) == 1

    trigger = trigger_events[0]
    assert trigger["event_type"] == "联动触发"
    assert "temp_sensor_01" in trigger["detail"]
    assert "critical" in trigger["detail"]
    assert trigger["status"] == "success"


@pytest.mark.anyio
async def test_timeline_action_events_detail(client, db_session):
    """联动动作事件包含正确的动作类型和状态"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    action_events = [e for e in events if e["phase"] == "action"]
    assert len(action_events) == 3

    # 第一个: ALARM_NOTIFY → 告警通知
    assert action_events[0]["event_type"] == "告警通知"
    assert action_events[0]["status"] == "success"
    assert action_events[0]["duration_ms"] == 200

    # 第二个: MQTT_COMMAND → MQTT 指令
    assert action_events[1]["event_type"] == "MQTT 指令"
    assert action_events[1]["status"] == "success"
    assert "空调系统" in action_events[1]["detail"]

    # 第三个: 失败的 MQTT_COMMAND
    assert action_events[2]["status"] == "failed"
    assert "设备离线" in action_events[2]["detail"]


@pytest.mark.anyio
async def test_timeline_recovery_events_detail(client, db_session):
    """恢复阶段事件包含恢复开始、步骤和完成"""
    execution, _ = await _create_execution_with_recovery(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}")
    assert resp.status_code == 200

    events = resp.json()["events"]
    recovery_events = [e for e in events if e["phase"] == "recovery"]

    # 恢复开始
    start_evt = recovery_events[0]
    assert start_evt["event_type"] == "恢复开始"
    assert "一键恢复" in start_evt["detail"]
    assert "test_admin" in start_evt["detail"]

    # 恢复步骤
    step_events = [e for e in recovery_events if "恢复步骤" in e["event_type"]]
    assert len(step_events) == 2
    assert "deactivate" in step_events[0]["detail"]
    assert "EMERGENCY_LIGHTING" in step_events[0]["detail"]
    assert "start" in step_events[1]["detail"]
    assert "NON_CRITICAL_POWER" in step_events[1]["detail"]

    # 恢复完成
    end_evt = recovery_events[-1]
    assert end_evt["event_type"] == "恢复完成"
    assert "已完成" in end_evt["detail"]


# ============================================================
# Tests — GET /timeline/{execution_id}/export
# ============================================================


@pytest.mark.anyio
async def test_export_timeline_success(client, db_session):
    """GET /timeline/{id}/export — 返回 Excel 文件"""
    execution = await _create_execution_only(db_session)

    resp = await client.get(f"{BASE_URL}/timeline/{execution.id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "content-disposition" in resp.headers
    assert "timeline_EVT-TL-001" in resp.headers["content-disposition"]
    # Excel 文件应有内容
    assert len(resp.content) > 0


@pytest.mark.anyio
async def test_export_timeline_not_found(client):
    """GET /timeline/99999/export → 404"""
    resp = await client.get(f"{BASE_URL}/timeline/99999/export")
    assert resp.status_code == 404
    assert "执行记录不存在" in resp.json()["detail"]
