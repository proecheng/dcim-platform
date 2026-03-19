"""
Story 34.4 — 通知分发器与告警引擎集成测试
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notification.dispatcher import NotificationDispatcher


# ==================== _to_minutes / _is_time_in_range 测试 ====================


class TestToMinutes:

    def test_midnight(self):
        assert NotificationDispatcher._to_minutes("00:00") == 0

    def test_morning(self):
        assert NotificationDispatcher._to_minutes("08:30") == 510

    def test_end_of_day(self):
        assert NotificationDispatcher._to_minutes("23:59") == 1439


class TestIsTimeInRange:

    def setup_method(self):
        self.d = NotificationDispatcher()

    def test_allday_returns_true(self):
        assert self.d._is_time_in_range("12:00", None, None) is True

    def test_in_normal_range(self):
        assert self.d._is_time_in_range("10:00", "08:00", "18:00") is True

    def test_outside_normal_range(self):
        assert self.d._is_time_in_range("20:00", "08:00", "18:00") is False

    def test_at_start_boundary(self):
        assert self.d._is_time_in_range("08:00", "08:00", "18:00") is True

    def test_at_end_boundary(self):
        assert self.d._is_time_in_range("18:00", "08:00", "18:00") is False

    def test_cross_midnight_evening(self):
        assert self.d._is_time_in_range("23:00", "22:00", "06:00") is True

    def test_cross_midnight_morning(self):
        assert self.d._is_time_in_range("03:00", "22:00", "06:00") is True

    def test_cross_midnight_outside(self):
        assert self.d._is_time_in_range("12:00", "22:00", "06:00") is False


# ==================== _match_policy 测试 ====================


class TestMatchPolicy:

    async def test_site_policy_priority(self, async_db):
        """站点策略优先于全局策略"""
        from app.models.notification_policy import NotificationPolicy
        from app.models.spatial import Site

        site = Site(site_code="S001", site_name="站点1")
        async_db.add(site)
        await async_db.flush()

        # 全局策略
        global_p = NotificationPolicy(
            name="全局", alarm_level="critical", channels=["im"],
            notify_user_ids=[1], is_default=True, is_enabled=True,
        )
        # 站点策略
        site_p = NotificationPolicy(
            name="站点", site_id=site.id, alarm_level="critical",
            channels=["im", "sms"], notify_user_ids=[1, 2],
            is_default=False, is_enabled=True,
        )
        async_db.add_all([global_p, site_p])
        await async_db.flush()

        d = NotificationDispatcher()
        with patch.object(d, "_is_time_in_range", return_value=True):
            result = await d._match_policy(async_db, site.id, "critical")
        assert result is not None
        assert result.id == site_p.id

    async def test_global_fallback(self, async_db):
        """无站点策略时回退到全局策略"""
        from app.models.notification_policy import NotificationPolicy

        global_p = NotificationPolicy(
            name="全局", alarm_level="critical", channels=["im"],
            notify_user_ids=[1], is_default=True, is_enabled=True,
        )
        async_db.add(global_p)
        await async_db.flush()

        d = NotificationDispatcher()
        with patch.object(d, "_is_time_in_range", return_value=True):
            result = await d._match_policy(async_db, 999, "critical")
        assert result is not None
        assert result.id == global_p.id

    async def test_no_match_returns_none(self, async_db):
        """无匹配策略返回 None"""
        d = NotificationDispatcher()
        result = await d._match_policy(async_db, None, "critical")
        assert result is None

    async def test_disabled_policy_skipped(self, async_db):
        """禁用策略不匹配"""
        from app.models.notification_policy import NotificationPolicy

        p = NotificationPolicy(
            name="禁用", alarm_level="critical", channels=["im"],
            notify_user_ids=[1], is_default=False, is_enabled=False,
        )
        async_db.add(p)
        await async_db.flush()

        d = NotificationDispatcher()
        result = await d._match_policy(async_db, None, "critical")
        assert result is None

    async def test_time_out_of_range_skipped(self, async_db):
        """当前时间不在时段内的策略不匹配"""
        from app.models.notification_policy import NotificationPolicy

        p = NotificationPolicy(
            name="白天", alarm_level="critical", channels=["im"],
            notify_user_ids=[1], is_default=False, is_enabled=True,
            time_range_start="08:00", time_range_end="18:00",
        )
        async_db.add(p)
        await async_db.flush()

        d = NotificationDispatcher()
        with patch.object(d, "_is_time_in_range", return_value=False):
            result = await d._match_policy(async_db, None, "critical")
        assert result is None

    async def test_allday_policy_always_matches(self, async_db):
        """全天策略始终匹配"""
        from app.models.notification_policy import NotificationPolicy

        p = NotificationPolicy(
            name="全天", alarm_level="info", channels=["im"],
            notify_user_ids=[1], is_default=True, is_enabled=True,
        )
        async_db.add(p)
        await async_db.flush()

        d = NotificationDispatcher()
        result = await d._match_policy(async_db, None, "info")
        assert result is not None
        assert result.id == p.id


# ==================== _get_user_contacts 测试 ====================


class TestGetUserContacts:

    async def test_returns_enabled_contacts(self, async_db):
        from app.models.user_notification_contact import UserNotificationContact
        from app.models.user import User
        from app.core.security import get_password_hash

        user = User(
            username="test_contact_user", password_hash=get_password_hash("test"),
            real_name="测试", email="t@t.com", role="admin", is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        c = UserNotificationContact(
            user_id=user.id, channel_type="im", platform="dingtalk",
            contact_value="user123", is_enabled=True,
        )
        async_db.add(c)
        await async_db.flush()

        d = NotificationDispatcher()
        contacts = await d._get_user_contacts(async_db, [user.id], "im")
        assert len(contacts) == 1
        assert contacts[0][0] == user.id
        assert contacts[0][1] == "user123"
        assert contacts[0][2] == "dingtalk"

    async def test_disabled_contacts_excluded(self, async_db):
        from app.models.user_notification_contact import UserNotificationContact
        from app.models.user import User
        from app.core.security import get_password_hash

        user = User(
            username="test_disabled_user", password_hash=get_password_hash("test"),
            real_name="测试", email="d@t.com", role="admin", is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        c = UserNotificationContact(
            user_id=user.id, channel_type="sms",
            contact_value="13800138000", is_enabled=False,
        )
        async_db.add(c)
        await async_db.flush()

        d = NotificationDispatcher()
        contacts = await d._get_user_contacts(async_db, [user.id], "sms")
        assert len(contacts) == 0


# ==================== dispatch 测试 ====================


class TestDispatch:

    async def test_empty_list_returns_empty(self):
        d = NotificationDispatcher()
        result = await d.dispatch([])
        assert result == {}

    async def test_no_matching_policy(self):
        """无匹配策略时返回 sent_count=0"""
        d = NotificationDispatcher()
        alarm_data = {
            "alarm_id": 1,
            "alarm_level": "critical",
            "alarm_message": "测试告警",
            "trigger_value": 35.0,
            "threshold_value": 30.0,
            "created_at": datetime.now(),
            "site_id": None,
            "site_name": None,
            "device_name": None,
            "point_name": None,
        }
        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=None):
            with patch("app.services.notification.dispatcher.async_session") as mock_session:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
                result = await d.dispatch([alarm_data])
        assert result[1] == 0

    async def test_empty_notify_user_ids_skips(self):
        """notify_user_ids 为空时跳过"""
        from app.models.notification_policy import NotificationPolicy

        p = NotificationPolicy(
            name="空用户", alarm_level="critical", channels=["im"],
            notify_user_ids=[], is_default=True, is_enabled=True,
        )

        d = NotificationDispatcher()
        alarm_data = {
            "alarm_id": 1, "alarm_level": "critical",
            "alarm_message": "测试", "trigger_value": 35.0,
            "threshold_value": 30.0, "created_at": datetime.now(),
            "site_id": None, "site_name": None,
            "device_name": None, "point_name": None,
        }
        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=p):
            with patch("app.services.notification.dispatcher.async_session") as mock_session:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
                result = await d.dispatch([alarm_data])
        assert result[1] == 0

    async def test_single_alarm_exception_isolated(self):
        """单个告警异常不影响其他告警"""
        d = NotificationDispatcher()
        data1 = {
            "alarm_id": 1, "alarm_level": "critical",
            "alarm_message": "告警1", "trigger_value": 35.0,
            "threshold_value": 30.0, "created_at": datetime.now(),
            "site_id": None, "site_name": None,
            "device_name": None, "point_name": None,
        }
        data2 = {
            "alarm_id": 2, "alarm_level": "major",
            "alarm_message": "告警2", "trigger_value": 28.0,
            "threshold_value": 25.0, "created_at": datetime.now(),
            "site_id": None, "site_name": None,
            "device_name": None, "point_name": None,
        }

        call_count = 0

        async def mock_dispatch_single(db, alarm_data):
            nonlocal call_count
            call_count += 1
            if alarm_data["alarm_id"] == 1:
                raise RuntimeError("模拟异常")
            return 2

        with patch.object(d, "_dispatch_single", side_effect=mock_dispatch_single):
            with patch("app.services.notification.dispatcher.async_session") as mock_session:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
                result = await d.dispatch([data1, data2])

        assert call_count == 2
        assert result[1] == 0  # 异常的返回 0
        assert result[2] == 2  # 正常的返回 2

    async def test_json_string_channels_deserialized(self):
        """JSON 字符串 channels 正确反序列化"""
        d = NotificationDispatcher()
        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.channels = '["im","sms"]'  # JSON 字符串
        mock_policy.notify_user_ids = '[1,2]'  # JSON 字符串

        alarm_data = {
            "alarm_id": 1, "alarm_level": "critical",
            "alarm_message": "测试", "trigger_value": 35.0,
            "threshold_value": 30.0, "created_at": datetime.now(),
            "site_id": None, "site_name": "站点",
            "device_name": "设备", "point_name": "点位",
        }

        mock_db = AsyncMock()
        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=mock_policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock, return_value=[]):
                result = await d._dispatch_single(mock_db, alarm_data)

        assert result == 0  # 无联系方式，但不应崩溃

    async def test_context_safe_defaults(self):
        """alarm_message/created_at 为 None 时使用安全默认值"""
        d = NotificationDispatcher()
        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.channels = ["im"]
        mock_policy.notify_user_ids = [1]

        alarm_data = {
            "alarm_id": 1, "alarm_level": "critical",
            "alarm_message": None,  # None
            "trigger_value": None,
            "threshold_value": None,
            "created_at": None,  # None
            "site_id": None, "site_name": None,
            "device_name": None, "point_name": None,
        }

        mock_db = AsyncMock()
        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=mock_policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock, return_value=[(1, "user@test.com", None)]):
                with patch.object(d, "send_notification", new_callable=AsyncMock):
                    result = await d._dispatch_single(mock_db, alarm_data)

        assert result == 1  # 不应崩溃


# ==================== _pending_tasks 测试 ====================


class TestPendingTasks:

    def test_pending_tasks_initialized(self):
        d = NotificationDispatcher()
        assert isinstance(d._pending_tasks, set)
        assert len(d._pending_tasks) == 0
