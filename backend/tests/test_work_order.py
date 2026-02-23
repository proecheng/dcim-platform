"""工单管理 API 测试 — 工单全生命周期"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.operation import WorkOrder, WorkOrderLog
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
# Constants & Helpers
# ============================================================

BASE_URL = "/api/v1/operation/workorders"

WORK_ORDER_PAYLOAD = {
    "title": "测试工单",
    "description": "测试工单描述",
    "order_type": "故障报修",
    "priority": "高",
}


async def _create_work_order(client: AsyncClient) -> dict:
    """通过 API 创建一个工单并返回响应 JSON"""
    resp = await client.post(BASE_URL, json=WORK_ORDER_PAYLOAD)
    assert resp.status_code == 200
    return resp.json()


async def _advance_to_processing(client: AsyncClient, order_id: int) -> None:
    """将工单推进到 processing 状态: assign → accept → start"""
    resp = await client.post(f"{BASE_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    assert resp.status_code == 200
    resp = await client.post(f"{BASE_URL}/{order_id}/accept")
    assert resp.status_code == 200
    resp = await client.post(f"{BASE_URL}/{order_id}/start")
    assert resp.status_code == 200


# ============================================================
# Tests
# ============================================================


@pytest.mark.anyio
async def test_create_work_order(client):
    """POST /workorders 创建工单，验证 order_no 和 status"""
    data = await _create_work_order(client)
    assert data["order_no"].startswith("WO-")
    assert data["status"] == "待处理"
    assert data["title"] == "测试工单"
    assert data["priority"] == "高"
    assert data["order_type"] == "故障报修"
    assert "id" in data


@pytest.mark.anyio
async def test_create_work_order_with_assignee(client):
    """POST /workorders 带 assignee 字段，状态仍为 pending（create 不自动派单）"""
    payload = {**WORK_ORDER_PAYLOAD, "title": "带处理人工单"}
    resp = await client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # WorkOrderCreate 不含 assignee 字段，所以 assignee 为 None，status 为 pending
    assert data["status"] == "待处理"
    assert data["assignee"] is None


@pytest.mark.anyio
async def test_list_work_orders(client):
    """GET /workorders 返回列表"""
    await _create_work_order(client)
    resp = await client.get(BASE_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_list_work_orders_filter_status(client):
    """GET /workorders?status=pending 按状态过滤"""
    await _create_work_order(client)
    resp = await client.get(BASE_URL, params={"status": "待处理"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for order in data:
        assert order["status"] == "待处理"


@pytest.mark.anyio
async def test_list_work_orders_filter_priority(client):
    """GET /workorders?priority=high 按优先级过滤"""
    await _create_work_order(client)
    resp = await client.get(BASE_URL, params={"priority": "高"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for order in data:
        assert order["priority"] == "高"


@pytest.mark.anyio
async def test_get_work_order_detail(client):
    """GET /workorders/{id} 获取工单详情"""
    created = await _create_work_order(client)
    order_id = created["id"]

    resp = await client.get(f"{BASE_URL}/{order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == order_id
    assert data["order_no"] == created["order_no"]
    assert data["title"] == "测试工单"
    assert data["status"] == "待处理"
    assert data["created_at"] is not None


@pytest.mark.anyio
async def test_get_work_order_not_found(client):
    """GET /workorders/99999 不存在返回 404"""
    resp = await client.get(f"{BASE_URL}/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_assign_work_order(client):
    """POST /workorders/{id}/assign 派单，验证 status=assigned"""
    created = await _create_work_order(client)
    order_id = created["id"]

    resp = await client.post(f"{BASE_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已派单"
    assert data["assignee"] == "engineer1"
    assert data["assigned_at"] is not None


@pytest.mark.anyio
async def test_accept_work_order(client):
    """POST /workorders/{id}/accept 接单，验证 status=accepted"""
    created = await _create_work_order(client)
    order_id = created["id"]

    # 先派单
    resp = await client.post(f"{BASE_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    assert resp.status_code == 200

    resp = await client.post(f"{BASE_URL}/{order_id}/accept")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已接单"
    assert data["accepted_at"] is not None


@pytest.mark.anyio
async def test_start_work_order(client):
    """POST /workorders/{id}/start 开始处理，验证 status=processing"""
    created = await _create_work_order(client)
    order_id = created["id"]

    # assign → accept → start
    await client.post(f"{BASE_URL}/{order_id}/assign", json={"assignee": "engineer1"})
    await client.post(f"{BASE_URL}/{order_id}/accept")

    resp = await client.post(f"{BASE_URL}/{order_id}/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "处理中"
    assert data["started_at"] is not None


@pytest.mark.anyio
async def test_complete_work_order(client):
    """完整生命周期: create→assign→accept→start→complete"""
    created = await _create_work_order(client)
    order_id = created["id"]

    await _advance_to_processing(client, order_id)

    resp = await client.post(f"{BASE_URL}/{order_id}/complete", json={"solution": "fixed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已完成"
    assert data["solution"] == "fixed"
    assert data["completed_at"] is not None


@pytest.mark.anyio
async def test_close_work_order(client):
    """完整生命周期: create→assign→accept→start→complete→close"""
    created = await _create_work_order(client)
    order_id = created["id"]

    await _advance_to_processing(client, order_id)

    resp = await client.post(f"{BASE_URL}/{order_id}/complete", json={"solution": "fixed"})
    assert resp.status_code == 200

    resp = await client.post(f"{BASE_URL}/{order_id}/close")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已关闭"
    assert data["closed_at"] is not None


@pytest.mark.anyio
async def test_invalid_status_transition(client):
    """pending 状态直接 start 应返回 400（必须先 assign→accept）"""
    created = await _create_work_order(client)
    order_id = created["id"]

    resp = await client.post(f"{BASE_URL}/{order_id}/start")
    assert resp.status_code == 400
