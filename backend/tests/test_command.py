"""控制命令分级确认 API 测试 — Story 9-6"""

import asyncio
import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.command import CommandApproval, CommandAuditLog
from app.models.config import SystemConfig
from app.models.device import Device
from app.models.user import User
from app.api.deps import (
    SiteAccessContext,
    enforce_inventory_authorization,
    get_db,
    get_site_access_context,
    require_admin,
    require_operator,
    require_viewer,
)
from app.services import command_service


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
        await session.execute(delete(CommandAuditLog))
        await session.execute(delete(CommandApproval))
        await session.execute(delete(SystemConfig).where(SystemConfig.config_group == "command_risk"))
        await session.execute(delete(Device))
        session.add_all(
            [
                Device(
                    id=1,
                    device_code="CMD-AC-001",
                    device_name="空调-A01",
                    device_type="AC",
                    area_code="A1",
                ),
                Device(
                    id=2,
                    device_code="CMD-PDU-002",
                    device_name="配电柜-B01",
                    device_type="PDU",
                    area_code="B1",
                ),
            ]
        )
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 2
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_operator():
    user = User()
    user.id = 1
    user.username = "test_operator"
    user.role = "operator"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin, mock_operator):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_operator

    async def override_require_viewer():
        return mock_admin

    async def override_inventory_authorization():
        return None

    async def override_site_access_context():
        return SiteAccessContext(user_id=mock_admin.id, role="admin", jti="test-jti", site_ids=None)

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[enforce_inventory_authorization] = override_inventory_authorization
    _app.dependency_overrides[get_site_access_context] = override_site_access_context
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Constants
# ============================================================

BASE_URL = "/api/v1/command"

NORMAL_CMD = {
    "command_type": "ac_temp_set",
    "target_device_id": 1,
    "target_device_name": "空调-A01",
    "command_content": {"temperature": 25},
}

CRITICAL_CMD = {
    "command_type": "power_off",
    "target_device_id": 2,
    "target_device_name": "配电柜-B01",
    "command_content": {"circuit": "B-01"},
}


# ============================================================
# Helper
# ============================================================


async def _submit_critical(client) -> dict:
    """提交一个关键命令并返回响应 JSON"""
    resp = await client.post(f"{BASE_URL}/submit", json=CRITICAL_CMD)
    assert resp.status_code == 200
    return resp.json()


# ============================================================
# Tests — POST /submit
# ============================================================


@pytest.mark.anyio
async def test_submit_normal_command(client):
    """提交普通命令，直接执行，status=executed"""
    resp = await client.post(f"{BASE_URL}/submit", json=NORMAL_CMD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed"
    assert data["audit_log_id"] is not None
    assert data.get("approval_id") is None


@pytest.mark.anyio
async def test_submit_uses_server_side_device_name_in_audit(client, db_session):
    payload = {**NORMAL_CMD, "target_device_name": "伪造设备名称"}

    response = await client.post(f"{BASE_URL}/submit", json=payload)

    assert response.status_code == 200
    audit_id = response.json()["audit_log_id"]
    audit = (await db_session.execute(select(CommandAuditLog).where(CommandAuditLog.id == audit_id))).scalar_one()
    assert audit.target_device_name == "空调-A01"


@pytest.mark.anyio
async def test_submit_critical_command(client):
    """提交关键命令，进入审批流程，status=pending_approval"""
    resp = await client.post(f"{BASE_URL}/submit", json=CRITICAL_CMD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["approval_id"] is not None
    assert data["audit_log_id"] is not None


# ============================================================
# Tests — GET /approvals
# ============================================================


@pytest.mark.anyio
async def test_list_approvals(client):
    """列出审批工单，验证分页结构"""
    await _submit_critical(client)
    await _submit_critical(client)

    resp = await client.get(f"{BASE_URL}/approvals", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.anyio
async def test_list_approvals_filter_status(client):
    """按状态筛选审批工单"""
    await _submit_critical(client)

    resp = await client.get(f"{BASE_URL}/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["status"] == "pending"


# ============================================================
# Tests — GET /approvals/{id}
# ============================================================


@pytest.mark.anyio
async def test_get_approval_detail(client):
    """获取单个审批工单详情"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    resp = await client.get(f"{BASE_URL}/approvals/{approval_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == approval_id
    assert data["command_type"] == "power_off"
    assert data["risk_level"] == "critical"
    assert data["status"] == "pending"
    assert data["target_device_name"] == "配电柜-B01"


@pytest.mark.anyio
async def test_get_approval_not_found(client):
    """获取不存在的审批工单，返回 404"""
    resp = await client.get(f"{BASE_URL}/approvals/99999")
    assert resp.status_code == 404


# ============================================================
# Tests — POST /approvals/{id}/approve
# ============================================================


@pytest.mark.anyio
async def test_approve_command(client):
    """批准审批工单，状态变为 approved"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    resp = await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approver_name"] == "test_admin"
    assert data["executed_at"] is not None


@pytest.mark.anyio
async def test_self_approval_is_rejected_and_audited(client, db_session, app, mock_operator):
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    async def override_require_admin():
        return mock_operator

    app.dependency_overrides[require_admin] = override_require_admin
    response = await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")

    assert response.status_code == 400
    assert "请求人不能审批" in response.json()["detail"]
    approval = (await db_session.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
    assert approval.status == "pending"
    audit_events = (
        (
            await db_session.execute(
                select(CommandAuditLog).where(
                    CommandAuditLog.approval_id == approval_id,
                    CommandAuditLog.result == "rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_events) == 1
    assert audit_events[0].operator_id == mock_operator.id
    assert "自审批" in audit_events[0].result_message


@pytest.mark.anyio
async def test_approve_nonexistent(client):
    """批准不存在的审批工单，返回 404"""
    resp = await client.post(f"{BASE_URL}/approvals/99999/approve")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_approve_already_approved(client):
    """重复批准已通过的工单，返回 400"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")
    resp = await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_approval_audit_is_append_only(client, db_session):
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")

    events = (
        (
            await db_session.execute(
                select(CommandAuditLog).where(CommandAuditLog.approval_id == approval_id).order_by(CommandAuditLog.id)
            )
        )
        .scalars()
        .all()
    )
    assert [event.result for event in events] == ["pending", "success"]
    assert events[0].result_message == "已提交审批，等待审批人确认"


@pytest.mark.anyio
async def test_concurrent_approval_has_exactly_one_success(tmp_path):
    database_path = tmp_path / "command-concurrency.db"
    concurrent_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    concurrent_sessions = async_sessionmaker(concurrent_engine, class_=AsyncSession, expire_on_commit=False)
    async with concurrent_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with concurrent_sessions() as setup_session:
        approval = CommandApproval(
            command_type="power_off",
            risk_level="critical",
            target_device_id=2,
            target_device_name="配电柜-B01",
            command_content={"circuit": "B-01"},
            requester_id=1,
            requester_name="requester",
            status="pending",
            expired_at=datetime.now() + timedelta(minutes=30),
        )
        setup_session.add(approval)
        await setup_session.commit()
        approval_id = approval.id

    async def approve(approver_id: int):
        async with concurrent_sessions() as session:
            try:
                result = await command_service.approve_command(
                    session,
                    approval_id,
                    approver_id=approver_id,
                    approver_name=f"approver-{approver_id}",
                )
                return "success" if result is not None else "missing"
            except ValueError:
                return "rejected"

    try:
        outcomes = await asyncio.gather(approve(2), approve(3))

        assert sorted(outcomes) == ["rejected", "success"]
        async with concurrent_sessions() as session:
            final_approval = (
                await session.execute(select(CommandApproval).where(CommandApproval.id == approval_id))
            ).scalar_one()
            assert final_approval.status == "approved"
            success_events = (
                (
                    await session.execute(
                        select(CommandAuditLog).where(
                            CommandAuditLog.approval_id == approval_id,
                            CommandAuditLog.result == "success",
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(success_events) == 1
    finally:
        await concurrent_engine.dispose()


# ============================================================
# Tests — POST /approvals/{id}/reject
# ============================================================


@pytest.mark.anyio
async def test_reject_command(client):
    """驳回审批工单，状态变为 rejected，包含驳回原因"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    resp = await client.post(
        f"{BASE_URL}/approvals/{approval_id}/reject",
        json={"reason": "风险过高，暂不执行"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["reject_reason"] == "风险过高，暂不执行"


@pytest.mark.anyio
async def test_reject_already_approved(client):
    """驳回已批准的工单，返回 400"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    await client.post(f"{BASE_URL}/approvals/{approval_id}/approve")
    resp = await client.post(
        f"{BASE_URL}/approvals/{approval_id}/reject",
        json={"reason": "太晚了"},
    )
    assert resp.status_code == 400


# ============================================================
# Tests — Approval timeout
# ============================================================


@pytest.mark.anyio
async def test_approval_timeout(client, db_session):
    """超时审批工单在列表查询时被自动标记为 timeout"""
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]

    # 手动将 expired_at 设为过去时间
    result = await db_session.execute(select(CommandApproval).where(CommandApproval.id == approval_id))
    approval = result.scalar_one()
    approval.expired_at = datetime.now() - timedelta(minutes=5)
    await db_session.commit()

    # 列表查询触发惰性超时检查
    resp = await client.get(f"{BASE_URL}/approvals", params={"status": "timeout"})
    assert resp.status_code == 200
    data = resp.json()
    timeout_ids = [item["id"] for item in data["items"]]
    assert approval_id in timeout_ids


@pytest.mark.anyio
async def test_reject_expired_approval_records_timeout(client, db_session):
    submit_data = await _submit_critical(client)
    approval_id = submit_data["approval_id"]
    approval = (await db_session.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
    approval.expired_at = datetime.now() - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        f"{BASE_URL}/approvals/{approval_id}/reject",
        json={"reason": "too late"},
    )

    assert response.status_code == 400
    await db_session.refresh(approval)
    assert approval.status == "timeout"
    timeout_event = (
        await db_session.execute(
            select(CommandAuditLog).where(
                CommandAuditLog.approval_id == approval_id,
                CommandAuditLog.result == "timeout",
            )
        )
    ).scalar_one()
    assert timeout_event.operator_name == "test_admin"


# ============================================================
# Tests — GET /audit-logs
# ============================================================


@pytest.mark.anyio
async def test_list_audit_logs(client):
    """列出审计日志，验证分页结构"""
    # 提交普通和关键命令各一条，产生审计日志
    await client.post(f"{BASE_URL}/submit", json=NORMAL_CMD)
    await _submit_critical(client)

    resp = await client.get(f"{BASE_URL}/audit-logs", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["page"] == 1


# ============================================================
# Tests — GET /risk-configs
# ============================================================


@pytest.mark.anyio
async def test_get_risk_configs(client):
    """获取风险等级配置列表，包含默认配置"""
    resp = await client.get(f"{BASE_URL}/risk-configs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6  # DEFAULT_RISK_CONFIGS 有 6 条

    types = {item["command_type"] for item in data}
    assert "power_off" in types
    assert "ac_temp_set" in types


@pytest.mark.anyio
async def test_get_risk_configs_ignores_unknown_invalid_and_downgraded_legacy_rows(client, db_session):
    from app.models.config import SystemConfig

    db_session.add_all(
        [
            SystemConfig(
                config_group="command_risk",
                config_key="future_unclassified_command",
                config_value="normal",
                value_type="string",
            ),
            SystemConfig(
                config_group="command_risk",
                config_key="power_off",
                config_value="normal",
                value_type="string",
            ),
            SystemConfig(
                config_group="command_risk",
                config_key="ac_temp_set",
                config_value="extreme",
                value_type="string",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"{BASE_URL}/risk-configs")

    assert response.status_code == 200
    config_map = {item["command_type"]: item["risk_level"] for item in response.json()}
    assert "future_unclassified_command" not in config_map
    assert config_map["power_off"] == "critical"
    assert config_map["ac_temp_set"] == "normal"


# ============================================================
# Tests — PUT /risk-configs
# ============================================================


@pytest.mark.anyio
async def test_update_risk_configs(client):
    """普通命令可升级，关键命令不可降级。"""
    update_payload = {
        "configs": [
            {"command_type": "ac_temp_set", "risk_level": "critical", "description": "调整空调温度（升级为关键）"},
        ]
    }
    resp = await client.put(f"{BASE_URL}/risk-configs", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1

    # 验证配置已变更
    resp2 = await client.get(f"{BASE_URL}/risk-configs")
    configs = resp2.json()
    config_map = {c["command_type"]: c["risk_level"] for c in configs}
    assert config_map["ac_temp_set"] == "critical"
    assert config_map["power_off"] == "critical"


@pytest.mark.anyio
async def test_update_risk_configs_rejects_critical_downgrade(client):
    response = await client.put(
        f"{BASE_URL}/risk-configs",
        json={
            "configs": [
                {"command_type": "power_off", "risk_level": "normal", "description": "unsafe downgrade"},
            ]
        },
    )

    assert response.status_code == 400
    assert "最低风险等级" in response.json()["detail"]


@pytest.mark.anyio
async def test_update_invalid_risk_level(client):
    """使用无效风险等级更新配置，返回 400"""
    update_payload = {
        "configs": [
            {"command_type": "ac_temp_set", "risk_level": "extreme", "description": "无效等级"},
        ]
    }
    resp = await client.put(f"{BASE_URL}/risk-configs", json=update_payload)
    assert resp.status_code == 400
