"""巡检计划与任务 API 测试 — 巡检全生命周期"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.operation import InspectionPlan, InspectionTask
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
        await session.execute(delete(InspectionTask))
        await session.execute(delete(InspectionPlan))
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

PLANS_URL = "/api/v1/operation/plans"
TASKS_URL = "/api/v1/operation/tasks"

PLAN_PAYLOAD = {
    "name": "测试巡检计划",
    "description": "每日机房巡检",
    "frequency": "daily",
    "location": "A栋机房",
    "assignee": "张三",
    "is_active": True,
}


async def _create_plan(client: AsyncClient) -> dict:
    """通过 API 创建一个巡检计划并返回响应 JSON"""
    resp = await client.post(PLANS_URL, json=PLAN_PAYLOAD)
    assert resp.status_code == 200
    return resp.json()


async def _create_task(client: AsyncClient, plan_id: int) -> dict:
    """通过 API 创建一个巡检任务并返回响应 JSON"""
    payload = {"plan_id": plan_id, "assignee": "张三"}
    resp = await client.post(TASKS_URL, json=payload)
    assert resp.status_code == 200
    return resp.json()


# ============================================================
# 巡检计划测试
# ============================================================


@pytest.mark.anyio
async def test_create_plan(client):
    """POST /plans 创建巡检计划，验证 name 和 is_active"""
    data = await _create_plan(client)
    assert data["name"] == "测试巡检计划"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.anyio
async def test_list_plans(client):
    """GET /plans 返回列表"""
    await _create_plan(client)
    resp = await client.get(PLANS_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_list_plans_filter_active(client):
    """GET /plans?is_active=true 按启用状态过滤"""
    await _create_plan(client)
    resp = await client.get(PLANS_URL, params={"is_active": True})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for plan in data:
        assert plan["is_active"] is True


@pytest.mark.anyio
async def test_list_plans_filter_name(client):
    """GET /plans?name=测试 按名称搜索"""
    await _create_plan(client)
    resp = await client.get(PLANS_URL, params={"name": "测试"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for plan in data:
        assert "测试" in plan["name"]


@pytest.mark.anyio
async def test_get_plan_detail(client):
    """GET /plans/{id} 获取巡检计划详情"""
    created = await _create_plan(client)
    plan_id = created["id"]

    resp = await client.get(f"{PLANS_URL}/{plan_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == plan_id
    assert data["name"] == "测试巡检计划"
    assert data["created_at"] is not None


@pytest.mark.anyio
async def test_update_plan(client):
    """PUT /plans/{id} 更新巡检计划名称"""
    created = await _create_plan(client)
    plan_id = created["id"]

    resp = await client.put(f"{PLANS_URL}/{plan_id}", json={"name": "更新后的计划"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新后的计划"


@pytest.mark.anyio
async def test_delete_plan(client):
    """DELETE /plans/{id} 删除巡检计划，再 GET 返回 404"""
    created = await _create_plan(client)
    plan_id = created["id"]

    resp = await client.delete(f"{PLANS_URL}/{plan_id}")
    assert resp.status_code == 200

    resp = await client.get(f"{PLANS_URL}/{plan_id}")
    assert resp.status_code == 404


# ============================================================
# 巡检任务测试
# ============================================================


@pytest.mark.anyio
async def test_create_task(client):
    """POST /tasks 创建巡检任务，验证 task_no 和 status"""
    plan = await _create_plan(client)
    data = await _create_task(client, plan["id"])
    assert data["task_no"].startswith("IT-")
    assert data["status"] == "待巡检"
    assert "id" in data


@pytest.mark.anyio
async def test_list_tasks(client):
    """GET /tasks 返回列表"""
    plan = await _create_plan(client)
    await _create_task(client, plan["id"])
    resp = await client.get(TASKS_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_list_tasks_filter_status(client):
    """GET /tasks?status=待巡检 按状态过滤"""
    plan = await _create_plan(client)
    await _create_task(client, plan["id"])
    resp = await client.get(TASKS_URL, params={"status": "待巡检"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for task in data:
        assert task["status"] == "待巡检"


@pytest.mark.anyio
async def test_list_tasks_filter_plan_id(client):
    """GET /tasks?plan_id={plan_id} 按计划ID过滤"""
    plan = await _create_plan(client)
    await _create_task(client, plan["id"])
    resp = await client.get(TASKS_URL, params={"plan_id": plan["id"]})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for task in data:
        assert task["plan_id"] == plan["id"]


@pytest.mark.anyio
async def test_start_task(client):
    """POST /tasks/{id}/start 开始巡检，验证 status 和 started_at"""
    plan = await _create_plan(client)
    task = await _create_task(client, plan["id"])
    task_id = task["id"]

    resp = await client.post(f"{TASKS_URL}/{task_id}/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "巡检中"
    assert data["started_at"] is not None


@pytest.mark.anyio
async def test_start_task_invalid_status(client):
    """已开始的任务再次 start 应返回 400"""
    plan = await _create_plan(client)
    task = await _create_task(client, plan["id"])
    task_id = task["id"]

    # 先开始
    resp = await client.post(f"{TASKS_URL}/{task_id}/start")
    assert resp.status_code == 200

    # 再次开始应失败
    resp = await client.post(f"{TASKS_URL}/{task_id}/start")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_complete_task(client):
    """先 start 再 complete，验证 status 和 result"""
    plan = await _create_plan(client)
    task = await _create_task(client, plan["id"])
    task_id = task["id"]

    # 先开始
    resp = await client.post(f"{TASKS_URL}/{task_id}/start")
    assert resp.status_code == 200

    # 完成
    resp = await client.post(
        f"{TASKS_URL}/{task_id}/complete",
        json={"result": "一切正常", "abnormal_count": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "已完成"
    assert data["result"] == "一切正常"
    assert data["abnormal_count"] == 0
    assert data["completed_at"] is not None


@pytest.mark.anyio
async def test_complete_task_invalid_status(client):
    """待巡检状态直接 complete 应返回 400（必须先 start）"""
    plan = await _create_plan(client)
    task = await _create_task(client, plan["id"])
    task_id = task["id"]

    resp = await client.post(
        f"{TASKS_URL}/{task_id}/complete",
        json={"result": "一切正常", "abnormal_count": 0},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_generate_task_from_plan(client):
    """POST /plans/{id}/generate-tasks 从计划生成任务"""
    plan = await _create_plan(client)
    plan_id = plan["id"]

    resp = await client.post(f"{PLANS_URL}/{plan_id}/generate-tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_no"].startswith("IT-")
    assert data["assignee"] == "张三"
    assert data["plan_name"] == "测试巡检计划"
    assert data["plan_id"] == plan_id


@pytest.mark.anyio
async def test_delete_task(client):
    """DELETE /tasks/{id} 删除巡检任务，再 GET 返回 404"""
    plan = await _create_plan(client)
    task = await _create_task(client, plan["id"])
    task_id = task["id"]

    resp = await client.delete(f"{TASKS_URL}/{task_id}")
    assert resp.status_code == 200

    resp = await client.get(f"{TASKS_URL}/{task_id}")
    assert resp.status_code == 404
