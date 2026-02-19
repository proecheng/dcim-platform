"""控制命令分级确认 API 测试 — Story 9-6"""
import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.command import CommandApproval, CommandAuditLog
from app.models.config import SystemConfig
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
        await session.execute(delete(CommandAuditLog))
        await session.execute(delete(CommandApproval))
        await session.execute(delete(SystemConfig).where(
            SystemConfig.config_group == "command_risk"
        ))
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
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_admin

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
    result = await db_session.execute(
        select(CommandApproval).where(CommandApproval.id == approval_id)
    )
    approval = result.scalar_one()
    approval.expired_at = datetime.now() - timedelta(minutes=5)
    await db_session.commit()

    # 列表查询触发惰性超时检查
    resp = await client.get(f"{BASE_URL}/approvals", params={"status": "timeout"})
    assert resp.status_code == 200
    data = resp.json()
    timeout_ids = [item["id"] for item in data["items"]]
    assert approval_id in timeout_ids


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


# ============================================================
# Tests — PUT /risk-configs
# ============================================================

@pytest.mark.anyio
async def test_update_risk_configs(client):
    """更新风险配置，验证变更生效"""
    update_payload = {
        "configs": [
            {"command_type": "ac_temp_set", "risk_level": "critical", "description": "调整空调温度（升级为关键）"},
            {"command_type": "power_off", "risk_level": "normal", "description": "切断电源（降级为普通）"},
        ]
    }
    resp = await client.put(f"{BASE_URL}/risk-configs", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 2

    # 验证配置已变更
    resp2 = await client.get(f"{BASE_URL}/risk-configs")
    configs = resp2.json()
    config_map = {c["command_type"]: c["risk_level"] for c in configs}
    assert config_map["ac_temp_set"] == "critical"
    assert config_map["power_off"] == "normal"


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
