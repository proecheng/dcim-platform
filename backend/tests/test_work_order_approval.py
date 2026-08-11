"""工单审批流程 API 测试"""

import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.operation import WorkOrder, WorkOrderLog, WorkOrderApproval
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
        await session.execute(delete(WorkOrderApproval))
        await session.execute(delete(WorkOrderLog))
        await session.execute(delete(WorkOrder))
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

    async def override_inventory_authorization():
        return None

    async def override_site_access_context():
        return SiteAccessContext(mock_admin.id, "admin", "test-jti", None)

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
# Constants & Helpers
# ============================================================

WO_URL = "/api/v1/operation/workorders"
APPROVAL_URL = "/api/v1/operation/approvals"

# 变更请求类型的工单（需要审批）
CHANGE_ORDER_PAYLOAD = {
    "title": "变更请求测试工单",
    "description": "需要审批的变更请求",
    "order_type": "变更请求",
    "priority": "高",
}

# 故障报修类型的工单（不需要审批）
FAULT_ORDER_PAYLOAD = {
    "title": "故障报修测试工单",
    "description": "不需要审批的故障报修",
    "order_type": "故障报修",
    "priority": "高",
}


async def _create_change_order_at_accepted(client: AsyncClient) -> dict:
    """创建变更请求工单并推进到已接单状态"""
    resp = await client.post(WO_URL, json=CHANGE_ORDER_PAYLOAD)
    assert resp.status_code == 200
    order = resp.json()
    order_id = order["id"]

    # assign → accept
    resp = await client.post(f"{WO_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    assert resp.status_code == 200
    resp = await client.post(f"{WO_URL}/{order_id}/accept")
    assert resp.status_code == 200

    return resp.json()


# ============================================================
# Tests
# ============================================================


@pytest.mark.anyio
async def test_submit_approval(client):
    """提交审批成功"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1", "timeout_hours": 48})
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == order_id
    assert data["approver"] == "manager1"
    assert data["status"] == "待审批"
    assert data["timeout_hours"] == 48


@pytest.mark.anyio
async def test_submit_approval_wrong_status(client):
    """非已接单状态提交审批失败"""
    # 创建工单但不推进到 accepted
    resp = await client.post(WO_URL, json=CHANGE_ORDER_PAYLOAD)
    assert resp.status_code == 200
    order_id = resp.json()["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    assert resp.status_code == 400
    assert "已接单" in resp.json()["detail"]


@pytest.mark.anyio
async def test_submit_approval_wrong_type(client):
    """非变更请求类型提交审批失败"""
    # 创建故障报修工单并推进到 accepted
    resp = await client.post(WO_URL, json=FAULT_ORDER_PAYLOAD)
    assert resp.status_code == 200
    order_id = resp.json()["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    assert resp.status_code == 200
    resp = await client.post(f"{WO_URL}/{order_id}/accept")
    assert resp.status_code == 200

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    assert resp.status_code == 400
    assert "变更请求" in resp.json()["detail"]


@pytest.mark.anyio
async def test_submit_approval_duplicate(client):
    """重复提交审批失败"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    assert resp.status_code == 200

    # 再次提交
    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager2"})
    assert resp.status_code == 400
    assert "进行中" in resp.json()["detail"]


@pytest.mark.anyio
async def test_list_approvals(client):
    """获取审批列表"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})

    resp = await client.get(APPROVAL_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_list_approvals_filter_status(client):
    """按状态过滤审批列表"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})

    resp = await client.get(APPROVAL_URL, params={"status": "待审批"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert item["status"] == "待审批"


@pytest.mark.anyio
async def test_approve_approval(client):
    """批准审批成功，工单自动转为处理中"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    approval_id = resp.json()["id"]

    resp = await client.post(f"{APPROVAL_URL}/{approval_id}/approve", json={"reason": "同意变更"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已批准"
    assert data["reason"] == "同意变更"
    assert data["resolved_at"] is not None

    # 验证工单已自动转为处理中
    resp = await client.get(f"{WO_URL}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "处理中"
    assert resp.json()["started_at"] is not None


@pytest.mark.anyio
async def test_reject_approval(client):
    """驳回审批成功，reason 必填"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    approval_id = resp.json()["id"]

    resp = await client.post(f"{APPROVAL_URL}/{approval_id}/reject", json={"reason": "方案不完善，请补充"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已驳回"
    assert data["reason"] == "方案不完善，请补充"

    # 验证工单仍为已接单
    resp = await client.get(f"{WO_URL}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "已接单"


@pytest.mark.anyio
async def test_reject_approval_no_reason(client):
    """驳回审批无 reason 失败（422 验证错误）"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    approval_id = resp.json()["id"]

    resp = await client.post(f"{APPROVAL_URL}/{approval_id}/reject", json={})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_approve_already_resolved(client):
    """批准已处理的审批失败"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1"})
    approval_id = resp.json()["id"]

    # 先批准
    resp = await client.post(f"{APPROVAL_URL}/{approval_id}/approve", json={})
    assert resp.status_code == 200

    # 再次批准
    resp = await client.post(f"{APPROVAL_URL}/{approval_id}/approve", json={})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_approval_timeout(client, db_session):
    """超时审批自动标记"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(f"{WO_URL}/{order_id}/submit-approval", json={"approver": "manager1", "timeout_hours": 1})
    assert resp.status_code == 200
    approval_id = resp.json()["id"]

    # 手动将 created_at 设为过去时间以模拟超时
    from sqlalchemy import update

    await db_session.execute(
        update(WorkOrderApproval)
        .where(WorkOrderApproval.id == approval_id)
        .values(created_at=datetime.now() - timedelta(hours=2))
    )
    await db_session.commit()

    # 查询审批详情触发惰性超时检查
    resp = await client.get(f"{APPROVAL_URL}/{approval_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "已超时"


@pytest.mark.anyio
async def test_approval_escalation(client, db_session):
    """超时升级到上级审批人"""
    order = await _create_change_order_at_accepted(client)
    order_id = order["id"]

    resp = await client.post(
        f"{WO_URL}/{order_id}/submit-approval",
        json={"approver": "manager1", "timeout_hours": 1, "escalate_to": "director1"},
    )
    assert resp.status_code == 200
    approval_id = resp.json()["id"]

    # 手动将 created_at 设为过去时间以模拟超时
    from sqlalchemy import update

    await db_session.execute(
        update(WorkOrderApproval)
        .where(WorkOrderApproval.id == approval_id)
        .values(created_at=datetime.now() - timedelta(hours=2))
    )
    await db_session.commit()

    # 查询审批详情触发惰性超时检查
    resp = await client.get(f"{APPROVAL_URL}/{approval_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已升级"

    # 验证新审批记录已创建给 director1
    resp = await client.get(APPROVAL_URL, params={"order_id": order_id, "status": "待审批"})
    assert resp.status_code == 200
    pending = resp.json()
    assert len(pending) >= 1
    assert any(a["approver"] == "director1" for a in pending)
