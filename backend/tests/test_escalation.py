"""告警升级规则与引擎测试 — Story 5-5"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, select

from app.core.database import Base
from app.models.alarm import Alarm, AlarmEscalation
from app.models.point import Point
from app.models.user import User
from app.api.deps import get_db, require_viewer, require_operator
from app.engines.escalation_engine import check_escalations


# ==================== fixtures ====================


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
        await session.execute(delete(Alarm))
        await session.execute(delete(AlarmEscalation))
        await session.execute(delete(Point))
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    user = User()
    user.id = 1
    user.username = "testoperator"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_user):
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
async def seed_point(db_session):
    """创建测试点位"""
    point = Point()
    point.id = 1
    point.point_code = "TH-A1-001"
    point.point_name = "A1区温度"
    point.point_type = "AI"
    point.device_type = "TH"
    db_session.add(point)
    await db_session.commit()


# ==================== CRUD API 测试 ====================


class TestEscalationCRUD:
    """升级规则 CRUD 测试"""

    async def test_create_escalation(self, client):
        """创建升级规则"""
        resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "次要升重要",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
                "notify_user_ids": [1, 2],
                "description": "次要告警30分钟未处理升级为重要",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "次要升重要"
        assert data["source_level"] == "minor"
        assert data["timeout_minutes"] == 30
        assert data["target_level"] == "major"
        assert data["notify_user_ids"] == [1, 2]
        assert data["is_enabled"] is True
        assert data["id"] > 0

    async def test_list_escalations(self, client):
        """列表查询"""
        # 先创建一条
        await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "重要升紧急",
                "source_level": "major",
                "timeout_minutes": 15,
                "target_level": "critical",
            },
        )
        resp = await client.get("/api/v1/escalations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_filter_source_level(self, client):
        """按源级别过滤"""
        # 创建两条不同级别
        await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "r1",
                "source_level": "info",
                "timeout_minutes": 60,
                "target_level": "minor",
            },
        )
        await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "r2",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
            },
        )
        resp = await client.get("/api/v1/escalations?source_level=info")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source_level"] == "info"

    async def test_get_escalation(self, client):
        """获取详情"""
        create_resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "详情测试",
                "source_level": "minor",
                "timeout_minutes": 20,
                "target_level": "major",
            },
        )
        eid = create_resp.json()["id"]
        resp = await client.get(f"/api/v1/escalations/{eid}")
        assert resp.status_code == 200
        assert resp.json()["rule_name"] == "详情测试"

    async def test_get_nonexistent(self, client):
        """获取不存在的规则"""
        resp = await client.get("/api/v1/escalations/99999")
        assert resp.status_code == 404

    async def test_update_escalation(self, client):
        """更新规则"""
        create_resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "待更新",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
            },
        )
        eid = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/escalations/{eid}",
            json={
                "rule_name": "已更新",
                "timeout_minutes": 45,
                "notify_user_ids": [3, 4],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "已更新"
        assert data["timeout_minutes"] == 45
        assert data["notify_user_ids"] == [3, 4]

    async def test_delete_escalation(self, client):
        """删除规则"""
        create_resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "待删除",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
            },
        )
        eid = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/escalations/{eid}")
        assert resp.status_code == 200
        # 确认已删除
        resp2 = await client.get(f"/api/v1/escalations/{eid}")
        assert resp2.status_code == 404

    async def test_toggle_escalation(self, client):
        """切换启用状态"""
        create_resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "切换测试",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
            },
        )
        eid = create_resp.json()["id"]
        assert create_resp.json()["is_enabled"] is True

        resp = await client.put(f"/api/v1/escalations/{eid}/toggle")
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

        resp2 = await client.put(f"/api/v1/escalations/{eid}/toggle")
        assert resp2.status_code == 200
        assert resp2.json()["is_enabled"] is True


# ==================== 升级引擎测试 ====================


class TestEscalationEngine:
    """升级引擎测试"""

    @patch("app.engines.escalation_engine.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_timed_out_alarm_gets_escalated(self, mock_broadcast, db_session, seed_point):
        """超时告警应被升级"""
        # 创建启用的升级规则
        rule = AlarmEscalation()
        rule.rule_name = "minor升major"
        rule.source_level = "minor"
        rule.timeout_minutes = 10
        rule.target_level = "major"
        rule.is_enabled = True
        db_session.add(rule)

        # 创建超时的 active 告警
        alarm = Alarm()
        alarm.alarm_no = "ALM-ESC-001"
        alarm.point_id = 1
        alarm.alarm_level = "minor"
        alarm.alarm_type = "threshold"
        alarm.alarm_message = "温度偏高"
        alarm.status = "active"
        alarm.escalation_count = 0
        alarm.created_at = datetime.now() - timedelta(minutes=20)
        db_session.add(alarm)
        await db_session.commit()

        await check_escalations(db_session)

        # 验证告警已升级
        result = await db_session.execute(select(Alarm).where(Alarm.alarm_no == "ALM-ESC-001"))
        updated = result.scalar_one()
        assert updated.alarm_level == "major"
        assert updated.escalated_from == "minor"
        assert updated.escalation_count == 1
        assert "自动升级" in updated.escalation_remark

        # 验证 WebSocket 广播
        mock_broadcast.assert_called_once()
        call_data = mock_broadcast.call_args[0][0]
        assert call_data["action"] == "escalate"
        assert call_data["alarm_level"] == "major"
        assert call_data["previous_level"] == "minor"

    @patch("app.engines.escalation_engine.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_non_timed_out_alarm_not_escalated(self, mock_broadcast, db_session, seed_point):
        """未超时告警不应被升级"""
        rule = AlarmEscalation()
        rule.rule_name = "minor升major"
        rule.source_level = "minor"
        rule.timeout_minutes = 30
        rule.target_level = "major"
        rule.is_enabled = True
        db_session.add(rule)

        alarm = Alarm()
        alarm.alarm_no = "ALM-ESC-002"
        alarm.point_id = 1
        alarm.alarm_level = "minor"
        alarm.alarm_type = "threshold"
        alarm.alarm_message = "温度偏高"
        alarm.status = "active"
        alarm.escalation_count = 0
        alarm.created_at = datetime.now() - timedelta(minutes=5)  # 只过了5分钟
        db_session.add(alarm)
        await db_session.commit()

        await check_escalations(db_session)

        result = await db_session.execute(select(Alarm).where(Alarm.alarm_no == "ALM-ESC-002"))
        updated = result.scalar_one()
        assert updated.alarm_level == "minor"  # 未变
        assert updated.escalation_count == 0
        mock_broadcast.assert_not_called()

    @patch("app.engines.escalation_engine.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_different_level_not_matched(self, mock_broadcast, db_session, seed_point):
        """已升级到不同级别的告警不会被同规则再次匹配"""
        rule = AlarmEscalation()
        rule.rule_name = "minor升major"
        rule.source_level = "minor"
        rule.timeout_minutes = 10
        rule.target_level = "major"
        rule.is_enabled = True
        db_session.add(rule)

        # 告警已经是 major 级别（之前已被升级过）
        alarm = Alarm()
        alarm.alarm_no = "ALM-ESC-003"
        alarm.point_id = 1
        alarm.alarm_level = "major"  # 已经不是 minor 了
        alarm.alarm_type = "threshold"
        alarm.alarm_message = "温度偏高"
        alarm.status = "active"
        alarm.escalation_count = 1
        alarm.escalated_from = "minor"
        alarm.created_at = datetime.now() - timedelta(minutes=20)
        db_session.add(alarm)
        await db_session.commit()

        await check_escalations(db_session)

        result = await db_session.execute(select(Alarm).where(Alarm.alarm_no == "ALM-ESC-003"))
        updated = result.scalar_one()
        assert updated.alarm_level == "major"  # 未变
        assert updated.escalation_count == 1  # 未增加
        mock_broadcast.assert_not_called()

    @patch("app.engines.escalation_engine.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_disabled_rule_not_fired(self, mock_broadcast, db_session, seed_point):
        """禁用的规则不应触发升级"""
        rule = AlarmEscalation()
        rule.rule_name = "禁用规则"
        rule.source_level = "minor"
        rule.timeout_minutes = 10
        rule.target_level = "major"
        rule.is_enabled = False  # 禁用
        db_session.add(rule)

        alarm = Alarm()
        alarm.alarm_no = "ALM-ESC-004"
        alarm.point_id = 1
        alarm.alarm_level = "minor"
        alarm.alarm_type = "threshold"
        alarm.alarm_message = "温度偏高"
        alarm.status = "active"
        alarm.escalation_count = 0
        alarm.created_at = datetime.now() - timedelta(minutes=20)
        db_session.add(alarm)
        await db_session.commit()

        await check_escalations(db_session)

        result = await db_session.execute(select(Alarm).where(Alarm.alarm_no == "ALM-ESC-004"))
        updated = result.scalar_one()
        assert updated.alarm_level == "minor"  # 未变
        assert updated.escalation_count == 0
        mock_broadcast.assert_not_called()
