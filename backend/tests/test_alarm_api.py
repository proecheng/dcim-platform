"""告警 API 测试 — Story 5.3"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.alarm import Alarm
from app.models.point import Point
from app.models.user import User
from app.api.deps import get_db, require_operator, require_viewer


# --------------- fixtures ---------------

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
        # 清理所有数据
        await session.execute(delete(Alarm))
        await session.execute(delete(Point))
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    """模拟操作员用户"""
    user = User()
    user.id = 1
    user.username = "testoperator"
    user.role = "operator"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_user):
    """创建测试 app，覆盖依赖"""
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_operator():
        return mock_user

    async def override_require_viewer():
        return mock_user

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer

    yield _app

    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_data(db_session):
    """创建测试点位和告警数据"""
    # 创建点位
    point = Point()
    point.id = 1
    point.point_code = "TH-A1-001"
    point.point_name = "A1区温度"
    point.point_type = "AI"
    point.device_type = "TH"
    db_session.add(point)

    point2 = Point()
    point2.id = 2
    point2.point_code = "UPS-A1-001"
    point2.point_name = "A1区UPS"
    point2.point_type = "AI"
    point2.device_type = "UPS"
    db_session.add(point2)

    # 创建告警
    alarm1 = Alarm()
    alarm1.id = 1
    alarm1.alarm_no = "ALM-20260216-001"
    alarm1.point_id = 1
    alarm1.alarm_level = "critical"
    alarm1.alarm_type = "threshold"
    alarm1.alarm_message = "温度超高"
    alarm1.trigger_value = 55.0
    alarm1.threshold_value = 50.0
    alarm1.status = "active"
    alarm1.created_at = datetime.now() - timedelta(hours=2)
    db_session.add(alarm1)

    alarm2 = Alarm()
    alarm2.id = 2
    alarm2.alarm_no = "ALM-20260216-002"
    alarm2.point_id = 1
    alarm2.alarm_level = "major"
    alarm2.alarm_type = "threshold"
    alarm2.alarm_message = "温度偏高"
    alarm2.trigger_value = 42.0
    alarm2.threshold_value = 40.0
    alarm2.status = "active"
    alarm2.created_at = datetime.now() - timedelta(hours=1)
    db_session.add(alarm2)

    alarm3 = Alarm()
    alarm3.id = 3
    alarm3.alarm_no = "ALM-20260216-003"
    alarm3.point_id = 2
    alarm3.alarm_level = "minor"
    alarm3.alarm_type = "threshold"
    alarm3.alarm_message = "UPS电压偏低"
    alarm3.trigger_value = 210.0
    alarm3.threshold_value = 220.0
    alarm3.status = "resolved"
    alarm3.resolved_by = 1
    alarm3.resolved_at = datetime.now()
    alarm3.duration_seconds = 3600
    alarm3.created_at = datetime.now() - timedelta(hours=3)
    db_session.add(alarm3)

    alarm4 = Alarm()
    alarm4.id = 4
    alarm4.alarm_no = "ALM-20260216-004"
    alarm4.point_id = 1
    alarm4.alarm_level = "critical"
    alarm4.alarm_type = "threshold"
    alarm4.alarm_message = "温度超高2"
    alarm4.status = "active"
    alarm4.created_at = datetime.now() - timedelta(minutes=30)
    db_session.add(alarm4)

    await db_session.commit()


# --------------- 确认告警测试 ---------------

class TestAcknowledgeAlarm:
    """测试确认告警 API"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_active_alarm(self, mock_broadcast, client, seed_data):
        """确认 active 告警应成功"""
        resp = await client.put("/api/v1/alarms/1/acknowledge", json={"remark": "已知晓"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "告警已确认"
        # 验证 WebSocket 广播
        mock_broadcast.assert_called_once()
        call_data = mock_broadcast.call_args[0][0]
        assert call_data["action"] == "ack"
        assert call_data["id"] == 1
        assert call_data["status"] == "acknowledged"

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_non_active_alarm(self, mock_broadcast, client, seed_data):
        """确认非 active 告警应返回 400"""
        # alarm 3 is resolved
        resp = await client.put("/api/v1/alarms/3/acknowledge", json={"remark": "test"})
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_nonexistent_alarm(self, mock_broadcast, client, seed_data):
        """确认不存在的告警应返回 404"""
        resp = await client.put("/api/v1/alarms/999/acknowledge", json={"remark": "test"})
        assert resp.status_code == 404


# --------------- 处理告警测试 ---------------

class TestProcessAlarm:
    """测试处理告警 API"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_active_alarm(self, mock_broadcast, client, seed_data):
        """处理 active 告警应成功"""
        resp = await client.put("/api/v1/alarms/2/process", json={"process_remark": "正在排查原因"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "告警处理记录已保存"
        # 验证 WebSocket 广播
        mock_broadcast.assert_called_once()
        call_data = mock_broadcast.call_args[0][0]
        assert call_data["action"] == "update"
        assert call_data["id"] == 2
        assert call_data["process_remark"] == "正在排查原因"

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_resolved_alarm(self, mock_broadcast, client, seed_data):
        """处理 resolved 告警应返回 400"""
        resp = await client.put("/api/v1/alarms/3/process", json={"process_remark": "test"})
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_nonexistent_alarm(self, mock_broadcast, client, seed_data):
        """处理不存在的告警应返回 404"""
        resp = await client.put("/api/v1/alarms/999/process", json={"process_remark": "test"})
        assert resp.status_code == 404

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_without_remark(self, mock_broadcast, client, seed_data):
        """处理告警缺少 process_remark 应返回 422"""
        resp = await client.put("/api/v1/alarms/2/process", json={})
        assert resp.status_code == 422


# --------------- 解决告警测试 ---------------

class TestResolveAlarm:
    """测试解决告警 API"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_active_alarm(self, mock_broadcast, client, seed_data):
        """解决 active 告警应成功"""
        resp = await client.put("/api/v1/alarms/4/resolve", json={"remark": "已修复", "resolve_type": "manual"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "告警已解决"
        # 验证 WebSocket 广播
        mock_broadcast.assert_called_once()
        call_data = mock_broadcast.call_args[0][0]
        assert call_data["action"] == "resolve"
        assert call_data["id"] == 4
        assert call_data["status"] == "resolved"
        assert "duration_seconds" in call_data

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_already_resolved(self, mock_broadcast, client, seed_data):
        """解决已解决的告警应返回 400"""
        resp = await client.put("/api/v1/alarms/3/resolve", json={"remark": "test"})
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_nonexistent_alarm(self, mock_broadcast, client, seed_data):
        """解决不存在的告警应返回 404"""
        resp = await client.put("/api/v1/alarms/999/resolve", json={"remark": "test"})
        assert resp.status_code == 404


# --------------- 批量确认测试 ---------------

class TestBatchAcknowledge:
    """测试批量确认告警 API"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_acknowledge(self, mock_broadcast, client, seed_data):
        """批量确认 active 告警应成功"""
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            json={"alarm_ids": [1, 2], "remark": "批量确认"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert data["count"] >= 0
        # 验证 WebSocket 广播
        mock_broadcast.assert_called_once()
        call_data = mock_broadcast.call_args[0][0]
        assert call_data["action"] == "batch_ack"
        assert call_data["alarm_ids"] == [1, 2]

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_acknowledge_resolved_alarms(self, mock_broadcast, client, seed_data):
        """批量确认已解决的告警应返回 count=0"""
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            json={"alarm_ids": [3]}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0


# --------------- 统计测试 ---------------

class TestAlarmStatistics:
    """测试告警统计 API"""

    async def test_statistics_default(self, client, seed_data):
        """默认统计应返回所有告警"""
        resp = await client.get("/api/v1/alarms/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_level" in data
        assert "by_status" in data
        assert "by_device_type" in data
        assert data["total"] >= 0

    async def test_statistics_by_device_type(self, client, seed_data):
        """按设备类型筛选统计"""
        resp = await client.get("/api/v1/alarms/statistics?device_type=TH")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_device_type" in data

    async def test_statistics_by_alarm_level(self, client, seed_data):
        """按告警级别筛选统计"""
        resp = await client.get("/api/v1/alarms/statistics?alarm_level=critical")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data

    async def test_statistics_has_device_type_breakdown(self, client, seed_data):
        """统计结果应包含设备类型分组"""
        resp = await client.get("/api/v1/alarms/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["by_device_type"], dict)
