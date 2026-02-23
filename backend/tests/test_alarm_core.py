"""
告警管理 API 核心测试
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.models.alarm import Alarm
from app.models.point import Point
from tests.conftest import auth_headers


@pytest.fixture
async def sample_point(async_db):
    """创建测试点位"""
    point = Point(
        point_code="TH-A1-001",
        point_name="A1区温度",
        point_type="AI",
        device_type="TH",
        unit="℃",
    )
    async_db.add(point)
    await async_db.flush()
    return point


@pytest.fixture
async def sample_alarm(async_db, sample_point):
    """创建测试告警"""
    alarm = Alarm(
        alarm_no="ALM-20260101-001",
        point_id=sample_point.id,
        alarm_level="major",
        alarm_type="threshold",
        alarm_message="温度超高",
        trigger_value=35.5,
        threshold_value=30.0,
        status="active",
    )
    async_db.add(alarm)
    await async_db.flush()
    return alarm


class TestAlarmList:
    """告警列表测试"""

    async def test_get_alarms_empty(self, client, admin_user):
        """测试空告警列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_get_alarms_with_data(self, client, admin_user, sample_alarm):
        """测试有数据的告警列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert len(body["items"]) >= 1
        assert body["items"][0]["alarm_no"] == "ALM-20260101-001"

    async def test_get_alarms_filter_status(self, client, admin_user, sample_alarm):
        """测试按状态筛选"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms?status=active", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        resp2 = await client.get("/api/v1/alarms?status=resolved", headers=auth_headers(token))
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 0

    async def test_get_alarms_filter_level(self, client, admin_user, sample_alarm):
        """测试按级别筛选"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms?level=major", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_alarms_unauthorized(self, client):
        """测试未认证访问"""
        resp = await client.get("/api/v1/alarms")
        assert resp.status_code == 401


class TestAlarmDetail:
    """告警详情测试"""

    async def test_get_alarm_detail(self, client, admin_user, sample_alarm):
        """测试获取告警详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/alarms/{sample_alarm.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["alarm_no"] == "ALM-20260101-001"
        assert body["alarm_level"] == "major"

    async def test_get_alarm_not_found(self, client, admin_user):
        """测试告警不存在"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestAlarmAcknowledge:
    """告警确认测试"""

    @patch("app.services.websocket.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_alarm(self, mock_broadcast, client, admin_user, sample_alarm):
        """测试确认告警"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/alarms/{sample_alarm.id}/acknowledge",
            headers=auth_headers(token),
            json={"remark": "已确认处理"},
        )
        assert resp.status_code == 200
        assert "已确认" in resp.json()["message"]
        mock_broadcast.assert_called_once()

    @patch("app.services.websocket.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_already_acknowledged(self, mock_broadcast, client, admin_user, async_db, sample_point):
        """测试重复确认"""
        _, token = admin_user
        alarm = Alarm(
            alarm_no="ALM-ACK-DUP",
            point_id=sample_point.id,
            alarm_level="minor",
            alarm_type="threshold",
            alarm_message="重复确认测试",
            status="acknowledged",
        )
        async_db.add(alarm)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/alarms/{alarm.id}/acknowledge",
            headers=auth_headers(token),
            json={"remark": "再次确认"},
        )
        assert resp.status_code == 400


class TestAlarmResolve:
    """告警解决测试"""

    @patch("app.services.websocket.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_alarm(self, mock_broadcast, client, admin_user, sample_alarm):
        """测试解决告警"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/alarms/{sample_alarm.id}/resolve",
            headers=auth_headers(token),
            json={"remark": "已修复", "resolve_type": "manual"},
        )
        assert resp.status_code == 200
        assert "已解决" in resp.json()["message"]
        mock_broadcast.assert_called_once()

    @patch("app.services.websocket.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_already_resolved(self, mock_broadcast, client, admin_user, async_db, sample_point):
        """测试重复解决"""
        _, token = admin_user
        alarm = Alarm(
            alarm_no="ALM-RES-DUP",
            point_id=sample_point.id,
            alarm_level="minor",
            alarm_type="threshold",
            alarm_message="重复解决测试",
            status="resolved",
        )
        async_db.add(alarm)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/alarms/{alarm.id}/resolve",
            headers=auth_headers(token),
            json={"remark": "再次解决"},
        )
        assert resp.status_code == 400


class TestAlarmCount:
    """告警计数测试"""

    async def test_get_alarm_count(self, client, admin_user, sample_alarm):
        """测试获取告警计数"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms/count", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "critical" in body
        assert "major" in body
        assert "total" in body
        assert body["total"] >= 1


class TestAlarmStatistics:
    """告警统计测试"""

    async def test_get_alarm_statistics(self, client, admin_user, sample_alarm):
        """测试获取告警统计"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "by_level" in body
        assert "by_status" in body


class TestAlarmActiveList:
    """活动告警测试"""

    async def test_get_active_alarms(self, client, admin_user, sample_alarm):
        """测试获取活动告警"""
        _, token = admin_user
        resp = await client.get("/api/v1/alarms/active", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1


class TestBatchAcknowledge:
    """批量确认测试"""

    @patch("app.services.websocket.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_acknowledge(self, mock_broadcast, client, admin_user, sample_alarm):
        """测试批量确认告警"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            headers=auth_headers(token),
            json={"alarm_ids": [sample_alarm.id], "remark": "批量确认"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
