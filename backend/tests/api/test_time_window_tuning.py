"""
时间窗口调参 API 集成测试
Story 26.4: 时间窗口自适应
"""

import pytest
import json
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.diagnosis import TimeWindowAdjustmentLog, DiagnosisResult, DiagnosisAnnotation
from app.models.config import SystemConfig
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.user import User, UserSession
from app.api.deps import get_db, require_admin, require_operator, require_viewer
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


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理测试数据
        await session.execute(delete(TimeWindowAdjustmentLog))
        await session.execute(delete(DiagnosisAnnotation))
        await session.execute(delete(DiagnosisResult))
        await session.execute(delete(Alarm))
        await session.execute(delete(Device))
        await session.execute(delete(SystemConfig))
        await session.execute(delete(UserSession))
        await session.execute(delete(User))
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
async def client(app, setup_test_data):
    headers = auth_headers(setup_test_data["token"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


@pytest.fixture
async def setup_test_data(db_session):
    """创建测试数据"""
    # 创建系统配置
    config = SystemConfig(
        config_group="diagnosis",
        config_key="diagnosis_time_windows",
        config_value='{"UPS": 5, "空调": 10, "配电柜": 3, "default": 5}',
        value_type="json",
        description="诊断时间窗口配置（分钟）"
    )
    db_session.add(config)

    # 创建管理员用户
    admin = User(
        id=1,
        username="admin",
        password_hash="$2b$12$test_hash",  # 测试用密码哈希
        email="admin@test.com",
        role="admin",
        is_active=True
    )
    db_session.add(admin)

    jti = uuid.uuid4().hex
    db_session.add(UserSession(user_id=admin.id, token_jti=jti, is_active=True))

    await db_session.commit()

    return {"config": config, "admin": admin, "token": _create_test_token(admin.username, jti)}


# ============================================================
# API 测试：查询调整记录
# ============================================================

@pytest.mark.asyncio
async def test_get_adjustments_list(client, db_session, setup_test_data):
    """测试查询调整记录列表"""
    # 创建测试调整记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending"
    )
    db_session.add(adjustment)
    await db_session.commit()

    # 调用 API
    response = await client.get("/api/v1/diagnosis/time-window-tuning/adjustments")

    # 验证响应
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["device_type"] == "UPS"
    assert data["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_adjustments_with_filter(client, db_session, setup_test_data):
    """测试带筛选条件的查询"""
    # 创建多条记录
    adjustments = [
        TimeWindowAdjustmentLog(
            device_type="UPS",
            current_window_minutes=5,
            proposed_window_minutes=6,
            adjustment_percent=20.0,
            sample_count=45,
            p50_duration_seconds=180.0,
            p90_duration_seconds=300.0,
            status="pending"
        ),
        TimeWindowAdjustmentLog(
            device_type="空调",
            current_window_minutes=10,
            proposed_window_minutes=120,
            adjustment_percent=1100.0,
            sample_count=50,
            p50_duration_seconds=3600.0,
            p90_duration_seconds=7200.0,
            status="approved"
        )
    ]
    for adj in adjustments:
        db_session.add(adj)
    await db_session.commit()

    # 筛选 pending 状态
    response = await client.get("/api/v1/diagnosis/time-window-tuning/adjustments?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "pending"

    # 筛选设备类型
    response = await client.get("/api/v1/diagnosis/time-window-tuning/adjustments?device_type=空调")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["device_type"] == "空调"


# ============================================================
# API 测试：审批流程
# ============================================================

@pytest.mark.asyncio
async def test_approve_adjustment(client, db_session, setup_test_data):
    """测试审批调整"""
    # 创建待审批记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending"
    )
    db_session.add(adjustment)
    await db_session.commit()
    await db_session.refresh(adjustment)

    # 调用审批 API
    response = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/approve",
        json={"reason": "测试审批"}
    )

    # 验证响应
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "时间窗口调整已审批，配置已更新"
    assert data["device_type"] == "UPS"
    assert data["new_window_minutes"] == 6

    # 验证数据库状态
    await db_session.refresh(adjustment)
    assert adjustment.status == "approved"
    assert adjustment.approved_by == 1
    assert adjustment.approved_at is not None

    # 验证配置已更新
    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    config_value = json.loads(config.config_value)
    assert config_value["UPS"] == 6


@pytest.mark.asyncio
async def test_reject_adjustment(client, db_session, setup_test_data):
    """测试拒绝调整"""
    # 创建待审批记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending"
    )
    db_session.add(adjustment)
    await db_session.commit()
    await db_session.refresh(adjustment)

    # 调用拒绝 API
    response = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/reject",
        json={"reason": "数据异常"}
    )

    # 验证响应
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "时间窗口调整已拒绝"

    # 验证数据库状态
    await db_session.refresh(adjustment)
    assert adjustment.status == "rejected"
    assert adjustment.reason == "数据异常"


# ============================================================
# API 测试：并发审批
# ============================================================

@pytest.mark.asyncio
async def test_concurrent_approval_conflict(client, db_session, setup_test_data):
    """测试用例 5: 并发审批场景"""
    # 创建待审批记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending",
        version=1
    )
    db_session.add(adjustment)
    await db_session.commit()
    await db_session.refresh(adjustment)

    # 第一次审批
    response1 = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/approve",
        json={"reason": "管理员A审批"}
    )
    assert response1.status_code == 200

    # 第二次审批（应该失败）
    response2 = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/approve",
        json={"reason": "管理员B审批"}
    )
    assert response2.status_code == 409  # Conflict
    assert "已被其他管理员" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_approve_and_reject_conflict(client, db_session, setup_test_data):
    """测试用例 6: 并发审批与拒绝冲突"""
    # 创建待审批记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending",
        version=1
    )
    db_session.add(adjustment)
    await db_session.commit()
    await db_session.refresh(adjustment)

    # 审批
    response1 = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/approve",
        json={"reason": "管理员A审批"}
    )
    assert response1.status_code == 200

    # 拒绝（应该失败）
    response2 = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/reject",
        json={"reason": "管理员B拒绝"}
    )
    assert response2.status_code == 409  # Conflict


# ============================================================
# API 测试：错误处理
# ============================================================

@pytest.mark.asyncio
async def test_approve_nonexistent_adjustment(client, db_session, setup_test_data):
    """测试审批不存在的记录"""
    response = await client.post(
        "/api/v1/diagnosis/time-window-tuning/adjustments/99999/approve",
        json={"reason": "测试"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_without_reason(client, db_session, setup_test_data):
    """测试拒绝时不提供理由"""
    # 创建待审批记录
    adjustment = TimeWindowAdjustmentLog(
        device_type="UPS",
        current_window_minutes=5,
        proposed_window_minutes=6,
        adjustment_percent=20.0,
        sample_count=45,
        p50_duration_seconds=180.0,
        p90_duration_seconds=300.0,
        status="pending"
    )
    db_session.add(adjustment)
    await db_session.commit()
    await db_session.refresh(adjustment)

    # 调用拒绝 API（不提供理由）
    response = await client.post(
        f"/api/v1/diagnosis/time-window-tuning/adjustments/{adjustment.id}/reject",
        json={}
    )
    # 空理由应被拒绝（Pydantic 验证：reason 为必填字段）
    assert response.status_code in (400, 422)
