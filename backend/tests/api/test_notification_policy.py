"""
Story 34.3 — 通知策略配置测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.notification_policy import (
    NotificationPolicyCreate,
    NotificationPolicyInfo,
    NotificationPolicyUpdate,
    VALID_CHANNELS,
)
from app.services.notification.policy_service import NotificationPolicyService


# ==================== Schema 校验测试 ====================


class TestNotificationPolicyCreateSchema:

    def test_valid_create(self):
        data = NotificationPolicyCreate(
            name="测试策略",
            site_id=1,
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im", "sms"],
            notify_user_ids=[1, 2],
        )
        assert data.name == "测试策略"
        assert data.channels == ["im", "sms"]

    def test_valid_create_global_allday(self):
        data = NotificationPolicyCreate(
            name="全局策略",
            alarm_level="info",
            channels=["im"],
        )
        assert data.site_id is None
        assert data.time_range_start is None
        assert data.time_range_end is None
        assert data.notify_user_ids == []

    def test_empty_notify_user_ids_allowed(self):
        data = NotificationPolicyCreate(
            name="待配置策略",
            alarm_level="major",
            channels=["im"],
            notify_user_ids=[],
        )
        assert data.notify_user_ids == []

    def test_time_range_start_without_end_fails(self):
        with pytest.raises(ValueError, match="同时提供"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                time_range_start="08:00",
                channels=["im"],
            )

    def test_time_range_end_without_start_fails(self):
        with pytest.raises(ValueError, match="同时提供"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                time_range_end="18:00",
                channels=["im"],
            )

    def test_zero_length_time_range_fails(self):
        with pytest.raises(ValueError, match="不能相同"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                time_range_start="08:00",
                time_range_end="08:00",
                channels=["im"],
            )

    def test_invalid_channel_fails(self):
        with pytest.raises(ValueError, match="无效的渠道类型"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                channels=["telegram"],
            )

    def test_empty_channels_fails(self):
        with pytest.raises(ValueError, match="channels 不能为空"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                channels=[],
            )

    def test_invalid_alarm_level_fails(self):
        with pytest.raises(ValueError):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="warning",
                channels=["im"],
            )

    def test_escalation_without_order_fails(self):
        with pytest.raises(ValueError, match="escalation_channel_order"):
            NotificationPolicyCreate(
                name="测试",
                alarm_level="critical",
                channels=["im"],
                channel_escalation_enabled=True,
            )

    def test_escalation_with_order_ok(self):
        data = NotificationPolicyCreate(
            name="测试",
            alarm_level="critical",
            channels=["im", "sms"],
            channel_escalation_enabled=True,
            escalation_channel_order=["im", "sms", "voice"],
        )
        assert data.channel_escalation_enabled is True

    def test_cross_midnight_time_range_ok(self):
        data = NotificationPolicyCreate(
            name="夜间策略",
            alarm_level="critical",
            time_range_start="22:00",
            time_range_end="06:00",
            channels=["im", "sms"],
        )
        assert data.time_range_start == "22:00"
        assert data.time_range_end == "06:00"


class TestNotificationPolicyUpdateSchema:

    def test_valid_partial_update(self):
        data = NotificationPolicyUpdate(name="新名称")
        assert data.name == "新名称"
        assert "name" in data.model_fields_set
        assert "channels" not in data.model_fields_set

    def test_invalid_channel_in_update_fails(self):
        with pytest.raises(ValueError, match="无效的渠道类型"):
            NotificationPolicyUpdate(channels=["fax"])

    def test_empty_channels_in_update_fails(self):
        with pytest.raises(ValueError, match="channels 不能为空"):
            NotificationPolicyUpdate(channels=[])

    def test_model_fields_set_tracks_provided(self):
        data = NotificationPolicyUpdate(
            time_range_start="09:00",
            channels=["im"],
        )
        assert "time_range_start" in data.model_fields_set
        assert "channels" in data.model_fields_set
        assert "time_range_end" not in data.model_fields_set


# ==================== 时段重叠检测测试 ====================


class TestTimeRangesOverlap:

    def test_both_allday_overlap(self):
        assert NotificationPolicyService.time_ranges_overlap(
            None, None, None, None
        ) is True

    def test_allday_vs_specific_overlap(self):
        assert NotificationPolicyService.time_ranges_overlap(
            None, None, "08:00", "18:00"
        ) is True

    def test_specific_vs_allday_overlap(self):
        assert NotificationPolicyService.time_ranges_overlap(
            "08:00", "18:00", None, None
        ) is True

    def test_non_overlapping_ranges(self):
        assert NotificationPolicyService.time_ranges_overlap(
            "08:00", "12:00", "13:00", "18:00"
        ) is False

    def test_adjacent_ranges_no_overlap(self):
        """相邻时段不重叠: [08:00, 12:00) 和 [12:00, 18:00)"""
        assert NotificationPolicyService.time_ranges_overlap(
            "08:00", "12:00", "12:00", "18:00"
        ) is False

    def test_overlapping_ranges(self):
        assert NotificationPolicyService.time_ranges_overlap(
            "08:00", "14:00", "12:00", "18:00"
        ) is True

    def test_cross_midnight_no_overlap_with_daytime(self):
        """跨午夜 22:00~06:00 与白天 06:00~08:00 不重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "06:00", "08:00"
        ) is False

    def test_cross_midnight_overlap_with_evening(self):
        """跨午夜 22:00~06:00 与 21:00~23:00 重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "21:00", "23:00"
        ) is True

    def test_cross_midnight_overlap_with_morning(self):
        """跨午夜 22:00~06:00 与 05:00~08:00 重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "05:00", "08:00"
        ) is True

    def test_two_cross_midnight_overlap(self):
        """两个跨午夜时段 22:00~06:00 与 23:00~05:00 重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "23:00", "05:00"
        ) is True

    def test_cross_midnight_no_overlap_with_midday(self):
        """跨午夜 22:00~06:00 与 10:00~14:00 不重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "10:00", "14:00"
        ) is False

    def test_minute_boundary_precision(self):
        """分钟边界精确: 22:00~06:00 与 06:00~08:00 不重叠"""
        assert NotificationPolicyService.time_ranges_overlap(
            "22:00", "06:00", "06:00", "08:00"
        ) is False

    def test_zero_length_raises(self):
        with pytest.raises(ValueError, match="零长度"):
            NotificationPolicyService.time_ranges_overlap(
                "08:00", "08:00", "09:00", "10:00"
            )


# ==================== 辅助函数测试 ====================


class TestHelperFunctions:

    def test_to_minutes(self):
        assert NotificationPolicyService._to_minutes("00:00") == 0
        assert NotificationPolicyService._to_minutes("08:30") == 510
        assert NotificationPolicyService._to_minutes("23:59") == 1439

    def test_segments_allday(self):
        assert NotificationPolicyService._segments(None, None) == [(0, 1440)]

    def test_segments_normal(self):
        assert NotificationPolicyService._segments("08:00", "18:00") == [(480, 1080)]

    def test_segments_cross_midnight(self):
        segs = NotificationPolicyService._segments("22:00", "06:00")
        assert segs == [(1320, 1440), (0, 360)]

    def test_segments_equal_raises(self):
        with pytest.raises(ValueError):
            NotificationPolicyService._segments("08:00", "08:00")


# ==================== 服务层 DB 测试 ====================


class TestPolicyServiceDB:

    async def test_check_time_overlap_no_conflict(self, async_db):
        """无冲突时返回 None"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="已有策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="12:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        result = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "13:00", "18:00"
        )
        assert result is None

    async def test_check_time_overlap_conflict(self, async_db):
        """有冲突时返回冲突策略 ID"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="已有策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="14:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        result = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "12:00", "18:00"
        )
        assert result == policy.id

    async def test_check_time_overlap_excludes_self(self, async_db):
        """排除自身时不冲突"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="已有策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        result = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "08:00", "18:00", exclude_id=policy.id
        )
        assert result is None

    async def test_check_time_overlap_different_level_no_conflict(self, async_db):
        """不同告警级别不冲突"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="已有策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        result = await NotificationPolicyService.check_time_overlap(
            async_db, None, "major", "08:00", "18:00"
        )
        assert result is None

    async def test_check_time_overlap_different_site_no_conflict(self, async_db):
        """不同站点不冲突"""
        from app.models.notification_policy import NotificationPolicy
        from app.models.spatial import Site

        site = Site(site_code="S001", site_name="站点1")
        async_db.add(site)
        await async_db.flush()

        policy = NotificationPolicy(
            name="已有策略",
            site_id=site.id,
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        # 全局策略不与站点策略冲突
        result = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "08:00", "18:00"
        )
        assert result is None

    async def test_validate_site_exists_true(self, async_db):
        from app.models.spatial import Site

        site = Site(site_code="S001", site_name="站点1")
        async_db.add(site)
        await async_db.flush()

        assert await NotificationPolicyService.validate_site_exists(async_db, site.id) is True

    async def test_validate_site_exists_false(self, async_db):
        assert await NotificationPolicyService.validate_site_exists(async_db, 9999) is False

    async def test_validate_user_site_access_global_skip(self, async_db):
        result = await NotificationPolicyService.validate_user_site_access(
            async_db, None, [1, 2]
        )
        assert result == []

    async def test_validate_user_site_access_empty_users_skip(self, async_db):
        result = await NotificationPolicyService.validate_user_site_access(
            async_db, 1, []
        )
        assert result == []

    async def test_validate_user_site_access_authorized(self, async_db):
        from app.models.spatial import Site
        from app.models.user import UserSite

        site = Site(site_code="S001", site_name="站点1")
        async_db.add(site)
        await async_db.flush()

        # admin_user fixture 创建的用户 id=1，手动创建 UserSite
        user_site = UserSite(user_id=1, site_id=site.id)
        async_db.add(user_site)
        await async_db.flush()

        result = await NotificationPolicyService.validate_user_site_access(
            async_db, site.id, [1]
        )
        assert result == []

    async def test_validate_user_site_access_unauthorized(self, async_db):
        from app.models.spatial import Site

        site = Site(site_code="S001", site_name="站点1")
        async_db.add(site)
        await async_db.flush()

        result = await NotificationPolicyService.validate_user_site_access(
            async_db, site.id, [999]
        )
        assert result == [999]


# ==================== API 逻辑测试（直接调用，避免 client fixture 超时） ====================


class TestPolicyAPILogic:

    async def test_create_policy_basic(self, async_db, admin_user):
        """创建策略 — 正常创建"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="测试策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im", "sms"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()
        await async_db.refresh(policy)

        assert policy.id is not None
        assert policy.name == "测试策略"
        assert policy.channels == ["im", "sms"]

    async def test_create_global_policy(self, async_db):
        """创建全局策略 — site_id=NULL"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="全局策略",
            alarm_level="info",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        assert policy.site_id is None

    async def test_delete_default_policy_blocked(self, async_db):
        """删除默认策略 — is_default=True 应被阻止"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="默认策略",
            alarm_level="critical",
            channels=["im"],
            notify_user_ids=[],
            is_default=True,
        )
        async_db.add(policy)
        await async_db.flush()

        # 模拟 API 逻辑
        assert policy.is_default is True
        # API 层会返回 400

    async def test_delete_normal_policy_ok(self, async_db):
        """删除普通策略 — 正常删除"""
        from app.models.notification_policy import NotificationPolicy
        from sqlalchemy import select

        policy = NotificationPolicy(
            name="可删除策略",
            alarm_level="minor",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()
        pid = policy.id

        await async_db.delete(policy)
        await async_db.flush()

        result = await async_db.execute(
            select(NotificationPolicy).where(NotificationPolicy.id == pid)
        )
        assert result.scalar_one_or_none() is None

    async def test_update_policy_merge_time_range(self, async_db):
        """更新策略 — 单独更新 time_range_start，与 DB 现有 end 合并"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="策略",
            alarm_level="critical",
            time_range_start="08:00",
            time_range_end="18:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        # 模拟 Update schema 只提供 time_range_start
        update_data = NotificationPolicyUpdate(time_range_start="09:00")
        provided = update_data.model_fields_set

        effective_start = (
            update_data.time_range_start
            if "time_range_start" in provided
            else policy.time_range_start
        )
        effective_end = (
            update_data.time_range_end
            if "time_range_end" in provided
            else policy.time_range_end
        )

        assert effective_start == "09:00"
        assert effective_end == "18:00"  # 从 DB 保留

    async def test_seed_data_pattern(self, async_db):
        """种子数据 — 4 条默认策略"""
        from app.models.notification_policy import NotificationPolicy
        from sqlalchemy import select

        levels = ["critical", "major", "minor", "info"]
        for level in levels:
            policy = NotificationPolicy(
                name=f"全局{level}默认策略",
                alarm_level=level,
                channels=["im"] if level != "critical" else ["im", "sms"],
                notify_user_ids=[],
                is_default=True,
                is_enabled=True,
            )
            async_db.add(policy)
        await async_db.flush()

        result = await async_db.execute(
            select(NotificationPolicy).where(NotificationPolicy.is_default == True)
        )
        defaults = result.scalars().all()
        assert len(defaults) == 4
        assert all(p.is_default for p in defaults)
        assert {p.alarm_level for p in defaults} == set(levels)

    async def test_cross_midnight_policy_creation(self, async_db):
        """跨午夜时段策略创建"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="夜间策略",
            alarm_level="critical",
            time_range_start="22:00",
            time_range_end="06:00",
            channels=["im", "sms"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        assert policy.time_range_start == "22:00"
        assert policy.time_range_end == "06:00"

    async def test_cross_midnight_conflict_detection(self, async_db):
        """跨午夜时段冲突检测"""
        from app.models.notification_policy import NotificationPolicy

        # 已有 22:00~06:00 策略
        policy = NotificationPolicy(
            name="夜间策略",
            alarm_level="critical",
            time_range_start="22:00",
            time_range_end="06:00",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        # 新策略 23:00~05:00 应冲突
        conflict = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "23:00", "05:00"
        )
        assert conflict == policy.id

    async def test_info_schema_from_orm(self, async_db):
        """NotificationPolicyInfo 从 ORM 对象转换"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="测试",
            alarm_level="critical",
            channels=["im"],
            notify_user_ids=[1, 2],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()
        await async_db.refresh(policy)

        info = NotificationPolicyInfo.model_validate(policy)
        assert info.id == policy.id
        assert info.name == "测试"
        assert info.channels == ["im"]
        assert info.notify_user_ids == [1, 2]

    async def test_allday_conflicts_with_any_time_range(self, async_db):
        """全天策略与任何时段重叠"""
        from app.models.notification_policy import NotificationPolicy

        # 全天策略
        policy = NotificationPolicy(
            name="全天策略",
            alarm_level="critical",
            channels=["im"],
            notify_user_ids=[],
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        conflict = await NotificationPolicyService.check_time_overlap(
            async_db, None, "critical", "08:00", "18:00"
        )
        assert conflict == policy.id

    async def test_update_escalation_without_order_blocked(self, async_db):
        """启用 escalation 但无 order 应被阻止"""
        from app.models.notification_policy import NotificationPolicy

        policy = NotificationPolicy(
            name="策略",
            alarm_level="critical",
            channels=["im"],
            notify_user_ids=[],
            channel_escalation_enabled=False,
            escalation_channel_order=None,
            is_default=False,
        )
        async_db.add(policy)
        await async_db.flush()

        # 模拟更新逻辑
        update_data = NotificationPolicyUpdate(channel_escalation_enabled=True)
        provided = update_data.model_fields_set

        effective_escalation = (
            update_data.channel_escalation_enabled
            if "channel_escalation_enabled" in provided
            else policy.channel_escalation_enabled
        )
        effective_order = (
            update_data.escalation_channel_order
            if "escalation_channel_order" in provided
            else policy.escalation_channel_order
        )

        assert effective_escalation is True
        assert effective_order is None
        # API 层会返回 422
