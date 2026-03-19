"""
Story 34.7 — 通知记录查询 API 测试
"""

from datetime import datetime

import pytest
from tests.conftest import auth_headers

from app.models.alarm import Alarm
from app.models.notification_record import NotificationRecord


# ==================== Fixtures ====================


@pytest.fixture
async def sample_records(async_db, admin_user):
    """创建测试通知记录（含关联告警）"""
    user, _ = admin_user

    # 创建告警（用于 outerjoin）
    alarm1 = Alarm(
        alarm_no="ALM-TEST-001",
        point_id=1,
        alarm_level="critical",
        alarm_message="温度超限",
        status="active",
    )
    alarm2 = Alarm(
        alarm_no="ALM-TEST-002",
        point_id=2,
        alarm_level="major",
        alarm_message="湿度超限",
        status="active",
    )
    async_db.add_all([alarm1, alarm2])
    await async_db.flush()

    # 创建通知记录
    records = [
        NotificationRecord(
            alarm_id=alarm1.id,
            user_id=user.id,
            policy_id=1,
            channel_type="email",
            contact_value="admin@test.com",
            content_summary="温度超限通知",
            status="sent",
            sent_at=datetime(2026, 3, 19, 10, 0, 0),
            created_at=datetime(2026, 3, 19, 10, 0, 0),
        ),
        NotificationRecord(
            alarm_id=alarm2.id,
            user_id=user.id,
            policy_id=1,
            channel_type="im",
            platform="dingtalk",
            contact_value="钉钉群",
            content_summary="湿度超限通知",
            status="sent",
            sent_at=datetime(2026, 3, 19, 11, 0, 0),
            created_at=datetime(2026, 3, 19, 11, 0, 0),
        ),
        NotificationRecord(
            alarm_id=alarm1.id,
            user_id=user.id,
            policy_id=1,
            channel_type="sms",
            contact_value="13800138000",
            content_summary="温度超限短信",
            status="failed",
            error_message="短信服务不可用",
            created_at=datetime(2026, 3, 19, 12, 0, 0),
        ),
        # 无关联告警的记录
        NotificationRecord(
            alarm_id=None,
            user_id=user.id,
            policy_id=None,
            channel_type="email",
            contact_value="admin@test.com",
            content_summary="系统测试通知",
            status="sent",
            sent_at=datetime(2026, 3, 19, 13, 0, 0),
            created_at=datetime(2026, 3, 19, 13, 0, 0),
        ),
    ]
    async_db.add_all(records)
    await async_db.flush()

    return records


# ==================== 基础查询测试 ====================


class TestListNotificationRecords:

    async def test_list_records_basic(self, client, admin_token, sample_records):
        """基础分页查询"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_list_records_pagination(self, client, admin_token, sample_records):
        """分页参数生效"""
        resp = await client.get(
            "/api/v1/notification/records?page=1&page_size=2",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 2

    async def test_list_records_page2(self, client, admin_token, sample_records):
        """第二页数据"""
        resp = await client.get(
            "/api/v1/notification/records?page=2&page_size=2",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2

    async def test_list_records_ordered_desc(self, client, admin_token, sample_records):
        """按 ID 降序排列"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids, reverse=True)


# ==================== 筛选测试 ====================


class TestRecordFilters:

    async def test_filter_by_channel_type(self, client, admin_token, sample_records):
        """按渠道类型筛选"""
        resp = await client.get(
            "/api/v1/notification/records?channel_type=email",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(item["channel_type"] == "email" for item in data["items"])

    async def test_filter_by_status(self, client, admin_token, sample_records):
        """按发送状态筛选"""
        resp = await client.get(
            "/api/v1/notification/records?status=failed",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "failed"

    async def test_filter_by_alarm_level(self, client, admin_token, sample_records):
        """按告警级别筛选（通过 JOIN Alarm 表）"""
        resp = await client.get(
            "/api/v1/notification/records?alarm_level=critical",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["total"] == 2  # alarm1 关联的两条记录
        assert all(item["alarm_level"] == "critical" for item in data["items"])

    async def test_filter_by_time_range(self, client, admin_token, sample_records):
        """按时间范围筛选"""
        resp = await client.get(
            "/api/v1/notification/records?start_time=2026-03-19T11:00:00&end_time=2026-03-19T12:30:00",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["total"] == 2  # 11:00 和 12:00 的记录

    async def test_filter_combined(self, client, admin_token, sample_records):
        """组合筛选"""
        resp = await client.get(
            "/api/v1/notification/records?channel_type=email&status=sent",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["total"] == 2


# ==================== alarm_level JOIN 测试 ====================


class TestAlarmLevelJoin:

    async def test_alarm_level_from_join(self, client, admin_token, sample_records):
        """alarm_level 通过 outerjoin 正确获取"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        # 找到无告警关联的记录
        no_alarm = [i for i in data["items"] if i["alarm_id"] is None]
        assert len(no_alarm) == 1
        assert no_alarm[0]["alarm_level"] is None

        # 找到有告警关联的记录
        with_alarm = [i for i in data["items"] if i["alarm_id"] is not None]
        assert all(i["alarm_level"] in ("critical", "major") for i in with_alarm)


# ==================== 权限测试 ====================


class TestRecordPermissions:

    async def test_viewer_can_access(self, client, viewer_token, sample_records):
        """viewer 角色可查看通知记录"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(viewer_token),
        )
        assert resp.status_code == 200

    async def test_operator_can_access(self, client, operator_token, sample_records):
        """operator 角色可查看通知记录"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 200

    async def test_unauthenticated_rejected(self, client, sample_records):
        """未认证用户被拒绝"""
        resp = await client.get("/api/v1/notification/records")
        assert resp.status_code == 401


# ==================== 空数据测试 ====================


class TestRecordEmptyData:

    async def test_empty_result(self, client, admin_token):
        """无记录时返回空列表"""
        resp = await client.get(
            "/api/v1/notification/records",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
