"""
Story 34.6 — 告警风暴抑制测试
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.core.redis import redis_service
from app.schemas.notification import build_storm_summary
from app.services.notification.storm import StormDetector


# ==================== build_storm_summary 测试 ====================


class TestBuildStormSummary:

    def test_basic_summary(self):
        """正确生成级别分布"""
        alarms = [
            {"alarm_level": "critical", "device_name": "空调1"},
            {"alarm_level": "major", "device_name": "UPS1"},
            {"alarm_level": "major", "device_name": "UPS2"},
        ]
        result = build_storm_summary("站点A", alarms, 60)
        assert "[告警风暴] 站点A" in result
        assert "3 条告警" in result
        assert "重要 2条" in result
        assert "紧急 1条" in result

    def test_critical_detail(self):
        """critical 告警突出设备列表"""
        alarms = [
            {"alarm_level": "critical", "device_name": "精密空调1"},
            {"alarm_level": "critical", "device_name": "精密空调2"},
            {"alarm_level": "minor", "device_name": "传感器1"},
        ]
        result = build_storm_summary("站点B", alarms, 60)
        assert "⚠ 紧急告警 2 条" in result
        assert "精密空调1" in result
        assert "精密空调2" in result

    def test_no_critical_no_detail(self):
        """无 critical 时不输出紧急告警行"""
        alarms = [
            {"alarm_level": "minor", "device_name": "传感器1"},
            {"alarm_level": "info", "device_name": "传感器2"},
        ]
        result = build_storm_summary("站点C", alarms, 120)
        assert "⚠" not in result
        assert "120s" in result

    def test_window_param_displayed(self):
        """window 参数正确传入显示"""
        alarms = [{"alarm_level": "major", "device_name": "D1"}]
        result = build_storm_summary("站点D", alarms, 90)
        assert "90s" in result

    def test_sorted_devices(self):
        """设备列表排序确定性"""
        alarms = [
            {"alarm_level": "critical", "device_name": "C设备"},
            {"alarm_level": "critical", "device_name": "A设备"},
            {"alarm_level": "critical", "device_name": "B设备"},
        ]
        result = build_storm_summary("站点E", alarms, 60)
        # sorted 保证 A, B, C 顺序
        idx_a = result.index("A设备")
        idx_b = result.index("B设备")
        idx_c = result.index("C设备")
        assert idx_a < idx_b < idx_c

    def test_none_device_name(self):
        """device_name=None 时显示未知设备"""
        alarms = [{"alarm_level": "critical", "device_name": None}]
        result = build_storm_summary("站点F", alarms, 60)
        assert "未知设备" in result


# ==================== StormDetector 测试 ====================


class TestStormDetector:

    def _make_detector(self, threshold=20, window=60):
        """创建一个预配置的 StormDetector（跳过 DB 查询）"""
        d = StormDetector()
        d._config_cache = {"threshold": threshold, "window": window}
        d._config_loaded_at = time.time()
        return d

    async def test_memory_below_threshold(self):
        """内存计数未达阈值返回 False"""
        d = self._make_detector(threshold=5)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            result = await d.check_storm(1, count=3)
        assert result is False

    async def test_memory_at_threshold(self):
        """内存计数达到阈值返回 True"""
        d = self._make_detector(threshold=5)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            result = await d.check_storm(1, count=5)
        assert result is True

    async def test_memory_accumulate(self):
        """内存计数累积：多次调用后达到阈值"""
        d = self._make_detector(threshold=5)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            r1 = await d.check_storm(1, count=3)
            r2 = await d.check_storm(1, count=3)
        assert r1 is False
        assert r2 is True  # 3+3=6 >= 5

    async def test_memory_sliding_window_expiry(self):
        """内存计数滑动窗口过期后重置"""
        d = self._make_detector(threshold=5, window=1)  # 1秒窗口
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            await d.check_storm(1, count=4)
            # 模拟时间过去2秒
            for ts_list in d._counter.values():
                ts_list[:] = [t - 2 for t in ts_list]
            result = await d.check_storm(1, count=2)
        assert result is False  # 旧的4条过期，只剩2条

    async def test_memory_different_sites_independent(self):
        """不同站点独立计数"""
        d = self._make_detector(threshold=3)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            await d.check_storm(1, count=2)
            await d.check_storm(2, count=2)
            r1 = await d.check_storm(1, count=1)  # site1: 2+1=3
            r2 = await d.check_storm(2, count=0)  # site2: 2+0=2
        assert r1 is True
        assert r2 is False

    async def test_redis_incr_below_threshold(self):
        """Redis 可用时未达阈值返回 False"""
        d = self._make_detector(threshold=20)
        mock_incr = AsyncMock(return_value=5)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(redis_service, "incr_with_ttl", mock_incr):
                result = await d.check_storm(1, count=1)
        assert result is False
        mock_incr.assert_called_once_with("notification:storm:1", ttl=60)

    async def test_redis_incr_at_threshold(self):
        """Redis 可用时达到阈值返回 True"""
        d = self._make_detector(threshold=20)
        mock_incr = AsyncMock(return_value=20)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(redis_service, "incr_with_ttl", mock_incr):
                result = await d.check_storm(1, count=1)
        assert result is True

    async def test_redis_incrby_batch(self):
        """Redis 批量递增使用 incrby_with_ttl"""
        d = self._make_detector(threshold=20)
        mock_incrby = AsyncMock(return_value=25)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(redis_service, "incrby_with_ttl", mock_incrby):
                result = await d.check_storm(1, count=10)
        assert result is True
        mock_incrby.assert_called_once_with("notification:storm:1", 10, ttl=60)

    async def test_redis_failure_fallback_memory(self):
        """Redis 异常时降级到内存计数"""
        d = self._make_detector(threshold=3)
        mock_incr = AsyncMock(side_effect=Exception("Redis down"))
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(redis_service, "incr_with_ttl", mock_incr):
                r1 = await d.check_storm(1, count=2)
                r2 = await d.check_storm(1, count=2)
        assert r1 is False
        assert r2 is True  # 2+2=4 >= 3

    async def test_redis_returns_negative_fallback_memory(self):
        """Redis 返回 -1 时降级到内存计数"""
        d = self._make_detector(threshold=3)
        mock_incr = AsyncMock(return_value=-1)
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(redis_service, "incr_with_ttl", mock_incr):
                result = await d.check_storm(1, count=3)
        assert result is True  # 内存降级：3 >= 3

    async def test_get_config_from_db(self):
        """get_config 从 SystemConfig 读取自定义阈值"""
        d = StormDetector()  # 无缓存

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("storm_threshold", "30"),
            ("storm_window", "120"),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.async_session",
                   return_value=mock_session):
            threshold, window = await d.get_config()

        assert threshold == 30
        assert window == 120

    async def test_get_config_cached(self):
        """get_config 缓存 300 秒内不重复查库"""
        d = self._make_detector(threshold=10, window=30)
        # 不 mock DB，直接调用应该返回缓存值
        threshold, window = await d.get_config()
        assert threshold == 10
        assert window == 30

    async def test_get_config_db_error_uses_defaults(self):
        """SystemConfig 查询异常时使用默认值"""
        d = StormDetector()  # 无缓存

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.async_session",
                   return_value=mock_session):
            threshold, window = await d.get_config()

        assert threshold == 20
        assert window == 60


# ==================== RedisService incr_with_ttl 测试 ====================


class TestRedisIncrWithTtl:

    async def test_incr_disabled(self):
        """Redis 不可用时返回 -1"""
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            result = await redis_service.incr_with_ttl("test_key")
        assert result == -1

    async def test_incrby_disabled(self):
        """Redis 不可用时 incrby 返回 -1"""
        with patch.object(type(redis_service), "is_available",
                          new_callable=PropertyMock, return_value=False):
            result = await redis_service.incrby_with_ttl("test_key", 5)
        assert result == -1


# ==================== dispatch 集成风暴检测测试 ====================


class TestDispatchStormIntegration:

    def _make_alarm(self, alarm_id, site_id=1, level="major",
                    device_name="设备1"):
        return {
            "alarm_id": alarm_id,
            "alarm_level": level,
            "alarm_message": f"告警{alarm_id}",
            "trigger_value": 100.0,
            "threshold_value": 90.0,
            "created_at": None,
            "site_id": site_id,
            "site_name": "测试站点",
            "device_name": device_name,
            "point_name": "温度",
        }

    async def test_normal_mode_below_threshold(self):
        """未达阈值时逐条分发"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [self._make_alarm(i) for i in range(3)]
        mock_single = AsyncMock(return_value=1)

        with patch.object(d, "_dispatch_single", mock_single):
            with patch(
                "app.services.notification.storm.storm_detector"
            ) as mock_sd:
                mock_sd.check_storm = AsyncMock(return_value=False)
                with patch(
                    "app.core.database.async_session"
                ) as mock_as:
                    mock_db = AsyncMock()
                    mock_as.return_value.__aenter__ = AsyncMock(
                        return_value=mock_db
                    )
                    mock_as.return_value.__aexit__ = AsyncMock(
                        return_value=None
                    )
                    result = await d.dispatch(alarms)

        assert all(v == 1 for v in result.values())
        assert mock_single.call_count == 3

    async def test_storm_mode_merges(self):
        """达到阈值时合并为摘要通知"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [self._make_alarm(i) for i in range(25)]
        mock_storm_summary = AsyncMock(return_value=2)

        with patch.object(d, "_dispatch_storm_summary", mock_storm_summary):
            with patch(
                "app.services.notification.storm.storm_detector"
            ) as mock_sd:
                mock_sd.check_storm = AsyncMock(return_value=True)
                with patch(
                    "app.core.database.async_session"
                ) as mock_as:
                    mock_db = AsyncMock()
                    mock_as.return_value.__aenter__ = AsyncMock(
                        return_value=mock_db
                    )
                    mock_as.return_value.__aexit__ = AsyncMock(
                        return_value=None
                    )
                    result = await d.dispatch(alarms)

        assert all(v == 1 for v in result.values())
        mock_storm_summary.assert_called_once()

    async def test_no_site_alarms_skip_storm(self):
        """site_id=None 的告警跳过风暴检测"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [
            {**self._make_alarm(1), "site_id": None},
            {**self._make_alarm(2), "site_id": None},
        ]
        mock_single = AsyncMock(return_value=1)

        with patch.object(d, "_dispatch_single", mock_single):
            with patch(
                "app.services.notification.storm.storm_detector"
            ) as mock_sd:
                mock_sd.check_storm = AsyncMock(return_value=True)
                with patch(
                    "app.core.database.async_session"
                ) as mock_as:
                    mock_db = AsyncMock()
                    mock_as.return_value.__aenter__ = AsyncMock(
                        return_value=mock_db
                    )
                    mock_as.return_value.__aexit__ = AsyncMock(
                        return_value=None
                    )
                    result = await d.dispatch(alarms)

        # 应该逐条分发，不调用 check_storm
        assert mock_single.call_count == 2
        mock_sd.check_storm.assert_not_called()

    async def test_different_sites_independent(self):
        """不同站点独立检测风暴"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [
            self._make_alarm(1, site_id=1),
            self._make_alarm(2, site_id=2),
        ]
        mock_single = AsyncMock(return_value=1)
        mock_storm_summary = AsyncMock(return_value=1)

        call_results = {1: True, 2: False}

        async def mock_check(sid, count=1):
            return call_results[sid]

        with patch.object(d, "_dispatch_single", mock_single):
            with patch.object(d, "_dispatch_storm_summary", mock_storm_summary):
                with patch(
                    "app.services.notification.storm.storm_detector"
                ) as mock_sd:
                    mock_sd.check_storm = mock_check
                    with patch(
                        "app.core.database.async_session"
                    ) as mock_as:
                        mock_db = AsyncMock()
                        mock_as.return_value.__aenter__ = AsyncMock(
                            return_value=mock_db
                        )
                        mock_as.return_value.__aexit__ = AsyncMock(
                            return_value=None
                        )
                        result = await d.dispatch(alarms)

        # site1 风暴合并，site2 逐条
        mock_storm_summary.assert_called_once()
        mock_single.assert_called_once()

    async def test_storm_summary_uses_highest_level(self):
        """_dispatch_storm_summary 使用最高级别告警匹配策略"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [
            self._make_alarm(1, level="minor"),
            self._make_alarm(2, level="critical"),
            self._make_alarm(3, level="major"),
        ]

        mock_match = AsyncMock(return_value=None)
        with patch.object(d, "_match_policy", mock_match):
            with patch(
                "app.services.notification.storm.storm_detector"
            ) as mock_sd:
                mock_sd.get_config = AsyncMock(return_value=(20, 60))
                result = await d._dispatch_storm_summary(
                    AsyncMock(), 1, alarms
                )

        assert result == 0  # 无策略
        # 验证 _match_policy 用 critical 级别调用
        call_args = mock_match.call_args
        assert call_args[0][1] == 1  # site_id
        assert call_args[0][2] == "critical"  # alarm_level

    async def test_storm_summary_no_policy_returns_zero(self):
        """无匹配策略时返回 0"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [self._make_alarm(1)]
        with patch.object(d, "_match_policy", AsyncMock(return_value=None)):
            with patch(
                "app.services.notification.storm.storm_detector"
            ) as mock_sd:
                mock_sd.get_config = AsyncMock(return_value=(20, 60))
                result = await d._dispatch_storm_summary(
                    AsyncMock(), 1, alarms
                )
        assert result == 0

    async def test_storm_summary_includes_critical_detail(self):
        """风暴摘要包含 critical 数量和设备列表"""
        from app.services.notification.dispatcher import NotificationDispatcher
        d = NotificationDispatcher()

        alarms = [
            self._make_alarm(1, level="critical", device_name="精密空调1"),
            self._make_alarm(2, level="critical", device_name="精密空调2"),
            self._make_alarm(3, level="major", device_name="UPS1"),
        ]

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.notify_user_ids = [1]
        mock_policy.channels = ["im"]

        mock_send = AsyncMock()
        mock_contacts = AsyncMock(return_value=[(1, "user@test.com", None)])

        with patch.object(d, "_match_policy", AsyncMock(return_value=mock_policy)):
            with patch.object(d, "_get_user_contacts", mock_contacts):
                with patch.object(d, "send_notification", mock_send):
                    with patch(
                        "app.services.notification.storm.storm_detector"
                    ) as mock_sd:
                        mock_sd.get_config = AsyncMock(return_value=(20, 60))
                        result = await d._dispatch_storm_summary(
                            AsyncMock(), 1, alarms
                        )

        assert result == 1
        context = mock_send.call_args[0][0]
        assert "紧急告警 2 条" in context.alarm_message
        assert "精密空调1" in context.alarm_message
